"""
The defaults as they ship, end to end: hybrid recall inside the budgeted replays, and the
similarity hint that `remember` returns.

Rules fixed before the first run (2026-10-31):

Part 1, budgeted replays. The published replays (RESULTS.md, RESULTS-locomo.md) ranked every
recall by embeddings alone, and gave each decay policy the settings LongMemEval's dev split
picked for each budget. Here ebbtide-count runs exactly as the server ships it
(POLICIES["ebbtide-count"]: weight 0, 216 h scale), and in the hybrid replay every recall is
hybrid, as the server's are: the agent's at each user turn and the question's.
- Main comparison: shipped ebbtide-count, hybrid replay minus the same policy replayed with
  embeddings alone, turn_all@10 on LongMemEval's 378 test questions at the 10%, 25% and 50%
  budgets, with 95% paired bootstrap intervals. LoCoMo the same, with intervals that resample
  whole conversations.
- Also: recency and LRU replayed both ways at the same budgets; shipped ebbtide-count minus LRU,
  both hybrid, on turn_all@10, session_all@10, evidence_kept and (LongMemEval knowledge-update
  questions only) latest@10; LongMemEval's turn_all@10 by question type, hybrid minus vector,
  for shipped ebbtide-count. And a check: with room for everything, ebbtide-count must score
  exactly what keep-all does, since it ranks by similarity alone.
- Nothing in the server changes because of part 1. It tests the default; the README reports
  the result either way, losses included.

Part 2, the similarity hint. remember returns up to 3 stored memories with a cosine similarity
of at least 0.5. On LongMemEval's knowledge-update questions (dev and test; nothing was tuned on
them) the history is replayed with nothing evicted, asking for the hint before each turn is
stored, as remember does. The hint catches a change if, while a turn of the newest evidence
session is stored, it names an evidence turn from an older session. Reported at cuts 0.3 to
0.7: the share of changes caught, and, as noise, the share of the other user turns that get any
hint. Turns are whole chat messages, longer and more mixed than the one-fact memories an agent
is told to store, so this is a proxy, and the cut stays at 0.5 whatever it shows.

    python -m bench.defaults   # writes bench/RESULTS-defaults.md; needs both benchmarks' embeddings
"""

from __future__ import annotations

import json
import time
from multiprocessing import get_context

import numpy as np

from bench import locomo
from bench import longmemeval as lm
from ebbtide.server import SIMILAR
from intelligence.memory import POLICIES, MemoryStore

BUDGETS = lm.BUDGETS
FORGETTING = ("recency", "lru", "ebbtide-count")
CONFIGS = [(name, f, hybrid) for hybrid in (False, True)
           for name, f in [("keep-all", None), ("ebbtide-count", None), *((n, f) for n in FORGETTING for f in BUDGETS)]]
CUTS = (0.3, 0.4, 0.5, 0.6, 0.7)
PRIMARY = lm.PRIMARY

_TEXTS: list[str] = []
_EMB: np.ndarray | None = None
_PLANS: list = []


def _budget(fraction: float | None, turns: int) -> int | None:
    return None if fraction is None else max(1, round(fraction * turns))


def _lm_task(task: tuple) -> dict:
    i, name, fraction, hybrid = task
    p = _PLANS[i]
    texts = _TEXTS if hybrid else None
    store, _ = lm.fill(p, POLICIES[name], _budget(fraction, len(p.rows)), lm.LIVE_K, _EMB, texts)
    return {**lm.ask(store, p, _EMB, texts), "qtype": p.qtype}


def _lc_task(task: tuple) -> list[dict]:
    c, name, fraction, hybrid = task
    turns, questions, _ = _PLANS[c]
    texts = _TEXTS if hybrid else None
    store, _ = lm.fill(turns, POLICIES[name], _budget(fraction, len(turns.rows)), lm.LIVE_K, _EMB, texts)
    return [{**lm.ask(store, q, _EMB, texts), "qtype": q.qtype, "conversation": c} for q in questions]


def _hint_replay(p: lm.Plan, emb: np.ndarray) -> tuple[float | None, list[float | None]]:
    """Store every turn, nothing evicted, asking for the hint first as remember does. Returns the
    highest similarity of a hint naming an older evidence turn while the newest evidence is
    stored (None if none is ever in the top 3), and each other user turn's top hint similarity."""
    store = MemoryStore(POLICIES["keep-all"])
    older = p.evidence - p.latest
    catch, others = None, []
    for i, row in enumerate(p.rows):
        hints = store.similar(emb[row], 3, min(CUTS))  # the top 3, then the cut, as remember does
        if i in p.latest:
            for m, s in hints:
                if m.source["turn"] in older:
                    catch = s if catch is None else max(catch, s)
        elif p.is_user[i]:
            others.append(hints[0][1] if hints else None)
        store.add("", emb[row], p.times[i], source={"turn": i})
    return catch, others


