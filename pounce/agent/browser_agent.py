import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from pounce import config
from pounce.agent.prompts import build_system_prompt, build_user_message
from pounce.core.session import PounceSession
from pounce.models import JobRecord, LearnedStepRecord, ProfileData


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_TERMINAL_SIGNALS = ("DONE_APPLIED", "DONE_DRY_RUN", "DONE_ERROR")
_HUMAN_INPUT_PREFIX = "HUMAN_INPUT_NEEDED:"


@dataclass
class AgentResult:
    status: str                                    # "applied" | "dry_run_completed" | "failed"
    agent_turns: int = 0
    error_message: str | None = None
    recorded_steps: list[LearnedStepRecord] = field(default_factory=list)
    human_inputs_used: int = 0


class BrowserAgent:
    """
    LLM agent loop that drives the browser via Playwright MCP tools.
    One instance per job application.
    """

    def __init__(
        self,
        session: PounceSession,
        job: JobRecord,
        profile: ProfileData,
        known_answers: str,
        dry_run: bool = False,
        supervised: bool = False,
        human_loop=None,          # HumanInTheLoop | None
    ):
        self.session = session
        self.job = job
        self.profile = profile
        self.known_answers = known_answers
        self.dry_run = dry_run
        self.supervised = supervised
        self.human_loop = human_loop

        self._system_prompt = build_system_prompt(job, profile, known_answers, dry_run)
        self._messages: list[dict] = []
        self._recorded_tool_calls: list[dict] = []
        self._current_page_name: str = "landing"
        self._recorded_steps: list[LearnedStepRecord] = []
        self._step_order: int = 0

    async def run(self) -> AgentResult:
        turns = 0
        max_turns = config.POUNCE_MAX_AGENT_TURNS
        consecutive_same_snapshot = 0
        last_snapshot_hash = ""

        # Seed: navigate to job URL
        await self.session.navigate(self.job.url)
        snapshot = await self.session.get_page_snapshot()

        while turns < max_turns:
            turns += 1

            # Detect stuck state — same page N turns in a row
            snapshot_hash = str(len(snapshot)) + snapshot[:200]
            if snapshot_hash == last_snapshot_hash:
                consecutive_same_snapshot += 1
            else:
                consecutive_same_snapshot = 0
            last_snapshot_hash = snapshot_hash

            if consecutive_same_snapshot >= 2:
                # Auto-check for new tabs — Apply buttons often open in a new tab
                try:
                    tab_result = await self.session.client.call_tool("browser_tab_list", {})
                    tabs = tab_result.get("tabs", [])
                    if len(tabs) > 1:
                        # Switch to the last (newest) tab
                        newest = tabs[-1]
                        await self.session.client.call_tool(
                            "browser_tab_select", {"index": newest.get("index", len(tabs) - 1)}
                        )
                        await asyncio.sleep(2)
                        new_snap = await self.session.get_page_snapshot()
                        if new_snap != snapshot:
                            print(f"  [AGENT] Switched to new tab — page changed.", flush=True)
                            snapshot = new_snap
                            consecutive_same_snapshot = 0
                            last_snapshot_hash = ""
                            continue
                except Exception:
                    pass

                # Still stuck — tell the LLM to try something different
                last_tool = ""
                last_args = ""
                for msg in reversed(self._messages):
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        tc = msg["tool_calls"][-1]
                        last_tool = tc["function"]["name"]
                        last_args = tc["function"].get("arguments", "")
                        break
                self._messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM ALERT] Page unchanged for {consecutive_same_snapshot} turns. "
                        f"The action '{last_tool}' with args {last_args[:80]} had NO effect. "
                        "STOP repeating it. Try: scroll to the element first, use JS click via browser_evaluate, "
                        "or use a CSS selector target like 'button:has-text(\"Apply\")' instead of a ref."
                    ),
                })

            # Build conversation
            user_msg = build_user_message(snapshot)
            self._messages.append({"role": "user", "content": user_msg})
            print(f"  [AGENT] turn {turns} — snapshot {len(snapshot)} chars, calling LLM...", flush=True)
            if consecutive_same_snapshot >= 2:
                print(f"  [SNAPSHOT] {snapshot[:300]}", flush=True)

            # Get available MCP tools for this turn
            tools = await self._get_tool_schemas()

            # Call LLM
            response_text, tool_calls = await self._call_llm(tools)
            print(f"  [AGENT] LLM response: {response_text[:120] if response_text else '(none)'}", flush=True)
            if tool_calls:
                for tc in tool_calls:
                    print(f"  [AGENT] tool call: {tc['function']['name']} {tc['function'].get('arguments','')[:100]}", flush=True)

            # Check terminal signals in text response
            if response_text:
                signal = self._check_terminal(response_text)
                if signal == "DONE_APPLIED":
                    self._flush_step()
                    return AgentResult(status="applied", agent_turns=turns,
                                       recorded_steps=self._recorded_steps)
                if signal == "DONE_DRY_RUN":
                    self._flush_step()
                    return AgentResult(status="dry_run_completed", agent_turns=turns,
                                       recorded_steps=self._recorded_steps)
                if signal and signal.startswith("DONE_ERROR"):
                    reason = signal[len("DONE_ERROR:"):].strip()
                    return AgentResult(status="failed", agent_turns=turns,
                                       error_message=reason,
                                       recorded_steps=self._recorded_steps)

                # Handle human input request
                if _HUMAN_INPUT_PREFIX in response_text and self.human_loop:
                    question = response_text.split(_HUMAN_INPUT_PREFIX, 1)[1].strip()
                    answer = await self.human_loop.ask(question, reason="agent requested")
                    if answer:
                        # Inject answer back as user message and continue
                        self._messages.append({"role": "assistant", "content": response_text})
                        self._messages.append({"role": "user", "content": f"Answer: {answer}"})
                        snapshot = await self.session.get_page_snapshot()
                        continue

            # Execute tool calls
            if tool_calls:
                tool_results = []
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    try:
                        result = await self.session.client.call_tool(tool_name, args)
                        result_text = json.dumps(result)

                        # Stale ref — take fresh snapshot and retry once
                        if "not found in the current page snapshot" in result_text and tool_name == "browser_click":
                            print(f"  [AGENT] Stale ref detected — refreshing snapshot and retrying...", flush=True)
                            fresh = await self.session.get_page_snapshot()
                            snapshot = fresh
                            # Inject fresh snapshot into conversation so LLM can re-pick the element
                            result_text = json.dumps({"content": [{"type": "text", "text": f"Ref was stale. Fresh page snapshot:\n{fresh[:3000]}"}]})

                        print(f"  [TOOL] {tool_name} → {result_text[:120]}", flush=True)
                        tool_results.append({
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "content": result_text,
                        })
                        self._recorded_tool_calls.append({"tool": tool_name, "args": args})
                        if tool_name in ("browser_click", "browser_navigate", "browser_press_key", "browser_evaluate"):
                            await asyncio.sleep(1)
                    except Exception as e:
                        print(f"  [TOOL ERROR] {tool_name} → {e}", flush=True)
                        tool_results.append({
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "content": f"Error: {e}",
                        })

                self._messages.append({
                    "role": "assistant",
                    "content": response_text or "",
                    "tool_calls": tool_calls,
                })
                self._messages.extend(tool_results)

                # Detect page change and flush step
                new_snapshot = await self.session.get_page_snapshot()
                if self._page_changed(snapshot, new_snapshot):
                    self._flush_step()
                snapshot = new_snapshot
            else:
                # LLM responded with text only — re-read page and try again
                self._messages.append({"role": "assistant", "content": response_text or ""})
                snapshot = await self.session.get_page_snapshot()

        return AgentResult(
            status="failed",
            agent_turns=turns,
            error_message=f"Exceeded max agent turns ({max_turns})",
            recorded_steps=self._recorded_steps,
        )

    async def _call_llm(
        self, tools: list[dict]
    ) -> tuple[str, list[dict]]:
        """Call the LLM via OpenRouter and return (text_response, tool_calls)."""
        # Keep only last 10 turns to avoid unbounded context growth
        recent_messages = self._messages[-20:]
        payload = {
            "model": config.POUNCE_MODEL,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *recent_messages,
            ],
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        text = choice.get("content") or ""
        tool_calls = choice.get("tool_calls") or []
        return text, tool_calls

    async def _get_tool_schemas(self) -> list[dict]:
        """Fetch MCP tool list and convert to OpenAI function-calling format."""
        mcp_tools = await self.session.client.list_tools()
        schemas = []
        for t in mcp_tools:
            schemas.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            })
        return schemas

    def _check_terminal(self, text: str) -> str | None:
        for signal in _TERMINAL_SIGNALS:
            if signal in text:
                idx = text.find(signal)
                return text[idx:].split("\n")[0].strip()
        return None

    def _page_changed(self, old: str, new: str) -> bool:
        # Simple heuristic: if >30% of content differs, treat as new page
        old_lines = set(old.splitlines())
        new_lines = set(new.splitlines())
        if not old_lines:
            return bool(new_lines)
        overlap = len(old_lines & new_lines) / len(old_lines)
        return overlap < 0.7

    def _flush_step(self) -> None:
        """Record accumulated tool calls as a completed LearnedStep."""
        if not self._recorded_tool_calls:
            return
        self._recorded_steps.append(LearnedStepRecord(
            step_order=self._step_order,
            step_name=self._current_page_name,
            tool_calls=list(self._recorded_tool_calls),
        ))
        self._step_order += 1
        self._recorded_tool_calls.clear()
