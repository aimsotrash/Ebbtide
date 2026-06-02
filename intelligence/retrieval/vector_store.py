"""
ChromaDB vector store adapter — the semantic-retrieval backbone.

Collection: dory_chunks
  - Embeddings: all-MiniLM-L6-v2 (384-dim)
  - Metadata per document: user_id, chunk_id, source_file
  - Persisted at <repo>/backend/data/chroma (kept alongside the SQLite file so a
    single volume mount covers both stores).

This module owns vector persistence only. It does not compute embeddings (that's
intelligence.embeddings) and knows nothing about the relational DB.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

_client: Optional[chromadb.ClientAPI] = None
_collection = None
COLLECTION_NAME = "dory_chunks"

# Default path keeps parity with the original layout (backend/data/chroma) so
# existing local data is picked up. Override with DORY_CHROMA_PATH if desired.
_DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "chroma"


def _chroma_path() -> Path:
    override = os.getenv("DORY_CHROMA_PATH")
    return Path(override) if override else _DEFAULT_CHROMA_PATH


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        path = _chroma_path()
        path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunk_ids: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
    """Store embeddings + metadata. Documents are not stored (content lives in SQLite)."""
    col = get_collection()
    col.add(ids=chunk_ids, embeddings=embeddings, metadatas=metadatas)


def upsert_chunk(chunk_id: str, embedding: list[float], metadata: dict) -> None:
    """Insert-or-replace a single chunk's embedding. Used after a content edit so
    the vector stays in sync with the SQLite content (AUDIT P0-1)."""
    get_collection().upsert(ids=[chunk_id], embeddings=[embedding], metadatas=[metadata])


def query_similar(
    query_embedding: list[float],
    user_id: str,
    n_results: int = 50,
) -> dict:
    """
    Return the top-n most similar chunks for a user.
    ChromaDB returns distances (lower = more similar for cosine space).
    We convert distance → similarity: similarity = 1 - distance.
    """
    col = get_collection()
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, col.count()),
        where={"user_id": user_id},
        include=["distances", "metadatas"],
    )
    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    similarities = [1.0 - d for d in distances]
    return {"ids": ids, "similarities": similarities, "metadatas": metadatas}


def delete_chunk(chunk_id: str, user_id: str) -> None:
    """Delete only if the embedding's metadata user_id matches. Silent no-op otherwise."""
    get_collection().delete(ids=[chunk_id], where={"user_id": user_id})


def count() -> int:
    return get_collection().count()
