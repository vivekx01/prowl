from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from api.deps import get_current_user
from db.database import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _make_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=30)}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def _user_dict(user: User, token: str) -> dict:
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
    }


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    user_count = db.query(User).count()
    if user_count > 0:
        raise HTTPException(403, "Registration is closed")
    user = User(
        email=body.email.lower(),
        password_hash=_pwd.hash(body.password),
        name=body.name,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_dict(user, _make_token(user.id))


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower()).first()
    if not user or not _pwd.verify(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    return _user_dict(user, _make_token(user.id))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
    }
