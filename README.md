# Engram

[![CI](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml/badge.svg)](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml)

**Long-term memory for AI agents that forgets on purpose, and the notes app it grew out of.**

Engram started as **Dory.md**, built in 48 hours at **UWB Hacks 2026** (MLH) by a
team of three. This repository continues the project from my last commit to the team
repository on June 7, 2026. The team repository,
[vaishnavi1064/Dory.md](https://github.com/vaishnavi1064/Dory.md), has since gone its
own way. The memory for AI agents, from October 2026, is my own work.

**Live:** [aimsotrash-engram.vercel.app](https://aimsotrash-engram.vercel.app)

## Memory for AI agents

[`engram_mcp/`](engram_mcp/README.md) is an MCP server that gives an agent such as Claude
Code long-term memory across sessions, through four tools: `remember`, `recall`, `forget`
and `memory_stats`. Each memory fades along a forgetting curve unless it is recalled, and
every recall makes it last longer. When the store reaches its budget, 1000 memories by
default, the weakest one goes first. The memories live in a SQLite file on your machine,
and only what a recall returns enters the agent's context.

A local panel lists the memories and how strong each one is, with a slider that looks
ahead to show which ones are fading. Setup is three commands; see
[`engram_mcp/README.md`](engram_mcp/README.md).

### Should an agent forget?

I replayed six memory policies on two public long-conversation benchmarks and measured
whether the memory still finds the evidence each question needs.
[LongMemEval](bench/RESULTS.md) has 500 questions with histories of about 490 turns;
settings were picked on 100 dev questions, and the other 400 were scored once.
[LoCoMo](bench/RESULTS-locomo.md) has 10 conversations that span 5 to 10 months, and
nothing was tuned on it.

- **Keeping everything wins when you can afford it.** With room for half the history, the
  best forgetting policy finds all the evidence for 37% of LongMemEval questions and 27% of
  LoCoMo questions. Keeping everything finds it for 58.5% and 44.6%.
- **No forgetting rule wins everywhere.** On LongMemEval, keeping what gets used beats
  keeping the newest. On LoCoMo, keeping the newest does best at the turn level.
- **Strengthening on recall beats plain LRU, modestly.** engram-count, the server's
  default, keeps up to 4 points more of the evidence than LRU on LongMemEval, and finds the
  right sessions up to 14 points more often. On LoCoMo, where this comparison was named
  before the run, it held, with smaller gains: up to 1.6 and 3.4 points.
- **Strengthening too hard backfires on facts that change.** FSRS-style spacing made old
  facts stick: on LongMemEval's knowledge-update questions it found the newest fact 12 to
  17 points less often than LRU.
- **Fading didn't help as a ranking signal.** Tuning picked similarity alone almost
  everywhere, so the gains come from what is kept, not from how it is ranked.

MemoryBank (Zhong et al., 2023) already applied an Ebbinghaus curve to LLM memory. What is
new here is the measured comparison with simple baselines, losses included.

## The notes app

Engram splits your notes into chunks and gives each chunk a retention score that
decays along an Ebbinghaus forgetting curve. That score is a ranking signal, not just
a number on a dashboard. Search puts what you're forgetting first, reviews are
scheduled with FSRS, and quizzes are built from your weakest material.

- **Decay-aware semantic search.** Sentence-transformer embeddings in ChromaDB,
  re-ranked by how close each match is to being forgotten.
- **Ingestion from many formats.** PDF, Word, HTML, Markdown and plain-text files,
  plus Notion pages through OAuth.
- **Spaced repetition and quizzes.** FSRS review scheduling and LLM-generated
  quizzes, with fallbacks when no model key is configured.
- **Knowledge-tree dashboard.** An interactive map of your notes and how well you
  remember them.

## Who built what

Share of the code, counted with `git blame -w -M -C -C` over the code files (Python,
TypeScript and JavaScript, CSS, HTML, SQL, shell and config files). Moved and copied lines keep their original
author, and `.mailmap` merges each person's commit identities, so anyone can
reproduce these numbers from this repository's history.

| Snapshot | Lines of code | Nikhil Pawar | Vaishnavi Chaughule | Shraddha Deshpande |
| --- | ---: | ---: | ---: | ---: |
| End of the hackathon, Apr 26, 2026 (`f6f9657`) | 14,371 | 62.5% | 22.5% | 15.0% |
| My last commit to the team repo, Jun 7, 2026 (`18d440e`, on the `Fix-login` branch) | 10,722 | 91.7% | 2.4% | 5.8% |

At the hackathon I wrote the FastAPI backend and most of the React app, building on
Shraddha's first version of the frontend. Vaishnavi wrote a separate intelligence
package. In May and June I rebuilt `intelligence/` around the backend's own
forgetting-curve engine, and that is the version in this repository.

## My part

- the FastAPI service and the API contract the React frontend calls
- multi-format ingestion, sentence-transformer embeddings, and SQLite + ChromaDB
  persistence
- the NumPy-vectorized forgetting-curve engine, 50–100x faster than per-chunk loops,
  which drives decay-aware search
- FSRS review scheduling and the retention-aware ranking
- bcrypt + JWT authentication with per-user data isolation, and the Notion OAuth
  import
- the June 2026 security pass: no hardcoded JWT secret, the demo account limited to
  dev, an explicit CORS allow-list, pinned dependencies, CI with dependency scans, a
  backup utility for both stores, and a P0 security test suite
- deployment: the Vercel frontend, and the backend, first on Railway (where switching
  to CPU-only PyTorch cut the image from 5.8 GB to about 1.5 GB) and now on Hugging
  Face Spaces
- frontend features: login and registration, the note editor, the knowledge-tree
  dashboard and the theme switcher
- memory for AI agents (October 2026): the forgetting-curve memory store and its six
  policies, the MCP server and its panel, and the LongMemEval and LoCoMo benchmark
  harnesses

## The hackathon team

- [Nikhil Pawar](https://github.com/aimsotrash): backend, the forgetting-curve
  engine, most of the frontend
- [Shraddha Deshpande](https://github.com/deshpandesk8): the first version of the
  React frontend
- [Vaishnavi Chaughule](https://github.com/vaishnavi1064): the hackathon
  intelligence package

## Stack

FastAPI · Python · MCP · sentence-transformers · ChromaDB · SQLite · FSRS · React ·
TypeScript · Vite · Tailwind CSS · Framer Motion

## Run it locally

```bash
# backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # optional: add an LLM key for quizzes and AI actions
.venv/bin/uvicorn main:app --port 8001

# frontend, in a second terminal
cd frontend
npm install
cp .env.example .env.local      # VITE_API_BASE_URL=http://localhost:8001
npm run dev
```

The MCP server has its own setup in [`engram_mcp/README.md`](engram_mcp/README.md). To
reproduce the benchmarks, after installing `engram_mcp/requirements.txt`:

```bash
python -m bench.longmemeval embed   # downloads the data and embeds it once, ~45 min on a laptop CPU
python -m bench.longmemeval run     # writes bench/RESULTS.md
python -m bench.locomo              # writes bench/RESULTS-locomo.md
```

The landing page for the MCP server lives in `site/` (Vite, React and Tailwind):

```bash
cd site && npm install && npm run dev   # http://localhost:5173
```

The app's environment variables keep the project's original `DORY_` prefix; those of
the agent-memory MCP server ([`engram_mcp/`](engram_mcp/README.md)) use `ENGRAM_`. They
are all listed in [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md), including the ones
production needs.

Tests (79: 51 backend, 22 intelligence, 2 MCP server, 4 benchmark) need only the light
dependency set:

```bash
pip install -r backend/requirements-test.txt
(cd backend && DORY_ENV=dev DORY_SKIP_WARMUP=1 python -m pytest tests/)
DORY_ENV=dev DORY_SKIP_WARMUP=1 python -m pytest intelligence/tests/
python -m pytest engram_mcp/tests/ bench/
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

[MIT](LICENSE). The code from the hackathon stays under the team's original notice,
"Dory.md contributors".
