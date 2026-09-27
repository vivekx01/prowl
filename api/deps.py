import hashlib

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

import config
from db.database import get_db
from db.models import ApiKey, User

_bearer = HTTPBearer()


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _user_from_jwt(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(401, "User not found")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    return _user_from_jwt(credentials.credentials, db)


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


def get_current_user_flexible(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Accepts either a per-user API key (X-API-Key) or a JWT bearer token.

    Used only on endpoints meant to be scriptable by external bots, so a
    leaked API key can't reach admin-only or account-management routes.
    """
    if x_api_key:
        key = db.query(ApiKey).filter_by(key_hash=hash_api_key(x_api_key)).first()
        if not key:
            raise HTTPException(401, "Invalid API key")
        user = db.get(User, key.user_id)
        if not user or not user.is_active:
            raise HTTPException(403, "Account disabled")
        key.last_used_at = config.now_ist()
        db.commit()
        return user

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    return _user_from_jwt(authorization.split(" ", 1)[1], db)
