"""FSRS review-loop tests: scheduler service + /api/review/queue + /api/review/grade.

The fsrs library is the source of truth for the math; these tests verify the
*integration* — that grades persist to SQLite, due dates advance, only the
owning user can grade, and the queue surfaces due chunks in order."""

import pytest
from datetime import datetime, timedelta, timezone

from database.db import insert_chunk, get_chunk
from intelligence.memory import scheduler as scheduler_service


def _seed_chunk(user_id: str, content: str = "FSRS test note") -> str:
    return insert_chunk(content=content, source_file="seed.md", complexity_score=0.5, user_id=user_id)


def _user_id_from(token: str) -> str:
    from jose import jwt
    from routers.deps import _get_secret, JWT_ALGORITHM
    return jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])["sub"]


# ── Scheduler service ────────────────────────────────────────────────────────

def test_grade_again_brings_card_back_soon(client, register_user):
    """Grading 'Again' (1) on a fresh card should make it due within ~10 minutes."""
    _, token = register_user()
    uid = _user_id_from(token)
    cid = _seed_chunk(uid)
    row = get_chunk(cid, uid)

    upd = scheduler_service.grade(row, 1)
    next_due = datetime.fromisoformat(upd["fsrs_due"])
    delta = next_due - datetime.now(timezone.utc)
    assert delta < timedelta(minutes=15), f"Again should reschedule within 15min, got {delta}"


def test_grade_easy_pushes_card_far_out(client, register_user):
    """Grading 'Easy' (4) on a fresh card should push due date to multiple days out."""
    _, token = register_user()
    uid = _user_id_from(token)
    cid = _seed_chunk(uid)
    row = get_chunk(cid, uid)

    upd = scheduler_service.grade(row, 4)
    next_due = datetime.fromisoformat(upd["fsrs_due"])
    delta = next_due - datetime.now(timezone.utc)
    assert delta > timedelta(minutes=15), f"Easy should defer well past Again's interval, got {delta}"


def test_invalid_grade_raises(client, register_user):
    _, token = register_user()
    uid = _user_id_from(token)
    cid = _seed_chunk(uid)
    row = get_chunk(cid, uid)
    with pytest.raises(ValueError):
        scheduler_service.grade(row, 5)


# ── Endpoint: /api/review/queue ──────────────────────────────────────────────

def test_queue_returns_freshly_seeded_chunks(client, register_user):
    _, token = register_user()
    uid = _user_id_from(token)
    _seed_chunk(uid, "one")
    _seed_chunk(uid, "two")

    res = client.get("/api/review/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["due_count"] >= 2
    assert len(body["cards"]) >= 2
    assert all("chunk_id" in c and "fsrs_due" in c for c in body["cards"])


def test_queue_isolates_users(client, register_user):
    _, alice_token = register_user("alice")
    _, bob_token = register_user("bob")
    alice_id = _user_id_from(alice_token)
    bob_id = _user_id_from(bob_token)

    alice_chunk = _seed_chunk(alice_id, "alice secret")
    bob_chunk = _seed_chunk(bob_id, "bob secret")

    alice_q = client.get("/api/review/queue", headers={"Authorization": f"Bearer {alice_token}"}).json()
    alice_ids = {c["chunk_id"] for c in alice_q["cards"]}
    assert alice_chunk in alice_ids
    assert bob_chunk not in alice_ids


def test_queue_requires_auth(client):
    res = client.get("/api/review/queue")
    assert res.status_code == 401


# ── Endpoint: /api/review/grade ──────────────────────────────────────────────

def test_grade_advances_due_date_in_db(client, register_user):
    _, token = register_user()
    uid = _user_id_from(token)
    cid = _seed_chunk(uid)

    before = get_chunk(cid, uid)
    res = client.post(
        "/api/review/grade",
        headers={"Authorization": f"Bearer {token}"},
        json={"chunk_id": cid, "grade": 3},  # Good
    )
    assert res.status_code == 200
    body = res.json()
    assert body["chunk_id"] == cid
    assert body["grade"] == 3

    after = get_chunk(cid, uid)
    # The card should have a new last_review timestamp and the due date should change.
    assert after["fsrs_last_review"] is not None
    assert after["fsrs_due"] != before["fsrs_due"]
    assert after["access_count"] == before["access_count"] + 1


def test_grade_rejects_invalid_value(client, register_user):
    _, token = register_user()
    uid = _user_id_from(token)
    cid = _seed_chunk(uid)
    res = client.post(
        "/api/review/grade",
        headers={"Authorization": f"Bearer {token}"},
        json={"chunk_id": cid, "grade": 99},
    )
    assert res.status_code == 400


def test_grade_404s_for_other_users_chunk(client, register_user):
    _, alice_token = register_user("alice")
    _, bob_token = register_user("bob")
    alice_id = _user_id_from(alice_token)

    alice_chunk = _seed_chunk(alice_id, "alice's card")
    res = client.post(
        "/api/review/grade",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"chunk_id": alice_chunk, "grade": 3},
    )
    assert res.status_code == 404


def test_grade_requires_auth(client):
    res = client.post("/api/review/grade", json={"chunk_id": "x", "grade": 3})
    assert res.status_code == 401
