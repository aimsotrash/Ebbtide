from fastapi import APIRouter, Depends, Query

from intelligence.memory import calculate_retention, classify_retention
from database.db import get_all_chunks
from models.schemas import ChunkOut, FadingResponse
from routers._shared import parse_dt, time_ago
from routers.deps import get_current_user_id

router = APIRouter()


@router.get("/fading", response_model=FadingResponse)
def get_fading(
    limit: int = Query(default=20, ge=1, le=2000),
    user_id: str = Depends(get_current_user_id),
):
    rows = get_all_chunks(user_id)
    results: list[ChunkOut] = []

    for row in rows:
        last_accessed = parse_dt(row["last_accessed"])
        r = calculate_retention(last_accessed, row["access_count"], row["complexity_score"])
        if r < 0.8:
            results.append(
                ChunkOut(
                    chunk_id=row["id"],
                    content=row["content"][:300],
                    source_file=row["source_file"],
                    category=row["category"],
                    retention=round(r, 4),
                    status=classify_retention(r),
                    last_accessed=time_ago(last_accessed),
                    last_accessed_iso=last_accessed.isoformat(),
                    access_count=row["access_count"],
                )
            )

    results.sort(key=lambda x: x.retention)
    return FadingResponse(chunks=results[:limit], total_fading=len(results))
