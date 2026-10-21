# Engram MCP server

Long-term memory for AI agents, served over the Model Context Protocol (stdio). Each
memory fades along a forgetting curve unless it is recalled, and each recall makes it
last longer. When the store is full, the weakest memory goes. The memory model and its
policies live in [`intelligence/memory/agent.py`](../intelligence/memory/agent.py); this
package adds the tools and SQLite persistence.

## Tools

| Tool | What it does |
|---|---|
| `remember(text, tags?)` | Stores one memory. Returns its id and the ids of any memories the budget pushed out. |
| `recall(query, k=5)` | Returns the `k` most relevant memories (at most 20), each with its strength just before this recall. Recalling strengthens a memory. |
| `forget(id)` | Deletes a memory permanently. |
| `memory_stats()` | Reports the count, budget, policy, mean strength, and how many memories have ever been stored. |

## Setup

From the repo root, with Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r engram_mcp/requirements.txt
claude mcp add engram -e PYTHONPATH="$PWD" -- "$PWD/.venv/bin/python" -m engram_mcp
```

`PYTHONPATH` lets the server import `intelligence/` from wherever Claude Code starts it.
`claude mcp add` registers the server for the current project only; add `-s user` to
use it in every project.

The first `remember` or `recall` in a session takes about 5 seconds while the embedding
model (`all-MiniLM-L6-v2`) loads, and the very first run also downloads it (~90 MB).
After that, a call takes about 10 ms.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ENGRAM_DB` | `~/.local/share/engram/memory.db` | SQLite file holding the memories and their embeddings. |
| `ENGRAM_POLICY` | `engram-spaced` | A policy name from `intelligence.memory.POLICIES`. |
| `ENGRAM_BUDGET` | `1000` | The most memories kept. `keep-all` ignores it. |

Pass them with `-e` when you register the server. Each tool call is one SQLite
transaction, so two agents can share one database safely.

## Test

```bash
python -m pytest engram_mcp/tests/
```

It calls every tool through an in-process MCP client, with a stub embedder and a fake
clock, so it needs only `backend/requirements-test.txt`, not the embedding model.
