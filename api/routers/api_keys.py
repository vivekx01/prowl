import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import now_ist
from api.deps import get_current_user, hash_api_key
from db.database import get_db
from db.models import ApiKey, User

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyGenerateRequest(BaseModel):
    label: str = ""


@router.get("")
def list_api_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keys = (
        db.query(ApiKey)
        .filter_by(user_id=user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        {
            "id": k.id,
            "label": k.label,
            "key_prefix": k.key_prefix,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at,
        }
        for k in keys
    ]


@router.post("/generate")
def generate_api_key(
    body: ApiKeyGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_key = f"prowl_{secrets.token_urlsafe(32)}"
    key = ApiKey(
        user_id=user.id,
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:12],
        label=body.label.strip(),
        created_at=now_ist(),
    )
    db.add(key)
    db.commit()
    return {
        "id": key.id,
        "api_key": raw_key,
        "key_prefix": key.key_prefix,
        "label": key.label,
        "created_at": key.created_at,
    }


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = db.get(ApiKey, key_id)
    if not key or key.user_id != user.id:
        raise HTTPException(404, "API key not found")
    db.delete(key)
    db.commit()
