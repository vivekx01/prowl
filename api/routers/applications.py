from config import now_ist

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from api.deps import get_current_user
from db.database import get_db
from db.models import Application, JobListing, User
from api.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(
    body: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = db.get(JobListing, body.listing_id)
    if not listing:
        raise HTTPException(404, "Job listing not found")

    existing = (
        db.query(Application)
        .filter_by(listing_id=body.listing_id, user_id=user.id)
        .first()
    )
    if existing:
        raise HTTPException(400, "Application already exists for this job")

    app = Application(
        listing_id=body.listing_id,
        user_id=user.id,
        status=body.status,
        notes=body.notes,
        applied_at=now_ist() if body.status == "applied" else None,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(
    app_id: int,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.get(Application, app_id)
    if not app or app.user_id != user.id:
        raise HTTPException(404, "Application not found")

    updates = body.model_dump(exclude_none=True)
    if "status" in updates and updates["status"] == "applied" and not app.applied_at:
        updates.setdefault("applied_at", now_ist())

    for field, val in updates.items():
        setattr(app, field, val)
    app.updated_at = now_ist()
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(
    app_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.get(Application, app_id)
    if not app or app.user_id != user.id:
        raise HTTPException(404, "Application not found")
    db.delete(app)
    db.commit()
