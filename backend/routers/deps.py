import os

from fastapi import Header, HTTPException
from jose import jwt, JWTError


def _get_secret() -> str:
    """Return JWT_SECRET. In dev (DORY_ENV=dev), fall back to a development default.
    In any other environment, JWT_SECRET must be set or the request fails 500."""
    env = os.getenv("DORY_ENV", "dev").lower()
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        if env != "dev":
            raise RuntimeError(
                "JWT_SECRET is required when DORY_ENV != 'dev'. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return "dory-dev-only-secret-do-not-deploy"
    return secret


JWT_ALGORITHM = "HS256"


def require_secret_configured() -> None:
    """Startup guard (AUDIT P1-7). Raises if running outside dev without a
    JWT_SECRET, so a misconfigured deploy fails to boot rather than silently
    500-ing every authenticated request."""
    env = os.getenv("DORY_ENV", "dev").lower()
    if env != "dev" and not os.getenv("JWT_SECRET"):
        raise RuntimeError(
            "JWT_SECRET is required when DORY_ENV != 'dev'. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )


def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("typ") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type.")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
