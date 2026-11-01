"""Vectorization: turn text into embeddings for semantic retrieval."""

from intelligence.embeddings.provider import (
    MAX_TOKENS,
    MODEL_NAME,
    embed_query,
    embed_texts,
    encode,
    fits,
    warm_model,
)

__all__ = ["MAX_TOKENS", "MODEL_NAME", "embed_query", "embed_texts", "encode", "fits", "warm_model"]
