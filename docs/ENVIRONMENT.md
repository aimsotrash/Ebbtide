# Dory.md — Environment Variable Inventory

Authoritative list of every environment variable the system reads, where it is
read, its default, and whether it is required for a public deployment.

Templates: [`backend/.env.example`](../backend/.env.example),
[`frontend/.env.example`](../frontend/.env.example), [`.env.example`](../.env.example).

---

## Backend (FastAPI + intelligence layer)

| Variable | Required? | Default | Read in | Purpose / notes |
|---|---|---|---|---|
| `DORY_ENV` | **Yes in prod** | `dev` | `routers/deps.py`, `main.py`, `ratelimit.py`, `database/db.py` | Runtime profile. Set to a **non-dev** value (e.g. `production`) in every real deployment. Controls JWT-secret policy, demo-account seeding, and rate limiting. |
| `JWT_SECRET` | **Yes when `DORY_ENV != dev`** | — | `routers/deps.py` | HMAC signing secret for access/refresh JWTs. **App fails fast at boot if missing in non-dev.** In dev, a random per-process ephemeral secret is generated (no hardcoded fallback). Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `CORS_ALLOW_ORIGINS` | **Yes in prod** (or `CORS_ORIGIN_REGEX`) | — | `main.py` | Comma-separated list of **exact** allowed browser origins. Preferred over regex. If neither this nor `CORS_ORIGIN_REGEX` is set in non-dev, all cross-origin requests are blocked. |
| `CORS_ORIGIN_REGEX` | Optional | — | `main.py` | Advanced alternative to `CORS_ALLOW_ORIGINS`. Avoid broad patterns (e.g. `.*\.vercel\.app`). |
| `LLM_PROVIDER` | Optional | `groq` | `intelligence/llm/provider.py` | `groq` \| `openai` \| `anthropic` \| `ollama`. |
| `LLM_MODEL` | Optional | provider-specific | `intelligence/llm/provider.py` | Model id for the selected provider. |
| `GROQ_API_KEY` | Optional* | — | `intelligence/llm/provider.py` | Required only if `LLM_PROVIDER=groq` and you want live LLM features. Without it, LLM features degrade gracefully (fallback quiz bank, "Other" category). |
| `OPENAI_API_KEY` | Optional* | — | `intelligence/llm/provider.py` | Required only if `LLM_PROVIDER=openai`. |
| `ANTHROPIC_API_KEY` | Optional* | — | `intelligence/llm/provider.py` | Required only if `LLM_PROVIDER=anthropic`. |
| `OLLAMA_BASE_URL` | Optional | `http://localhost:11434/v1` | `intelligence/llm/provider.py` | Only if `LLM_PROVIDER=ollama`. |
| `LOG_LEVEL` | Optional | `INFO` | `observability.py` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR`. |
| `DORY_RATE_LIMIT_PER_MIN` | Optional | `60` | `ratelimit.py` | Requests/min/client-IP on auth + AI endpoints. `0` disables. Inert when `DORY_ENV=dev`. |
| `DORY_DB_PATH` | Optional | `backend/data/dory.db` | `database/db.py` | SQLite file path. Point at a **persistent volume** in production. |
| `DORY_CHROMA_PATH` | Optional | `backend/data/chroma` | `intelligence/retrieval/vector_store.py` | ChromaDB directory. Point at a **persistent volume** in production. |
| `DORY_BACKUP_DIR` | Optional | `backend/data/backups` | `scripts/backup.py` | Output directory for `scripts/backup.py` snapshots. |
| `DORY_SKIP_WARMUP` | Optional | unset | `main.py` | `1` skips the SentenceTransformer warm-up at boot (faster start, lazy model load). Set by tests/CI. |
| `PORT` | Optional | `8001` | `Procfile` / platform | Listen port (Heroku/Render-style). |

\* "Optional*" = not required to boot, but the corresponding feature is degraded without it.

## Frontend (Vite SPA — must be `VITE_`-prefixed)

| Variable | Required? | Default | Read in | Purpose |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | **Yes in prod** | `http://localhost:8001` | `src/lib/config.ts` | Base URL of the deployed backend. |
| `VITE_USE_MOCKS` | Optional | `false` | `src/lib/config.ts` | If `true`, the SPA returns bundled mock JSON instead of calling the backend. |
| `VITE_DISCOVERY_POLL_MS` | Optional | `30000` | `src/lib/config.ts` | Dashboard `/api/discovery` poll interval (ms). |

> Vite inlines `VITE_*` vars at build time and exposes them in the browser
> bundle — never put secrets here.

---

## Minimum required for a public production deployment

Backend:
```
DORY_ENV=production
JWT_SECRET=<output of: python -c "import secrets; print(secrets.token_urlsafe(48))">
CORS_ALLOW_ORIGINS=https://your-frontend-origin
# plus a persistent volume for DORY_DB_PATH + DORY_CHROMA_PATH (see docs/STORAGE_AND_BACKUP.md)
# plus the LLM key matching LLM_PROVIDER if you want AI features
```

Frontend:
```
VITE_API_BASE_URL=https://your-backend-origin
```

## Startup failure behaviour (explicit & actionable)

- **Missing `JWT_SECRET` in non-dev** → the app raises at boot:
  `RuntimeError: JWT_SECRET is required when DORY_ENV != 'dev'. Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- **Missing CORS config in non-dev** → the app boots but logs a `WARNING`
  ("All cross-origin browser requests will be blocked. Set CORS_ALLOW_ORIGINS …")
  and rejects cross-origin requests instead of silently allowing everything.