def _versus(a: list[dict], b: list[dict], metric: str, by_conversation: bool = False) -> str:
    """Mean of a − b over the questions both score, in points, with a 95% interval."""
    pairs = [(x, y) for x, y in zip(a, b) if x.get(metric) is not None and y.get(metric) is not None]
    diffs = [x[metric] - y[metric] for x, y in pairs]
    if not diffs:
        return "–"
    if by_conversation:
        groups = [[] for _ in range(1 + max(x["conversation"] for x, _ in pairs))]
        for (x, _), d in zip(pairs, diffs):
            groups[x["conversation"]].append(d)
        lo, hi = locomo._interval(groups)
    else:
        lo, hi = lm._bootstrap(diffs)
    return f"{100 * sum(diffs) / len(diffs):+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]"


def _name(name: str, fraction: float | None) -> str:
    return name if fraction is None else f"{name} @ {fraction:.0%}"


def _part1(res: dict, by_conversation: bool, metrics: list[str]) -> list[str]:
    """Report lines for one benchmark's results, keyed (name, fraction, hybrid)."""
    ship = "ebbtide-count"
    main = lm.table(["budget", "embeddings-only replay", "hybrid replay", "hybrid − embeddings [95% CI]"], [
        [f"{f:.0%}", lm._pct(lm.mean(res[(ship, f, False)], PRIMARY)), lm._pct(lm.mean(res[(ship, f, True)], PRIMARY)),
         _versus(res[(ship, f, True)], res[(ship, f, False)], PRIMARY, by_conversation)]
        for f in BUDGETS
    ])
    policies = lm.table(["policy", *(f"{f:.0%} budget" for f in BUDGETS)], [
        [f"{name}, {'hybrid' if hybrid else 'embeddings only'}",
         *(lm._pct(lm.mean(res[(name, f, hybrid)], PRIMARY)) for f in BUDGETS)]
        for name in FORGETTING for hybrid in (False, True)
    ])
    versus = lm.table(["metric", *(f"{f:.0%} budget" for f in BUDGETS)], [
        [m, *(_versus(res[(ship, f, True)], res[("lru", f, True)], m, by_conversation) for f in BUDGETS)]
        for m in metrics
    ])
    keep_all = {h: lm.mean(res[("keep-all", None, h)], PRIMARY) for h in (False, True)}
    room = {h: lm.mean(res[(ship, None, h)], PRIMARY) for h in (False, True)}
    check = "holds" if all(
        a == b for h in (False, True) for a, b in zip(res[("keep-all", None, h)], res[(ship, None, h)])) else "FAILS"
    return [
        f"### {PRIMARY}: shipped ebbtide-count, hybrid replay against embeddings only",
        "",
        main,
        "",
        f"### {PRIMARY} for each forgetting policy, replayed both ways",
        "",
        policies,
        "",
        f"keep-all scores {lm._pct(keep_all[False])} with embeddings only and {lm._pct(keep_all[True])} with hybrid "
        f"search at every budget. Check: with room for everything, ebbtide-count scores {lm._pct(room[False])} and "
        f"{lm._pct(room[True])}, question for question the same as keep-all ({check}).",
        "",
        "### Shipped ebbtide-count minus LRU, both hybrid",
        "",
        "Each cell is ebbtide-count minus LRU, in points, with a 95% interval.",
        "",
        versus,
        "",
    ]


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
    updates = [i for i, p in enumerate(_PLANS) if p.qtype == "knowledge-update"]
    del data, scored, row
    tasks = [(i, *config) for config in CONFIGS for i in test]
    with get_context("fork").Pool() as pool:
        flat = pool.map(_lm_task, tasks, chunksize=4)
    lm_res = {config: flat[j * len(test):(j + 1) * len(test)] for j, config in enumerate(CONFIGS)}

    hints = [_hint_replay(_PLANS[i], _EMB) for i in updates if _PLANS[i].evidence - _PLANS[i].latest]
    one_session = len(updates) - len(hints)

    lc_data = lm.fetch(locomo.FILE, locomo.URL, locomo.SHA256)
    _TEXTS = locomo.texts(lc_data)
    _EMB = np.load(locomo.EMBEDDINGS)
    row = {t: i for i, t in enumerate(_TEXTS)}
    _PLANS = [locomo.conversation(d, row) for d in lc_data]
    tasks = [(c, *config) for config in CONFIGS for c in range(len(_PLANS))]
    with get_context("fork").Pool() as pool:
        flat = pool.map(_lc_task, tasks, chunksize=1)
    n = len(_PLANS)
    lc_res = {config: [r for rows in flat[j * n:(j + 1) * n] for r in rows] for j, config in enumerate(CONFIGS)}
    minutes = (time.time() - started) / 60

    ship = "ebbtide-count"
    types = sorted({r["qtype"] for r in lm_res[("keep-all", None, False)]})
    per_type = lm.table(["question type", *(f"{f:.0%} budget" for f in BUDGETS)], [
        [f"{t} ({sum(r['qtype'] == t for r in lm_res[('keep-all', None, False)])})",
         *(_versus([r for r in lm_res[(ship, f, True)] if r["qtype"] == t],
                   [r for r in lm_res[(ship, f, False)] if r["qtype"] == t], PRIMARY) for f in BUDGETS)]
        for t in types
    ])
    others = [s for _, sims in hints for s in sims]
    hint_table = lm.table(["cut", "changes caught", "other user turns given a hint"], [
        [f"**{cut}** (shipped)" if cut == SIMILAR else f"{cut}",
         lm._pct(sum(c is not None and c >= cut for c, _ in hints) / len(hints)),
         lm._pct(sum(s is not None and s >= cut for s in others) / len(others))]
        for cut in CUTS
    ])
    best = sorted(c for c, _ in hints if c is not None)

    report = [
        "# The defaults as they ship, end to end",
        "",
        f"Generated by `python -m bench.defaults` on {time.strftime('%Y-%m-%d')} (about {max(1, round(minutes))} "
        f"minute{'s' if round(minutes) > 1 else ''} on a laptop CPU). Its rules were fixed before the first run and "
        "are in the docstring of [`bench/defaults.py`](defaults.py).",
        "",
        "## Part 1: hybrid recall inside the budgeted replays",
        "",
        "The published replays ranked every recall by embeddings alone, and gave each decay policy the settings "
        "LongMemEval's dev split picked for each budget. Here ebbtide-count runs exactly as the server ships it "
        "(weight 0, 216 h scale), and in the hybrid replay every recall is hybrid: the agent's recall at each user "
        "turn, which strengthens what it returns and so decides what survives, and the question's.",
        "",
        f"## LongMemEval, {len(test)} test questions",
        "",
        *_part1(lm_res, False, [PRIMARY, "session_all@10", "evidence_kept", "latest@10"]),
        f"### {PRIMARY} by question type: shipped ebbtide-count, hybrid minus embeddings only",
        "",
        per_type,
        "",
        f"## LoCoMo, {len(lc_res[('keep-all', None, False)])} questions",
        "",
        "Intervals resample whole conversations.",
        "",
        *_part1(lc_res, True, [PRIMARY, "session_all@10", "evidence_kept"]),
        "## Part 2: the similarity hint",
        "",
        f"`remember` returns up to 3 stored memories with a cosine similarity of at least {SIMILAR}. Replaying "
        f"LongMemEval's knowledge-update histories with nothing evicted, {len(hints)} questions have evidence in an "
        f"older session as well as the newest ({one_session} more keep all their evidence in one session and are "
        "left out). A change is caught if the hint, while a turn of the newest evidence session is stored, names an "
        "evidence turn from an older session. Noise is the share of the other "
        f"{len(others):,} user turns that get any hint.",
        "",
        hint_table,
        "",
        f"The outdated turn was among the top 3 for {len(best)} of {len(hints)} changes, at a median similarity of "
        f"{np.median(best):.2f}." if best else "The outdated turn was never among the top 3.",
        "",
        "Turns are whole chat messages, often long and about several things, while an agent is told to store one "
        "fact per memory, so this is a proxy. The cut stays where it is.",
        "",
    ]
    (lm.DATA / "results" / "defaults.json").write_text(json.dumps({
        "longmemeval": {f"{n} {f} {'hybrid' if h else 'vector'}": r for (n, f, h), r in lm_res.items()},
        "locomo": {f"{n} {f} {'hybrid' if h else 'vector'}": r for (n, f, h), r in lc_res.items()},
        "hints": [{"catch": c, "others": s} for c, s in hints],
    }))
    (lm.ROOT / "bench" / "RESULTS-defaults.md").write_text("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    run()
