"""Engram MCP server: every tool through an in-process MCP client, on a temporary
database, with a fake clock and a stub embedder, so no model loads."""

import asyncio
import sqlite3
from types import SimpleNamespace

from mcp import Client

from engram_mcp import server
from intelligence import embeddings

DAY = 86400.0
WORDS = ["coffee", "black", "deploy", "python", "cat", "tea"]


def _embed(text):  # bag of words over a tiny vocabulary; the constant keeps it nonzero
    return [text.lower().count(w) for w in WORDS] + [0.1]


def test_tools_round_trip(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    db = tmp_path / "memory.db"
    monkeypatch.setenv("ENGRAM_DB", str(db))
    monkeypatch.setenv("ENGRAM_BUDGET", "2")
    monkeypatch.delenv("ENGRAM_POLICY", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", _embed)
    monkeypatch.setattr(server, "time", SimpleNamespace(time=lambda: clock.now))

    async def session(steps):
        """Run (day, tool, args) steps in one client session; return each result."""
        async with Client(server.mcp) as client:
            results = []
            for day, tool, args in steps:
                clock.now = day * DAY
                results.append(await client.call_tool(tool, args))
            return results

    first = asyncio.run(session([
        (0, "remember", {"text": "I take my coffee black", "tags": ["preference"]}),
        (0, "remember", {"text": "We deploy with Python 3.12"}),
        (3, "recall", {"query": "how do I take coffee", "k": 1}),
        (3, "remember", {"text": "   "}),
        (3, "recall", {"query": "   "}),
    ]))
    assert [r.structured_content for r in first[:2]] == [{"id": 1, "evicted": []}, {"id": 2, "evicted": []}]
    assert first[2].structured_content == {"result": [{
        "id": 1, "text": "I take my coffee black", "tags": ["preference"],
        "strength": 0.717, "created": "1970-01-01T00:00+00:00",  # e^(-72 h / 216 h)
    }]}
    assert first[3].is_error and first[4].is_error

    # A new session sees what the first one stored. The recalled coffee memory has
    # grown strong, so the budget pushes out the never-recalled deploy memory instead.
    second = asyncio.run(session([
        (4, "memory_stats", {}),
        (4, "remember", {"text": "My cat is called Miso"}),
        (4, "forget", {"id": 3}),
        (4, "forget", {"id": 3}),
        (4, "remember", {"text": "Green tea after lunch"}),
    ]))
    assert [r.structured_content for r in second] == [
        {"memories": 2, "budget": 2, "policy": "engram-count", "mean_strength": 0.781, "stored_ever": 2},
        {"id": 3, "evicted": [2]},
        {"result": True},
        {"result": False},
        {"id": 4, "evicted": []},  # id 3 was deleted, and is not handed out again
    ]
    rows = sqlite3.connect(db).execute("SELECT id, round(stability, 1), recall_count FROM memories ORDER BY id").fetchall()
    assert rows == [(1, 1.3, 1), (4, 1.0, 0)]  # one recall: S = 1 + 0.5 ln 2
