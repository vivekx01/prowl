import io

from config import now_ist

import pypdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.database import get_db
from db.models import Profile, Setting, User
from api.schemas import ProfileOut, ProfileUpdate, SettingOut, SettingUpdate, CheckJDRequest, CheckJDResult
from llm.resume_parser import ResumeParser

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.put("/profile", response_model=ProfileOut)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter_by(user_id=user.id).first()
    if profile:
        profile.content = body.content
        profile.updated_at = now_ist()
    else:
        profile = Profile(content=body.content, user_id=user.id)
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/settings", response_model=list[SettingOut])
def list_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # User-level settings fall back to global defaults
    user_keys = {s.key for s in db.query(Setting).filter_by(user_id=user.id).all()}
    user_settings = db.query(Setting).filter_by(user_id=user.id).all()
    global_defaults = [
        s for s in db.query(Setting).filter_by(user_id=None).all()
        if s.key not in user_keys
    ]
    return user_settings + global_defaults


@router.put("/settings/{key}", response_model=SettingOut)
def upsert_setting(
    key: str,
    body: SettingUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    setting = db.query(Setting).filter_by(key=key, user_id=user.id).first()
    if setting:
        setting.value = body.value
    else:
        setting = Setting(key=key, value=body.value, user_id=user.id)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.post("/score-jd", response_model=CheckJDResult)
async def score_jd(
    body: CheckJDRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from llm.filter import JobFilter
    from scrapers.base import JobListing as ScraperListing

    profile = db.query(Profile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(400, "No profile found — add one in the Profile page first")

    listing = ScraperListing(
        company=body.company or "Unknown",
        title=body.title or "Job",
        job_id="manual",
        location="",
        posted_on="",
        url="",
        description=body.description,
    )
    job_filter = JobFilter(profile.content)
    result = await job_filter.stage2_score(listing)
    if result is None:
        raise HTTPException(502, "LLM returned unparseable response — try again")
    return result


@router.post("/profile/parse-resume")
async def parse_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    contents = await file.read()
    try:
        reader = pypdf.PdfReader(io.BytesIO(contents))
        text = "\n\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")

    if not text:
        raise HTTPException(422, "No text found in PDF — it may be a scanned image")

    profile_text = await ResumeParser().generate_profile(text)
    return {"profile": profile_text}
