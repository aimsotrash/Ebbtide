from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

import numpy as np

from intelligence.memory import calculate_retention_batch, classify_retention
from database.db import get_all_chunks
from models.schemas import CategoryHealth, HealthResponse
from routers._shared import parse_dt
from routers.deps import get_current_user_id

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(
    time_offset_hours: float = Query(default=0.0, ge=0.0),
    user_id: str = Depends(get_current_user_id),
):
    rows = get_all_chunks(user_id)
    if not rows:
        projected = datetime.now(tz=timezone.utc) + timedelta(hours=time_offset_hours)
        return HealthResponse(
            categories=[],
            forgotten_count=0,
            total_chunks=0,
            avg_retention=1.0,
            projected_date=projected.strftime("%B %d, %Y"),
            time_offset_hours=time_offset_hours,
        )

    last_accessed_list = [parse_dt(r["last_accessed"]) for r in rows]
    access_counts = [r["access_count"] for r in rows]
    complexity_scores = [r["complexity_score"] for r in rows]
    categories = [r["category"] or "Uncategorized" for r in rows]

    retentions = calculate_retention_batch(
        last_accessed_list, access_counts, complexity_scores, time_offset_hours
    )

    cat_data: dict[str, dict] = defaultdict(lambda: {"strong": 0, "fading": 0, "weak": 0, "critical": 0, "retentions": []})
    forgotten_count = 0
    for i, r in enumerate(retentions):
        status = classify_retention(float(r))
        cat = categories[i]
        cat_data[cat][status] += 1
        cat_data[cat]["retentions"].append(float(r))
        if float(r) < 0.2:
            forgotten_count += 1

    category_health = []
    for name, data in sorted(cat_data.items()):
        avg = float(np.mean(data["retentions"]))
        total = data["strong"] + data["fading"] + data["weak"] + data["critical"]
        urgency = "low" if avg >= 0.7 else ("medium" if avg >= 0.4 else "high")
        category_health.append(
            CategoryHealth(
                name=name,
                avg_retention=round(avg, 4),
                strong=data["strong"],
                fading=data["fading"],
                weak=data["weak"],
                critical=data["critical"],
                total=total,
                count=total,
                urgency=urgency,
            )
        )

    overall_avg = float(np.mean(retentions))
    projected = datetime.now(tz=timezone.utc) + timedelta(hours=time_offset_hours)

    return HealthResponse(
        categories=category_health,
        forgotten_count=forgotten_count,
        total_chunks=len(rows),
        avg_retention=round(overall_avg, 4),
        projected_date=projected.strftime("%B %d, %Y"),
        time_offset_hours=time_offset_hours,
    )
