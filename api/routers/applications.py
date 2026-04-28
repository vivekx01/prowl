from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from db.models import Application, JobListing
from api.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.created_at.desc()).all()


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    listing = db.get(JobListing, body.listing_id)
    if not listing:
        raise HTTPException(404, "Job listing not found")
    if listing.application:
        raise HTTPException(400, "Application already exists for this job")

    app = Application(
        listing_id=body.listing_id,
        status=body.status,
        notes=body.notes,
        applied_at=datetime.utcnow() if body.status == "applied" else None,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, body: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")

    updates = body.model_dump(exclude_none=True)
    if "status" in updates and updates["status"] == "applied" and not app.applied_at:
        updates.setdefault("applied_at", datetime.utcnow())

    for field, val in updates.items():
        setattr(app, field, val)
    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    db.delete(app)
    db.commit()
