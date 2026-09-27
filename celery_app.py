from celery import Celery
from celery.schedules import crontab
import config

celery_app = Celery(
    "job_scraper",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "tasks.scrape": {"queue": "scrape"},
        "tasks.score": {"queue": "score"},
    },
    beat_schedule={
        "check-schedule": {
            "task": "tasks.check_schedule",
            "schedule": crontab(minute="*"),  # every minute — cron expressions need minute precision
        },
        "cleanup-old-listings": {
            "task": "tasks.cleanup_old_listings",
            "schedule": crontab(hour=2, minute=0),  # 2 AM IST daily
        },
    },
)
