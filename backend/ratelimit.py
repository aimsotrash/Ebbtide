"""Lightweight in-memory sliding-window rate limiter (AUDIT P1-2).

Honest scope: this is per-process. It protects a single-node deployment against
brute-force auth and runaway LLM spend. For a multi-instance deployment, replace
the backing store with Redis (the dependency interface stays the same).

Config:
  DORY_RATE_LIMIT_PER_MIN  requests/min/bucket/client-IP (default 60). 0 disables.
The limiter is inert when DORY_ENV=dev so local dev and the test suite are not
throttled; production (DORY_ENV != dev) gets protection by default.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)
_WINDOW_SECONDS = 60.0


def _limit() -> int:
    try:
        return int(os.getenv("DORY_RATE_LIMIT_PER_MIN", "60"))
    except ValueError:
        return 60


def _enabled() -> bool:
    if os.getenv("DORY_ENV", "dev").lower() == "dev":
        return False
    return _limit() > 0


def rate_limit(bucket: str):
    """Return a FastAPI dependency that throttles `bucket` per client IP."""

    def dependency(request: Request) -> None:
        if not _enabled():
            return
        client_ip = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client_ip}"
        now = time.monotonic()
        limit = _limit()
        with _lock:
            dq = _hits[key]
            while dq and now - dq[0] > _WINDOW_SECONDS:
                dq.popleft()
            if len(dq) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
            dq.append(now)

    return dependency
