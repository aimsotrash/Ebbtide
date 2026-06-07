# Dory.md — Dependency Security & Upgrade Guidance

## Where dependencies live

| File | Scope | Pinned? | Installed/validated on |
|---|---|---|---|
| `backend/requirements.txt` | Full production backend (incl. ML + LLM SDKs) | Yes (`==`) | Python 3.12 (Dockerfile / build job) |
| `backend/requirements-test.txt` | CI/test subset (no torch) | Yes (`==`) | Python 3.11–3.14 (CI uses 3.12) |
| `frontend/package.json` + `frontend/package-lock.json` | SPA | Ranges in manifest, exact in lockfile | Node 22 |

> The backend torch pin (`torch==2.5.1+cpu`) has **no cp314 wheel**, so the full
> `requirements.txt` install is validated on **Python 3.12** (the Dockerfile and
> CI both pin 3.12). The test subset installs across 3.11–3.14.

## Automated vulnerability scanning

CI (`.github/workflows/ci.yml`) runs on every push/PR to `main`:

- **Backend:** `pip-audit` against the installed dependency set.
- **Frontend:** `npm audit --audit-level=high`.

Both currently run as **non-blocking** (`continue-on-error: true`) so advisories
are surfaced without wedging the pipeline on an un-upgradable transitive issue.
Once the audit is clean, flip them to blocking by removing `continue-on-error`.

Run locally:

```bash
# Backend
python -m pip install pip-audit
pip-audit                          # audits the active environment
pip-audit -r backend/requirements-test.txt   # audits a requirements file

# Frontend
cd frontend && npm audit --audit-level=high
```

## Upgrading a backend dependency

1. Bump the pin in `requirements.txt` (and `requirements-test.txt` if shared).
2. In a **clean Python 3.12 venv**: `pip install -r backend/requirements.txt`.
3. Run the suites:
   ```bash
   cd backend && DORY_ENV=dev DORY_SKIP_WARMUP=1 python -m pytest tests/ -v
   DORY_ENV=dev python -m pytest intelligence/tests/ -v
   ```
4. `pip-audit` to confirm no new advisories.
5. Commit `requirements*.txt` together.

## Producing a fully hash-locked file (recommended next step)

Top-level `==` pins fix direct dependencies but not the full transitive tree.
For supply-chain-grade reproducibility, generate a hash-locked file on 3.12:

```bash
pip install pip-tools
pip-compile --generate-hashes \
  --output-file=backend/requirements.lock backend/requirements.txt
# deploy with:  pip install --require-hashes -r backend/requirements.lock
```

This is deferred from the P0 pass because it must be generated and validated on
the 3.12 target with the full ML stack (torch has no 3.14 wheel and the pass ran
offline on 3.14). The `==` pins above are the interim lock.

## Frontend

`package-lock.json` is committed and CI installs with `npm ci` (lockfile-exact).
To upgrade: `npm update <pkg>` / edit `package.json`, then `npm install`, then
`npm audit`, then commit the updated lockfile.

## Known accepted items

- `torch==2.5.1+cpu` is pinned for the CPU-only deploy and lacks a Python 3.14
  wheel — deploy on 3.12. Revisit when bumping torch.
- The Ollama provider passes `api_key="ollama"` to the OpenAI-compatible client
  ([intelligence/llm/provider.py](../intelligence/llm/provider.py)); this is a
  required placeholder for local Ollama, not a real credential.
