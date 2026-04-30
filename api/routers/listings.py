from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.database import get_db
from db.models import JobListing, User

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("")
def list_listings(
    company_id: Optional[int] = Query(None),
    days_back: int = Query(7, ge=0, le=365),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(JobListing)

    if company_id is not None:
        q = q.filter(JobListing.company_id == company_id)

    if days_back > 0:
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        q = q.filter(JobListing.first_seen_at >= cutoff)

    total = q.count()
    items = q.order_by(JobListing.first_seen_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "company_id": l.company_id,
                "company_name": l.company.name,
                "title": l.title,
                "location": l.location,
                "posted_on": l.posted_on,
                "posted_date": l.posted_date,
                "url": l.url,
                "department": l.department,
                "first_seen_at": l.first_seen_at,
            }
            for l in items
        ],
    }
