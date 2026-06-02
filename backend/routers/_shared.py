"""Helpers shared across router modules.

Centralizes the small datetime/formatting/chunk-shape utilities that were
previously duplicated in fading.py, chunks.py, search.py, discovery.py,
stats.py, and health.py.
"""

from datetime import datetime, timezone

from intelligence.ranking import display_complexity_k, display_stability


def parse_dt(s: str) -> datetime:
    """Parse an ISO timestamp. Treats naive datetimes as UTC."""
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def time_ago(dt: datetime) -> str:
    """Render a tz-aware datetime as a coarse 'Nh / Nd / Nmo ago' string."""
    delta = datetime.now(tz=timezone.utc) - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours}h ago" if hours else "just now"
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


_FILE_EXTS = {"pdf", "docx", "txt", "md", "html", "htm", "rst", "json"}


def to_chunk_full(row: dict, retention: float) -> dict:
    """Normalize a chunk DB row into the wire shape used by /api/search,
    /api/discovery, and other 'rich chunk' responses.

    Computes stability_S and complexity_k from access_count and complexity_score.
    Splits source_file into a (source_type, source_name) pair: 'file' for known
    extensions, otherwise 'note'.
    """
    access_count = row["access_count"]
    complexity_score = row["complexity_score"]
    stability_s = display_stability(access_count)
    complexity_k = display_complexity_k(complexity_score)

    source_file = row["source_file"] or ""
    ext = source_file.rsplit(".", 1)[-1].lower() if "." in source_file else ""
    if ext in _FILE_EXTS:
        source_type = "file"
        source_name = source_file.replace("\\", "/").split("/")[-1]
    else:
        source_type = "note"
        source_name = source_file or "manual entry"

    return {
        "id": row["id"],
        "content": row["content"][:400],
        "source_type": source_type,
        "source_name": source_name,
        "category": row["category"] or "general",
        "created_at": row["created_at"],
        "last_accessed": row["last_accessed"],
        "access_count": access_count,
        "stability_S": stability_s,
        "complexity_k": complexity_k,
        "retention": round(retention, 4),
        "tags": [],
    }
