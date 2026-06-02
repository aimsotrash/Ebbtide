"""Unit tests for the intelligence layer.

Pure logic only — no FastAPI, no DB, no network, and no heavy ML model load
(embeddings/LLM/Chroma are exercised via the backend integration tests). These
also enforce the architectural boundary: nothing under intelligence/ may import
the backend.
"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from intelligence.domain import chunk_text, complexity_score
from intelligence.memory import (
    calculate_retention,
    calculate_retention_batch,
    classify_retention,
)
from intelligence.ranking import (
    composite_score,
    display_complexity_k,
    display_stability,
    recency_bonus,
)


# ── Ebbinghaus retention ──────────────────────────────────────────────────────

def test_fresh_chunk_has_high_retention():
    now = datetime.now(timezone.utc)
    r = calculate_retention(now, access_count=0, complexity_score=0.5)
    assert r > 0.99


def test_retention_decreases_over_time():
    now = datetime.now(timezone.utc)
    recent = calculate_retention(now - timedelta(days=2), 1, 0.5)
    old = calculate_retention(now - timedelta(days=60), 1, 0.5)
    assert recent > old
    assert 0.0 <= old <= recent <= 1.0


def test_more_reviews_slow_decay():
    old = datetime.now(timezone.utc) - timedelta(days=20)
    few = calculate_retention(old, access_count=1, complexity_score=0.5)
    many = calculate_retention(old, access_count=10, complexity_score=0.5)
    assert many > few


def test_classify_retention_buckets():
    assert classify_retention(0.95) == "strong"
    assert classify_retention(0.6) == "fading"
    assert classify_retention(0.3) == "weak"
    assert classify_retention(0.05) == "critical"


def test_batch_matches_scalar():
    now = datetime.now(timezone.utc)
    dts = [now - timedelta(days=d) for d in (1, 10, 30)]
    counts = [0, 2, 1]
    scores = [0.5, 0.7, 0.3]
    batch = calculate_retention_batch(dts, counts, scores)
    for i, dt in enumerate(dts):
        assert abs(batch[i] - calculate_retention(dt, counts[i], scores[i])) < 1e-9


# ── Ranking ───────────────────────────────────────────────────────────────────

def test_composite_score_weights():
    # similarity 1, retention 1 (no urgency), recency 0 -> 0.4
    assert abs(composite_score(1.0, 1.0, 0.0) - 0.4) < 1e-9
    # urgency dominates when retention is 0
    assert composite_score(0.0, 0.0, 0.0) == 0.4


def test_recency_bonus_monotonic():
    assert recency_bonus(0) > recency_bonus(30) > recency_bonus(365)
    assert abs(recency_bonus(0) - 1.0) < 1e-9


def test_display_metrics_ranges():
    assert display_stability(0) == 9.0
    assert display_stability(10) > display_stability(0)
    assert 0.5 <= display_complexity_k(0.0) <= display_complexity_k(1.0) <= 2.0


# ── Chunking & complexity ─────────────────────────────────────────────────────

def test_chunk_text_returns_nonempty_for_real_text():
    text = "\n\n".join(["This is a paragraph about memory science."] * 5)
    chunks = chunk_text(text)
    assert chunks and all(isinstance(c, str) and c.strip() for c in chunks)


def test_complexity_score_in_range():
    assert 0.0 <= complexity_score("hello world") <= 1.0
    assert complexity_score("") == 0.5  # empty guard
    # code-bearing text scores higher than plain prose of similar length
    code = "def f(x):\n    return x + 1\n"
    prose = "the the the the the the the the"
    assert complexity_score(code) > complexity_score(prose)


# ── Architectural boundary ────────────────────────────────────────────────────

def test_intelligence_does_not_import_backend():
    """No module under intelligence/ may import backend packages."""
    forbidden = {"database", "routers", "models", "services", "main"}
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts:
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden:
                        offenders.append((str(py), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden:
                    offenders.append((str(py), node.module))
    assert not offenders, f"intelligence layer leaks into backend: {offenders}"
