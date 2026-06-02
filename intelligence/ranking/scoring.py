"""
Hybrid ranking + derived memory metrics.

Pure numeric helpers shared by search ranking and the chunk wire-shape. No I/O.

Composite search score blends three signals:
  - semantic similarity   (0.4)  how close the query embedding is
  - decay urgency         (0.4)  1 - retention  (surface what you're forgetting)
  - recency               (0.2)  exponential bonus for recently-created chunks
"""

import math

SIMILARITY_WEIGHT = 0.4
DECAY_URGENCY_WEIGHT = 0.4
RECENCY_WEIGHT = 0.2


def recency_bonus(days_since_created: float) -> float:
    """Exponential decay of 'how recent' a chunk is. 30-day characteristic time."""
    return math.exp(-days_since_created / 30)


def composite_score(similarity: float, retention: float, recency: float) -> float:
    """Blend the three ranking signals into one comparable score."""
    decay_urgency = 1.0 - retention
    return (
        similarity * SIMILARITY_WEIGHT
        + decay_urgency * DECAY_URGENCY_WEIGHT
        + recency * RECENCY_WEIGHT
    )


def display_stability(access_count: int) -> float:
    """Human-facing stability_S value shown in chunk cards (days-ish scale)."""
    return round((1.0 + 0.5 * math.log1p(access_count)) * 9.0, 2)


def display_complexity_k(complexity_score: float) -> float:
    """Human-facing complexity modifier k shown in chunk cards."""
    return round(0.5 + 1.5 * max(0.0, min(1.0, complexity_score)), 3)
