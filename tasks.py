import asyncio
import json
from datetime import datetime, timedelta, timezone

from croniter import croniter

from celery_app import celery_app
from config import IST
from runner import run_scrape


@celery_app.task(bind=True, name="tasks.scrape", max_retries=0)
def scrape_task(self, run_id: int, company_ids: list[int] | None):
    asyncio.run(run_scrape(run_id=run_id, company_ids=company_ids))


@celery_app.task(bind=True, name="tasks.score", max_retries=0)
def score_task(self, run_id: int, user_id: int, company_ids: list[int] | None = None):
    from scorer import run_score
    asyncio.run(run_score(run_id=run_id, user_id=user_id, company_ids=company_ids))


@celery_app.task(name="tasks.cleanup_old_listings", max_retries=0)
def cleanup_old_listings():
    from datetime import timedelta
    from db.database import SessionLocal
    from db.models import Application, JobListing, JobScore, PounceRun
    from config import now_ist

    db = SessionLocal()
    try:
        cutoff = now_ist() - timedelta(days=30)

        protected = set()
        protected.update(r[0] for r in db.query(Application.listing_id).all())
        protected.update(r[0] for r in db.query(PounceRun.listing_id).filter(PounceRun.listing_id.isnot(None)).all())

        ids = [
            r[0] for r in db.query(JobListing.id).filter(JobListing.first_seen_at < cutoff).all()
            if r[0] not in protected
        ]
        if not ids:
            return

        db.query(JobScore).filter(JobScore.listing_id.in_(ids)).delete(synchronize_session=False)
        db.query(JobListing).filter(JobListing.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        print(f"[cleanup] removed {len(ids)} listings older than 30 days")
    except Exception as e:
        db.rollback()
        print(f"[cleanup] error: {e}")
    finally:
        db.close()


@celery_app.task(name="tasks.check_schedule", max_retries=0)
def check_schedule_task():
    """Runs every minute. Triggers scrape/score if current IST time matches a configured slot."""
    from db.database import SessionLocal
    from db.models import Profile, ScoreRun, Setting, ScrapeRun, User

    now = datetime.now(IST).replace(second=0, microsecond=0)
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    current_minutes = now_utc.hour * 60 + now_utc.minute

    def _cron_fires_now(expr: str) -> bool:
        """True if the cron expression fired at the current IST minute."""
        if not expr:
            return False
        try:
            prev = now - timedelta(seconds=1)
            return croniter(expr, prev).get_next(datetime).replace(tzinfo=None) == now.replace(tzinfo=None)
        except Exception:
            return False

    def _slot_fires_now(times: list[str]) -> bool:
        """True if current IST time is within 2 minutes of any HH:MM slot."""
        for t in times:
            h, m = map(int, t.split(":"))
            diff = (current_minutes - (h * 60 + m)) % (24 * 60)
            if diff < 2:
                return True
        return False

    db = SessionLocal()
    try:
        def _get_setting(key: str, user_id=None) -> str | None:
            row = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == key).first()
            return row.value if row else None

        scrape_cron = _get_setting("scrape_schedule")
        scrape_times_raw = _get_setting("scrape_times")
        scrape_times = json.loads(scrape_times_raw) if scrape_times_raw else []

        if _cron_fires_now(scrape_cron) or _slot_fires_now(scrape_times):
            active = db.query(ScrapeRun).filter(ScrapeRun.status.in_(["pending", "running"])).first()
            if not active:
                run = ScrapeRun(status="pending", company_ids=None, completed_company_ids="[]")
                db.add(run)
                db.commit()
                db.refresh(run)
                task = scrape_task.delay(run.id, None)
                run.celery_task_id = task.id
                db.commit()

        # Per-user score schedules (HH:MM IST slots)
        users = (
            db.query(User)
            .join(Profile, Profile.user_id == User.id)
            .filter(User.is_active == True)
            .all()
        )
        for user in users:
            raw = _get_setting("score_schedule", user_id=user.id)
            user_score_times = json.loads(raw) if raw else []
            if not user_score_times or not _slot_fires_now(user_score_times):
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
    finally:
        db.close()
