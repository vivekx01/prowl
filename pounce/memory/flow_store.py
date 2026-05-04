from datetime import datetime
from typing import TYPE_CHECKING

from pounce.models import LearnedFlowRecord, LearnedStepRecord

if TYPE_CHECKING:
    from pounce.core.session import PounceSession


class FlowStore:
    """
    In-memory store of per-company learned MCP tool-call sequences.
    Loaded from server sync at start of run; dirty flows pushed back after.
    """

    def __init__(self, records: list[LearnedFlowRecord]):
        self._flows: dict[str, LearnedFlowRecord] = {
            r.company_domain: r for r in records
        }
        self._dirty: list[LearnedFlowRecord] = []

    def get(self, company_domain: str) -> LearnedFlowRecord | None:
        return self._flows.get(company_domain)

    async def try_replay(
        self,
        company_domain: str,
        session: "PounceSession",
        answers: dict[str, str],
    ) -> tuple[bool, int]:
        """
        Attempt to replay the stored flow for this company.
        Returns (success, steps_replayed).
        Switches to agent mode on first failure.
        """
        flow = self.get(company_domain)
        if not flow or not flow.steps:
            return False, 0

        replayed = 0
        for step in sorted(flow.steps, key=lambda s: s.step_order):
            ok = await self._replay_step(step, session, answers)
            if not ok:
                return False, replayed
            replayed += 1

        return True, replayed

    async def _replay_step(
        self,
        step: LearnedStepRecord,
        session: "PounceSession",
        answers: dict[str, str],
    ) -> bool:
        """Try executing a stored step's tool calls. Returns False on failure."""
        if step.page_indicator:
            snapshot = await session.get_page_snapshot()
            if step.page_indicator not in snapshot:
                return False  # wrong page — abort replay

        for tool_call in step.tool_calls:
            try:
                args = dict(tool_call.get("args", {}))
                # Substitute known answers into text-fill calls
                if tool_call["tool"] in ("browser_type", "browser_fill"):
                    text = args.get("text", "")
                    if text.startswith("{{") and text.endswith("}}"):
                        key = text[2:-2]
                        args["text"] = answers.get(key, text)
                await session.client.call_tool(tool_call["tool"], args)
            except Exception:
                return False

        return True

    def record_flow(
        self,
        company_domain: str,
        portal_key: str | None,
        steps: list[LearnedStepRecord],
    ) -> None:
        """Save or update the learned flow for a company after a successful run."""
        existing = self._flows.get(company_domain)
        if existing:
            existing.steps = steps
            existing.success_count += 1
            existing.last_success = datetime.utcnow()
            if existing not in self._dirty:
                self._dirty.append(existing)
        else:
            flow = LearnedFlowRecord(
                company_domain=company_domain,
                portal_key=portal_key,
                success_count=1,
                last_success=datetime.utcnow(),
                steps=steps,
            )
            self._flows[company_domain] = flow
            self._dirty.append(flow)

    def dirty_flows(self) -> list[LearnedFlowRecord]:
        return list(self._dirty)

    def clear_dirty(self) -> None:
        self._dirty.clear()
