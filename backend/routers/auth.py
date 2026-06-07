import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt, JWTError
from pydantic import BaseModel, field_validator

from ratelimit import rate_limit

# Pragmatic email shape check — avoids pulling in the `email-validator` dependency
# while still rejecting obviously-malformed addresses (AUDIT P1 validation gap).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from database.db import (
    DEFAULT_USER_ID,
    create_user,
    get_active_refresh_token,
    get_user_by_email,
    get_user_by_id,
    purge_expired_refresh_tokens,
    revoke_refresh_token,
    set_user_password_hash,
    store_refresh_token,
)
from routers.deps import JWT_ALGORITHM, _get_secret, get_current_user_id

router = APIRouter()

_DEMO_PASSWORD = "demo123"
ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _encode(claims: dict, ttl: timedelta) -> str:
    return jwt.encode(
        {**claims, "exp": datetime.now(timezone.utc) + ttl},
        _get_secret(),
        algorithm=JWT_ALGORITHM,
    )


def _issue_tokens(user_id: str, email: str, name: str) -> dict:
    # jti makes every JWT unique even when issued in the same second for the same user,
    # so two refresh tokens never collide on their SHA-256 hash in storage.
    access = _encode(
        {"sub": user_id, "email": email, "name": name, "typ": "access", "jti": uuid.uuid4().hex},
        ACCESS_TOKEN_TTL,
    )
    refresh = _encode(
        {"sub": user_id, "typ": "refresh", "jti": uuid.uuid4().hex},
        REFRESH_TOKEN_TTL,
    )
    store_refresh_token(_hash_token(refresh), user_id, datetime.now(timezone.utc) + REFRESH_TOKEN_TTL)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "name": name,
        "email": email,
    }


def setup_demo_user() -> None:
    """Dev-only: give the demo account a usable bcrypt hash + display name.

    In any non-dev environment this is a no-op, so there are NO shared demo
    credentials in production (P0 demo-account security). The demo row itself is
    only created in dev (see database.db.init_db)."""
    if os.getenv("DORY_ENV", "dev").lower() != "dev":
        return
    from database.db import get_connection
    conn = get_connection()
    conn.execute(
        "UPDATE users SET name = 'Demo User' WHERE id = ? AND (name IS NULL OR name = '')",
        (DEFAULT_USER_ID,),
    )
    conn.commit()
    conn.close()

    user = get_user_by_email("demo@dory.md")
    if user and not user["password_hash"]:
        set_user_password_hash(DEFAULT_USER_ID, _hash_password(_DEMO_PASSWORD))


class RegisterBody(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v


class LoginBody(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/auth/register", dependencies=[Depends(rate_limit("auth"))])
def register(body: RegisterBody):
    if len(body.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="An account with that email already exists.")
    name = body.name.strip()
    user_id = create_user(body.email, name, _hash_password(body.password))
    return _issue_tokens(user_id, body.email, name)


@router.post("/auth/login", dependencies=[Depends(rate_limit("auth"))])
def login(body: LoginBody):
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    pwd_hash = user["password_hash"]
    if not pwd_hash or not _verify_password(body.password, pwd_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _issue_tokens(user["id"], user["email"], user["name"] or "")


@router.post("/auth/refresh")
def refresh(body: RefreshBody):
    """Exchange a refresh token for a new access + refresh pair. Old refresh is revoked (rotation)."""
    try:
        payload = jwt.decode(body.refresh_token, _get_secret(), algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Wrong token type.")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token payload.")

    token_hash = _hash_token(body.refresh_token)
    if not get_active_refresh_token(token_hash):
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired.")
    revoke_refresh_token(token_hash)
    # Opportunistic cleanup so the refresh_tokens table doesn't grow forever
    # (AUDIT P0-5). Cheap, runs on the natural refresh cadence.
    purge_expired_refresh_tokens()

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return _issue_tokens(user["id"], user["email"], user["name"] or "")


@router.post("/auth/logout")
def logout(body: RefreshBody, user_id: str = Depends(get_current_user_id)):
    """Revoke the refresh token. Access token will still work until it expires (max 1h)."""
    revoke_refresh_token(_hash_token(body.refresh_token))
    return {"ok": True}
