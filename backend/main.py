import logging
import os
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Make the sibling `intelligence/` package importable. The backend consumes the
# intelligence domain layer through its public interfaces; it lives at the repo
# root next to backend/, so the repo root must be on sys.path. (For independent
# deployment, `pip install -e intelligence/` achieves the same — see ARCHITECTURE_REFACTOR.md.)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv(Path(__file__).parent / ".env")

from intelligence.embeddings import warm_model
from database.db import get_connection, init_db, purge_expired_refresh_tokens
from observability import setup_logging
from routers import ai, auth, chunks, discovery, fading, health, ingest, quiz, review, search, seed, stats
from routers.auth import setup_demo_user
from routers.deps import require_secret_configured
from services.category_service import classify_all_uncategorized

setup_logging()
logger = logging.getLogger("dory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on misconfiguration instead of 500-ing every auth request later
    # (AUDIT P1-7): in any non-dev environment a JWT secret MUST be configured.
    require_secret_configured()
    init_db()
    setup_demo_user()
    purge_expired_refresh_tokens()  # AUDIT P0-5
    if os.getenv("DORY_SKIP_WARMUP") != "1":
        warm_model()
        threading.Thread(target=classify_all_uncategorized, daemon=True).start()
    logger.info("Dory.md API started (env=%s)", os.getenv("DORY_ENV", "dev"))
    yield


app = FastAPI(title="Dory.md API", version="1.0.0", lifespan=lifespan)

# CORS (AUDIT P1-3 / P0 CORS hardening). The browser-facing allow-list is built
# explicitly — there is NO wildcard, no `*.vercel.app`, and no public-IP regex in
# any non-dev environment. Production must declare its origins.
#
# Dev-only convenience regex: localhost + RFC-1918 private LAN ranges (so you can
# hit the dev server from a phone on the same Wi-Fi). It never matches public hosts.
_DEV_CORS_REGEX = (
    r"https?://(localhost|127\.0\.0\.1|"
    r"10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?"
)


def resolve_cors_kwargs(env: str | None = None) -> dict:
    """Compute the CORS origin policy from the environment.

    Precedence (first match wins):
      1. CORS_ALLOW_ORIGINS — comma-separated list of EXACT origins (recommended
         for production, e.g. "https://app.dory.md,https://dory.vercel.app").
      2. CORS_ORIGIN_REGEX  — an explicit regex, for advanced multi-origin setups.
      3. dev with neither set — localhost + private LAN ranges only.
      4. non-dev with neither set — deny all cross-origin requests (and warn).
         We never fall back to a permissive default outside dev.
    """
    env = (env or os.getenv("DORY_ENV", "dev")).lower()
    explicit = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    regex = os.getenv("CORS_ORIGIN_REGEX", "").strip()

    if explicit:
        return {"allow_origins": [o.strip() for o in explicit.split(",") if o.strip()]}
    if regex:
        return {"allow_origin_regex": regex}
    if env == "dev":
        return {"allow_origin_regex": _DEV_CORS_REGEX}

    logger.warning(
        "CORS: neither CORS_ALLOW_ORIGINS nor CORS_ORIGIN_REGEX is set in a "
        "non-dev environment (DORY_ENV=%s). All cross-origin browser requests "
        "will be blocked. Set CORS_ALLOW_ORIGINS to your frontend origin(s).",
        env,
    )
    return {"allow_origins": []}


app.add_middleware(
    CORSMiddleware,
    **resolve_cors_kwargs(),
    # The SPA authenticates with a bearer Authorization header (not cookies), so
    # credentialed CORS is not strictly required, but we keep it on for parity
    # with the explicit allow-list. It is never paired with a wildcard origin.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Attach a request id and log timing/status for every request (AUDIT P1-1)."""
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception("request_failed id=%s %s %s after %.1fms", request_id, request.method, request.url.path, elapsed)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."}, headers={"X-Request-ID": request_id})
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info("id=%s %s %s -> %s %.1fms", request_id, request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(auth.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(fading.router, prefix="/api")
app.include_router(chunks.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(seed.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "Dory.md"}


@app.get("/livez")
def livez():
    """Liveness probe — process is up. No dependencies touched (AUDIT P1-8)."""
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    """Readiness probe — can we reach the database?"""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ready"}
    except Exception:
        logger.exception("readiness check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready"})
