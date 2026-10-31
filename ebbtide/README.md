# Ebbtide MCP server

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

With [uv](https://docs.astral.sh/uv/), on Linux or an Apple silicon Mac (macOS 14 or later):

```bash
uv tool install git+https://github.com/aimsotrash/Ebbtide
claude mcp add ebbtide -s user -- ebbtide
```

The first command installs two commands, `ebbtide` and `ebbtide-panel`, in an isolated
environment with CPU-only PyTorch (about 1.2 GB on disk). `-s user` makes Ebbtide available in
every project; without it, Claude Code would use it only in the folder you ran it from. To
update later, run `uv tool upgrade ebbtide`.

Other MCP clients take the same server as a `uvx` command:

```json
{
  "mcpServers": {
    "ebbtide": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/aimsotrash/Ebbtide", "ebbtide"]
    }
  }
}
```

`uvx` installs on the first launch, which takes a minute or two and can outlast a client's
startup timeout. Running `uvx --from git+https://github.com/aimsotrash/Ebbtide ebbtide < /dev/null`
once in a terminal does that install ahead of time.

The first `remember` or `recall` in a session takes about 5 seconds while the embedding
model (`all-MiniLM-L6-v2`) loads, and the very first run also downloads it (~90 MB).
After that, a call takes about 10 ms.

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

They call every tool through an in-process MCP client and fetch the panel through its
HTTP handler, with a stub embedder and a fake clock, so they never load the embedding model or need
PyTorch.
