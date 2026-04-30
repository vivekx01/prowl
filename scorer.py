"""
Per-user scoring run.
All data comes from the DB — no web calls. Descriptions are stored at scrape time.
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import Company, JobListing, JobScore, Profile, ScoreRun, ScoreRunLog
from llm.filter import JobFilter
from scrapers.base import JobListing as ScraperListing


async def run_score(run_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        await _score(db, run_id, user_id)
    finally:
        db.close()


def _log(db: Session, run_id: int, message: str, level: str = "info") -> None:
    db.add(ScoreRunLog(run_id=run_id, message=message.strip(), level=level))
    db.commit()


async def _score(db: Session, run_id: int, user_id: int) -> None:
    run = db.get(ScoreRun, run_id)
    if not run:
        return

    profile = db.query(Profile).filter_by(user_id=user_id).first()
    if not profile:
        run.status = "failed"
        db.commit()
        _log(db, run_id, "No profile found for user", "error")
        return

    companies = db.query(Company).filter_by(active=True).all()
    run.status = "running"
    run.companies_total = len(companies)
    db.commit()
    _log(db, run_id, f"Starting score run: {len(companies)} companies, days_back={run.days_back or 'all'}")

    job_filter = JobFilter(profile.content)
    results: list[dict] = []
    total_apply = 0

    cutoff = None
    if run.days_back and run.days_back > 0:
        cutoff = datetime.utcnow() - timedelta(days=run.days_back)

    try:
        for company in companies:
            db.refresh(run)
            if run.status == "cancelled":
                _log(db, run_id, "Run cancelled — stopping", "warning")
                return

            run.current_company_id = company.id
            db.commit()
            _log(db, run_id, f"Scoring {company.name}")

            # Listings not yet scored by this user
            already_scored = {
                row[0] for row in
                db.query(JobScore.listing_id)
                .filter(
                    JobScore.user_id == user_id,
                    JobScore.listing_id.in_(
                        db.query(JobListing.id).filter_by(company_id=company.id)
                    ),
                )
                .all()
            }

            listing_q = db.query(JobListing).filter_by(company_id=company.id)
            if cutoff is not None:
                listing_q = listing_q.filter(JobListing.posted_date >= cutoff)
            db_listings = [l for l in listing_q.all() if l.id not in already_scored]

            if not db_listings:
                _log(db, run_id, f"  {company.name}: no new listings to score")
                results.append({"id": company.id, "name": company.name, "platform": company.platform, "matches": 0})
                run.company_results = list(results)
                run.companies_done += 1
                db.commit()
                continue

            # Build scraper listing objects for stage 1 title filter
            scraper_listings = [
                ScraperListing(
                    company=company.name,
                    title=l.title,
                    job_id=l.job_req_id,
                    location=l.location,
                    posted_on=l.posted_on,
                    url=l.url,
                    department=l.department,
                    description=l.description or "",
                    raw={"_db_id": l.id},
                )
                for l in db_listings
            ]

            _log(db, run_id, f"  {company.name}: {len(db_listings)} listings to evaluate")

            # Stage 1 — title filter
            candidates = await job_filter.stage1_filter(scraper_listings)
            if not candidates:
                _log(db, run_id, f"  {company.name}: 0 passed stage 1 filter")
                for sl in scraper_listings:
                    db.add(JobScore(listing_id=sl.raw["_db_id"], user_id=user_id, score=0.0, verdict="skip", reason="filtered by stage 1"))
                db.commit()
                results.append({"id": company.id, "name": company.name, "platform": company.platform, "matches": 0})
                run.company_results = list(results)
                run.companies_done += 1
                db.commit()
                continue

            _log(db, run_id, f"  {company.name}: {len(candidates)}/{len(scraper_listings)} passed stage 1, deep scoring…")

            # Write skip scores for stage 1 rejects
            candidate_ids = {id(c) for c in candidates}
            for sl in scraper_listings:
                if id(sl) not in candidate_ids:
                    db.add(JobScore(listing_id=sl.raw["_db_id"], user_id=user_id, score=0.0, verdict="skip", reason="filtered by stage 1"))
            db.commit()

            # Stage 2 — deep score using stored description
            matches = 0
            for sl in candidates:
                if not sl.description:
                    db.add(JobScore(listing_id=sl.raw["_db_id"], user_id=user_id, score=0.0, verdict="skip", reason="no description stored"))
                    db.commit()
                    continue

                result = await job_filter.stage2_score(sl)
                if result is None:
                    # Parse failed — leave unscored so the next run retries it
                    db.commit()
                    continue
                db.add(JobScore(
                    listing_id=sl.raw["_db_id"],
                    user_id=user_id,
                    score=result.get("score", 0),
                    verdict=result.get("verdict", "skip"),
                    reason=result.get("reason", ""),
                ))
                if result.get("verdict") == "apply":
                    matches += 1
                db.commit()
                await asyncio.sleep(0.3)

            total_apply += matches
            _log(db, run_id, f"  {company.name}: {matches} matches")
            results.append({"id": company.id, "name": company.name, "platform": company.platform, "matches": matches})
            run.company_results = list(results)
            run.companies_done += 1
            run.apply_count = total_apply
            db.commit()

        inp, out = job_filter.token_usage
        run.input_tokens = inp
        run.output_tokens = out
        run.status = "completed"
        _log(db, run_id, f"Done — {total_apply} total matches · {inp:,} in / {out:,} out tokens")

    except Exception as e:
        print(f"[score run {run_id}] fatal: {e}")
        run.status = "failed"
        _log(db, run_id, f"Fatal error: {e}", "error")

    finally:
        run.finished_at = datetime.utcnow()
        run.current_company_id = None
        db.commit()
