from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user
from db.database import get_db
from db.models import Company, JobListing, JobScore, Application, User
from api.schemas import JobOut, JobsPageOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize(listing: JobListing, user_id: int) -> dict:
    user_score = next((s for s in listing.scores if s.user_id == user_id), None)
    user_app = next((a for a in listing.applications if a.user_id == user_id), None)
    return {
        **{c.name: getattr(listing, c.name) for c in listing.__table__.columns},
        "company_name": listing.company.name,
        "score": user_score,
        "application": user_app,
    }


@router.get("", response_model=JobsPageOut)
def list_jobs(
    verdict: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    score_min: Optional[float] = Query(None),
    unscored: bool = Query(False),
    has_application: bool = Query(False),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(JobListing)
        .order_by(JobListing.first_seen_at.desc())
    )

    if has_application:
        q = q.join(
            Application,
            (Application.listing_id == JobListing.id) & (Application.user_id == user.id),
        )

    if company_id:
        q = q.filter(JobListing.company_id == company_id)

    if search:
        term = f"%{search.strip()}%"
        matching_company_ids = db.query(Company.id).filter(Company.name.ilike(term))
        q = q.filter(
            or_(JobListing.title.ilike(term), JobListing.company_id.in_(matching_company_ids))
        )

    if unscored:
        scored_ids = db.query(JobScore.listing_id).filter(JobScore.user_id == user.id)
        q = q.filter(~JobListing.id.in_(scored_ids))
    elif verdict:
        q = (
            q.join(JobScore, (JobScore.listing_id == JobListing.id) & (JobScore.user_id == user.id))
            .filter(JobScore.verdict == verdict)
        )
        if score_min is not None:
            q = q.filter(JobScore.score >= score_min)

    total = q.count()
    listings = (
        q.options(
            joinedload(JobListing.company),
            selectinload(JobListing.scores),
            selectinload(JobListing.applications),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [_serialize(l, user.id) for l in listings]}


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = (
        db.query(JobListing)
        .options(
            joinedload(JobListing.company),
            selectinload(JobListing.scores),
            selectinload(JobListing.applications),
        )
        .filter(JobListing.id == job_id)
        .first()
    )
    if not listing:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return _serialize(listing, user.id)
