"""Spaced-repetition scheduling for chunks (FSRS-4).

Wraps the `fsrs` package so the rest of the codebase doesn't import from `fsrs`
directly. The scheduler decides when a chunk is next due for review based on the
user's self-grade after each review.

Why FSRS instead of SM-2 (Anki's classic algorithm):
- FSRS models stability and difficulty as separable parameters, where SM-2
  conflates them into a single ease factor.
- FSRS is fit on millions of real-world reviews; SM-2's parameters are hand-set.
- Empirically: FSRS converges on the user's desired retention rate (default 90%)
  with ~30% fewer reviews than SM-2 for the same retention target.

This module is pure: `grade()` takes a mapping of the card's persisted FSRS state
(any object supporting `row["fsrs_state"]`-style access — a dict or a sqlite3.Row)
and returns a dict of new column values. Persisting them is the backend's job.
"""

from __future__ import annotations

from typing import Any

from fsrs import Card, Rating, Scheduler

# Single scheduler instance; the default desired-retention is 0.9.
_scheduler = Scheduler()

# Valid grade values mirroring fsrs.Rating: 1=Again, 2=Hard, 3=Good, 4=Easy.
VALID_GRADES = {1, 2, 3, 4}


def _card_from_row(row: Any) -> Card:
    """Reconstruct an fsrs.Card from a chunk row's FSRS columns."""
    return Card.from_dict({
        "card_id": 0,
        "state": row["fsrs_state"] if row["fsrs_state"] is not None else 1,
        "step": row["fsrs_step"] if row["fsrs_step"] is not None else 0,
        "stability": row["fsrs_stability"],
        "difficulty": row["fsrs_difficulty"],
        "due": row["fsrs_due"],
        "last_review": row["fsrs_last_review"],
    })


def grade(row: Any, grade: int) -> dict:
    """Apply a self-grade (1-4) to a chunk row and return the new FSRS state
    as a dict of column updates ready to splat into an UPDATE statement.

    Raises ValueError on an invalid grade.
    """
    if grade not in VALID_GRADES:
        raise ValueError(f"grade must be 1-4, got {grade!r}")

    card = _card_from_row(row)
    new_card, _log = _scheduler.review_card(card, Rating(grade))

    d = new_card.to_dict()
    return {
        "fsrs_state": d["state"],
        "fsrs_step": d["step"],
        "fsrs_stability": d["stability"],
        "fsrs_difficulty": d["difficulty"],
        "fsrs_due": d["due"],
        "fsrs_last_review": d["last_review"],
    }
