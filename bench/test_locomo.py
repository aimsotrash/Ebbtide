"""LoCoMo harness: reading a conversation and its questions, typos included."""

from bench.locomo import conversation, dia_ids, turn_text


def test_conversation_plan_and_evidence_ids():
    d = {
        "conversation": {
            "session_2": [{"speaker": "Ana", "dia_id": "D2:1", "text": "I adopted a cat"}],
            "session_2_date_time": "9:00 am on 3 June, 2023",
            "session_1": [
                {"speaker": "Ana", "dia_id": "D1:1", "text": "Hi Ben"},
                {"speaker": "Ben", "dia_id": "D1:2", "text": "Look", "blip_caption": "a photo of a lake"},
            ],
            "session_1_date_time": "1:56 pm on 8 May, 2023",
        },
        "qa": [
            {"question": "What did Ben share?", "category": 4, "evidence": ["D1:02"]},
            {"question": "What happened when?", "category": 2, "evidence": ["D1:2; D:2:1"]},
            {"question": "What did Ana paint?", "category": 5, "evidence": ["D1:1"]},  # adversarial
            {"question": "Unresolvable", "category": 1, "evidence": ["D9:9", "D"]},
        ],
    }
    texts = ["Ana said, \"Hi Ben\"", "Ben said, \"Look\" [shares a photo of a lake]", "Ana said, \"I adopted a cat\"",
             "What did Ben share?", "What happened when?", "What did Ana paint?", "Unresolvable"]
    assert turn_text(d["conversation"]["session_1"][1]) == texts[1]
    assert dia_ids(["D8:6; D9:17", "D:11:26", "D30:05", "D"]) == ["D8:6", "D9:17", "D11:26", "D30:5"]

    turns, questions, skipped = conversation(d, {t: i for i, t in enumerate(texts)})
    assert turns.rows == [0, 1, 2] and turns.session == [0, 0, 1] and all(turns.is_user)
    assert turns.times[1] == turns.times[0] + 1 and turns.times[2] > turns.times[1]
    assert [(q.qtype, q.evidence, q.answer_sessions) for q in questions] == [
        ("single-hop", {1}, {0}),
        ("temporal", {1, 2}, {0, 1}),
    ]
    assert skipped == 1 and questions[0].question_time == turns.times[-1] + 1
