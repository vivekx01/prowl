from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import ScrapeRun
from api.schemas import ScrapeRequest

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.post("/run", status_code=202)
def start_scrape(body: ScrapeRequest, db: Session = Depends(get_db)):
    from tasks import scrape_task

    # Reject if a run is already in progress
    active = db.query(ScrapeRun).filter(ScrapeRun.status.in_(["pending", "running"])).first()
    if active:
        raise HTTPException(409, f"Run #{active.id} is already in progress")

    company_ids = body.company_ids or None
    run = ScrapeRun(
        status="pending",
        company_ids=None if not company_ids else __import__("json").dumps(company_ids),
        completed_company_ids="[]",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    task = scrape_task.delay(run.id, company_ids)
    run.celery_task_id = task.id
    db.commit()

    return {"run_id": run.id, "celery_task_id": task.id}


@router.post("/stop/{run_id}", status_code=200)
def stop_scrape(run_id: int, db: Session = Depends(get_db)):
    from datetime import datetime
    from celery_app import celery_app

    run = db.get(ScrapeRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(400, "Run is not active")

    if run.celery_task_id:
        celery_app.control.revoke(run.celery_task_id, terminate=True, signal="SIGTERM")

    run.status = "cancelled"
    run.finished_at = datetime.utcnow()
    db.commit()

    return {"run_id": run_id, "status": "cancelled"}


@router.post("/resume/{run_id}", status_code=202)
def resume_scrape(run_id: int, db: Session = Depends(get_db)):
    from tasks import scrape_task
    import json

    failed_run = db.get(ScrapeRun, run_id)
    if not failed_run:
        raise HTTPException(404, "Run not found")
    if failed_run.status not in ("failed", "completed", "cancelled"):
        raise HTTPException(400, "Only failed or completed runs can be resumed")

    active = db.query(ScrapeRun).filter(ScrapeRun.status.in_(["pending", "running"])).first()
    if active:
        raise HTTPException(409, f"Run #{active.id} is already in progress")

    original_ids = json.loads(failed_run.company_ids) if failed_run.company_ids else None
    completed_ids = set(json.loads(failed_run.completed_company_ids or "[]"))

    # Pending = original set minus already completed
    if original_ids:
        pending_ids = [i for i in original_ids if i not in completed_ids]
    else:
        from db.models import Company
        all_ids = [c.id for c in db.query(Company).filter_by(active=True).all()]
        pending_ids = [i for i in all_ids if i not in completed_ids]

    if not pending_ids:
        raise HTTPException(400, "All companies already completed in this run")

    new_run = ScrapeRun(
        status="pending",
        company_ids=json.dumps(pending_ids),
        completed_company_ids="[]",
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    task = scrape_task.delay(new_run.id, pending_ids)
    new_run.celery_task_id = task.id
    db.commit()

    return {"run_id": new_run.id, "resumed_from": run_id, "pending_companies": len(pending_ids)}
