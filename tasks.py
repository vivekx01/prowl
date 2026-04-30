import asyncio
from celery_app import celery_app
from runner import run_scrape


@celery_app.task(bind=True, name="tasks.scrape", max_retries=0)
def scrape_task(self, run_id: int, company_ids: list[int] | None):
    asyncio.run(run_scrape(run_id=run_id, company_ids=company_ids))


@celery_app.task(bind=True, name="tasks.score", max_retries=0)
def score_task(self, run_id: int, user_id: int):
    from scorer import run_score
    asyncio.run(run_score(run_id=run_id, user_id=user_id))
