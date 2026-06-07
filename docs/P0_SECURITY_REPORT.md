# Dory.md — P0 Security & Deployment Hardening Report

**Date:** 2026-06-07
**Scope:** Public-deployment safety only. No new features, no UI redesign, no
reminders work, no architecture redesign. Eight P0 objectives.
**Baseline:** 45 tests passing (34 backend + 11 intelligence) before this pass.
**After:** **62 tests passing (51 backend + 11 intelligence).** +17 backend tests.

Verification environment: Python 3.14.5, `backend/requirements-test.txt` subset
(torch/sentence-transformers excluded — tests stub embeddings). The heavy ML
stack and live LLM/embedding paths were **not** executed here (no cp314 torch
wheel, offline). Items needing the full stack are marked **UNVERIFIED (runtime)**
and must be exercised on the Python 3.12 deploy target / staging.

---

## 1. Security findings verified

Each verified by reading the source against a runnable baseline.

| # | Objective | Finding (pre-fix) | Evidence | Severity |
|---|---|---|---|---|
| 1 | JWT secret | Dev fell back to a **hardcoded** secret `"dory-dev-only-secret-do-not-deploy"`; reachable in prod if `DORY_ENV` was left at its `dev` default. | `routers/deps.py:_get_secret` | P0 |
| 3 | Demo account | `setup_demo_user()` + the `demo@dory.md` row were seeded **unconditionally at startup in every environment**, creating shared `demo123` credentials in production. | `routers/auth.py:setup_demo_user`, `database/db.py:init_db` | P0 |
| 3 | Demo bypass | Frontend `login()` fabricated a **tokenless "logged-in" session** for `demo@dory.md/demo123` whenever the backend was unreachable/non-OK. A hidden client-side auth bypass. | `frontend/src/contexts/AuthContext.tsx:adoptLocalDemo` | P0 |
| 4 | CORS | Default allowed **any `*.vercel.app`** and any RFC-1918 IP with `allow_credentials=True` — overly broad domain matching for a credentialed API. | `backend/main.py` CORS regex | P0 |
| 5 | Dependencies | `requirements.txt` unpinned (except torch); no vulnerability scanning. | `backend/requirements.txt` | P0 |
| 6 | CI | The CI workflow had been **deleted from the working tree**; no automated tests/security/build gate. | `git status` (`.github/workflows/ci.yml` deleted) | P0 |
| 7 | Storage | SQLite + Chroma on local disk; **data lost on redeploy** on ephemeral hosts; no backup tooling. | `database/db.py`, `vector_store.py` | P0 |
| 8 | Dangerous defaults | Hardcoded dev secret, hardcoded `_DEMO_PASSWORD="demo123"`, unconditional `DEFAULT_USER_ID="default"` demo row, the client bypass above. | grep sweep | P0 |

Confirmed **safe / not changed** by the sweep: the Ollama provider's
`api_key="ollama"` is a required placeholder, not a credential; demo *content*
strings (e.g. "Wifi password: change every 6 months") are note text, not secrets;
all request paths pass an explicit `user_id` from `get_current_user_id`, so the
`DEFAULT_USER_ID` default parameters are not reachable from production endpoints.

---

## 2. Changes implemented

### 1 & 8 — JWT secret safety / dangerous defaults — `backend/routers/deps.py`
- Removed the hardcoded dev secret entirely.
- Dev with no `JWT_SECRET` now mints a **random per-process ephemeral secret**
  (`secrets.token_urlsafe(48)`), cached for the process and logged with a warning.
- `JWT_SECRET` is used verbatim in every environment when set.
- Non-dev without a secret raises at **both** boot (`require_secret_configured()`
  in `main.py` lifespan) and per-request (`_get_secret`) — defence in depth.

### 3 — Demo account security — `auth.py`, `database/db.py`, frontend
- `setup_demo_user()` is a **no-op outside dev**.
- The `demo@dory.md` / `DEFAULT_USER_ID` row is **only created in dev** (`init_db`).
- Removed the frontend offline demo bypass (`adoptLocalDemo`) — auth is now
  strictly backend-token-driven; no fabricated sessions.
