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

# CORS: the default deliberately does NOT allow arbitrary public IPs (AUDIT P1-3).
# It permits localhost/loopback and RFC-1918 private ranges for LAN dev, plus
# *.vercel.app for preview deploys. Production should set CORS_ORIGIN_REGEX to an
# explicit allow-list of its own origins.
_CORS_REGEX = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?"
    r"|https://[\w-]+\.vercel\.app",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_CORS_REGEX,
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
