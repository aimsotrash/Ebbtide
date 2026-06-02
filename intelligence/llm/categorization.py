"""
LLM-based category classifier (pure).

`classify(content)` returns a category string from CATEGORIES. It performs no
persistence — the backend is responsible for storing the result. An in-memory
content-hash cache avoids re-classifying identical text.

CATEGORIES is the single source of truth for the taxonomy (AUDIT P4-1): the LLM
output is validated against it, and the demo seeder only writes values from it.
"""

import hashlib

from intelligence.llm.provider import get_llm

CATEGORIES = [
    "Computer Science",
    "AI/ML",
    "System Design",
    "Mathematics",
    "Design",
    "Productivity",
    "Research",
    "Personal",
    "Other",
]

_cache: dict[str, str] = {}

SYSTEM_PROMPT = (
    "You are a knowledge classifier. "
    "Given a text chunk, return ONLY a JSON object with one key 'category' "
    f"whose value is exactly one of: {CATEGORIES}. "
    "No explanation, no markdown, just the JSON."
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def classify(content: str) -> str:
    """Classify a chunk's content into one of CATEGORIES. Cached by content hash."""
    key = _hash(content)
    if key in _cache:
        return _cache[key]

    result = get_llm().complete_json(
        prompt=f"Classify this text:\n\n{content[:800]}",
        system=SYSTEM_PROMPT,
        fallback={"category": "Other"},
    )
    category = result.get("category", "Other")
    if category not in CATEGORIES:
        category = "Other"

    _cache[key] = category
    return category
