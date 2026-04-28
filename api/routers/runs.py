from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from db.models import ScrapeRun, ScrapeRunLog

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
def list_runs(limit: int = Query(20), db: Session = Depends(get_db)):
    runs = (
        db.query(ScrapeRun)
        .order_by(ScrapeRun.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_run(r) for r in runs]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(ScrapeRun, run_id)
    if not run:
        from fastapi import HTTPException
        raise HTTPException(404, "Run not found")
    return _serialize_run(run)


@router.get("/{run_id}/logs")
def get_run_logs(
    run_id: int,
    after_id: int = Query(0, description="Return only logs with id > after_id"),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ScrapeRunLog)
        .filter(ScrapeRunLog.run_id == run_id)
        .order_by(ScrapeRunLog.id)
    )
    if after_id:
        q = q.filter(ScrapeRunLog.id > after_id)
    logs = q.all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "level": l.level,
            "message": l.message,
        }
        for l in logs
    ]


def _serialize_run(run: ScrapeRun) -> dict:
    import json
    return {
        "id": run.id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "company_ids": json.loads(run.company_ids) if run.company_ids else None,
        "completed_company_ids": json.loads(run.completed_company_ids or "[]"),
        "companies_total": run.companies_total,
        "companies_done": run.companies_done,
        "new_listings": run.new_listings,
        "apply_count": run.apply_count,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "celery_task_id": run.celery_task_id,
    }
