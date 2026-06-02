# Dory.md Intelligence Layer

An **independent domain layer** for the memory-science, retrieval, ranking, and
LLM logic that powers Dory.md. It is consumed by the FastAPI backend through each
subpackage's public interface and could be deployed/published on its own.

## Contract

- **Pure domain logic.** No HTTP, no auth, no relational DB. Inputs are plain
  values (text, vectors, mappings, numbers); outputs are plain values.
- **Boundary (enforced by `tests/test_intelligence.py::test_intelligence_does_not_import_backend`):**
  no module here may import `database`, `routers`, `models`, `services`, or `main`.
- The backend owns persistence and orchestration. Where intelligence needs a
  side effect (store a category), it returns the value and the backend persists it.

## Layout

| Package | Responsibility | Public interface (`__init__`) |
|---|---|---|
| `memory/` | Ebbinghaus retention + FSRS scheduling | `calculate_retention[_batch]`, `classify_retention`, `grade`, `VALID_GRADES`, thresholds |
| `embeddings/` | SentenceTransformer vectorization (lazy) | `embed_query`, `embed_texts`, `warm_model`, `get_model` |
| `retrieval/` | ChromaDB vector store adapter | `add_chunks`, `upsert_chunk`, `query_similar`, `delete_chunk`, `count` |
| `ranking/` | Hybrid composite scoring + display metrics | `composite_score`, `recency_bonus`, `display_stability`, `display_complexity_k` |
| `llm/` | Provider abstraction, categorization, quiz gen | `get_llm`, `classify`, `CATEGORIES`, `generate_mcq`, `difficulty`, `FALLBACK_QUESTIONS` |
| `domain/` | Chunking + complexity scoring | `chunk_text`, `complexity_score` |

## How the backend consumes it

The repo root is placed on `sys.path` by `backend/main.py` and the test
`conftest.py`, so `from intelligence.memory import calculate_retention` resolves.
For an independent deployment, `pip install -e intelligence/` (uses `pyproject.toml`)
achieves the same without the path shim.

Heavy/optional dependencies (torch, chromadb, LLM SDKs) are imported lazily inside
the subsystems that need them and are declared as optional extras in
`pyproject.toml`, so a consumer can install only what it uses.

## Tests

```bash
python -m pytest intelligence/tests/   # pure logic, no heavy ML, ~0.1s
```
