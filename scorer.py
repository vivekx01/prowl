"""
Per-user scoring run.
All data comes from the DB — no web calls. Descriptions are stored at scrape time.
"""

import asyncio
import traceback
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import config
from config import now_ist
from db.database import SessionLocal
from db.models import Company, JobListing, JobScore, Profile, ScoreRun, ScoreRunLog
from llm.filter import JobFilter
from scrapers.base import JobListing as ScraperListing, is_clearly_foreign


def _load_model_config(db: Session) -> dict:
    """Load model/pricing config from DB settings, falling back to env config."""
    from db.models import Setting
    keys_defaults = {
        "model.filter_model":           config.FILTER_MODEL,
        "model.score_model":            config.SCORE_MODEL,
        "model.filter_price_in":        str(config.FILTER_MODEL_PRICE_IN),
        "model.filter_price_out":       str(config.FILTER_MODEL_PRICE_OUT),
        "model.score_price_in":         str(config.SCORE_MODEL_PRICE_IN),
        "model.score_price_out":        str(config.SCORE_MODEL_PRICE_OUT),
        "model.score_cache_discount":   str(config.SCORE_MODEL_CACHE_DISCOUNT),
        "model.score_threshold":        str(config.SCORE_THRESHOLD),
    }
    rows = {
        r.key: r.value
        for r in db.query(Setting).filter(
            Setting.user_id == None, Setting.key.in_(list(keys_defaults))
        ).all()
    }
    def _get(k):
        return rows.get(k, keys_defaults[k])

    return {
        "filter_model":         _get("model.filter_model"),
        "score_model":          _get("model.score_model"),
        "filter_price_in":      float(_get("model.filter_price_in")),
        "filter_price_out":     float(_get("model.filter_price_out")),
        "score_price_in":       float(_get("model.score_price_in")),
        "score_price_out":      float(_get("model.score_price_out")),
        "score_cache_discount": float(_get("model.score_cache_discount")),
        "score_threshold":      float(_get("model.score_threshold")),
    }


def _compute_cost(usage: dict, model_cfg: dict) -> float:
    """Calculate run cost in USD from per-stage token counts."""
    filter_cost = (
        usage["filter_input"] * model_cfg["filter_price_in"]
        + usage["filter_output"] * model_cfg["filter_price_out"]
    ) / 1_000_000

    cached = usage["cached"]
    score_in = usage["score_input"]
    score_cost = (
        cached * model_cfg["score_price_in"] * model_cfg["score_cache_discount"]
        + max(score_in - cached, 0) * model_cfg["score_price_in"]
        + usage["score_output"] * model_cfg["score_price_out"]
    ) / 1_000_000

    return filter_cost + score_cost


async def run_score(run_id: int, user_id: int, company_ids: list[int] | None = None) -> None:
    db = SessionLocal()
    try:
        await _score(db, run_id, user_id, company_ids)
    finally:
        db.close()


def _log(db: Session, run_id: int, message: str, level: str = "info") -> None:
    db.add(ScoreRunLog(run_id=run_id, message=message.strip(), level=level))
    db.commit()


async def _score(db: Session, run_id: int, user_id: int, company_ids: list[int] | None = None) -> None:
    run = db.get(ScoreRun, run_id)
    if not run:
        return

    profile = db.query(Profile).filter_by(user_id=user_id).first()
    if not profile:
        run.status = "failed"
        db.commit()
        _log(db, run_id, "No profile found for user", "error")
        return

    q = db.query(Company).filter_by(active=True)
    if company_ids:
        q = q.filter(Company.id.in_(company_ids))
    companies = q.all()
    run.status = "running"
    run.companies_total = len(companies)
    db.commit()
    _log(db, run_id, f"Starting score run: {len(companies)} companies, days_back={run.days_back or 'all'}")

    model_cfg = _load_model_config(db)
    job_filter = JobFilter(
        profile.content,
        filter_model=model_cfg["filter_model"],
        score_model=model_cfg["score_model"],
        score_threshold=model_cfg["score_threshold"],
    )
    await job_filter.warm_up()
    _log(db, run_id, f"  compact profile: {job_filter._compact_profile}")
    results: list[dict] = []
    total_apply = 0
    notify_matches: list[dict] = []

    cutoff = None
    if run.days_back and run.days_back > 0:
        cutoff = now_ist() - timedelta(days=run.days_back)

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
                listing_q = listing_q.filter(JobListing.first_seen_at >= cutoff)
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

            no_desc_count = sum(1 for l in db_listings if not l.description)
            _log(db, run_id, f"  {company.name}: {len(db_listings)} listings to evaluate ({no_desc_count} missing description)")
            _log(db, run_id, "  titles: " + " | ".join(l.title for l in db_listings))

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
                # Hard location gate: skip only when location is unambiguously non-India
                if is_clearly_foreign(sl.location):
                    db.add(JobScore(listing_id=sl.raw["_db_id"], user_id=user_id, score=0.0, verdict="skip", reason="location not India or remote"))
                    db.commit()
                    continue

                if not sl.description:
                    _log(db, run_id, f"  {company.name}: skipping '{sl.title}' — no description stored", "warning")
                    db.add(JobScore(listing_id=sl.raw["_db_id"], user_id=user_id, score=0.0, verdict="skip", reason="no description stored"))
                    db.commit()
                    continue

                result = await job_filter.stage2_score(sl)
                if result is None:
                    # Parse failed — leave unscored so the next run retries it
                    db.commit()
                    continue
                verdict = result.get("verdict", "skip")
                score = result.get("score", 0)
                db.add(JobScore(
                    listing_id=sl.raw["_db_id"],
                    user_id=user_id,
                    score=score,
                    verdict=verdict,
                    reason=result.get("reason", ""),
                ))
                if verdict in ("apply", "consider"):
                    matches += 1
                    notify_matches.append({
                        "title": sl.title,
                        "company": sl.company,
                        "score": round(score),
                        "verdict": verdict,
                        "url": sl.url,
                    })
                db.commit()
                await asyncio.sleep(0.3)

            total_apply += matches
            _log(db, run_id, f"  {company.name}: {matches} matches")
            results.append({"id": company.id, "name": company.name, "platform": company.platform, "matches": matches})
            run.company_results = list(results)
            run.companies_done += 1
            run.apply_count = total_apply
            db.commit()

        usage = job_filter.detailed_token_usage
        inp, out = job_filter.token_usage
        run.input_tokens = inp
        run.output_tokens = out
        run.filter_input_tokens = usage["filter_input"]
        run.filter_output_tokens = usage["filter_output"]
        run.score_input_tokens = usage["score_input"]
        run.score_output_tokens = usage["score_output"]
        run.cached_tokens = usage["cached"]
        run.cost_usd = _compute_cost(usage, model_cfg)
        run.status = "completed"
        _log(db, run_id, f"Done — {total_apply} total matches · {inp:,} in / {out:,} out tokens · ${run.cost_usd:.4f}")

        if notify_matches:
            from notify import notify_new_matches
            notify_matches_sorted = sorted(notify_matches, key=lambda x: x["score"], reverse=True)
            await notify_new_matches(user_id, notify_matches_sorted, db)

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[score run {run_id}] fatal: {type(e).__name__}: {e!r}\n{tb}")
        run.status = "failed"
        _log(db, run_id, f"Fatal error: {type(e).__name__}: {e!r}", "error")

    finally:
        run.finished_at = now_ist()
        run.current_company_id = None
        db.commit()
