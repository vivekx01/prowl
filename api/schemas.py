from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class CompanyBase(BaseModel):
    name: str
    platform: str = "workday"
    active: bool = True
    config: dict = {}


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[str] = None
    active: Optional[bool] = None
    config: Optional[dict] = None


class CompanyCreateResult(BaseModel):
    company: "CompanyOut"
    warning: Optional[str] = None


class CompanyOut(CompanyBase):
    id: int
    created_at: datetime
    listing_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

class ScoreOut(BaseModel):
    score: float
    verdict: str
    reason: str
    processed_at: datetime

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: int
    listing_id: int
    status: str
    applied_at: Optional[datetime]
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    company_id: int
    company_name: str
    job_req_id: str
    title: str
    location: str
    posted_on: str
    posted_date: Optional[datetime]
    url: str
    department: str
    platform: str
    first_seen_at: datetime
    score: Optional[ScoreOut]
    application: Optional[ApplicationOut]

    model_config = {"from_attributes": True}


class JobsPageOut(BaseModel):
    total: int
    items: list[JobOut]


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class ApplicationCreate(BaseModel):
    listing_id: int
    status: str = "saved"
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileOut(BaseModel):
    id: int
    content: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingOut(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class BulkImportRequest(BaseModel):
    companies: list[CompanyCreate]

class BulkImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class CheckJDRequest(BaseModel):
    title: str = ""
    company: str = ""
    description: str


class CheckJDResult(BaseModel):
    score: float
    verdict: str
    reason: str


class ScrapeRequest(BaseModel):
    company_ids: Optional[list[int]] = None


class ScrapeStatus(BaseModel):
    running: bool
    started_at: Optional[str]
    log: list[str]
    result: Optional[dict]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    user_id: int
    email: str
    name: str
    is_admin: bool


# ---------------------------------------------------------------------------
# Score Run
# ---------------------------------------------------------------------------

class ScoreRunOut(BaseModel):
    id: int
    user_id: int
    celery_task_id: Optional[str]
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    companies_total: int
    companies_done: int
    apply_count: int
    input_tokens: int
    output_tokens: int
    current_company_id: Optional[int]
    company_results: list
    days_back: Optional[int]

    model_config = {"from_attributes": True}
