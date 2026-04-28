"""
Scrape orchestration.
Called by Celery tasks (tasks.py) and the CLI (main.py).
"""

import asyncio
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

import config
from db.database import SessionLocal
from db.models import (
    Company, JobListing, JobScore,
    Profile, ScrapeRun, ScrapeRunLog, Setting,
)
from scrapers import get_scraper
from llm.filter import JobFilter


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def parse_posted_on(raw: str) -> datetime | None:
    if not raw:
        return None
    s = raw.strip().lower()
    if "today" in s:
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    m = re.search(r"(\d+)\+?\s+day", s)
    if m:
        return datetime.utcnow() - timedelta(days=int(m.group(1)))
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


def get_setting(db: Session, key: str, default: str) -> str:
    row = db.query(Setting).filter_by(key=key).first()
    return row.value if row else default


# ---------------------------------------------------------------------------
# Seeding helpers (first-run)
# ---------------------------------------------------------------------------

def seed_companies_from_csv(db: Session) -> int:
    if db.query(Company).count() > 0:
        return 0
    csv_path = Path(config.COMPANIES_CSV)
    if not csv_path.exists():
        return 0
    added = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for row in reader:
            endpoint = row.get("Job listing fetch", "").strip()
            if not endpoint:
                continue
            db.add(Company(
                name=row["Company Name"].strip(),
                platform="workday",
                active=True,
                config={
                    "listing_endpoint": endpoint,
                    "payload": row.get("Payload", "{}") or "{}",
                    "jd_base": row.get("JD page base", "").strip(),
                    "base_careers_url": row.get("Base careers page", "").strip(),
                },
            ))
            added += 1
    db.commit()
    return added


def seed_defaults(db: Session):
    if not db.query(Profile).first():
        profile_path = Path(config.PROFILE_PATH)
        if profile_path.exists():
            db.add(Profile(content=profile_path.read_text(encoding="utf-8")))
    defaults = {"max_job_age_days": "30"}
    for key, val in defaults.items():
        if not db.query(Setting).filter_by(key=key).first():
            db.add(Setting(key=key, value=val))
    db.commit()


# ---------------------------------------------------------------------------
# Run logging helpers
# ---------------------------------------------------------------------------

def _write_log(db: Session, run_id: int, message: str, level: str = "info"):
    db.add(ScrapeRunLog(run_id=run_id, message=message.strip(), level=level))
    db.commit()


def _log_level(message: str) -> str:
    msg = message.lower()
    if "error" in msg or "failed" in msg:
        return "error"
    if "✓" in message or "apply" in msg:
        return "success"
    if "warning" in msg or "warn" in msg:
        return "warning"
    return "info"


# ---------------------------------------------------------------------------
# Main entry point (called from Celery task and CLI)
# ---------------------------------------------------------------------------

async def run_scrape(run_id: int, company_ids: list[int] | None = None) -> None:
    db = SessionLocal()
    try:
        await _run(db, run_id, company_ids)
    finally:
        db.close()


