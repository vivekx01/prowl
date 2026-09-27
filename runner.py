"""
Scrape orchestration — fetch and store raw listings only.
No LLM work here. Scoring is per-user via scorer.py.
"""

import asyncio
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session

import config
from config import now_ist
from db.database import SessionLocal
from db.models import Company, JobListing, JobScore, Profile, ScoreRun, ScrapeRun, ScrapeRunLog, Setting, User
from scrapers import get_scraper


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def parse_posted_on(raw: str) -> datetime | None:
    if not raw:
        return None
    s = raw.strip().lower()
    if "today" in s:
        return now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    m = re.search(r"(\d+)\+?\s+day", s)
    if m:
        return now_ist() - timedelta(days=int(m.group(1)))
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


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
            name = row.get("name", "").strip()
            if not name:
                continue
            db.add(Company(
                name=name,
                platform=row.get("platform", "").strip() or "workday",
                active=row.get("active", "true").strip().lower() == "true",
                config=json.loads(row.get("config") or "{}"),
            ))
            added += 1
    db.commit()
    return added


def seed_admin_user(db: Session):
    if db.query(User).count() > 0:
        return
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    db.add(User(
        email=config.ADMIN_EMAIL,
        password_hash=_pwd.hash(config.ADMIN_PASSWORD),
        name="Admin",
        is_admin=True,
    ))
    db.commit()
    print(f"[startup] Created {config.ADMIN_EMAIL}")




# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_listings(db: Session) -> int:
    cutoff = now_ist() - timedelta(days=config.LISTING_RETENTION_DAYS)
    protected = set()
    protected.update(r[0] for r in db.query(JobListing.id).join(JobListing.applications).all())
    old_ids = [
        row[0] for row in
        db.query(JobListing.id)
        .filter(JobListing.last_seen_at < cutoff)
        .all()
        if row[0] not in protected
    ]
    if not old_ids:
        return 0
    db.query(JobScore).filter(JobScore.listing_id.in_(old_ids)).delete(synchronize_session=False)
    db.query(JobListing).filter(JobListing.id.in_(old_ids)).delete(synchronize_session=False)
    db.commit()
    return len(old_ids)


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
    if "warning" in msg or "warn" in msg:
        return "warning"
    return "info"


