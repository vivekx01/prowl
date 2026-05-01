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