async def _run(db: Session, run_id: int, company_ids: list[int] | None) -> None:
    run = db.get(ScrapeRun, run_id)
    if not run:
        return

    def log(message: str, level: str | None = None):
        print(message)
        _write_log(db, run_id, message, level or _log_level(message))

    # Resolve companies — honour resume by skipping already-completed ones
    completed_ids: set[int] = set(json.loads(run.completed_company_ids or "[]"))

    q = db.query(Company).filter_by(active=True)
    if company_ids:
        q = q.filter(Company.id.in_(company_ids))
    companies = [c for c in q.all() if c.id not in completed_ids]

    run.status = "running"
    run.companies_total = len(companies) + len(completed_ids)
    run.companies_done = len(completed_ids)
    db.commit()

    log(
        f"Filter model: {config.FILTER_MODEL}  ·  "
        f"Score model: {config.SCORE_MODEL}"
    )

    profile_row = db.query(Profile).first()
    profile_text = (
        profile_row.content if profile_row
        else config.PROFILE_PATH.read_text(encoding="utf-8")
    )
    max_age_days = int(get_setting(db, "max_job_age_days", "30"))
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    total_new = run.new_listings
    total_apply = run.apply_count
    inp_tokens = run.input_tokens
    out_tokens = run.output_tokens

    try:
        # Group companies by platform so we open one scraper per platform
        from collections import defaultdict
        by_platform: dict[str, list[Company]] = defaultdict(list)
        for c in companies:
            by_platform[c.platform].append(c)

        job_filter = JobFilter(profile_text)

        for platform, platform_companies in by_platform.items():
            scraper_cls = get_scraper(platform)
            async with scraper_cls() as scraper:
                for company in platform_companies:
                    log(f"\nProcessing: {company.name} [{platform}]")
                    company_row = {"name": company.name, **(company.config or {})}

                    try:
                        raw_listings = await scraper.fetch_listings(company_row)
                    except Exception as e:
                        log(f"  Error fetching listings: {e}", "error")
                        _mark_company_done(db, run, company.id, completed_ids)
                        continue

                    # Dedup + age filter
                    new_listings = []
                    listing_to_db_id: dict[int, int] = {}

                    for listing in raw_listings:
                        posted_date = parse_posted_on(listing.posted_on)
                        if posted_date and posted_date < cutoff:
                            continue

                        existing = (
                            db.query(JobListing)
                            .filter_by(company_id=company.id, job_req_id=listing.job_id)
                            .first()
                        )
                        if existing:
                            if existing.score is not None:
                                continue
                            listing_to_db_id[id(listing)] = existing.id
                        else:
                            db_listing = JobListing(
                                company_id=company.id,
                                job_req_id=listing.job_id,
                                title=listing.title,
                                location=listing.location,
                                posted_on=listing.posted_on,
                                posted_date=posted_date,
                                url=listing.url,
                                department=listing.department or "",
                                platform=platform,
                            )
                            db.add(db_listing)
                            db.flush()
                            listing_to_db_id[id(listing)] = db_listing.id
                            total_new += 1

                        new_listings.append(listing)

                    db.commit()

                    if not new_listings:
                        log("  No new listings")
                        _mark_company_done(db, run, company.id, completed_ids)
                        continue

                    log(f"  {len(new_listings)} new → stage 1 filter")
                    candidates = await job_filter.stage1_filter(new_listings)

                    # Write skip scores for stage-1 rejects immediately
                    candidate_obj_ids = {id(c) for c in candidates}
                    scored_db_ids: set[int] = set()
                    for listing in new_listings:
                        if id(listing) not in candidate_obj_ids:
                            db_id = listing_to_db_id.get(id(listing))
                            if db_id and db_id not in scored_db_ids:
                                db.add(JobScore(
                                    listing_id=db_id,
                                    score=0.0,
                                    verdict="skip",
                                    reason="filtered by stage 1",
                                ))
                                scored_db_ids.add(db_id)
                    db.commit()

                    if not candidates:
                        log("  None passed stage 1")
                        _mark_company_done(db, run, company.id, completed_ids)
                        continue

                    log(f"  {len(candidates)} candidates → scoring")
                    for listing in candidates:
                        print(f"  Scanning: {listing.title[:70]:<75}", end="\r", flush=True)
                        listing.description = await scraper.fetch_description(listing)
                        score_result = await job_filter.stage2_score(listing)

                        db_id = listing_to_db_id.get(id(listing))
                        if db_id and db_id not in scored_db_ids:
                            db.add(JobScore(
                                listing_id=db_id,
                                score=score_result.get("score", 0),
                                verdict=score_result.get("verdict", "skip"),
                                reason=score_result.get("reason", ""),
                            ))
                            scored_db_ids.add(db_id)
                            db.commit()

                        if score_result.get("verdict") == "apply":
                            total_apply += 1
                            log(
                                f"  ✓ [{score_result['score']:.1f}/10] {listing.title}"
                                f" — {score_result['reason'][:90]}",
                                "success",
                            )

                        await asyncio.sleep(0.5)

                    print(" " * 80, end="\r", flush=True)
                    _mark_company_done(db, run, company.id, completed_ids)

            inp_tokens_now, out_tokens_now = job_filter.token_usage
            inp_tokens = inp_tokens_now
            out_tokens = out_tokens_now

        run.status = "completed"

    except Exception as e:
        log(f"[fatal] {e}", "error")
        run.status = "failed"

    finally:
        run.finished_at = datetime.utcnow()
        run.new_listings = total_new
        run.apply_count = total_apply
        run.input_tokens = inp_tokens
        run.output_tokens = out_tokens
        db.commit()

        summary = (
            f"\n{'='*50}\n"
            f"New listings: {total_new}  |  Recommended to apply: {total_apply}\n"
            f"Tokens — input: {inp_tokens:,}  output: {out_tokens:,}  total: {inp_tokens + out_tokens:,}"
        )
        log(summary)


def _mark_company_done(
    db: Session, run: ScrapeRun, company_id: int, completed_ids: set[int]
):
    completed_ids.add(company_id)
    run.completed_company_ids = json.dumps(list(completed_ids))
    run.companies_done = len(completed_ids)
    db.commit()
