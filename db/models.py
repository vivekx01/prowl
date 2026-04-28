from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


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
    posted_on = Column(String, default="")   # raw string from API
    posted_date = Column(DateTime, nullable=True)  # parsed
    url = Column(String, default="")
    department = Column(String, default="")
    platform = Column(String, default="workday")
    first_seen_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="listings")
    score = relationship("JobScore", back_populates="listing", uselist=False)
    application = relationship("Application", back_populates="listing", uselist=False)

    __table_args__ = (
        UniqueConstraint("company_id", "job_req_id", name="uq_company_job"),
    )


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False, unique=True)
    score = Column(Float, default=0.0)
    verdict = Column(String, default="skip")
    reason = Column(Text, default="")
    processed_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("JobListing", back_populates="score")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False, unique=True)
    status = Column(String, default="saved")  # saved/applied/interviewing/rejected/offer/withdrawn
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing = relationship("JobListing", back_populates="application")


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True)
    celery_task_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending/running/completed/failed
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    company_ids = Column(Text, nullable=True)           # JSON array, null = all
    completed_company_ids = Column(Text, default="[]")  # JSON array — updated as each company finishes
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
    level = Column(String, default="info")   # info/success/error/warning
    message = Column(Text, nullable=False)

    run = relationship("ScrapeRun", back_populates="logs")
