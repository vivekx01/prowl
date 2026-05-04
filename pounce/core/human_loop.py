import asyncio
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pounce.memory.answer_store import AnswerStore


class HumanInTheLoop:
    """
    Pauses the agent and prompts the user for input via CLI.
    Browser stays open while waiting.
    Saves the answer to memory so it's never asked again.
    """

    def __init__(
        self,
        interactive: bool = True,
        answer_store: "AnswerStore | None" = None,
        company_domain: str | None = None,
        portal_key: str | None = None,
    ):
        self.interactive = interactive
        self.answer_store = answer_store
        self.company_domain = company_domain
        self.portal_key = portal_key

    async def ask(
        self,
        question: str,
        options: list[str] | None = None,
        reason: str = "unknown field",
        field_type: str | None = None,
    ) -> str | None:
        """
        Ask the user for input. Returns the answer string, or None to skip.
        In --automated mode always returns None without prompting.
        """
        if not self.interactive:
            print(f"  [POUNCE] Skipping (automated mode): {question!r}", flush=True)
            return None

        print(f"\n[POUNCE PAUSED — {reason}]", flush=True)
        print(f"  Question : {question}", flush=True)
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  {i:>3}. {opt}", flush=True)
        print("  Type answer (or Enter to skip): ", end="", flush=True)

        # Run blocking input() in a thread so async loop isn't blocked
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, sys.stdin.readline)
        answer = answer.strip()

        if not answer:
            print("  [POUNCE] Skipped.", flush=True)
            return None

        # If user typed a number, resolve to the option text
        if options:
            try:
                idx = int(answer) - 1
                if 0 <= idx < len(options):
                    answer = options[idx]
            except ValueError:
                pass

        print(f"  [POUNCE] Got it. Saving to memory and resuming...", flush=True)

        if self.answer_store:
            await self.answer_store.save_answer(
                question_text=question,
                answer=answer,
                field_type=field_type,
                options=options or [],
                source="user",
                confidence=1.0,
                company_domain=self.company_domain,
                portal_key=self.portal_key,
            )

        return answer

    async def confirm_page(self, page_description: str) -> bool:
        """In --supervised mode, ask the user to confirm before continuing."""
        if not self.interactive:
            return True

        print(f"\n[POUNCE SUPERVISED — {page_description}]", flush=True)
        print("  Press Enter to continue, or type 'stop' to abort: ", end="", flush=True)
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, sys.stdin.readline)
        return answer.strip().lower() != "stop"
