"""LongMemEval harness: replay order, the replay loop, and the official metrics, on
hand-made questions in the dataset's shape."""

import numpy as np

from bench.longmemeval import Plan, _timestamp, plan, replay, score
from intelligence.memory import POLICIES


def _turn(role, content, evidence=False):
    return {"role": role, "content": content, **({"has_answer": True} if evidence else {})}


def test_plan_sorts_sessions_and_asks_after_the_last_turn():
    q = {  # stored newest first, and the question is dated an hour before the last session
        "question_type": "knowledge-update", "question": "Q", "question_date": "2023/05/03 (Wed) 08:00",
        "haystack_session_ids": ["answer_new", "chat", "answer_old"],
        "haystack_dates": ["2023/05/03 (Wed) 09:00", "2023/05/02 (Tue) 09:00", "2023/05/01 (Mon) 09:00"],
        "haystack_sessions": [
            [_turn("user", "now 26:10", evidence=True)],
            [_turn("user", "hello"), _turn("assistant", "hi")],
            [_turn("user", "best 25:50", evidence=True), _turn("assistant", "nice")],
        ],
        "answer_session_ids": ["answer_new", "answer_old"],
    }
    row = {t: i for i, t in enumerate(["now 26:10", "hello", "hi", "best 25:50", "nice", "Q"])}
    p = plan(q, row)
    assert p.rows == [3, 4, 1, 2, 0] and p.is_user == [True, False, True, False, True]
    assert p.session == [0, 0, 1, 1, 2]
    assert (p.evidence, p.answer_sessions, p.latest) == ({0, 4}, {0, 2}, {4})
    assert p.times[:2] == [_timestamp("2023/05/01 (Mon) 09:00"), _timestamp("2023/05/01 (Mon) 09:00") + 1]
    assert p.question_time == p.times[-1] + 1  # not the earlier question_date


def test_replay_keeps_recalled_evidence_only_when_recall_strengthens():
    q = {
        "question_type": "single-session-user", "question": "where is the car", "question_date": "2023/05/10 (Wed) 12:00",
        "haystack_session_ids": ["answer_1", "chat"],
        "haystack_dates": ["2023/05/01 (Mon) 09:00", "2023/05/04 (Thu) 09:00"],
        "haystack_sessions": [
            [_turn("user", "I parked on level 3", evidence=True), _turn("assistant", "noted")],
            [_turn("user", "where did I park?"), _turn("assistant", "level 3")],
        ],
        "answer_session_ids": ["answer_1"],
    }
    texts = ["I parked on level 3", "noted", "where did I park?", "level 3", "where is the car"]
    emb = np.array([[1, 0, 0], [0, 1, 0], [0.9, 0.1, 0], [0, 0, 1], [1, 0, 0.1]], dtype=np.float32)
    p = plan(q, {t: i for i, t in enumerate(texts)})
    # With room for 2 memories, recency drops the evidence when "where did I park?" arrives.
    # ebbtide-spaced recalls the evidence for that turn first, which keeps it strongest.
    forgetful = replay(p, POLICIES["recency"], 2, 1, emb)
    ebbtide = replay(p, POLICIES["ebbtide-spaced"], 2, 1, emb)
    assert (forgetful["evidence_kept"], forgetful["turn_all@5"]) == (0.0, 0.0)
    assert (ebbtide["evidence_kept"], ebbtide["turn_all@5"], ebbtide["memories"]) == (1.0, 1.0, 2)


def test_score_matches_the_official_definitions():
    p = Plan("knowledge-update", [], [], [], session=[0, 0, 0, 0, 1, 1, 2, 2, 3, 4, 4, 4],
             evidence=frozenset({1, 9}), answer_sessions=frozenset({0, 4}), latest=frozenset({9}),
             question_row=0, question_time=0.0)
    s = score(list(range(12)), p)
    assert (s["turn_any@5"], s["turn_all@5"], s["turn_all@10"]) == (1.0, 0.0, 1.0)
    assert (s["latest@5"], s["latest@10"]) == (0.0, 1.0)
    # Reading down to 5 distinct sessions reaches session 4 at turn 9; the top 5 turns alone would not.
    assert (s["session_any@5"], s["session_all@5"]) == (1.0, 1.0)
