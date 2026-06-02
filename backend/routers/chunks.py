from fastapi import APIRouter, Depends, HTTPException, Query

import logging

from intelligence.memory import calculate_retention, classify_retention
from database.db import (
    delete_chunk,
    get_all_chunks,
    get_chunk_full,
    get_folders,
    set_chunk_folder,
    update_chunk_content,
)
from models.schemas import (
    BulkDeleteRequest,
    ChunkDetailOut,
    ChunkOut,
    ChunksResponse,
    FolderRequest,
    UpdateChunkRequest,
)
from routers._shared import parse_dt, time_ago
from routers.deps import get_current_user_id
from intelligence.retrieval import delete_chunk as chroma_delete
from intelligence.retrieval import upsert_chunk as chroma_upsert

logger = logging.getLogger("dory.chunks")

router = APIRouter()


def _reindex_chunk(chunk_id: str, content: str, user_id: str, source_file: str) -> bool:
    """Recompute the embedding for an edited chunk and upsert it into the vector
    store so semantic search reflects the new text (AUDIT P0-1). Returns True on
    success. Failures are logged, not raised — the SQLite content is already saved,
    and a failed re-index is recoverable, but it must be observable."""
    try:
        from intelligence.embeddings import embed_query  # heavy import: defer to call time
        embedding = embed_query(content)
        chroma_upsert(chunk_id, embedding, {"user_id": user_id, "chunk_id": chunk_id, "source_file": source_file})
        return True
    except Exception:
        logger.exception("Failed to re-index chunk %s after edit; vector is now stale", chunk_id)
        return False


@router.get("/chunks", response_model=ChunksResponse)
def get_chunks(
    limit: int = Query(default=2000, ge=1, le=5000),
    sort: str = Query(default="retention", pattern="^(retention|recent|access)$"),
    user_id: str = Depends(get_current_user_id),
):
    """Return ALL chunks for Library and Calendar views."""
    rows = get_all_chunks(user_id)
    results: list[ChunkOut] = []

    for row in rows:
        last_accessed = parse_dt(row["last_accessed"])
        r = calculate_retention(last_accessed, row["access_count"], row["complexity_score"])
        results.append(
            ChunkOut(
                chunk_id=row["id"],
                content=row["content"][:300],
                source_file=row["source_file"],
                category=row["category"],
                retention=round(r, 4),
                status=classify_retention(r),
                last_accessed=time_ago(last_accessed),
                last_accessed_iso=last_accessed.isoformat(),
                access_count=row["access_count"],
                folder=row["folder"],
            )
        )

    if sort == "retention":
        results.sort(key=lambda x: x.retention)
    elif sort == "recent":
        # Sort by ISO timestamp, not the human-readable "Nd ago" string which would sort lexicographically.
        results.sort(key=lambda x: x.last_accessed_iso, reverse=True)
    elif sort == "access":
        results.sort(key=lambda x: x.access_count, reverse=True)

    return ChunksResponse(chunks=results[:limit], total=len(results))


@router.get("/chunks/{chunk_id}", response_model=ChunkDetailOut)
def get_chunk_detail(chunk_id: str, user_id: str = Depends(get_current_user_id)):
    """Return full (untruncated) chunk content for editing."""
    row = get_chunk_full(chunk_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return ChunkDetailOut(
        chunk_id=row["id"],
        content=row["content"],
        source_file=row["source_file"],
        folder=row["folder"],
    )


@router.put("/chunks/{chunk_id}")
def update_chunk(chunk_id: str, body: UpdateChunkRequest, user_id: str = Depends(get_current_user_id)):
    """Update chunk content (used by inline editor). Re-embeds the chunk so the
    vector store stays consistent with the edited text."""
    if not update_chunk_content(chunk_id, body.content, user_id):
        raise HTTPException(status_code=404, detail="Chunk not found")
    row = get_chunk_full(chunk_id, user_id)
    reindexed = _reindex_chunk(chunk_id, body.content, user_id, row["source_file"] if row else "") if row else False
    return {"updated": chunk_id, "reindexed": reindexed}


@router.delete("/chunks/{chunk_id}")
def delete_chunk_route(chunk_id: str, user_id: str = Depends(get_current_user_id)):
    """Delete a single chunk."""
    if not delete_chunk(chunk_id, user_id):
        raise HTTPException(status_code=404, detail="Chunk not found")
    try:
        chroma_delete(chunk_id, user_id)
    except Exception:
        pass
    return {"deleted": chunk_id}


@router.post("/chunks/bulk-delete")
def bulk_delete_chunks(body: BulkDeleteRequest, user_id: str = Depends(get_current_user_id)):
    """Delete multiple chunks by ID. Only chunks owned by user_id are deleted."""
    deleted = 0
    for cid in body.chunk_ids:
        if delete_chunk(cid, user_id):
            deleted += 1
            try:
                chroma_delete(cid, user_id)
            except Exception:
                pass
    return {"deleted": deleted}


@router.patch("/chunks/{chunk_id}/folder")
def patch_chunk_folder(chunk_id: str, body: FolderRequest, user_id: str = Depends(get_current_user_id)):
    """Move a chunk to a folder (or remove from folder if folder=null)."""
    if not set_chunk_folder(chunk_id, body.folder, user_id):
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {"updated": chunk_id, "folder": body.folder}


@router.get("/folders")
def list_folders(user_id: str = Depends(get_current_user_id)):
    """List all distinct folder names."""
    return {"folders": get_folders(user_id)}
