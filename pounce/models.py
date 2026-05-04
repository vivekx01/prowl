from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobRecord(BaseModel):
    application_id: int
    listing_id: int
    title: str
    company: str
    url: str
    description: str | None = None
    score: float | None = None


class ProfileData(BaseModel):
    content: str
    updated_at: datetime | None = None


class AnswerMemoryRecord(BaseModel):
    id: int | None = None
    question_text: str
    normalized_key: str
    answer: str
    field_type: str | None = None
    options: list[str] = []
    source: str = "llm"
    confidence: float = 0.7
    company_domain: str | None = None
    portal_key: str | None = None
    use_count: int = 1
    last_used: datetime | None = None


class LearnedStepRecord(BaseModel):
    id: int | None = None
    step_order: int
    step_name: str
    page_indicator: str | None = None
    tool_calls: list[dict[str, Any]] = []
    next_button: str | None = None


class LearnedFlowRecord(BaseModel):
    id: int | None = None
    company_domain: str
    portal_key: str | None = None
    success_count: int = 0
    last_success: datetime | None = None
    steps: list[LearnedStepRecord] = []


class ListingRecord(BaseModel):
    listing_id: int
    title: str
    company: str
    url: str
    description: str | None = None
    location: str | None = None
    posted_on: str | None = None
    score: float | None = None
    verdict: str | None = None
    saved: bool = False

    def to_job_record(self) -> "JobRecord":
        return JobRecord(
            application_id=0,
            listing_id=self.listing_id,
            title=self.title,
            company=self.company,
            url=self.url,
            description=self.description,
            score=self.score,
        )


class StepResult(BaseModel):
    step_name: str
    success: bool
    skipped: bool = False
    replay: bool = False
    agent_turns: int = 0
    error: str | None = None


class RunResult(BaseModel):
    listing_id: int | None
    status: str
    dry_run: bool
    agent_turns: int
    step_results: list[StepResult]
    error_message: str | None = None


class SyncData(BaseModel):
    jobs: list[JobRecord] = []
    profile: ProfileData | None = None
    memory: list[AnswerMemoryRecord] = []
    flows: list[LearnedFlowRecord] = []
