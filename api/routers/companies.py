from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import get_admin_user, get_current_user
from db.database import get_db
from db.models import Company, JobListing, User
from api.schemas import CompanyCreate, CompanyOut, CompanyUpdate, BulkImportRequest, BulkImportResult

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/platforms")
def list_platforms(_: User = Depends(get_current_user)):
    from scrapers import REGISTRY
    return list(REGISTRY.keys())


@router.get("", response_model=list[CompanyOut])
def list_companies(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    counts = dict(
        db.query(JobListing.company_id, func.count(JobListing.id))
        .group_by(JobListing.company_id)
        .all()
    )
    companies = db.query(Company).order_by(Company.name).all()
    result = []
    for c in companies:
        d = CompanyOut.model_validate(c).model_dump()
        d["listing_count"] = counts.get(c.id, 0)
        result.append(d)
    return result


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(
    body: CompanyCreate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if db.query(Company).filter_by(name=body.name).first():
        raise HTTPException(400, f"Company '{body.name}' already exists")
    company = Company(**body.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.post("/bulk", response_model=BulkImportResult)
def bulk_import(
    body: BulkImportRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    imported, skipped, errors = 0, 0, []
    for item in body.companies:
        try:
            if db.query(Company).filter_by(name=item.name).first():
                skipped += 1
                continue
            db.add(Company(**item.model_dump()))
            imported += 1
        except Exception as e:
            errors.append(f"{item.name}: {e}")
    db.commit()
    return BulkImportResult(imported=imported, skipped=skipped, errors=errors)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    body: CompanyUpdate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(company, field, val)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    db.delete(company)
    db.commit()
