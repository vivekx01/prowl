from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, default="")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profiles = relationship("Profile", back_populates="user")
    score_runs = relationship("ScoreRun", back_populates="user")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False, default="workday")
    active = Column(Boolean, default=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    listings = relationship("JobListing", back_populates="company")


class JobListing(Base):
    __tablename__ = "job_listings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    job_req_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    location = Column(String, default="")
    posted_on = Column(String, default="")
    posted_date = Column(DateTime, nullable=True)
    url = Column(String, default="")
    department = Column(String, default="")
    platform = Column(String, default="workday")
    description = Column(Text, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="listings")
    scores = relationship("JobScore", back_populates="listing")
    applications = relationship("Application", back_populates="listing")

    __table_args__ = (
        UniqueConstraint("company_id", "job_req_id", name="uq_company_job"),
    )


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    score = Column(Float, default=0.0)
    verdict = Column(String, default="skip")
    reason = Column(Text, default="")
    processed_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("JobListing", back_populates="scores")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing_score"),
    )


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="saved")
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing = relationship("JobListing", back_populates="applications")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing_app"),
    )


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profiles")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_setting"),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True)
    celery_task_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    company_ids = Column(Text, nullable=True)
    completed_company_ids = Column(Text, default="[]")
    companies_total = Column(Integer, default=0)
    companies_done = Column(Integer, default=0)
    new_listings = Column(Integer, default=0)
    apply_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)

    logs = relationship("ScrapeRunLog", back_populates="run", order_by="ScrapeRunLog.id")


class ScrapeRunLog(Base):
    __tablename__ = "scrape_run_logs"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, default="info")
    message = Column(Text, nullable=False)

    run = relationship("ScrapeRun", back_populates="logs")


class ScoreRun(Base):
    __tablename__ = "score_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    celery_task_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    companies_total = Column(Integer, default=0)
    companies_done = Column(Integer, default=0)
    apply_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    filter_input_tokens = Column(Integer, default=0)
    filter_output_tokens = Column(Integer, default=0)
    score_input_tokens = Column(Integer, default=0)
    score_output_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    current_company_id = Column(Integer, nullable=True)
    company_results = Column(JSON, default=list)
    days_back = Column(Integer, nullable=True)
    company_ids = Column(JSON, nullable=True)

    user = relationship("User", back_populates="score_runs")
    logs = relationship("ScoreRunLog", back_populates="run", order_by="ScoreRunLog.id")


class ScoreRunLog(Base):
    __tablename__ = "score_run_logs"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("score_runs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, default="info")
    message = Column(Text, nullable=False)

    run = relationship("ScoreRun", back_populates="logs")


# ---------------------------------------------------------------------------
# Pounce — application bot
# ---------------------------------------------------------------------------

class PounceRun(Base):
    __tablename__ = "pounce_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=True)
    status = Column(String, default="pending")  # pending/running/completed/failed/dry_run_completed
    dry_run = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    agent_turns = Column(Integer, default=0)
    step_results = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)

    logs = relationship("PounceRunLog", back_populates="run", order_by="PounceRunLog.id")


class PounceRunLog(Base):
    __tablename__ = "pounce_run_logs"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("pounce_runs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, default="info")
    message = Column(Text, nullable=False)

    run = relationship("PounceRun", back_populates="logs")


class AnswerMemory(Base):
    __tablename__ = "pounce_answer_memory"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    normalized_key = Column(String, nullable=False)
    answer = Column(Text, nullable=False)
    field_type = Column(String, nullable=True)       # text/radio/dropdown/textarea
    options = Column(JSON, default=list)
    source = Column(String, default="llm")           # "user" | "llm"
    confidence = Column(Float, default=0.7)          # user=1.0, llm=0.7
    company_domain = Column(String, nullable=True)   # "google.wd5.myworkdayjobs.com" | null
    portal_key = Column(String, nullable=True)       # "workday" | null (global)
    use_count = Column(Integer, default=1)
    last_used = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "normalized_key", "company_domain", "portal_key",
                         name="uq_answer_memory"),
    )


class LearnedFlow(Base):
    __tablename__ = "pounce_learned_flows"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_domain = Column(String, nullable=False)  # primary lookup key
    portal_key = Column(String, nullable=True)       # "workday" | null (metadata only)
    success_count = Column(Integer, default=0)
    last_success = Column(DateTime, nullable=True)

    steps = relationship("LearnedStep", back_populates="flow",
                         order_by="LearnedStep.step_order", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "company_domain", name="uq_learned_flow"),
    )


class LearnedStep(Base):
    __tablename__ = "pounce_learned_steps"

    id = Column(Integer, primary_key=True)
    flow_id = Column(Integer, ForeignKey("pounce_learned_flows.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_name = Column(String, nullable=False)
    page_indicator = Column(String, nullable=True)   # aria-label/text to identify page
    tool_calls = Column(JSON, default=list)          # [{tool, args}] replay hints
    next_button = Column(String, nullable=True)      # aria-label of continue button

    flow = relationship("LearnedFlow", back_populates="steps")
