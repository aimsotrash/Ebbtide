"""Vectorization: turn text into embeddings for semantic retrieval."""

from intelligence.embeddings.provider import (
    MODEL_NAME,
    embed_query,
    embed_texts,
    get_model,
    warm_model,
)

__all__ = ["MODEL_NAME", "embed_query", "embed_texts", "get_model", "warm_model"]
