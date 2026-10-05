# Dory.md

**The notes app that knows what you're about to forget.** Built in 48 hours at
**UWB Hacks 2026** (MLH) by a team of three.

**Live:** [dory-md-fork.vercel.app](https://dory-md-fork.vercel.app) ·
**Upstream:** [vaishnavi1064/Dory.md](https://github.com/vaishnavi1064/Dory.md), where the
project has kept evolving and has its own [live demo](https://dory-md.vercel.app).

This fork holds the hackathon build and the work that followed it through June 2026,
plus my frontend fixes.

## What it does

Dory.md splits your notes into chunks and gives each chunk a retention score that
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

## My part

I led the backend:

- the FastAPI service and the API contract the React frontend calls
- multi-format ingestion, sentence-transformer embeddings, and SQLite + ChromaDB
  persistence
- the NumPy-vectorized forgetting-curve engine, 50–100x faster than per-chunk loops,
  which drives decay-aware search
- bcrypt + JWT authentication with per-user data isolation, and the Notion OAuth
  import
- deployment: a Vercel frontend and a Railway backend, where switching to CPU-only
  PyTorch cut the image from 5.8 GB to about 1.5 GB

I also built frontend features: login and registration, the note editor, the
knowledge-tree dashboard and the theme switcher.

## Team

- [Vaishnavi Chaughule](https://github.com/vaishnavi1064)
- [Shraddha Deshpande](https://github.com/deshpandesk8)
- [Nikhil Pawar](https://github.com/aimsotrash)

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
