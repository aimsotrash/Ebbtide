import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from intelligence.memory import calculate_retention
from intelligence.llm import FALLBACK_QUESTIONS, difficulty, generate_mcq
from database.db import (
    complete_quiz_session,
    create_quiz_session,
    get_lowest_retention_chunks,
    get_quiz_history,
    update_chunk_access_by,
)
from models.schemas import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizQuestion,
    QuizStartResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizResultItem,
)
from routers.deps import get_current_user_id

# In-memory store: {session_id: {question_id: {correct_index, chunk_id}}}
# Process-scoped — see AUDIT P0-3 for the multi-worker limitation.
_session_store: dict[str, dict[str, dict]] = {}

# Fallback questions live in the intelligence layer (degrade gracefully w/o an LLM).
_FALLBACK_QUESTIONS = FALLBACK_QUESTIONS

router = APIRouter()


def _generate_question(chunk_id: str, content: str, access_count: int, complexity_score: float, source_file: str, category: str, fallback_q: dict) -> QuizQuestion:
    """Compose the API quiz-question shape. The MCQ text/options come from the
    intelligence layer; retention/difficulty are derived from the memory model.
    The backend owns only the wire-shape mapping."""
    r = calculate_retention(datetime.now(tz=timezone.utc), access_count, complexity_score)
    mcq = generate_mcq(content, fallback_q)
    return QuizQuestion(
        id=chunk_id,
        chunk_id=chunk_id,
        question=mcq["question"],
        options=mcq["options"],
        correct_index=mcq["correct_index"],
        difficulty=difficulty(complexity_score),
        category=category or "general",
        retention=round(r, 4),
        source_file=source_file,
    )


@router.post("/quiz/start", response_model=QuizStartResponse)
def start_quiz(user_id: str = Depends(get_current_user_id)):
    rows = get_lowest_retention_chunks(user_id, limit=5)
    session_id = create_quiz_session(user_id, total=len(rows) or 5)

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    if not rows:
        questions = [
            QuizQuestion(
                id=f"fallback-{i}",
                chunk_id=f"fallback-{i}",
                question=q["question"],
                options=q["options"],
                correct_index=q["correct_index"],
                difficulty="medium",
                category="general",
                retention=0.3,
                source_file="demo",
            )
            for i, q in enumerate(_FALLBACK_QUESTIONS)
        ]
        _session_store[session_id] = {
            f"fallback-{i}": {"correct_index": q["correct_index"], "chunk_id": f"fallback-{i}"}
            for i, q in enumerate(_FALLBACK_QUESTIONS)
        }
        return QuizStartResponse(session_id=session_id, questions=questions, created_at=now_iso)

    questions = []
    session_map = {}
    for i, row in enumerate(rows):
        fallback = _FALLBACK_QUESTIONS[i % len(_FALLBACK_QUESTIONS)]
        q = _generate_question(
            chunk_id=row["id"],
            content=row["content"],
            access_count=row["access_count"],
            complexity_score=row["complexity_score"],
            source_file=row["source_file"],
            category=row["category"] or "general",
            fallback_q=fallback,
        )
        questions.append(q)
        session_map[q.id] = {"correct_index": q.correct_index, "chunk_id": row["id"]}

    _session_store[session_id] = session_map
    return QuizStartResponse(session_id=session_id, questions=questions, created_at=now_iso)


@router.post("/quiz/answer", response_model=QuizAnswerResponse)
def submit_answer(body: QuizAnswerRequest, user_id: str = Depends(get_current_user_id)):
    # Server-authoritative scoring (AUDIT P0-4): the correct answer is looked up
    # from the server-side session map, never trusted from the request body. The
    # client-supplied correct_index is only a fallback for a session the server
    # has lost (e.g. after a restart), and even then it cannot grant a reward.
    session = _session_store.get(body.session_id, {})
    meta = session.get(body.chunk_id)
    server_known = meta is not None
    correct_index = meta["correct_index"] if server_known else body.correct_index
    correct = body.selected_index == correct_index
    new_r = 0.0
    # Only a server-verified correct answer earns a retention reward, so a client
    # cannot farm access_count by replaying answers against a lost/forged session.
    if correct and server_known and not body.chunk_id.startswith("fallback-"):
        updated = update_chunk_access_by(body.chunk_id, delta=2, user_id=user_id, source="quiz")
        if updated is not None:
            last_accessed = datetime.now(tz=timezone.utc)
            new_r = calculate_retention(last_accessed, updated["access_count"], updated["complexity_score"])

    return QuizAnswerResponse(
        correct=correct,
        correct_index=correct_index,
        new_retention=round(new_r, 4),
        message="Memory revived!" if correct else "Keep reviewing — you'll get it next time.",
    )


@router.post("/quiz/{session_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz(session_id: str, body: QuizSubmitRequest, user_id: str = Depends(get_current_user_id)):
    """Batch answer submission — matches frontend POST /api/quiz/{sessionId}/submit."""
    session_map = _session_store.get(session_id, {})

    results = []
    score = 0
    max_streak = 0
    current_streak = 0

    for answer in body.answers:
        qid = answer.question_id
        meta = session_map.get(qid, {})
        correct_index = meta.get("correct_index", 0)
        chunk_id = meta.get("chunk_id", qid)
        correct = answer.selected_index == correct_index

        stability_delta = 0.0
        if correct and not chunk_id.startswith("fallback-"):
            updated = update_chunk_access_by(chunk_id, delta=2, user_id=user_id, source="quiz")
            if updated is not None:
                stability_delta = 12.0
                score += 1
                current_streak += 1
                max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
            if not chunk_id.startswith("fallback-") and not correct:
                stability_delta = -4.0

        results.append(QuizResultItem(
            question_id=qid,
            correct=correct,
            selected_index=answer.selected_index,
            correct_index=correct_index,
            stability_delta=stability_delta,
        ))

    # Persist the finished session so it shows up in history (AUDIT P0-2).
    complete_quiz_session(session_id, score, user_id)
    # Free the in-memory answer key now that the session is scored.
    _session_store.pop(session_id, None)

    return QuizSubmitResponse(
        session_id=session_id,
        score=score,
        total=len(body.answers),
        results=results,
        xp_earned=score * 50,
        streaks=max_streak,
    )


@router.get("/quiz/history")
def quiz_history(user_id: str = Depends(get_current_user_id)):
    """Return the user's completed quiz sessions, most recent first."""
    rows = get_quiz_history(user_id, limit=20)
    return {
        "sessions": [
            {
                "session_id": r["id"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "correct_count": r["correct_count"],
                "total_count": r["total_count"],
                "accuracy": round(r["correct_count"] / r["total_count"], 4) if r["total_count"] else 0.0,
            }
            for r in rows
        ]
    }
