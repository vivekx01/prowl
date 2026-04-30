from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from api.deps import get_current_user
from db.database import get_db
from db.models import JobListing, JobScore, Application, User
from api.schemas import JobOut

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


@router.get("", response_model=list[JobOut])
def list_jobs(
    verdict: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    score_min: Optional[float] = Query(None),
    unscored: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(JobListing)
        .options(
            joinedload(JobListing.company),
            joinedload(JobListing.scores),
            joinedload(JobListing.applications),
        )
        .order_by(JobListing.first_seen_at.desc())
    )

    if company_id:
        q = q.filter(JobListing.company_id == company_id)

    if unscored:
        # No score row for this user
        scored_ids = db.query(JobScore.listing_id).filter(JobScore.user_id == user.id)
        q = q.filter(~JobListing.id.in_(scored_ids))
    elif verdict:
        q = (
            q.join(JobScore, (JobScore.listing_id == JobListing.id) & (JobScore.user_id == user.id))
            .filter(JobScore.verdict == verdict)
        )
        if score_min is not None:
            q = q.filter(JobScore.score >= score_min)

    listings = q.all()
    return [_serialize(l, user.id) for l in listings]


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
            joinedload(JobListing.scores),
            joinedload(JobListing.applications),
        )
        .filter(JobListing.id == job_id)
        .first()
    )
    if not listing:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return _serialize(listing, user.id)
