from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from intelligence.memory import calculate_retention, classify_retention
from intelligence.embeddings import embed_query
from intelligence.ranking import composite_score, recency_bonus
from intelligence.retrieval import query_similar
from database.db import get_chunk
from models.schemas import SearchRequest, SearchResponse, SearchResult
from routers._shared import parse_dt, time_ago, to_chunk_full
from routers.deps import get_current_user_id

router = APIRouter()


def _recency_bonus(created_at: str) -> float:
    """Exponential decay of 'how recent' the chunk is, used as a small ranking signal."""
    dt = parse_dt(created_at)
    days = (datetime.now(tz=timezone.utc) - dt).days
    return recency_bonus(days)


@router.post("/search", response_model=SearchResponse)
def context_search(body: SearchRequest, user_id: str = Depends(get_current_user_id)):
    if not body.context.strip():
        raise HTTPException(status_code=400, detail="Context cannot be empty.")

    q_emb = embed_query(body.context)
    raw = query_similar(q_emb, user_id, n_results=50)

    if not raw["ids"]:
        return SearchResponse(results=[], discovery=None)

    scored: list[tuple[float, float, dict]] = []
    for cid, sim in zip(raw["ids"], raw["similarities"]):
        row = get_chunk(cid, user_id)
        if row is None:
            continue
        last_accessed = parse_dt(row["last_accessed"])
        r = calculate_retention(last_accessed, row["access_count"], row["complexity_score"])
        recency = _recency_bonus(row["created_at"])
        composite = composite_score(sim, r, recency)
        scored.append((composite, r, dict(row)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(body.limit, 10)]

    sim_map = {cid: s for cid, s in zip(raw["ids"], raw["similarities"])}
    best_discovery_score = -1.0
    discovery_idx = None
    for i, (_composite, r, row) in enumerate(top[:10]):
        du = 1.0 - r
        sim = sim_map.get(row["id"], 0.0)
        ds = du * sim
        if ds > best_discovery_score and r < 0.5:
            best_discovery_score = ds
            discovery_idx = i

    results: list[SearchResult] = []
    discovery_result: SearchResult | None = None

    for i, (composite, r, row) in enumerate(top[: body.limit]):
        last_accessed = parse_dt(row["last_accessed"])
        is_disc = i == discovery_idx
        sr = SearchResult(
            chunk_id=row["id"],
            content=row["content"][:400],
            source_file=row["source_file"],
            category=row["category"],
            retention=round(r, 4),
            status=classify_retention(r),
            relevance_score=round(composite, 4),
            is_discovery=is_disc,
            time_ago=time_ago(last_accessed),
        )
        results.append(sr)
        if is_disc:
            discovery_result = sr

    return SearchResponse(results=results, discovery=discovery_result)


@router.get("/search")
def search_get(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
):
    """GET /api/search?q=... — frontend-compatible endpoint."""
    q_emb = embed_query(q)
    raw = query_similar(q_emb, user_id, n_results=50)

    if not raw["ids"]:
        return {"results": [], "query": q, "total": 0}

    scored = []
    for cid, sim in zip(raw["ids"], raw["similarities"]):
        row = get_chunk(cid, user_id)
        if row is None:
            continue
        last_accessed = parse_dt(row["last_accessed"])
        r = calculate_retention(last_accessed, row["access_count"], row["complexity_score"])
        recency = _recency_bonus(row["created_at"])
        composite = composite_score(sim, r, recency)
        scored.append((composite, r, dict(row), sim))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = [
        {"chunk": to_chunk_full(row, r), "score": round(composite, 4), "highlight": None}
        for composite, r, row, _sim in scored[:limit]
    ]
    return {"results": results, "query": q, "total": len(results)}
