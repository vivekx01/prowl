from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from api.deps import get_current_user
from db.database import get_db
from db.models import (
    Application, AnswerMemory, Company, JobListing, JobScore, LearnedFlow,
    LearnedStep, Profile, PounceRun, PounceRunLog, User,
)

router = APIRouter(prefix="/pounce", tags=["pounce"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class JobOut(BaseModel):
    application_id: int
    listing_id: int
    title: str
    company: str
    url: str
    description: str | None
    score: float | None

    class Config:
        from_attributes = True


class ListingOut(BaseModel):
    listing_id: int
    title: str
    company: str
    url: str
    description: str | None
    location: str | None
    posted_on: str | None
    score: float | None
    verdict: str | None
    saved: bool   # whether user has already saved/applied

    class Config:
        from_attributes = True


class ProfileOut(BaseModel):
    content: str
    updated_at: datetime | None


class AnswerMemoryOut(BaseModel):
    id: int
    question_text: str
    normalized_key: str
    answer: str
    field_type: str | None
    options: list
    source: str
    confidence: float
    company_domain: str | None
    portal_key: str | None
    use_count: int
    last_used: datetime | None

    class Config:
        from_attributes = True


class LearnedStepOut(BaseModel):
    id: int
    step_order: int
    step_name: str
    page_indicator: str | None
    tool_calls: list
    next_button: str | None

    class Config:
        from_attributes = True


class LearnedFlowOut(BaseModel):
    id: int
    company_domain: str
    portal_key: str | None
    success_count: int
    last_success: datetime | None
    steps: list[LearnedStepOut]

    class Config:
        from_attributes = True


class AnswerMemoryUpsert(BaseModel):
    question_text: str
    normalized_key: str
    answer: str
    field_type: str | None = None
    options: list = []
    source: str = "llm"
    confidence: float = 0.7
    company_domain: str | None = None
    portal_key: str | None = None


class LearnedStepIn(BaseModel):
    step_order: int
    step_name: str
    page_indicator: str | None = None
    tool_calls: list = []
    next_button: str | None = None


class LearnedFlowUpsert(BaseModel):
    company_domain: str
    portal_key: str | None = None
    steps: list[LearnedStepIn] = []


class PounceRunCreate(BaseModel):
    listing_id: int | None = None
    status: str = "pending"
    dry_run: bool = False
    agent_turns: int = 0
    step_results: list = []
    error_message: str | None = None


class PounceRunOut(BaseModel):
    id: int
    listing_id: int | None
    status: str
    dry_run: bool
    started_at: datetime
    finished_at: datetime | None
    agent_turns: int
    step_results: list
    error_message: str | None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=list[JobOut])
def get_jobs(
    min_score: float = 0.5,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return saved applications whose job score meets the threshold, ready to apply."""
    rows = (
        db.query(Application, JobListing, JobScore)
        .join(JobListing, Application.listing_id == JobListing.id)
        .outerjoin(
            JobScore,
            (JobScore.listing_id == JobListing.id) & (JobScore.user_id == user.id),
        )
        .filter(Application.user_id == user.id)
        .filter(Application.status == "saved")
        .filter((JobScore.score >= min_score) | (JobScore.score.is_(None)))
        .order_by(JobScore.score.desc().nullslast())
        .all()
    )

    result = []
    for app, listing, score in rows:
        result.append(JobOut(
            application_id=app.id,
            listing_id=listing.id,
            title=listing.title,
            company=listing.company.name if listing.company else "",
            url=listing.url,
            description=listing.description,
            score=score.score if score else None,
        ))
    return result


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(404, "No profile found — add one in The Prowl first")
    return ProfileOut(content=profile.content, updated_at=profile.updated_at)


@router.get("/listings", response_model=list[ListingOut])
def get_listings(
    search: str | None = Query(default=None, description="Search in title or company name"),
    company: str | None = Query(default=None, description="Filter by company name (partial match)"),
    min_score: float = Query(default=0.0, description="Minimum score (0 = show all)"),
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return scraped job listings with optional search/filter — regardless of save status."""
    q = (
        db.query(JobListing, JobScore, Application)
        .outerjoin(
            JobScore,
            (JobScore.listing_id == JobListing.id) & (JobScore.user_id == user.id),
        )
        .outerjoin(
            Application,
            (Application.listing_id == JobListing.id) & (Application.user_id == user.id),
        )
        .join(JobListing.company)
    )

    if search:
        term = f"%{search}%"
        q = q.filter(
            JobListing.title.ilike(term) | Company.name.ilike(term)
        )
    if company:
        q = q.filter(Company.name.ilike(f"%{company}%"))
    if min_score > 0:
        q = q.filter(JobScore.score >= min_score)

    q = q.order_by(JobScore.score.desc().nullslast(), JobListing.first_seen_at.desc())
    rows = q.limit(limit).all()

    result = []
    for listing, score, app in rows:
        result.append(ListingOut(
            listing_id=listing.id,
            title=listing.title,
            company=listing.company.name,
            url=listing.url,
            description=listing.description,
            location=listing.location,
            posted_on=listing.posted_on,
            score=score.score if score else None,
            verdict=score.verdict if score else None,
            saved=app is not None,
        ))
    return result


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single listing by ID — used by Pounce client before applying."""
    listing = db.get(JobListing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    score = (
        db.query(JobScore)
        .filter_by(listing_id=listing_id, user_id=user.id)
        .first()
    )
    app = (
        db.query(Application)
        .filter_by(listing_id=listing_id, user_id=user.id)
        .first()
    )
    return ListingOut(
        listing_id=listing.id,
        title=listing.title,
        company=listing.company.name if listing.company else "",
        url=listing.url,
        description=listing.description,
        location=listing.location,
        posted_on=listing.posted_on,
        score=score.score if score else None,
        verdict=score.verdict if score else None,
        saved=app is not None,
    )


@router.post("/listings/{listing_id}/apply-record", status_code=201)
def ensure_application(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update an application record to status='applied'. Used by Pounce after a direct listing apply."""
    listing = db.get(JobListing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    app = db.query(Application).filter_by(listing_id=listing_id, user_id=user.id).first()
    if app:
        app.status = "applied"
        app.applied_at = datetime.utcnow()
    else:
        app = Application(
            listing_id=listing_id,
            user_id=user.id,
            status="applied",
            applied_at=datetime.utcnow(),
            notes="Applied via Pounce",
        )
        db.add(app)
    db.commit()
    db.refresh(app)
    return {"application_id": app.id, "status": app.status}


@router.get("/memory", response_model=list[AnswerMemoryOut])
def get_memory(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(AnswerMemory).filter_by(user_id=user.id).all()


@router.get("/flows", response_model=list[LearnedFlowOut])
def get_flows(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(LearnedFlow)
        .options(joinedload(LearnedFlow.steps))
        .filter_by(user_id=user.id)
        .all()
    )


@router.post("/memory", status_code=200)
def upsert_memory(
    body: list[AnswerMemoryUpsert],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upsert answer memory entries pushed from the Pounce client after a run."""
    updated = 0
    for item in body:
        existing = (
            db.query(AnswerMemory)
            .filter_by(
                user_id=user.id,
                normalized_key=item.normalized_key,
                company_domain=item.company_domain,
                portal_key=item.portal_key,
            )
            .first()
        )
        if existing:
            existing.answer = item.answer
            existing.confidence = item.confidence
            existing.source = item.source
            existing.use_count += 1
            existing.last_used = datetime.utcnow()
        else:
            db.add(AnswerMemory(
                user_id=user.id,
                question_text=item.question_text,
                normalized_key=item.normalized_key,
                answer=item.answer,
                field_type=item.field_type,
                options=item.options,
                source=item.source,
                confidence=item.confidence,
                company_domain=item.company_domain,
                portal_key=item.portal_key,
            ))
        updated += 1
    db.commit()
    return {"upserted": updated}


@router.post("/flows", status_code=200)
def upsert_flows(
    body: list[LearnedFlowUpsert],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upsert learned flow scripts pushed from the Pounce client after a run."""
    updated = 0
    for item in body:
        flow = (
            db.query(LearnedFlow)
            .filter_by(user_id=user.id, company_domain=item.company_domain)
            .first()
        )
        if flow:
            flow.portal_key = item.portal_key
            flow.success_count += 1
            flow.last_success = datetime.utcnow()
            # Replace all steps
            for step in flow.steps:
                db.delete(step)
            db.flush()
        else:
            flow = LearnedFlow(
                user_id=user.id,
                company_domain=item.company_domain,
                portal_key=item.portal_key,
                success_count=1,
                last_success=datetime.utcnow(),
            )
            db.add(flow)
            db.flush()

        for s in item.steps:
            db.add(LearnedStep(
                flow_id=flow.id,
                step_order=s.step_order,
                step_name=s.step_name,
                page_indicator=s.page_indicator,
                tool_calls=s.tool_calls,
                next_button=s.next_button,
            ))
        updated += 1
    db.commit()
    return {"upserted": updated}


@router.post("/runs", response_model=PounceRunOut, status_code=201)
def create_run(
    body: PounceRunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = PounceRun(
        user_id=user.id,
        listing_id=body.listing_id,
        status=body.status,
        dry_run=body.dry_run,
        agent_turns=body.agent_turns,
        step_results=body.step_results,
        error_message=body.error_message,
        finished_at=datetime.utcnow() if body.status in ("completed", "failed", "dry_run_completed") else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.patch("/runs/{run_id}", response_model=PounceRunOut)
def update_run(
    run_id: int,
    body: PounceRunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.get(PounceRun, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(404, "Run not found")

    updates = body.model_dump(exclude_none=True)
    for field, val in updates.items():
        setattr(run, field, val)
    if body.status in ("completed", "failed", "dry_run_completed") and not run.finished_at:
        run.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run
