"""
Hybrid retrieval: does keyword search fused with the embeddings rank the evidence better?

Rules fixed before the first run (2026-10-31):
- Hybrid = reciprocal rank fusion (k = 60) of the embedding ranking and a BM25 ranking
  (k1 = 1.5, b = 0.75, lowercase word tokens, statistics over the memories being ranked).
  Nothing is tuned.
- Main comparison: keep-all on LongMemEval's test questions, turn_all@10, hybrid minus
  vector, with a 95% paired bootstrap interval. Also turn_any@10, session_all@10, each
  question type, and LoCoMo with keep-all (intervals that resample whole conversations).
- Also ebbtide-count at the 25% and 50% budgets: the replay stays vector-only, so this only
  changes the ranking at question time, over what that replay kept.
- The server ranks with hybrid only if the main interval is above zero and LoCoMo's
  turn_all@10 does not fall.

    python -m bench.hybrid     # writes bench/RESULTS-hybrid.md; needs both benchmark runs first
"""

from __future__ import annotations

import json
import time
from multiprocessing import get_context

import numpy as np

from bench import locomo
from bench import longmemeval as lm
from intelligence.memory.hybrid import bm25, rrf, words

METRICS = ("turn_all@10", "turn_any@10", "session_all@10")
METHODS = ("vector", "bm25", "hybrid")

_TEXTS: list[str] = []
_EMB: np.ndarray | None = None
_PLANS: list = []


def _score_all(p, vector: list[int]) -> dict:
    """Score the vector ranking, a BM25 ranking of the same turns, and their fusion."""
    turns = sorted(vector)
    scores = bm25(words(_TEXTS[p.question_row]), [words(_TEXTS[p.rows[t]]) for t in turns])
    keyword = [turns[i] for i in np.argsort(-scores, kind="stable")]
    ranked = {"vector": vector, "bm25": keyword, "hybrid": [i for i, _ in rrf(vector, keyword)]}
    return {"qtype": p.qtype, **{m: lm.score(ranked[m], p) for m in METHODS}}


def _keep_all(i: int) -> dict:
    p = _PLANS[i]
    sims = np.asarray(_EMB[p.rows]) @ np.asarray(_EMB[p.question_row])
    return _score_all(p, [int(j) for j in np.argsort(-sims, kind="stable")])  # keep-all's ranking


def _budgeted(task: tuple) -> dict:
    i, policy, fraction = task
    p = _PLANS[i]
    store, _ = lm.fill(p, policy, max(1, round(fraction * len(p.rows))), lm.LIVE_K, _EMB)
    hits = store.recall(_EMB[p.question_row], len(store.memories), p.question_time, refresh=False)
    return _score_all(p, [m.source["turn"] for m, _ in hits])  # the published ranking, then fused


def _mean(rows: list[dict], method: str, metric: str) -> float | None:
    values = [r[method][metric] for r in rows if metric in r[method]]
    return 100 * sum(values) / len(values) if values else None


def _diffs(rows: list[dict], metric: str) -> list[float]:
    return [r["hybrid"][metric] - r["vector"][metric] for r in rows if metric in r["vector"]]


def _line(label: str, rows: list[dict], metric: str, interval) -> list[str]:
    v, k, h = (_mean(rows, m, metric) for m in METHODS)
    lo, hi = interval(metric)
    return [label, f"{v:.1f}", f"{k:.1f}", f"{h:.1f}", f"{h - v:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]"]


