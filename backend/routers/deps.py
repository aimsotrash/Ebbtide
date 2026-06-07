import logging
import os
import secrets

from fastapi import Header, HTTPException
from jose import jwt, JWTError

logger = logging.getLogger("dory.auth")

JWT_ALGORITHM = "HS256"

# Per-process ephemeral secret used ONLY in development when no JWT_SECRET is
# configured. Generated once and cached for the lifetime of the process so that
# tokens issued and verified within the same run agree. A restart rotates it
# (dev tokens do not survive a restart) — which is exactly what we want: there
# is no hardcoded secret that could leak into a real deployment.
_DEV_EPHEMERAL_SECRET: str | None = None


def _is_dev() -> bool:
    return os.getenv("DORY_ENV", "dev").lower() == "dev"


def _missing_secret_error() -> RuntimeError:
    return RuntimeError(
        "JWT_SECRET is required when DORY_ENV != 'dev'. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )


def _get_secret() -> str:
    """Return the signing secret.

    Order of resolution:
      1. JWT_SECRET (used in every environment when set).
      2. dev only: a randomly generated, per-process ephemeral secret.
      3. otherwise: hard error (no hardcoded fallback ever ships to prod).
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    if not _is_dev():
        raise _missing_secret_error()

    global _DEV_EPHEMERAL_SECRET
    if _DEV_EPHEMERAL_SECRET is None:
        _DEV_EPHEMERAL_SECRET = secrets.token_urlsafe(48)
        logger.warning(
            "DORY_ENV=dev and JWT_SECRET is unset — using a randomly generated "
            "ephemeral secret. Tokens will not survive a server restart. NEVER "
            "run a non-dev environment without a real JWT_SECRET."
        )
    return _DEV_EPHEMERAL_SECRET


def require_secret_configured() -> None:
    """Startup guard (AUDIT P1-7). Raises if running outside dev without a
    JWT_SECRET, so a misconfigured deploy fails to boot rather than silently
    500-ing every authenticated request — or, worse, signing tokens with a
    predictable fallback."""
    if not _is_dev() and not os.getenv("JWT_SECRET", "").strip():
        raise _missing_secret_error()


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
