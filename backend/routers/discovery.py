"""GET /api/discovery — surface the single most at-risk chunk as a notification.

Picks the non-critical chunk with the lowest retention (highest decay urgency).
Returns {has_discovery: false} when nothing warrants a notification.
"""

from fastapi import APIRouter, Depends

from intelligence.memory import calculate_retention
from database.db import get_all_chunks
from routers._shared import parse_dt, to_chunk_full
from routers.deps import get_current_user_id

router = APIRouter()

_REASONS = [
    "This memory is slipping away — time to review.",
    "You haven't visited this in a while.",
    "This chunk is fading fast from your knowledge graph.",
    "Ebbinghaus says you're about to forget this.",
    "Rediscover this before it's gone.",
]


@router.get("/discovery")
def get_discovery(user_id: str = Depends(get_current_user_id)):
    rows = get_all_chunks(user_id)
    if not rows:
        return {"has_discovery": False}

    best_row = None
    best_retention = 1.0

    for row in rows:
        row = dict(row)
        last_accessed = parse_dt(row["last_accessed"])
        r = calculate_retention(last_accessed, row["access_count"], row["complexity_score"])
        if 0.1 <= r <= 0.65 and r < best_retention:
            best_retention = r
            best_row = row

    if best_row is None:
        return {"has_discovery": False}

    reason = _REASONS[hash(best_row["id"]) % len(_REASONS)]
    return {
        "has_discovery": True,
        "chunk": to_chunk_full(best_row, best_retention),
        "reason": reason,
    }
