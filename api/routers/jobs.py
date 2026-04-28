from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from db.models import JobListing, JobScore
from api.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize(listing: JobListing) -> dict:
    return {
        **{c.name: getattr(listing, c.name) for c in listing.__table__.columns},
        "company_name": listing.company.name,
        "score": listing.score,
        "application": listing.application,
    }


@router.get("", response_model=list[JobOut])
def list_jobs(
    verdict: Optional[str] = Query(None, description="apply | skip"),
    company_id: Optional[int] = Query(None),
    score_min: Optional[float] = Query(None),
    unscored: bool = Query(False, description="Return listings with no score yet"),
    db: Session = Depends(get_db),
):
    q = (
        db.query(JobListing)
        .options(
            joinedload(JobListing.company),
            joinedload(JobListing.score),
            joinedload(JobListing.application),
        )
        .order_by(JobListing.first_seen_at.desc())
    )

    if company_id:
        q = q.filter(JobListing.company_id == company_id)

    if unscored:
        q = q.filter(~JobListing.score.has())
    elif verdict:
        q = q.join(JobScore).filter(JobScore.verdict == verdict)
        if score_min is not None:
            q = q.filter(JobScore.score >= score_min)

    listings = q.all()
    return [_serialize(l) for l in listings]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    listing = (
        db.query(JobListing)
        .options(
            joinedload(JobListing.company),
            joinedload(JobListing.score),
            joinedload(JobListing.application),
        )
        .filter(JobListing.id == job_id)
        .first()
    )
    if not listing:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return _serialize(listing)
