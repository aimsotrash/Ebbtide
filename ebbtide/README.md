# Ebbtide MCP server

Long-term memory for AI agents, served over the Model Context Protocol (stdio). Recall
fuses keyword search (BM25) with embedding search. Each memory fades along a forgetting
curve unless it is recalled, and each recall makes it last longer. When the store is full,
the weakest memory goes. The memory model and its
policies live in [`intelligence/memory/agent.py`](../intelligence/memory/agent.py); this
package adds the tools and SQLite persistence.

## Tools

| Tool | What it does |
|---|---|
| `remember(text, tags?)` | Stores one memory: one fact, preference, decision or lesson, up to the 256 tokens (about 1,000 characters) the embedding model reads. Returns its id, the ids of any memories the budget pushed out, and up to 3 existing memories with a cosine similarity of 0.5 or more, so the agent can forget an older version. |
| `recall(query, k=5)` | Returns the `k` most relevant memories (at most 20), ranked by BM25 fused with embedding similarity, each with its strength just before this recall. Recalling strengthens a memory. |
| `update(id, text)` | Replaces a memory's text when a fact changes. It keeps its id and earned stability, and starts again at full strength. |
| `forget(id)` | Deletes a memory permanently. |
| `memory_stats()` | Reports the count, budget, policy, mean strength, and how many memories have ever been stored. |

## Resources

Reading a resource is not recalling: neither one strengthens a memory.

| Resource | What it holds |
|---|---|
| `ebbtide://memories` | Every kept memory, strongest first, with its strength now. |
| `ebbtide://memories/{id}` | One memory by its id. |

## Prompts

| Prompt | What it asks the agent to do |
|---|---|
| `recall_first(question)` | Recall what's relevant before answering the question. |
| `save_session()` | Store each fact, preference, decision or lesson from the conversation worth keeping. |

## Setup

With [uv](https://docs.astral.sh/uv/), on Linux, Windows, or an Apple silicon Mac (macOS 14 or
later):

```bash
uv tool install ebbtide==0.3.1
claude mcp add ebbtide -s user -- ebbtide
```

The first command installs two commands, `ebbtide` and `ebbtide-panel`, from PyPI in an
isolated environment of about 180 MB. `-s user` makes Ebbtide available in
every project; without it, Claude Code would use it only in the folder you ran it from. To
update later, run `uv tool upgrade ebbtide`. To run the latest commit instead of the latest
release, install `git+https://github.com/aimsotrash/Ebbtide` in place of `ebbtide`.

Other MCP clients take the same server as a `uvx` command:

```json
{
  "mcpServers": {
    "ebbtide": {
      "command": "uvx",
      "args": ["ebbtide==0.3.1"]
    }
  }
}
```

`uvx` installs on the first launch. If that outlasts a client's startup timeout, run
`uvx ebbtide==0.3.1 < /dev/null` once in a terminal to install ahead of time.

The embedding model is `all-MiniLM-L6-v2`, run through ONNX Runtime. The very first
`remember` or `recall` downloads it (~90 MB) into `~/.cache/ebbtide` and checks it against a
pinned SHA-256; after that it loads from disk in under a second, and a call takes a few
milliseconds.

## Panel

```bash
ebbtide-panel        # then open http://127.0.0.1:8765
```

A quiet local page beside the agent: every memory, strongest first, with its strength,
half-life and recall count. It reads the same database read-only every 2 seconds, so a
`remember`, a `recall` or an eviction shows up as it happens. The look-ahead slider shows
how strong each memory would be after that many more days without a recall: the recalled
ones fade more slowly. It listens on 127.0.0.1 only and loads nothing from the internet.

For a demo that shouldn't touch your real memories, point both at a scratch database: set
`EBBTIDE_DB=/tmp/ebbtide-demo.db` for the panel, and pass `-e EBBTIDE_DB=/tmp/ebbtide-demo.db`
when you register the server. Once a first run has downloaded the embedding model, the server
loads it from disk and never goes online, so venue Wi-Fi doesn't matter.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `EBBTIDE_DB` | `~/.local/share/ebbtide/memory.db` | SQLite file holding the memories and their embeddings. |
| `EBBTIDE_POLICY` | `ebbtide-count` | A policy name from `intelligence.memory.POLICIES`. Of the forgetting-curve policies, the default scored best on the benchmark's dev split at the 25% and 50% budgets; see [`bench/RESULTS.md`](../bench/RESULTS.md). |
| `EBBTIDE_BUDGET` | `1000` | The most memories kept. `keep-all` ignores it. |

Pass them with `-e` when you register the server, and give the panel the same values, since it
reads them from its own environment. Each tool call is one SQLite
transaction, so two agents can share one database safely.

## Test

From the repo root:

```bash
uv venv -p 3.12 .venv && uv pip install --python .venv -r requirements-test.txt
.venv/bin/python -m pytest ebbtide/tests/
```

They call every tool through an in-process MCP client, run two writers against one database,
and fetch the panel through its HTTP handler, with a stub embedder and a fake clock, so they
never load the embedding model.
