# Ebbtide MCP

[![CI](https://github.com/aimsotrash/Ebbtide/actions/workflows/ci.yml/badge.svg)](https://github.com/aimsotrash/Ebbtide/actions/workflows/ci.yml)
[![MCP Badge](https://lobehub.com/badge/mcp/aimsotrash-ebbtide)](https://lobehub.com/mcp/aimsotrash-ebbtide)

**Local long-term memory for AI agents: hybrid search over what you've told it, with a
forgetting curve that keeps a bounded store to what keeps mattering.**

Ebbtide MCP is a memory server, not the zombie strategy game of the same name. It was called
Engram until October 31, 2026; I renamed it because several other memory servers for AI agents
already use that name. It began as a notes app, whose last version is the git tag
[`notes-app`](https://github.com/aimsotrash/Ebbtide/tree/notes-app).

**Live:** [aimsotrash-ebbtide.vercel.app](https://aimsotrash-ebbtide.vercel.app)

## Install

With [uv](https://docs.astral.sh/uv/), on Linux, Windows, or an Apple silicon Mac (macOS 14 or
later). For Claude Code:

```bash
uv tool install ebbtide==0.3.0
claude mcp add ebbtide -s user -- ebbtide
```

For any other MCP client, add this to its configuration:

```json
{
  "mcpServers": {
    "ebbtide": {
      "command": "uvx",
      "args": ["ebbtide==0.3.0"]
    }
  }
}
```

The install is about 180 MB: ONNX Runtime rather than PyTorch. The first `remember` or
`recall` downloads the 90 MB embedding model and checks it against a pinned SHA-256; after
that, Ebbtide never goes online. The examples pin a version because the project is young; drop
`==0.3.0` to track the latest. Settings and the memory panel are in
[`ebbtide/README.md`](ebbtide/README.md).

## What it does

Five tools:

| Tool | What it does |
|---|---|
| `remember(text, tags?)` | Stores one fact, preference, decision or lesson. Returns similar memories already stored, so the agent can drop an older version instead of keeping both. |
| `recall(query, k)` | The most relevant memories, by keyword search (BM25) fused with embedding search. Recalling a memory strengthens it. |
| `update(id, text)` | Corrects a memory in place when a fact changes. |
| `forget(id)` | Deletes a memory. |
| `memory_stats()` | Count, budget, policy and mean strength. |

Two resources, `ebbtide://memories` and `ebbtide://memories/{id}`, let a client attach
memories as context; reading one never strengthens it. Two prompts, `recall_first` and
`save_session`, start the common workflows. A local panel shows every memory and how strong it
is, with a slider that looks ahead to show which ones are fading.

Everything lives in one SQLite file on your machine, and only what a recall returns enters the
agent's context. Each tool call is one transaction, so two agents can share a database.

## Choosing a policy

Each memory fades along a forgetting curve unless it is recalled, and every recall makes it
last longer. Fading only matters once the store is full: **until it holds its budget, 1000
memories by default, nothing is forgotten** and Ebbtide is a local hybrid-search memory. At the
budget, the weakest memory goes first.

By the benchmarks below, keeping everything retrieves best when you can afford it. If you'd
rather never lose a memory, set `EBBTIDE_POLICY=keep-all`; the store then grows without limit.
The default, `ebbtide-count`, is for a bounded store: of the forgetting rules tested, it kept the
most of what later questions needed.

## Should an agent forget?

I replayed six memory policies on two public long-conversation benchmarks and measured
whether the memory still finds the evidence each question needs.
[LongMemEval](bench/RESULTS.md) has 500 questions with histories of about 490 turns;
its 30 abstention questions have no evidence to find, so 470 are scored. Settings were picked on
92 dev questions and fixed before the other 378 were first scored.
[LoCoMo](bench/RESULTS-locomo.md) has 10 conversations that span 5 to 10 months, and
nothing was tuned on it.

- **Retrieval mattered more than forgetting.** Fusing keyword search with the embeddings,
  untuned, raised keep-all's turn_all@10 from 58.5 to 69.8 on LongMemEval and from 44.6 to 53.3
  on LoCoMo, with 95% intervals above zero
  ([RESULTS-hybrid.md](bench/RESULTS-hybrid.md)). That is a bigger gain than any forgetting
  rule produced, so the server now ranks this way. It lost ground on preference questions
  (−12.5 points, 24 questions, interval crossing zero).
- **Keeping everything wins when you can afford it.** With room for half the history, the
  best forgetting policy finds all the evidence in its top 10 results for 37% of LongMemEval
  questions and 27% of LoCoMo questions. Keeping everything does for 58.5% and 44.6% (with
  embedding-only ranking).
- **No forgetting rule wins everywhere.** On LongMemEval, keeping what gets used beats
  keeping the newest. On LoCoMo, keeping the newest does best at the turn level.
- **Strengthening on recall beats plain LRU, modestly.** ebbtide-count keeps up to 4 points
  more of the evidence than LRU on LongMemEval, and ranks every answer session in its top 10
  up to 14 points more often; I chose these comparisons after seeing the results. On LoCoMo,
  where I chose the comparison before running it, both gains held but were smaller (up to 1.6
  and 3.4 points), and it found all the evidence in its top 10 about as often as LRU.
- **Strengthening too hard backfires on facts that change.** FSRS-style spacing made old
  facts stick: on LongMemEval's knowledge-update questions it found the newest fact 12 to
  17 points less often than LRU. This is why `update` exists, and why `remember` points out
  similar memories.
- **Fading didn't help as a ranking signal.** Tuning picked similarity alone almost
  everywhere, so the gains come from what is kept, not from how it is ranked.

**Reading the numbers.** turn_all@10 is strict: a question counts only if every evidence turn
is in the top 10 results. It measures retrieval, not answers, so it isn't comparable to the
answer-accuracy percentages, often in the 90s, that other memory projects report with an LLM
grading the answers.

MemoryBank (Zhong et al., 2023) already applied an Ebbinghaus curve to LLM memory. What is
new here is the measured comparison with simple baselines, losses included.

## Limitations

- **Recall strengthens whatever it returns,** whether or not the agent used it, so a memory
  that resembles many queries can stay strong. The benchmarks measured exactly this behavior.
- **The benchmark agent recalls at every user turn,** five memories at a time. A real agent
  recalls less often, so which memories survive a full store may differ in practice.
- **Hybrid ranking was measured at question time.** The budgeted replays that decide what is
  kept used embedding-only recalls.
- **The embedding model is small and reads 256 tokens** (about 1,000 characters), so
  `remember` refuses longer text and asks for one fact per memory. It works best in English.
- **"Similar" is a heuristic:** a cosine similarity of 0.5 or more, set from a handful of
  hand-made pairs. Ebbtide never deletes or merges memories by itself.
- **It's young:** renamed on October 31, 2026, with version 0.3.0 the first on ONNX Runtime.
  Pin a version.

## Stack

Python · MCP · ONNX Runtime · NumPy · SQLite · React · TypeScript · Vite · Tailwind CSS · Motion

## Run it locally

To run the MCP server, follow the setup in [`ebbtide/README.md`](ebbtide/README.md).

To reproduce the benchmarks, from the repo root:

```bash
uv venv -p 3.12 .venv && uv pip install --python .venv -e .
.venv/bin/python -m bench.longmemeval embed   # downloads the data and embeds it once, ~45 min on a laptop CPU
.venv/bin/python -m bench.longmemeval run     # writes bench/RESULTS.md
.venv/bin/python -m bench.locomo              # writes bench/RESULTS-locomo.md
.venv/bin/python -m bench.hybrid              # writes bench/RESULTS-hybrid.md
```

The benchmark embeddings were made with sentence-transformers and PyTorch before Ebbtide moved
to ONNX Runtime. The two agree to a cosine similarity of at least 0.9999998 on about 4,000
sampled texts, including the longest, so the results stand.

The landing page lives in `site/` (Vite, React and Tailwind):

```bash
cd site && npm install && npm run dev   # http://localhost:5173
```

The Python tests (25: 15 intelligence, 6 MCP server, 4 benchmark) stub the embedding model,
so they need only `requirements-test.txt`, which adds pytest:

```bash
uv pip install --python .venv -r requirements-test.txt
.venv/bin/python -m pytest intelligence/tests ebbtide/tests bench
```

## References

- Di Wu et al. *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.*
  2024. [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)
- Adyasha Maharana et al. *Evaluating Very Long-Term Conversational Memory of LLM Agents.*
  ACL 2024. [arXiv:2402.17753](https://arxiv.org/abs/2402.17753). The LoCoMo data is
  CC BY-NC 4.0; it is downloaded, never committed, and used here for non-commercial research.
- Wanjun Zhong et al. *MemoryBank: Enhancing Large Language Models with Long-Term Memory.*
  2023. [arXiv:2305.10250](https://arxiv.org/abs/2305.10250)
- FSRS, the spaced-repetition scheduler whose default weights the spaced rule uses:
  [open-spaced-repetition](https://github.com/open-spaced-repetition)

## License

[MIT](LICENSE).
