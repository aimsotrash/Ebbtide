# Engram

[![CI](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml/badge.svg)](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml)

**The notes app that knows what you're about to forget.**

Engram started as **Dory.md**, built in 48 hours at **UWB Hacks 2026** (MLH) by a
team of three. This repository continues the project from my last commit to the team
repository on June 7, 2026. The team repository,
[vaishnavi1064/Dory.md](https://github.com/vaishnavi1064/Dory.md), has since gone its
own way.

**Live:** [dory-md-fork.vercel.app](https://dory-md-fork.vercel.app)

## What it does

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

## The hackathon team

- [Nikhil Pawar](https://github.com/aimsotrash): backend, the forgetting-curve
  engine, most of the frontend
- [Shraddha Deshpande](https://github.com/deshpandesk8): the first version of the
  React frontend
- [Vaishnavi Chaughule](https://github.com/vaishnavi1064): the hackathon
  intelligence package

## Stack

FastAPI · Python · sentence-transformers · ChromaDB · SQLite · FSRS · React ·
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

The app's environment variables keep the project's original `DORY_` prefix; those of
the agent-memory MCP server ([`engram_mcp/`](engram_mcp/README.md)) use `ENGRAM_`. They
are all listed in [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md), including the ones
production needs.

Tests (74: 51 backend, 22 intelligence, 1 MCP server) need only the light dependency set:

```bash
pip install -r backend/requirements-test.txt
(cd backend && DORY_ENV=dev DORY_SKIP_WARMUP=1 python -m pytest tests/)
DORY_ENV=dev DORY_SKIP_WARMUP=1 python -m pytest intelligence/tests/
python -m pytest engram_mcp/tests/
```

## License

[MIT](LICENSE). The code from the hackathon stays under the team's original notice,
"Dory.md contributors".
