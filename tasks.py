import asyncio
from celery_app import celery_app
from runner import run_scrape


@celery_app.task(bind=True, name="tasks.scrape", max_retries=0)
def scrape_task(self, run_id: int, company_ids: list[int] | None):
    """Celery task that drives a full scrape run."""
    asyncio.run(run_scrape(run_id=run_id, company_ids=company_ids))
