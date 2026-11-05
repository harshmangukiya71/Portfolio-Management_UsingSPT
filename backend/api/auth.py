"""
Auth API — JWT-based register / login / me using PostgreSQL.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.database.models import Token, TokenData, UserCreate, UserOut
from backend.database.pg_models import User
from backend.database.postgres import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("JWT_SECRET", "changeme-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
disable_auth = os.getenv("DISABLE_AUTH", "false").lower() in {"1", "true", "yes"}
DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@portfolio.testmail.com")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=EXPIRE_MIN)
    )
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _get_or_create_demo_user() -> UserOut:
    """Return a stable local demo user in PostgreSQL while auth is disabled."""
    with get_db_session() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(
                email=DEMO_EMAIL,
                password_hash="auth-disabled",
                role="user",
                created_at=datetime.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return UserOut(
            id=str(user.id),
            email=user.email,
            created_at=user.created_at,
        )


async def get_current_user(token: Optional[str] = Depends(oauth2)) -> UserOut:
    """FastAPI dependency — resolves JWT → user from PostgreSQL."""
    if disable_auth:
        return _get_or_create_demo_user()

    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_exc

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise cred_exc
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise cred_exc

    with get_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise cred_exc

        return UserOut(
            id=str(user.id),
            email=user.email,
            created_at=user.created_at,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    """Create a new user account in PostgreSQL."""
    with get_db_session() as db:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user = User(
            email=payload.email,
            password_hash=_hash_password(payload.password),
            role="user",
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = _create_token({"sub": str(user.id)})
        logger.info("User registered: %s (id=%d)", payload.email, user.id)
        return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Authenticate against PostgreSQL and return JWT."""
    with get_db_session() as db:
        user = db.query(User).filter(User.email == form.username).first()
        if not user or not _verify_password(form.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        token = _create_token({"sub": str(user.id)})
        logger.info("User login: %s (id=%d)", form.username, user.id)
        return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: UserOut = Depends(get_current_user)):
    """Return current user info."""
    return user
