import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from passlib.context import CryptContext

from api.deps import get_admin_user
from db.database import get_db
from db.models import Profile, ScoreRun, ScoreRunLog, Setting, User

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/admin", tags=["admin"])


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    is_admin: bool
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str
    name: str = ""
    is_admin: bool = False


class UserPatch(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    name: Optional[str] = None


class ScoreTrigger(BaseModel):
    days_back: Optional[int] = None
    company_ids: Optional[list[int]] = None


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "is_admin": u.is_admin,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=_pwd.hash(body.password),
        name=body.name,
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.get("/users")
def list_users(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return [_serialize(u) for u in db.query(User).order_by(User.created_at).all()]


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    body: UserPatch,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(400, "Cannot disable your own account")
    if user.id == admin.id and body.is_admin is False:
        raise HTTPException(400, "Cannot remove your own admin role")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.name is not None:
        user.name = body.name

    db.commit()
    return _serialize(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete your own account")
    db.delete(user)
    db.commit()


# ---------------------------------------------------------------------------
# Score management
# ---------------------------------------------------------------------------

def _start_score_run(db, user_id: int, days_back: int | None, company_ids: list[int] | None = None) -> ScoreRun:
    from tasks import score_task
    run = ScoreRun(user_id=user_id, status="pending", days_back=days_back, company_ids=company_ids or None)
    db.add(run)
    db.commit()
    db.refresh(run)
    task = score_task.delay(run.id, user_id, company_ids)
    run.celery_task_id = task.id
    db.commit()
    return run


@router.post("/score/run/{user_id}")
def score_single_user(
    user_id: int,
    body: ScoreTrigger = ScoreTrigger(),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if not db.query(Profile).filter_by(user_id=user_id).first():
        raise HTTPException(400, "User has no profile")
    active = db.query(ScoreRun).filter(ScoreRun.user_id == user_id, ScoreRun.status.in_(["pending", "running"])).first()
    if active:
        raise HTTPException(409, f"Score run #{active.id} already in progress for this user")
    run = _start_score_run(db, user_id, body.days_back, body.company_ids)
    return {"user_id": user_id, "run_id": run.id}


@router.post("/score/run-all")
def score_all_users(
    body: ScoreTrigger = ScoreTrigger(),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    users_with_profile = (
        db.query(User)
        .join(Profile, Profile.user_id == User.id)
        .filter(User.is_active == True)
        .all()
    )

    started, skipped = [], []
    for user in users_with_profile:
        active = db.query(ScoreRun).filter(ScoreRun.user_id == user.id, ScoreRun.status.in_(["pending", "running"])).first()
        if active:
            skipped.append({"user_id": user.id, "email": user.email, "reason": "already running"})
            continue
        run = _start_score_run(db, user.id, body.days_back)
        started.append({"user_id": user.id, "email": user.email, "run_id": run.id})

    return {"started": started, "skipped": skipped}


@router.get("/score/runs")
def list_all_score_runs(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(ScoreRun)
        .order_by(ScoreRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [_serialize_score_run(r) for r in runs]


def _serialize_score_run(r: ScoreRun) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "user_email": r.user.email if r.user else None,
        "status": r.status,
        "days_back": r.days_back,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "companies_total": r.companies_total,
        "companies_done": r.companies_done,
        "apply_count": r.apply_count,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "cost_usd": r.cost_usd or 0.0,
        "company_ids": r.company_ids,
    }


@router.get("/score/runs/{run_id}/logs")
def get_score_run_logs(
    run_id: int,
    after_id: int = Query(0),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ScoreRunLog)
        .filter(ScoreRunLog.run_id == run_id)
        .order_by(ScoreRunLog.id)
    )
    if after_id:
        q = q.filter(ScoreRunLog.id > after_id)
    return [
        {"id": l.id, "timestamp": l.timestamp.isoformat(), "level": l.level, "message": l.message}
        for l in q.all()
    ]


@router.post("/score/runs/{run_id}/stop")
def stop_score_run(
    run_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from celery_app import celery_app

    run = db.get(ScoreRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(400, "Run is not active")

    if run.celery_task_id:
        celery_app.control.revoke(run.celery_task_id, terminate=True, signal="SIGTERM")

    from config import now_ist
    run.status = "cancelled"
    run.finished_at = now_ist()
    db.commit()
    return {"run_id": run_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def _next_scrape(cron: str) -> str | None:
    if not cron:
        return None
    try:
        from datetime import datetime
        from croniter import croniter
        from config import now_ist
        nxt: datetime = croniter(cron, now_ist()).get_next(datetime)
        return nxt.isoformat()
    except Exception:
        return None


class ScheduleOut(BaseModel):
    scrape_cron: str
    scrape_times: list[str] = []
    next_scrape_at: str | None = None


class ScheduleUpdate(BaseModel):
    scrape_cron: str = ""
    scrape_times: list[str] = []


class UserScheduleOut(BaseModel):
    score_times: list[str]
    align_with_scraping: bool = False


class UserScheduleUpdate(BaseModel):
    score_times: list[str]
    align_with_scraping: bool = False


def _validate_times(times: list[str]) -> None:
    for t in times:
        try:
            h, m = map(int, t.split(":"))
            assert 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            raise HTTPException(400, f"Invalid time '{t}' — use HH:MM (IST, 24-hour)")


def _get_times(db: Session, user_id: int | None, key: str) -> list[str]:
    row = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == key).first()
    return json.loads(row.value) if row else []


def _set_times(db: Session, user_id: int | None, key: str, times: list[str]) -> None:
    _validate_times(times)
    row = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == key).first()
    if row:
        row.value = json.dumps(times)
    else:
        db.add(Setting(user_id=user_id, key=key, value=json.dumps(times)))
    db.commit()


@router.get("/schedule", response_model=ScheduleOut)
def get_schedule(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    cron_row = db.query(Setting).filter(Setting.user_id == None, Setting.key == "scrape_schedule").first()
    value = cron_row.value if cron_row else ""
    # Migrate: old format was a JSON array e.g. "[]" or "[\"06:00\"]"
    if value.startswith("["):
        value = ""
    times_row = db.query(Setting).filter(Setting.user_id == None, Setting.key == "scrape_times").first()
    times = json.loads(times_row.value) if times_row else []
    return ScheduleOut(scrape_cron=value, scrape_times=times, next_scrape_at=_next_scrape(value))


@router.put("/schedule", response_model=ScheduleOut)
def update_schedule(
    body: ScheduleUpdate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    cron = body.scrape_cron.strip()
    if cron:
        try:
            from croniter import croniter
            if not croniter.is_valid(cron):
                raise ValueError
        except (ValueError, Exception):
            raise HTTPException(400, f"Invalid cron expression: {cron!r}")
    _validate_times(body.scrape_times)

    cron_row = db.query(Setting).filter(Setting.user_id == None, Setting.key == "scrape_schedule").first()
    if cron_row:
        cron_row.value = cron
    else:
        db.add(Setting(user_id=None, key="scrape_schedule", value=cron))

    times_row = db.query(Setting).filter(Setting.user_id == None, Setting.key == "scrape_times").first()
    times_json = json.dumps(body.scrape_times)
    if times_row:
        times_row.value = times_json
    else:
        db.add(Setting(user_id=None, key="scrape_times", value=times_json))

    db.commit()
    return ScheduleOut(scrape_cron=cron, scrape_times=body.scrape_times, next_scrape_at=_next_scrape(cron))


@router.get("/users/{user_id}/score-schedule", response_model=UserScheduleOut)
def get_user_score_schedule(
    user_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")
    align_row = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == "score_align_with_scraping").first()
    align = align_row.value == "true" if align_row else False
    return UserScheduleOut(score_times=_get_times(db, user_id, "score_schedule"), align_with_scraping=align)


@router.put("/users/{user_id}/score-schedule", response_model=UserScheduleOut)
def update_user_score_schedule(
    user_id: int,
    body: UserScheduleUpdate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")
    _set_times(db, user_id, "score_schedule", body.score_times)
    align_row = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == "score_align_with_scraping").first()
    align_val = "true" if body.align_with_scraping else "false"
    if align_row:
        align_row.value = align_val
    else:
        db.add(Setting(user_id=user_id, key="score_align_with_scraping", value=align_val))
    db.commit()
    return UserScheduleOut(score_times=body.score_times, align_with_scraping=body.align_with_scraping)
