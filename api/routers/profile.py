import io
from datetime import datetime

import pypdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Profile, Setting
from api.schemas import ProfileOut, ProfileUpdate, SettingOut, SettingUpdate, CheckJDRequest, CheckJDResult
from llm.resume_parser import ResumeParser

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    if profile:
        profile.content = body.content
        profile.updated_at = datetime.utcnow()
    else:
        profile = Profile(content=body.content)
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/settings", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.put("/settings/{key}", response_model=SettingOut)
def upsert_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter_by(key=key).first()
    if setting:
        setting.value = body.value
    else:
        setting = Setting(key=key, value=body.value)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.post("/score-jd", response_model=CheckJDResult)
async def score_jd(body: CheckJDRequest, db: Session = Depends(get_db)):
    from llm.filter import JobFilter
    from scrapers.base import JobListing as ScraperListing

    profile = db.query(Profile).first()
    if not profile:
        raise HTTPException(404, "No profile found — add one in the Profile page first")

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
    return result


@router.post("/profile/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
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
