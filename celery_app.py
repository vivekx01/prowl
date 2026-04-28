from celery import Celery
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
    worker_prefetch_multiplier=1,  # one task at a time per worker
)
