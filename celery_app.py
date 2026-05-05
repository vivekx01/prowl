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
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-schedule": {
            "task": "tasks.check_schedule",
            "schedule": crontab(minute="*"),  # every minute — cron expressions need minute precision
        },
    },
)
