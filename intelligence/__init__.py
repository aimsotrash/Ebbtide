"""Dory.md Intelligence Layer.

An independent domain layer for the memory-science, retrieval, ranking, and LLM
logic that powers Dory.md. It deliberately knows NOTHING about HTTP, auth, or the
relational database — it takes plain inputs (text, vectors, mappings, numbers) and
returns plain outputs. The FastAPI backend orchestrates persistence and wiring and
consumes this package through each subpackage's public `__init__` interface.

Subpackages:
  memory      Ebbinghaus retention math + FSRS spaced-repetition scheduling.
  embeddings  SentenceTransformer vectorization (lazy, singleton).
  retrieval   Vector store (ChromaDB) adapter for semantic retrieval.
  ranking     Hybrid composite scoring + derived memory metrics.
  llm         Provider abstraction + categorization + quiz generation.
  domain      Chunking + complexity scoring of raw knowledge.

Boundary rule (enforced by review + intelligence/tests): no module here may
`import` from the backend (`database`, `routers`, `models`, `services`).
"""

__version__ = "1.0.0"
