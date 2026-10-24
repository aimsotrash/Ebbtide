"""
Singleton SentenceTransformer wrapper.

The model is loaded lazily (importing sentence_transformers + torch is expensive,
so we defer it until the first embed); warm_model() loads it ahead of time. The
tests stub the embedder, so they never load it.
"""

_model = None  # type: ignore[var-annotated]
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"  # pinned: a changed upstream repo is never loaded


def warm_model() -> None:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy import: defer
        try:  # the cache first: offline, the Hugging Face client retries for minutes before using it
            _model = SentenceTransformer(MODEL_NAME, revision=REVISION, local_files_only=True)
        except OSError:  # not downloaded yet
            _model = SentenceTransformer(MODEL_NAME, revision=REVISION)


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