- The "Demo credentials" hint on the login page renders **only in dev builds**
  (`import.meta.env.DEV`).

### 4 — CORS hardening — `backend/main.py`
- New `resolve_cors_kwargs()` with explicit precedence: `CORS_ALLOW_ORIGINS`
  (exact list) → `CORS_ORIGIN_REGEX` → dev LAN regex → **deny-all + warn** in
  non-dev when unconfigured.
- Removed `*.vercel.app` and public-IP matching from the default. No permissive
  fallback exists outside dev.

### 2 — Environment configuration
- Rewrote `backend/.env.example` and `.env.example`; documented `DORY_ENV`,
  `JWT_SECRET`, `CORS_ALLOW_ORIGINS`, and every other variable.
- New `docs/ENVIRONMENT.md`: complete variable inventory + minimum-prod set +
  explicit startup-failure behaviour.
- Fixed `frontend/src/lib/config.ts` default API port (`8000` → `8001`).

### 5 — Dependency security
- Pinned `backend/requirements.txt` and `backend/requirements-test.txt` to exact
  versions.
- `docs/DEPENDENCY_UPGRADES.md`: scanning, upgrade workflow, and the hash-lock
  (`pip-compile --generate-hashes`) next step.

### 6 — CI pipeline — `.github/workflows/ci.yml`
- Restored and extended: backend + intelligence pytest, frontend tsc/lint/build,
  plus **`pip-audit`** and **`npm audit`** (non-blocking, flip to blocking once clean).

### 7 — Storage & backup
- `backend/scripts/backup.py`: WAL-safe SQLite online-backup snapshot + Chroma
  tar.gz, env-driven paths, CLI.
- `docs/STORAGE_AND_BACKUP.md`: risks, per-platform persistence requirements,
  backup/restore/cron, and next steps.

---

## 3. Files modified / added

**Backend (modified):** `routers/deps.py`, `routers/auth.py`, `database/db.py`,
`main.py`, `requirements.txt`, `requirements-test.txt`.
**Backend (added):** `scripts/__init__.py`, `scripts/backup.py`,
`tests/test_p0_security.py`.
**Frontend (modified):** `src/contexts/AuthContext.tsx`, `src/pages/LoginPage.tsx`,
`src/lib/config.ts`.
**Config (modified/restored):** `.github/workflows/ci.yml`, `.env.example`,
`backend/.env.example`.
**Docs (added):** `docs/ENVIRONMENT.md`, `docs/DEPENDENCY_UPGRADES.md`,
`docs/STORAGE_AND_BACKUP.md`, `docs/P0_SECURITY_REPORT.md` (this file).

---

## 4. Tests added

`backend/tests/test_p0_security.py` — 17 tests, all passing:

- **JWT (7):** prod boot fails without secret; prod boot OK with secret; dev OK
  secret-less; dev mints a safe ephemeral secret (not the old hardcoded one,
  stable within process); explicit `JWT_SECRET` preferred; `_get_secret` raises
  in prod without secret; old hardcoded string absent from source.
- **Demo (4):** demo user not seeded in prod; seeded (usable) in dev; end-to-end
  demo login 401s in prod; 200s in dev.
- **CORS (4):** explicit allow-list wins; regex honoured; prod blocks all when
  unconfigured; dev regex matches localhost/LAN but rejects vercel/public hosts.
- **Backup (2):** snapshot is a valid restorable DB + Chroma archive; missing
  Chroma handled.

Full run: `51 passed` (backend) + `11 passed` (intelligence).

---

## 5. Remaining risks

