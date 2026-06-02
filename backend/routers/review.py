"""Review endpoints.

  POST /api/review/{chunk_id}   — legacy "mark as viewed" bump (still used by
                                  the note-detail panel for non-quiz access)
  GET  /api/review/queue        — cards currently due for FSRS review
  POST /api/review/grade        — submit a self-grade (1-4) for one card,
                                  advances FSRS state, returns next due date
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from intelligence.memory import calculate_retention
from intelligence.memory import VALID_GRADES, grade as fsrs_grade
from database.db import (
    apply_fsrs_update,
    count_due_chunks,
    get_chunk,
    get_review_queue,
    update_chunk_access,
)
from models.schemas import (
    GradeRequest,
    GradeResponse,
    ReviewCard,
    ReviewQueueResponse,
    ReviewResponse,
)
from routers.deps import get_current_user_id

router = APIRouter()


@router.get("/review/queue", response_model=ReviewQueueResponse)
def review_queue(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    """Return chunks due for review, oldest-due first."""
    rows = get_review_queue(user_id, limit=limit)
    total = count_due_chunks(user_id)
    cards = [
        ReviewCard(
            chunk_id=r["id"],
            content=r["content"],
            source_file=r["source_file"],
            category=r["category"],
            fsrs_state=r["fsrs_state"] or 1,
            fsrs_due=r["fsrs_due"],
            fsrs_stability=r["fsrs_stability"],
            fsrs_difficulty=r["fsrs_difficulty"],
            fsrs_last_review=r["fsrs_last_review"],
        )
        for r in rows
    ]
    return ReviewQueueResponse(cards=cards, due_count=total)


@router.post("/review/grade", response_model=GradeResponse)
def review_grade(body: GradeRequest, user_id: str = Depends(get_current_user_id)):
    """Apply a self-grade (1=Again, 2=Hard, 3=Good, 4=Easy) to a chunk and
    advance the FSRS schedule. Returns the new due date."""
    if body.grade not in VALID_GRADES:
        raise HTTPException(status_code=400, detail="Grade must be 1, 2, 3, or 4.")

    row = get_chunk(body.chunk_id, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Chunk not found.")

    fsrs = fsrs_grade(row, body.grade)
    if not apply_fsrs_update(body.chunk_id, user_id, fsrs):
        # Should never happen since we just read it above with the same user_id.
        raise HTTPException(status_code=404, detail="Chunk not found.")

    return GradeResponse(
        chunk_id=body.chunk_id,
        grade=body.grade,
        next_due=fsrs["fsrs_due"],
        stability=fsrs["fsrs_stability"],
        difficulty=fsrs["fsrs_difficulty"],
        state=fsrs["fsrs_state"],
    )


@router.post("/review/{chunk_id}", response_model=ReviewResponse)
def review_chunk(chunk_id: str, user_id: str = Depends(get_current_user_id)):
    """Legacy 'I viewed this chunk' bump. Increments access_count and recomputes
    Ebbinghaus retention for the dashboard. Does NOT advance the FSRS scheduler —
    use POST /review/grade for that."""
    updated = update_chunk_access(chunk_id, user_id=user_id, source="review")
    if updated is None:
        raise HTTPException(status_code=404, detail="Chunk not found.")

    last_accessed = datetime.fromisoformat(updated["last_accessed"]).replace(tzinfo=timezone.utc)
    new_r = calculate_retention(last_accessed, updated["access_count"], updated["complexity_score"])

    return ReviewResponse(
        chunk_id=chunk_id,
        new_retention=round(new_r, 4),
        access_count=updated["access_count"],
        message=f"Memory revived. Retention now {new_r:.0%}.",
    )
