from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.schemas import ScoreRunOut
from db.database import get_db
from db.models import ScoreRun, User

router = APIRouter(prefix="/score", tags=["score"])


@router.get("/runs", response_model=list[ScoreRunOut])
def list_score_runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ScoreRun)
        .filter(ScoreRun.user_id == user.id)
        .order_by(ScoreRun.started_at.desc())
        .limit(20)
        .all()
    )


@router.get("/runs/{run_id}", response_model=ScoreRunOut)
def get_score_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.get(ScoreRun, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(404, "Run not found")
    return run
