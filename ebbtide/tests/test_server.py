"""Ebbtide MCP server: every tool through an in-process MCP client, on a temporary
database, with a fake clock and a stub embedder, so no model loads."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace

from mcp import Client

from ebbtide import server
from intelligence import embeddings

DAY = 86400.0
WORDS = ["coffee", "black", "deploy", "python", "cat", "tea"]


def _embed(text):  # bag of words over a tiny vocabulary; the constant keeps it nonzero
    return [text.lower().count(w) for w in WORDS] + [0.1]


def test_tools_round_trip(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    db = tmp_path / "memory.db"
    monkeypatch.setenv("EBBTIDE_DB", str(db))
    monkeypatch.setenv("EBBTIDE_BUDGET", "2")
    monkeypatch.delenv("EBBTIDE_POLICY", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", _embed)
    monkeypatch.setattr(embeddings, "fits", lambda text: True)
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
    assert [r.structured_content for r in first[:2]] == [{"id": 1, "evicted": [], "similar": []},
                                                        {"id": 2, "evicted": [], "similar": []}]
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
        {"memories": 2, "budget": 2, "policy": "ebbtide-count", "mean_strength": 0.781, "stored_ever": 2},
        {"id": 3, "evicted": [2], "similar": []},
        {"result": True},
        {"result": False},
        {"id": 4, "evicted": [], "similar": []},  # id 3 was deleted, and is not handed out again
    ]
    rows = sqlite3.connect(db).execute("SELECT id, round(stability, 1), recall_count FROM memories ORDER BY id").fetchall()
    assert rows == [(1, 1.3, 1), (4, 1.0, 0)]  # one recall: S = 1 + 0.5 ln 2


def test_resources_and_prompts(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    db = tmp_path / "memory.db"
    monkeypatch.setenv("EBBTIDE_DB", str(db))
    monkeypatch.delenv("EBBTIDE_BUDGET", raising=False)
    monkeypatch.delenv("EBBTIDE_POLICY", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", _embed)
    monkeypatch.setattr(embeddings, "fits", lambda text: True)
    monkeypatch.setattr(server, "time", SimpleNamespace(time=lambda: clock.now))

    async def session():
        async with Client(server.mcp) as client:
            await client.call_tool("remember", {"text": "I take my coffee black"})
            clock.now = 3 * DAY
            await client.call_tool("remember", {"text": "We deploy with Python 3.12"})
            listed = await client.read_resource("ebbtide://memories")
            one = await client.read_resource("ebbtide://memories/1")
            missing = None
            try:
                await client.read_resource("ebbtide://memories/99")
            except Exception as error:  # the client raises on a resource error
                missing = error
            prompts = await client.list_prompts()
            asked = await client.get_prompt("recall_first", {"question": "How do I take coffee?"})
            return listed, one, missing, prompts, asked

    listed, one, missing, prompts, asked = asyncio.run(session())
    rows = json.loads(listed.contents[0].text)
    assert [r["id"] for r in rows] == [2, 1]  # strongest first: the fresh memory leads
    assert json.loads(one.contents[0].text)["strength"] == 0.717  # e^(-72 h / 216 h)
    assert missing is not None
    # Reading is not recalling: nothing was strengthened.
    assert sqlite3.connect(db).execute("SELECT sum(recall_count) FROM memories").fetchone() == (0,)
    assert {p.name for p in prompts.prompts} == {"recall_first", "save_session"}
    assert "How do I take coffee?" in asked.messages[0].content.text


def test_update_similar_hints_and_length_check(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    db = tmp_path / "memory.db"
    monkeypatch.setenv("EBBTIDE_DB", str(db))
    monkeypatch.delenv("EBBTIDE_BUDGET", raising=False)
    monkeypatch.delenv("EBBTIDE_POLICY", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", _embed)
    monkeypatch.setattr(embeddings, "fits", lambda text: len(text) < 60)  # stands in for 256 tokens
    monkeypatch.setattr(server, "time", SimpleNamespace(time=lambda: clock.now))

    async def session(steps):
        async with Client(server.mcp) as client:
            results = []
            for day, tool, args in steps:
                clock.now = day * DAY
                results.append(await client.call_tool(tool, args))
            return results

    out = asyncio.run(session([
        (0, "remember", {"text": "I take my coffee black"}),
        (0, "remember", {"text": "We deploy with Python 3.12"}),
        (5, "remember", {"text": "Now I take my coffee black with tea"}),  # close to memory 1
        (9, "update", {"id": 1, "text": "I take my coffee with tea"}),
        (9, "update", {"id": 99, "text": "nothing here"}),
        (9, "remember", {"text": "coffee " * 20}),  # longer than the model reads
        (9, "update", {"id": 2, "text": "   "}),
    ]))
    hint = out[2].structured_content["similar"]
    assert [h["id"] for h in hint] == [1] and hint[0]["similarity"] >= server.SIMILAR
    assert out[3].structured_content == {"id": 1, "text": "I take my coffee with tea"}
    assert out[4].is_error and out[5].is_error and out[6].is_error
    rows = sqlite3.connect(db).execute(
        "SELECT id, text, last_recalled_at FROM memories ORDER BY id").fetchall()
    assert rows[0] == (1, "I take my coffee with tea", 9 * DAY)  # corrected, and fresh again
    assert [r[0] for r in rows] == [1, 2, 3]  # the failed calls stored nothing


def test_two_agents_sharing_a_database_lose_nothing(tmp_path, monkeypatch):
    """The README's claim: each call is one SQLite transaction, so concurrent writers are safe."""
    import threading

    db = tmp_path / "memory.db"
    monkeypatch.setenv("EBBTIDE_DB", str(db))
    monkeypatch.delenv("EBBTIDE_BUDGET", raising=False)
    monkeypatch.delenv("EBBTIDE_POLICY", raising=False)
    monkeypatch.setattr(embeddings, "embed_query", _embed)
    monkeypatch.setattr(embeddings, "fits", lambda text: True)

    def agent(name):
        for i in range(25):
            server.remember(f"{name} note {i} about coffee")

    threads = [threading.Thread(target=agent, args=(n,)) for n in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = sqlite3.connect(db).execute("SELECT id, text FROM memories").fetchall()
    assert len(rows) == 50 and len({i for i, _ in rows}) == 50


def test_bad_settings_fail_at_startup(monkeypatch):
    monkeypatch.setenv("EBBTIDE_POLICY", "no-such-policy")
    try:
        server._config()
    except ValueError as error:
        assert "EBBTIDE_POLICY" in str(error)
    else:
        raise AssertionError("an unknown policy was accepted")
