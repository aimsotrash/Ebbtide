"""Semantic retrieval: the vector store adapter."""

from intelligence.retrieval.vector_store import (
    COLLECTION_NAME,
    add_chunks,
    count,
    delete_chunk,
    get_collection,
    query_similar,
    upsert_chunk,
)

__all__ = [
    "add_chunks",
    "upsert_chunk",
    "query_similar",
    "delete_chunk",
    "count",
    "get_collection",
    "COLLECTION_NAME",
]
