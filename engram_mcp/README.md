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

From the repo root, with Python 3.12, on Linux or an Apple silicon Mac (macOS 14 or later):

```bash
python3.12 -m venv .venv          # no python3.12? uv venv -p 3.12 .venv
.venv/bin/pip install -r engram_mcp/requirements.txt
claude mcp add engram -s user -e PYTHONPATH="$PWD" -- "$PWD/.venv/bin/python" -P -m engram_mcp
```

`PYTHONPATH` lets the server import `intelligence/` from wherever Claude Code starts it, and
`-P` stops Python from importing anything from that folder. `-s user` makes Engram available
in every project; without it, Claude Code would use it only inside this folder.

The first `remember` or `recall` in a session takes about 5 seconds while the embedding
model (`all-MiniLM-L6-v2`) loads, and the very first run also downloads it (~90 MB).
After that, a call takes about 10 ms.

## Panel

```bash
.venv/bin/python -m engram_mcp.panel        # then open http://127.0.0.1:8765
```

A quiet local page beside the agent: every memory, strongest first, with its strength,
half-life and recall count. It reads the same database read-only every 2 seconds, so a
`remember`, a `recall` or an eviction shows up as it happens. The look-ahead slider shows
how strong each memory would be after that many more days without a recall: the recalled
ones fade more slowly. It listens on 127.0.0.1 only and loads nothing from the internet.

For a demo that shouldn't touch your real memories, point both at a scratch database: set
`ENGRAM_DB=/tmp/engram-demo.db` for the panel, and pass `-e ENGRAM_DB=/tmp/engram-demo.db`
when you register the server. Once a first run has downloaded the embedding model, the server
loads it from disk and never goes online, so venue Wi-Fi doesn't matter.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ENGRAM_DB` | `~/.local/share/engram/memory.db` | SQLite file holding the memories and their embeddings. |
| `ENGRAM_POLICY` | `engram-count` | A policy name from `intelligence.memory.POLICIES`. Of the forgetting-curve policies, the default scored best on the benchmark's dev split at the 25% and 50% budgets; see [`bench/RESULTS.md`](../bench/RESULTS.md). |
| `ENGRAM_BUDGET` | `1000` | The most memories kept. `keep-all` ignores it. |

Pass them with `-e` when you register the server, and give the panel the same values, since it
reads them from its own environment. Each tool call is one SQLite
transaction, so two agents can share one database safely.

## Test

```bash
.venv/bin/pip install -r requirements-test.txt   # adds pytest
.venv/bin/python -m pytest engram_mcp/tests/
```

They call every tool through an in-process MCP client and fetch the panel through its
HTTP handler, with a stub embedder and a fake clock, so they never load the embedding model;
a venv with only [`requirements-test.txt`](../requirements-test.txt) runs them too.
