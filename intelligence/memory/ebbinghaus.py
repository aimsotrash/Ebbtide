"""
Ebbinghaus forgetting curve engine.

Formula:  R(t) = e^( -t / (S * k * BASE_HOURS) )
  t          = hours elapsed since last access + any projection offset
  S          = stability factor = 1.0 + 0.5 * ln(1 + access_count)
               (dimensionless, range 1.0 – ~3.5)
  k          = complexity modifier = 0.5 + 1.5 * complexity_score
               (range 0.5 – 2.0; higher k = slower decay for complex content)
  BASE_HOURS = 216 h (9 days) — characteristic half-life for a brand-new note.

Typical behaviour:
  - Note accessed 3 days ago, 3 reviews  → R ≈ 0.87 (strong)
  - Note accessed 10 days ago, 1 review  → R ≈ 0.44 (weak)
  - Note accessed 30 days ago, 0 reviews → R ≈ 0.04 (critical)

Two entry points:
  calculate_retention()        — single chunk, used by fading feed / search
  calculate_retention_batch()  — numpy vectorized, used by Time Machine (50-100x faster)
"""

import math
from datetime import datetime, timezone

import numpy as np

_BASE_HOURS = 24 * 9  # 216 hours — 9-day characteristic time for a new, unreviewed note


def _elapsed_hours(last_accessed: datetime) -> float:
    if last_accessed.tzinfo is None:
        last_accessed = last_accessed.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    return max((now - last_accessed).total_seconds() / 3600, 0.0)


def stability(access_count: int) -> float:
    return 1.0 + 0.5 * math.log1p(access_count)


def complexity_modifier(complexity_score: float) -> float:
    return 0.5 + 1.5 * max(0.0, min(1.0, complexity_score))


def calculate_retention(
    last_accessed: datetime,
    access_count: int,
    complexity_score: float,
    offset_hours: float = 0.0,
) -> float:
    t = _elapsed_hours(last_accessed) + offset_hours
    S = stability(access_count)
    k = complexity_modifier(complexity_score)
    return float(math.exp(-t / (S * k * _BASE_HOURS)))


def calculate_retention_batch(
    last_accessed_list: list[datetime],
    access_counts: list[int],
    complexity_scores: list[float],
    offset_hours: float = 0.0,
) -> np.ndarray:
    """
    Vectorized retention for all chunks at once.
    Returns a float64 ndarray of shape (n,) with values in [0, 1].
    Called by GET /api/health for Time Machine — avoids a Python loop.
    """
    elapsed = np.array([_elapsed_hours(dt) for dt in last_accessed_list], dtype=np.float64)
    t = elapsed + offset_hours
    counts = np.array(access_counts, dtype=np.float64)
    scores = np.clip(np.array(complexity_scores, dtype=np.float64), 0.0, 1.0)
    S = 1.0 + 0.5 * np.log1p(counts)
    k = 0.5 + 1.5 * scores
    return np.exp(-t / (S * k * _BASE_HOURS))


# Retention status thresholds — the single source of truth shared by backend
# responses AND the frontend (mirror these in the SPA, see UI_REVIEW D-1).
STRONG_THRESHOLD = 0.8
FADING_THRESHOLD = 0.5
WEAK_THRESHOLD = 0.2


def classify_retention(r: float) -> str:
    if r >= STRONG_THRESHOLD:
        return "strong"
    if r >= FADING_THRESHOLD:
        return "fading"
    if r >= WEAK_THRESHOLD:
        return "weak"
    return "critical"
