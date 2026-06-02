"""
Quiz (MCQ) generation from a knowledge chunk.

Pure generation logic: given chunk text, produce a multiple-choice question dict
`{"question", "options", "correct_index"}`. Falls back to a hardcoded question
bank when the LLM is unavailable so the feature degrades gracefully without a key.

The backend router maps these dicts onto its API schema and pairs them with
retention computed by intelligence.memory — keeping web/DB shapes out of here.
"""

from intelligence.llm.provider import get_llm

# Fallback questions used if the LLM is unavailable.
FALLBACK_QUESTIONS = [
    {
        "question": "What is the primary purpose of spaced repetition?",
        "options": [
            "To memorize information faster in one session",
            "To review information at increasing intervals to strengthen memory",
            "To organize notes by topic",
            "To summarize long documents automatically",
        ],
        "correct_index": 1,
    },
    {
        "question": "According to Ebbinghaus, how much information is forgotten after one week without review?",
        "options": ["~10%", "~25%", "~75%", "~99%"],
        "correct_index": 2,
    },
    {
        "question": "What does the stability factor S represent in the decay formula?",
        "options": [
            "The size of the document",
            "How often a chunk was reviewed (durability of memory)",
            "The complexity of the content",
            "The time since the note was created",
        ],
        "correct_index": 1,
    },
    {
        "question": "Which retention score range is classified as 'Critical' in Dory.md?",
        "options": ["0.8 – 1.0", "0.5 – 0.8", "0.2 – 0.5", "0.0 – 0.2"],
        "correct_index": 3,
    },
    {
        "question": "What does the Time Machine slider project?",
        "options": [
            "The history of your notes",
            "Future knowledge retention using the decay formula",
            "Your weekly study schedule",
            "The similarity between documents",
        ],
        "correct_index": 1,
    },
]

MCQ_SYSTEM = (
    "You are a quiz generator. Given a text chunk, generate exactly 1 multiple-choice question "
    "that tests understanding of the content. Return ONLY valid JSON with this exact structure: "
    '{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_index": 0} '
    "where correct_index is 0-based. No markdown, no explanation."
)


def difficulty(complexity_score: float) -> str:
    if complexity_score < 0.33:
        return "easy"
    if complexity_score < 0.66:
        return "medium"
    return "hard"


def generate_mcq(content: str, fallback: dict) -> dict:
    """Generate one MCQ from `content`. Returns a normalized dict with a valid,
    in-range `correct_index`. On any LLM error/parse failure, returns `fallback`."""
    result = get_llm().complete_json(
        prompt=f"Generate a quiz question for this text:\n\n{content[:600]}",
        system=MCQ_SYSTEM,
        fallback=fallback,
    )

    question = result.get("question", fallback["question"])
    options = result.get("options", fallback["options"])
    try:
        correct_index = int(result.get("correct_index", fallback["correct_index"]))
    except (TypeError, ValueError):
        correct_index = fallback["correct_index"]

    if not isinstance(options, list) or len(options) < 2:
        options = fallback["options"]
        correct_index = fallback["correct_index"]
    correct_index = max(0, min(correct_index, len(options) - 1))

    return {"question": question, "options": options, "correct_index": correct_index}
