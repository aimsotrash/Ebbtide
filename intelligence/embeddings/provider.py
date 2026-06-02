"""
Singleton SentenceTransformer wrapper.

The model is loaded lazily (importing sentence_transformers + torch is expensive,
so we defer it until the first ingest/search). The backend's lifespan calls
warm_model() once at startup so the first real request is never cold; tests skip
that via DORY_SKIP_WARMUP.
"""

_model = None  # type: ignore[var-annotated]
MODEL_NAME = "all-MiniLM-L6-v2"


def warm_model() -> None:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy import: defer
        _model = SentenceTransformer(MODEL_NAME)


def get_model():
    global _model
    if _model is None:
        warm_model()
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of strings. Returns a list of 384-dim float vectors."""
    model = get_model()
    return model.encode(texts, batch_size=32, show_progress_bar=False).tolist()


def embed_query(text: str) -> list[float]:
    """Encode a single query string."""
    return get_model().encode([text], show_progress_bar=False)[0].tolist()