| Risk | Severity | Status / mitigation |
|---|---|---|
| **SQLite + Chroma on local disk** — data lost on redeploy without a persistent volume | High | Documented + backup tool shipped. **Action: mount a volume** (see STORAGE_AND_BACKUP.md). Managed Postgres/hosted vectors recommended for scale. |
| **Multi-worker quiz scoring** (`_session_store` in-process) | Medium | Pre-existing (AUDIT P0-3, out of this P0 scope). Run a single worker until the answer key is persisted. |
| **Full ML stack pins UNVERIFIED on 3.12** (torch has no 3.14 wheel; offline here) | Medium | Validate `requirements.txt` install + suite on 3.12 in CI/staging; generate the hash-lock. |
| **No full transitive hash-lock yet** | Medium | `==` top-level pins are the interim lock; `pip-compile --generate-hashes` instructions provided. |
| **`pip-audit` / `npm audit` non-blocking** | Low | Intentional; flip to blocking once advisories are triaged. |
| **Tokens in `localStorage`** (XSS → token theft) | Low–Med | Pre-existing; XSS sinks were sanitized in the prior pass (DOMPurify). Out of this P0 scope. |
| **`backend/seed_demo_data.py`** uses `DEFAULT_USER_ID` and a sibling repo | Low | Dead local script, not wired to any endpoint; `sys.exit`s if its data is absent. Not reachable in prod. |
| **CORS `allow_credentials=True`** | Low | The SPA uses bearer headers, not cookies; never paired with a wildcard origin. Can be set False later. |

---

## 6. Deployment checklist

**Backend (required):**
- [ ] `DORY_ENV=production` (any non-dev value).
- [ ] `JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">` (boot fails without it).
- [ ] `CORS_ALLOW_ORIGINS=https://<your-frontend-origin>` (else cross-origin is blocked).
- [ ] Persistent volume mounted at `/app/backend/data` (or set `DORY_DB_PATH` / `DORY_CHROMA_PATH`).
- [ ] Deploy on **Python 3.12** (Dockerfile already pins it).
- [ ] Run **one** backend worker (single-node) until the quiz answer key is persisted.
- [ ] LLM key matching `LLM_PROVIDER` if AI features are wanted (optional; degrades gracefully).
- [ ] Schedule `python -m scripts.backup` (cron) writing off the app volume.

**Frontend (required):**
- [ ] `VITE_API_BASE_URL=https://<your-backend-origin>`.
- [ ] Production build (`import.meta.env.DEV` false → no demo hint).

**Verify after deploy:**
- [ ] `GET /livez` → 200, `GET /readyz` → 200.
- [ ] `POST /api/auth/login` with `demo@dory.md/demo123` → **401** (no demo account in prod).
- [ ] Cross-origin request from a non-allow-listed origin is rejected.
- [ ] Boot with no `JWT_SECRET` fails fast (don't ship it — just confirm the guard).

---

## 7. Production readiness score — BEFORE

**4 / 10** (against the 8 P0 dimensions)

| Objective | Before |
|---|---|
| 1 JWT secret | ⚠️ Hardcoded dev fallback; prod-reachable if `DORY_ENV` unset |
| 2 Env config | ⚠️ Partial; demo/dev fallback misdocumented |
| 3 Demo account | ❌ Shared `demo123` seeded in all envs + client bypass |
| 4 CORS | ❌ `*.vercel.app` + private-IP wildcard, credentialed |
| 5 Dependencies | ❌ Unpinned, no scanning |
| 6 CI | ❌ Workflow deleted |
| 7 Storage/backup | ❌ No backup; redeploy data-loss undocumented |
| 8 Dangerous defaults | ❌ Hardcoded secret, demo creds, default user |

## 8. Production readiness score — AFTER

**8 / 10**

| Objective | After |
|---|---|
| 1 JWT secret | ✅ No hardcoded secret; dev ephemeral; prod fail-fast (tested) |
| 2 Env config | ✅ Full inventory + actionable startup errors |
| 3 Demo account | ✅ Dev-only; no prod creds; bypass removed (tested) |
| 4 CORS | ✅ Explicit allow-list; deny-by-default in prod (tested) |
| 5 Dependencies | ✅ Pinned + audited in CI (full hash-lock pending) |
| 6 CI | ✅ Restored + security + build gates |
| 7 Storage/backup | ✅ Backup tool + restore docs (managed DB still recommended) |
| 8 Dangerous defaults | ✅ All identified production-risk defaults removed (tested) |

**Not 10/10 because:** data durability still relies on an operator-mounted
volume (no managed DB), the multi-worker quiz store is unfixed (pre-existing,
out of scope), and the full ML-stack pins + transitive hash-lock remain to be
validated on the 3.12 target. These are documented with exact next steps.
