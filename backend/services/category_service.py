"""Category classification orchestration (backend side).

The actual classification logic lives in the intelligence layer
(`intelligence.llm.classify`). This module is the thin backend wrapper that wires
classification to persistence: classify the content, then store the result in the
relational DB. Keeping DB access here (not in intelligence) preserves the
architectural boundary — see ARCHITECTURE_REFACTOR.md.

Runs as a BackgroundTask after ingestion so uploads return immediately.
"""

import logging

from intelligence.llm import CATEGORIES, classify
from database.db import get_all_chunks, update_chunk_category

logger = logging.getLogger("dory.classification")

__all__ = ["CATEGORIES", "classify_and_store", "classify_all_uncategorized"]


def classify_and_store(chunk_id: str, content: str) -> None:
    """Classify a chunk's content and persist the category."""
    category = classify(content)
    update_chunk_category(chunk_id, category)


def classify_all_uncategorized() -> None:
    """Classify every chunk that has no category. Safe to call from a background
    thread at startup. Failures are logged per-chunk, never raised."""
    rows = get_all_chunks()
    uncategorized = [r for r in rows if not r["category"]]
    for row in uncategorized:
        try:
            classify_and_store(row["id"], row["content"])
        except Exception:
            logger.exception("classification failed for chunk %s", row["id"])