# ---------------------------------------------------------------------------
# Main entry point
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

    completed_ids: set[int] = set(json.loads(run.completed_company_ids or "[]"))

    q = db.query(Company).filter_by(active=True)
    if company_ids:
        q = q.filter(Company.id.in_(company_ids))
    companies = [c for c in q.all() if c.id not in completed_ids]

    run.status = "running"
    run.companies_total = len(companies) + len(completed_ids)
    run.companies_done = len(completed_ids)
    db.commit()

    total_companies = run.companies_total
    log(f"Starting scrape run: {total_companies} companies")

    try:
        purged = cleanup_old_listings(db)
        if purged:
            log(f"Purged {purged} listings older than {config.LISTING_RETENTION_DAYS} days")
    except Exception as e:
        db.rollback()
        log(f"Cleanup error (continuing): {e}", "error")

    total_new = run.new_listings
    company_index = len(completed_ids)

    try:
        from collections import defaultdict
        by_platform: dict[str, list[Company]] = defaultdict(list)
        for c in companies:
            by_platform[c.platform].append(c)

        sem = asyncio.Semaphore(config.SCRAPE_CONCURRENCY)

        async def scrape_one(scraper, company: Company, platform: str) -> dict:
            """Fetch + store one company's listings, using its own DB session
            so concurrent companies never share a SQLAlchemy session."""
            async with sem:
                cdb = SessionLocal()
                try:
                    company_row = {"name": company.name, **(company.config or {})}
                    try:
                        raw_listings = await scraper.fetch_listings(company_row)
                    except Exception as e:
                        return {"company": company, "error": str(e)}

                    fetched_count = len(raw_listings)
                    new_count = 0
                    seen_in_batch: set[str] = set()
                    for listing in raw_listings:
                        if listing.job_id in seen_in_batch:
                            continue
                        existing = (
                            cdb.query(JobListing)
                            .filter_by(company_id=company.id, job_req_id=listing.job_id)
                            .first()
                        )
                        if existing:
                            existing.last_seen_at = now_ist()
                            cdb.commit()
                            continue

                        seen_in_batch.add(listing.job_id)

                        # New listing — fetch full detail (description + startDate)
                        detail = await scraper.fetch_detail(listing)
                        start_date = detail.get("start_date")
                        if start_date:
                            try:
                                posted_date = datetime.fromisoformat(start_date[:10])
                            except ValueError:
                                posted_date = parse_posted_on(listing.posted_on)
                        else:
                            posted_date = parse_posted_on(listing.posted_on)

                        try:
                            cdb.add(JobListing(
                                company_id=company.id,
                                job_req_id=listing.job_id,
                                title=listing.title,
                                location=listing.location,
                                posted_on=listing.posted_on,
                                posted_date=posted_date,
                                url=listing.url,
                                department=listing.department or "",
                                platform=platform,
                                description=detail.get("description") or None,
                            ))
                            cdb.commit()
                            new_count += 1
                        except IntegrityError:
                            cdb.rollback()
                    return {"company": company, "fetched_count": fetched_count, "new_count": new_count}
                finally:
                    cdb.close()

        for platform, platform_companies in by_platform.items():
            db.refresh(run)
            if run.status == "cancelled":
                log("Run cancelled — stopping", "warning")
                return

            scraper_cls = get_scraper(platform)
            async with scraper_cls() as scraper:
                # Launched up front; `sem` throttles how many actually run at once.
                tasks = [asyncio.create_task(scrape_one(scraper, c, platform)) for c in platform_companies]
                try:
                    for coro in asyncio.as_completed(tasks):
                        result = await coro
                        company = result["company"]
                        company_index += 1
                        log(f"\n[{company_index}/{total_companies}] {company.name} [{platform}]")
                        if "error" in result:
                            log(f"  Error fetching listings: {result['error']}", "error")
                        else:
                            log(f"  {result['fetched_count']} fetched · {result['new_count']} new")
                            total_new += result["new_count"]
                        _mark_company_done(db, run, company.id, completed_ids)

                        db.refresh(run)
                        if run.status == "cancelled":
                            log("Run cancelled — stopping", "warning")
                            for t in tasks:
                                t.cancel()
                            return
                finally:
                    # Let any still-pending/cancelled tasks settle before the
                    # scraper's httpx client closes on `async with` exit.
                    await asyncio.gather(*tasks, return_exceptions=True)

        run.status = "completed"

    except Exception as e:
        log(f"Fatal error: {e}", "error")
        run.status = "failed"

    finally:
        run.finished_at = now_ist()
        run.new_listings = total_new
        db.commit()

        log(f"\n{'='*40}\nDone — {total_new} new listings stored")

        if run.status == "completed":
            try:
                _trigger_aligned_scoring(db)
            except Exception as e:
                print(f"[align] error triggering aligned scoring: {e}")


def _mark_company_done(
    db: Session, run: ScrapeRun, company_id: int, completed_ids: set[int]
):
    completed_ids.add(company_id)
    run.completed_company_ids = json.dumps(list(completed_ids))
    run.companies_done = len(completed_ids)
    db.commit()


def _trigger_aligned_scoring(db: Session) -> None:
    """Start a score run for every active user with score_align_with_scraping=true."""
    from tasks import score_task

    users = (
        db.query(User)
        .join(Profile, Profile.user_id == User.id)
        .filter(User.is_active == True)
        .all()
    )
    for user in users:
        align_row = db.query(Setting).filter(
            Setting.user_id == user.id,
            Setting.key == "score_align_with_scraping",
        ).first()
        if not align_row or align_row.value != "true":
            continue
        active = db.query(ScoreRun).filter(
            ScoreRun.user_id == user.id,
            ScoreRun.status.in_(["pending", "running"]),
        ).first()
        if active:
            continue
        run = ScoreRun(user_id=user.id, status="pending", days_back=None)
        db.add(run)
        db.commit()
        db.refresh(run)
        task = score_task.delay(run.id, user.id, None)
        run.celery_task_id = task.id
        db.commit()
        print(f"[align] triggered scoring for user {user.id} after scrape completion")
