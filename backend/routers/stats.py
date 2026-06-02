import numpy as np
from fastapi import APIRouter, Depends

from intelligence.memory import calculate_retention
from database.db import get_all_chunks
from models.schemas import StatsResponse
from routers._shared import parse_dt
from routers.deps import get_current_user_id

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats(user_id: str = Depends(get_current_user_id)):
    rows = get_all_chunks(user_id)
    if not rows:
        return StatsResponse(total_chunks=0, avg_retention=1.0, strong=0, fading=0, weak=0, critical=0)

    retentions = [
        calculate_retention(parse_dt(r["last_accessed"]), r["access_count"], r["complexity_score"])
        for r in rows
    ]
    counts = {"strong": 0, "fading": 0, "weak": 0, "critical": 0}
    for r in retentions:
        if r >= 0.8:
            counts["strong"] += 1
        elif r >= 0.5:
            counts["fading"] += 1
        elif r >= 0.2:
            counts["weak"] += 1
        else:
            counts["critical"] += 1

    return StatsResponse(
        total_chunks=len(rows),
        avg_retention=round(float(np.mean(retentions)), 4),
        **counts,
    )
