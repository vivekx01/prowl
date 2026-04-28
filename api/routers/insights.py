from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Application, Company, JobListing, JobScore, ScrapeRun
from llm.insights import InsightsChat

router = APIRouter(prefix="/insights", tags=["insights"])


def _summary(db: Session) -> dict:
    total = db.query(func.count(JobListing.id)).scalar() or 0

    scores = db.query(JobScore.score, JobScore.verdict).all()
    apply_count = sum(1 for s in scores if s.verdict == "apply")
    skip_count = sum(1 for s in scores if s.verdict == "skip")

    buckets: dict[str, int] = {"1-2": 0, "3-4": 0, "5-6": 0, "7-8": 0, "9-10": 0}
    for s in scores:
        if s.score <= 2:
            buckets["1-2"] += 1
        elif s.score <= 4:
            buckets["3-4"] += 1
        elif s.score <= 6:
            buckets["5-6"] += 1
        elif s.score <= 8:
            buckets["7-8"] += 1
        else:
            buckets["9-10"] += 1

    app_rows = (
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    apps_by_status = {row[0]: row[1] for row in app_rows}

    company_listings = (
        db.query(Company.name, func.count(JobListing.id).label("cnt"))
        .join(JobListing, JobListing.company_id == Company.id)
        .group_by(Company.id)
        .order_by(func.count(JobListing.id).desc())
        .limit(20)
        .all()
    )
    company_matches = (
        db.query(Company.name, func.count(JobScore.id).label("matches"))
        .join(JobListing, JobListing.company_id == Company.id)
        .join(JobScore, JobScore.listing_id == JobListing.id)
        .filter(JobScore.verdict == "apply")
        .group_by(Company.id)
        .all()
    )
    match_map = {r.name: r.matches for r in company_matches}

    recent_runs = (
        db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(10).all()
    )

    return {
        "total_listings": total,
        "scored": len(scores),
        "apply_count": apply_count,
        "skip_count": skip_count,
        "score_distribution": buckets,
        "applications": apps_by_status,
        "top_companies": [
            {"name": c.name, "listings": c.cnt, "matches": match_map.get(c.name, 0)}
            for c in company_listings
        ],
        "recent_runs": [
            {
                "id": r.id,
                "status": r.status,
                "new_listings": r.new_listings,
                "apply_count": r.apply_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in recent_runs
        ],
    }


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    return _summary(db)


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    data = _summary(db)
    return await InsightsChat().ask(body.message, data, body.history)
