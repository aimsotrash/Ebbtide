"""
Engram as an MCP server: long-term memory for AI agents, over stdio.

Every tool call is one SQLite transaction: load the store, apply the call, write back
what changed. Nothing is kept between calls, so two agents sharing a database (two
Claude Code sessions, say) can't overwrite each other's memories.

  ENGRAM_DB      SQLite file, default ~/.local/share/engram/memory.db
  ENGRAM_POLICY  a name from intelligence.memory.POLICIES, default engram-count
  ENGRAM_BUDGET  most memories kept, default 1000
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from intelligence import embeddings
from intelligence.memory import POLICIES, Memory, MemoryStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- AUTOINCREMENT: a deleted id is never reused
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,               -- float32, unit length
    created_at REAL NOT NULL,              -- Unix seconds
    last_recalled_at REAL,
    stability REAL NOT NULL,
    recall_count INTEGER NOT NULL,
    source TEXT                            -- JSON, e.g. {"tags": [...]}
)
"""

mcp = MCPServer(
    "engram",
    instructions=(
        "Long-term memory that lasts across sessions. Memories fade unless they are "
        "recalled, and each recall makes one last longer. Use remember for facts, "
        "preferences and decisions worth keeping, one per call. Use recall when past "
        "context could help."
    ),
)


def _config() -> tuple[Path, str, int]:
    db = Path(os.environ.get("ENGRAM_DB", "~/.local/share/engram/memory.db")).expanduser()
    policy = os.environ.get("ENGRAM_POLICY", "engram-count")
    if policy not in POLICIES:
        raise ValueError(f"ENGRAM_POLICY must be one of {sorted(POLICIES)}, got {policy!r}")
    return db, policy, int(os.environ.get("ENGRAM_BUDGET", "1000"))


def _stored_ever(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'memories'").fetchone()
    return row[0] if row else 0


def _load(conn: sqlite3.Connection, policy: str, budget: int) -> MemoryStore:
    rows = conn.execute(
        "SELECT id, text, embedding, created_at, last_recalled_at, stability, recall_count,"
        " source FROM memories ORDER BY id"
    ).fetchall()
    memories = [
        Memory(i, text, np.frombuffer(emb, np.float32), created, recalled, s, n,
               json.loads(source) if source else None)
        for i, text, emb, created, recalled, s, n, source in rows
    ]
    return MemoryStore(POLICIES[policy], budget, memories, next_id=_stored_ever(conn) + 1)


@contextmanager
def _store():
    """Yield (connection, store) inside one write transaction; commit if no error."""
    db, policy, budget = _config()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, isolation_level=None)  # transactions by hand, below
    try:
        conn.execute(_SCHEMA)
        conn.execute("BEGIN IMMEDIATE")  # one writer at a time, across processes too
        yield conn, _load(conn, policy, budget)
        conn.execute("COMMIT")
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="minutes")


@mcp.tool()
def remember(text: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Store one thing worth remembering across sessions: a fact, preference, decision
    or lesson. Returns its id, and the ids of any memories the budget pushed out."""
    if not text.strip():
        raise ToolError("text is empty")
    embedding = embeddings.embed_query(text)  # outside the transaction: the first call loads the model
    with _store() as (conn, store):
        before = {m.id for m in store.memories}
        memory = store.add(text, embedding, time.time(), source={"tags": tags} if tags else None)
        evicted = sorted(before - {m.id for m in store.memories})
        conn.executemany("DELETE FROM memories WHERE id = ?", [(i,) for i in evicted])
        conn.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (memory.id, memory.text, memory.embedding.tobytes(), memory.created_at, memory.last_recalled_at,
             memory.stability, memory.recall_count, json.dumps(memory.source) if memory.source else None),
        )
    return {"id": memory.id, "evicted": evicted}


@mcp.tool()
def recall(query: str, k: Annotated[int, Field(ge=1, le=20)] = 5) -> list[dict[str, Any]]:
    """The memories most relevant to a query, best first, each with its strength just
    before this recall (1 = fresh, near 0 = almost forgotten). Recalling a memory
    strengthens it, so recall when you need context, not to browse."""
    embedding = embeddings.embed_query(query)
    with _store() as (conn, store):
        now = time.time()
        strength = dict(zip((m.id for m in store.memories), store.retrievability(now)))
        hits = [m for m, _ in store.recall(embedding, k, now)]
        conn.executemany(
            "UPDATE memories SET last_recalled_at = ?, stability = ?, recall_count = ? WHERE id = ?",
            [(m.last_recalled_at, m.stability, m.recall_count, m.id) for m in hits],
        )
    return [
        {"id": m.id, "text": m.text, "tags": (m.source or {}).get("tags", []),
         "strength": round(float(strength[m.id]), 3), "created": _iso(m.created_at)}
        for m in hits
    ]


@mcp.tool()
def forget(id: int) -> bool:
    """Permanently delete one memory by its id. Returns whether it existed."""
    with _store() as (conn, store):
        found = store.forget(id)
        conn.execute("DELETE FROM memories WHERE id = ?", (id,))
    return found


@mcp.tool()
def memory_stats() -> dict[str, Any]:
    """How many memories are kept, the budget and policy, their average strength
    (1 = all fresh), and how many have ever been stored."""
    with _store() as (conn, store):
        stats = store.stats(time.time())
        stored_ever = _stored_ever(conn)
    mean = stats["mean_retrievability"]
    return {
        "memories": stats["count"],
        "budget": stats["budget"],
        "policy": _config()[1],
        "mean_strength": None if mean is None else round(mean, 3),
        "stored_ever": stored_ever,
    }


def main() -> None:
    _, policy, budget = _config()
    MemoryStore(POLICIES[policy], budget)  # a bad ENGRAM_* value fails here, not on the first call
    mcp.run()