def run() -> None:
    global _TEXTS, _EMB, _PLANS
    started = time.time()

    data = lm.load()
    _TEXTS = lm.texts(data)
    _EMB = np.load(lm.EMBEDDINGS, mmap_mode="r")
    row = {t: i for i, t in enumerate(_TEXTS)}
    in_dev = lm.dev_ids(data)
    scored = [q for q in data if not q["question_id"].endswith("_abs")]
    _PLANS = [lm.plan(q, row) for q in scored]
    test = [i for i, q in enumerate(scored) if q["question_id"] not in in_dev]
    del data, scored, row
    configs = locomo.configs()  # the dev-picked settings from the published run
    with get_context("fork").Pool() as pool:
        keep_all = pool.map(_keep_all, test, chunksize=8)
        budgeted = {f: pool.map(_budgeted, [(i, configs[("ebbtide-count", f)][0], f) for i in test], chunksize=8)
                    for f in (0.25, 0.50)}

    lc_data = lm.fetch(locomo.FILE, locomo.URL, locomo.SHA256)
    _TEXTS = locomo.texts(lc_data)
    _EMB = np.load(locomo.EMBEDDINGS)
    row = {t: i for i, t in enumerate(_TEXTS)}
    by_conversation = []
    for d in lc_data:
        _PLANS = locomo.conversation(d, row)[1]
        by_conversation.append([_keep_all(i) for i in range(len(_PLANS))])
    lc_rows = [r for rows in by_conversation for r in rows]
    minutes = (time.time() - started) / 60

    def lm_ci(rows):
        return lambda metric: lm._bootstrap(_diffs(rows, metric))

    def lc_ci(metric):
        return locomo._interval([_diffs(rows, metric) for rows in by_conversation])

    header = ["", "vector", "BM25 alone", "hybrid", "hybrid − vector [95% CI]"]
    main_lo = lm_ci(keep_all)("turn_all@10")[0]
    lc_change = _mean(lc_rows, "hybrid", "turn_all@10") - _mean(lc_rows, "vector", "turn_all@10")
    adopt = main_lo > 0 and lc_change >= 0
    types = sorted({r["qtype"] for r in keep_all})
    lc_types = sorted({r["qtype"] for r in lc_rows})

    report = [
        "# Hybrid retrieval: keyword search fused with the embeddings",
        "",
        f"Generated by `python -m bench.hybrid` on {time.strftime('%Y-%m-%d')} (about {max(1, round(minutes))} "
        f"minute{'s' if round(minutes) > 1 else ''} on a laptop CPU). Its rules, including when the server would switch to hybrid ranking, are in "
        "the docstring of [`bench/hybrid.py`](hybrid.py) and were fixed before the first run.",
        "",
        "Hybrid is reciprocal rank fusion (k = 60) of the embedding ranking and BM25 (k1 = 1.5, b = 0.75), with "
        "nothing tuned. The vector column is the published ranking, so it matches [RESULTS.md](RESULTS.md) and "
        "[RESULTS-locomo.md](RESULTS-locomo.md).",
        "",
        f"**Verdict: {'adopted' if adopt else 'not adopted'}.** The rule needs the main interval above zero "
        f"(its lower end is {100 * main_lo:+.1f}) and LoCoMo's turn_all@10 not to fall (it moved "
        f"{lc_change:+.1f} points). "
        + ("Both hold, so the server now ranks with hybrid search." if adopt
           else "That fails, so the server keeps ranking by embeddings alone."),
        "",
        f"## LongMemEval, keep-all, {len(keep_all)} test questions",
        "",
        lm.table(header, [_line(m, keep_all, m, lm_ci(keep_all)) for m in METRICS]),
        "",
        "### turn_all@10 by question type",
        "",
        lm.table(header, [_line(f"{t} ({sum(r['qtype'] == t for r in keep_all)})",
                                [r for r in keep_all if r["qtype"] == t], "turn_all@10",
                                lm_ci([r for r in keep_all if r["qtype"] == t])) for t in types]),
        "",
        "## LongMemEval, ebbtide-count, ranking at question time only",
        "",
        "The replay that decides what is kept stays vector-only; hybrid search only reorders what it kept.",
        "",
        lm.table(header, [_line(f"{int(100 * f)}% budget", rows, "turn_all@10", lm_ci(rows))
                          for f, rows in budgeted.items()]),
        "",
        f"## LoCoMo, keep-all, {len(lc_rows)} questions",
        "",
        "Intervals resample whole conversations.",
        "",
        lm.table(header, [_line(m, lc_rows, m, lc_ci) for m in METRICS]),
        "",
        "### turn_all@10 by category",
        "",
        lm.table(header, [_line(f"{t} ({sum(r['qtype'] == t for r in lc_rows)})",
                                [r for r in lc_rows if r["qtype"] == t], "turn_all@10",
                                lambda m, t=t: locomo._interval([_diffs([r for r in rows if r["qtype"] == t], m)
                                                                 for rows in by_conversation]))
                          for t in lc_types]),
        "",
    ]
    (lm.DATA / "results" / "hybrid.json").write_text(json.dumps(
        {"keep_all": keep_all, "budgeted": {str(f): r for f, r in budgeted.items()}, "locomo": by_conversation}))
    (lm.ROOT / "bench" / "RESULTS-hybrid.md").write_text("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    run()
