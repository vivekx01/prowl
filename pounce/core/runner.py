import asyncio
from urllib.parse import urlparse

from pounce import config
from pounce.agent.browser_agent import BrowserAgent
from pounce.core.human_loop import HumanInTheLoop
from pounce.core.session import PounceSession
from pounce.memory.answer_store import AnswerStore
from pounce.memory.flow_store import FlowStore
from pounce.models import JobRecord, ProfileData, RunResult, StepResult
from pounce.sync import client as sync


class PounceRunner:
    """Orchestrates a single job application: sync → replay/agent → push results."""

    def __init__(
        self,
        interactive: bool = True,
        supervised: bool = False,
        dry_run: bool = False,
        headless: bool | None = None,
        min_score: float = 0.5,
    ):
        self.interactive = interactive
        self.supervised = supervised
        self.dry_run = dry_run
        self.headless = headless
        self.min_score = min_score

    async def run_all_pending(self) -> list[RunResult]:
        """Fetch all pending jobs from server and apply to each."""
        jobs = sync.fetch_jobs(self.min_score)
        if not jobs:
            print("[POUNCE] No pending jobs.", flush=True)
            return []

        profile = sync.fetch_profile()
        memory_records = sync.fetch_memory()
        flow_records = sync.fetch_flows()

        answer_store = AnswerStore(memory_records)
        flow_store = FlowStore(flow_records)

        results = []
        for job in jobs:
            print(f"\n[POUNCE] Applying: {job.title} @ {job.company}", flush=True)
            result = await self._apply_one(job, profile, answer_store, flow_store)
            results.append(result)

            # Push results back to server after each job
            self._push_results(job, result, answer_store, flow_store)

        return results

    async def apply_url(self, url: str) -> RunResult:
        """Apply to any job URL directly — does not need to be saved in The Prowl."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # Build a minimal JobRecord from the URL — no DB lookup required
        job = JobRecord(
            application_id=0,   # 0 = not tracked in DB; mark_applied skipped
            listing_id=0,
            title="(direct URL)",
            company=domain,
            url=url,
        )

        profile = sync.fetch_profile()
        memory_records = sync.fetch_memory()
        flow_records = sync.fetch_flows()

        answer_store = AnswerStore(memory_records)
        flow_store = FlowStore(flow_records)

        result = await self._apply_one(job, profile, answer_store, flow_store)
        self._push_results(job, result, answer_store, flow_store)
        return result

    async def apply_single(self, job_id: int) -> RunResult:
        """
        Apply to a job by listing ID.
        Works for saved applications AND any scraped listing in the DB.
        If not saved yet, auto-creates the application record after applying.
        """
        # Try saved applications first
        saved_jobs = sync.fetch_jobs(min_score=0.0)
        job = next((j for j in saved_jobs if j.listing_id == job_id), None)

        listing = None
        if not job:
            # Fall back to any scraped listing in the DB
            try:
                listing = sync.fetch_listing(job_id)
                job = listing.to_job_record()
            except ValueError:
                raise ValueError(
                    f"Listing ID {job_id} not found.\n"
                    f"  Browse scraped jobs: pounce listings\n"
                    f"  Or apply by URL:     pounce apply --url <url>"
                )

        profile = sync.fetch_profile()
        memory_records = sync.fetch_memory()
        flow_records = sync.fetch_flows()

        answer_store = AnswerStore(memory_records)
        flow_store = FlowStore(flow_records)

        result = await self._apply_one(job, profile, answer_store, flow_store)

        # For unsaved listings, create the application record now
        if listing is not None and result.status == "applied" and not self.dry_run:
            sync.ensure_applied(job_id)

        self._push_results(job, result, answer_store, flow_store)
        return result

    async def _apply_one(
        self,
        job: JobRecord,
        profile: ProfileData,
        answer_store: AnswerStore,
        flow_store: FlowStore,
    ) -> RunResult:
        company_domain = urlparse(job.url).netloc
        portal_key = _detect_portal(company_domain)

        human_loop = HumanInTheLoop(
            interactive=self.interactive,
            answer_store=answer_store,
            company_domain=company_domain,
            portal_key=portal_key,
        )

        known_answers = answer_store.dump_for_prompt(company_domain, portal_key)

        # Local profile override — replaces server profile if set
        if config.POUNCE_PROFILE_PATH:
            from pathlib import Path
            override_path = Path(config.POUNCE_PROFILE_PATH)
            if override_path.exists():
                from pounce.models import ProfileData as _PD
                profile = _PD(content=override_path.read_text(encoding="utf-8"))
                print(f"  [POUNCE] Using local profile override: {override_path}", flush=True)
            else:
                print(f"  [POUNCE] WARNING: POUNCE_PROFILE_PATH not found: {override_path}", flush=True)

        async with PounceSession(headless=self.headless) as session:
            # Try replay first
            if not self.supervised:
                replayed, steps_done = await flow_store.try_replay(
                    company_domain, session, answers={}
                )
                if replayed:
                    print(f"  [POUNCE] Replayed {steps_done} steps from memory.", flush=True)
                    if not self.dry_run:
                        sync.mark_applied(job.application_id)
                    return RunResult(
                        listing_id=job.listing_id,
                        status="applied" if not self.dry_run else "dry_run_completed",
                        dry_run=self.dry_run,
                        agent_turns=0,
                        step_results=[StepResult(
                            step_name="replay",
                            success=True,
                            replay=True,
                            agent_turns=0,
                        )],
                    )

            # Full agent mode
            agent = BrowserAgent(
                session=session,
                job=job,
                profile=profile,
                known_answers=known_answers,
                dry_run=self.dry_run,
                supervised=self.supervised,
                human_loop=human_loop,
            )
            agent_result = await agent.run()

        # Map agent result to RunResult
        if agent_result.status == "applied" and not self.dry_run and job.application_id:
            sync.mark_applied(job.application_id)

        if agent_result.status == "applied" and agent_result.recorded_steps:
            flow_store.record_flow(company_domain, portal_key, agent_result.recorded_steps)

        step_results = [
            StepResult(
                step_name=s.step_name,
                success=True,
                replay=False,
                agent_turns=agent_result.agent_turns,
            )
            for s in agent_result.recorded_steps
        ] or [StepResult(
            step_name="agent_run",
            success=agent_result.status != "failed",
            agent_turns=agent_result.agent_turns,
            error=agent_result.error_message,
        )]

        return RunResult(
            listing_id=job.listing_id,
            status=agent_result.status,
            dry_run=self.dry_run,
            agent_turns=agent_result.agent_turns,
            step_results=step_results,
            error_message=agent_result.error_message,
        )

    def _push_results(
        self,
        job: JobRecord,
        result: RunResult,
        answer_store: AnswerStore,
        flow_store: FlowStore,
    ) -> None:
        dirty_memory = answer_store.dirty_records()
        dirty_flows = flow_store.dirty_flows()

        if dirty_memory:
            pushed = sync.push_memory(dirty_memory)
            print(f"  [POUNCE] Pushed {pushed} memory entries to server.", flush=True)
            answer_store.clear_dirty()

        if dirty_flows:
            pushed = sync.push_flows(dirty_flows)
            print(f"  [POUNCE] Pushed {pushed} learned flows to server.", flush=True)
            flow_store.clear_dirty()

        sync.push_run(result, job.listing_id)


def _detect_portal(domain: str) -> str | None:
    portal_map = {
        "myworkdayjobs.com": "workday",
        "greenhouse.io": "greenhouse",
        "lever.co": "lever",
        "ashbyhq.com": "ashby",
        "rippling.com": "rippling",
        "smartrecruiters.com": "smartrecruiters",
    }
    for pattern, key in portal_map.items():
        if pattern in domain:
            return key
    return None
