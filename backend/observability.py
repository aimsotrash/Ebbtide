"""Centralized logging configuration.

Kept deliberately small and stdlib-only so it has no runtime dependencies and is
safe to import at module load. Log level is controlled by LOG_LEVEL (default INFO);
set LOG_LEVEL=DEBUG locally for verbose output. Format is line-based and
grep-friendly; swap for JSON here if shipping to a structured log sink.
"""

import logging
import os

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    # ChromaDB / sentence-transformers are chatty; keep their INFO noise down.
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    _CONFIGURED = True
