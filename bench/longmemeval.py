"""
Should an agent forget? The memory policies, replayed on LongMemEval.

  python -m bench.longmemeval embed   # download the data, embed every turn once (~45 min on a laptop CPU)
  python -m bench.longmemeval run     # pick settings on dev, report on test -> bench/RESULTS.md

Each question comes with a ~48-session chat history. The replay walks it in date
order and stores every turn as a memory. At each user turn it first recalls the top
LIVE_K memories for that turn, as a live agent would, which strengthens them. The
budget is enforced throughout. At the end it recalls for the question and scores the
ranking against the turns and sessions that hold the answer.

Data: longmemeval_s_cleaned.json (MIT) at a pinned revision, checked by SHA-256,
kept in the git-ignored data/ folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from intelligence.memory import POLICIES, MemoryStore, Policy

LIVE_K = 5  # memories the agent recalls at each user turn
KS = (5, 10)  # recall@k cutoffs
BUDGETS = (0.10, 0.25, 0.50)  # memory budget, as a fraction of the history's turns
PRIMARY = "turn_all@10"  # the one metric settings are picked on, fixed before any run
# The dev grid: each decay policy gets every fusion x weight x decay scale (hours).
WEIGHTS = {"add": (0.0, 0.01, 0.03, 0.1, 0.3), "mul": (0.03, 0.1, 0.3, 1.0)}
SCALES = (24.0, 72.0, 216.0, 648.0)
TUNED = {
    "keep-all, decay-ranked": Policy(evict=None, strengthen="spaced"),
    "decay-only": POLICIES["decay-only"],
    "engram-count": POLICIES["engram-count"],
    "engram-spaced": POLICIES["engram-spaced"],
}
DATE_FORMAT = "%Y/%m/%d (%a) %H:%M"

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FILE = DATA / "longmemeval_s_cleaned.json"
URL = (
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/"
    "98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json"
)
SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
EMBEDDINGS = DATA / "longmemeval_s_minilm.npy"  # one row per text, in texts() order
CHUNK = 10_000


def fetch(path: Path, url: str, sha256: str):
    """The pinned dataset at `path`, downloaded if missing and checked by SHA-256."""
    if not path.exists():
        DATA.mkdir(exist_ok=True)
        part = path.with_suffix(".part")
        urllib.request.urlretrieve(url, part)
        part.rename(path)
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            digest.update(block)
    if digest.hexdigest() != sha256:
        raise SystemExit(f"{path} does not match the pinned SHA-256; delete it and run again")
    return json.loads(path.read_text())


def load() -> list[dict]:
    return fetch(FILE, URL, SHA256)


def texts(data: list[dict]) -> list[str]:
    """Every distinct turn and question, in a fixed order."""
    turns = (t["content"] for q in data for s in q["haystack_sessions"] for t in s)
    return list(dict.fromkeys([*turns, *(q["question"] for q in data)]))


def embed(all_texts: list[str], out: Path) -> None:
    """Embed every text once into `out`, CHUNK at a time, so an interrupted run resumes."""
    from intelligence.embeddings import get_model  # heavy: loads torch

    model = get_model()
    parts = out.with_suffix(".parts")
    parts.mkdir(exist_ok=True)
    starts = range(0, len(all_texts), CHUNK)
    for start in starts:
        path = parts / f"{start:07d}.npy"
        if not path.exists():
            vectors = model.encode(all_texts[start:start + CHUNK], batch_size=64, show_progress_bar=False)
            np.save(parts / "partial.npy", vectors.astype(np.float32))
            (parts / "partial.npy").rename(path)
        print(f"embedded {min(start + CHUNK, len(all_texts)):,} / {len(all_texts):,}", flush=True)
    np.save(out, np.concatenate([np.load(parts / f"{s:07d}.npy") for s in starts]))
    for path in parts.iterdir():
        path.unlink()
    parts.rmdir()


@dataclass(frozen=True)
class Plan:
    """One question, ready to replay. Turns are numbered by replay position."""

    qtype: str
    rows: list[int]  # embedding row of each turn
    is_user: list[bool]
    times: list[float]  # Unix seconds
    session: list[int]  # session of each turn, numbered in date order
    evidence: frozenset[int]  # turns marked has_answer
    answer_sessions: frozenset[int]
    latest: frozenset[int]  # knowledge-update only: the evidence in the newest answer session
    question_row: int
    question_time: float


def _timestamp(text: str) -> float:
    return datetime.strptime(text, DATE_FORMAT).replace(tzinfo=timezone.utc).timestamp()


def plan(q: dict, row: dict[str, int]) -> Plan:
    """Sessions in date order (211 histories are stored out of order; ties keep the
    file's order), turns 1 s apart, and the question after the last turn: 76 questions
    are dated up to a day before their last session, sometimes before evidence."""
    dates = [_timestamp(d) for d in q["haystack_dates"]]
    order = sorted(range(len(dates)), key=dates.__getitem__)
    answer_ids = set(q["answer_session_ids"])
    rows, is_user, times, session, evidence, answer_sessions = [], [], [], [], [], set()
    for s, i in enumerate(order):
        if q["haystack_session_ids"][i] in answer_ids:
            answer_sessions.add(s)
        start = max(dates[i], times[-1] + 1) if times else dates[i]  # time never runs backwards
        for j, turn in enumerate(q["haystack_sessions"][i]):
            if turn.get("has_answer"):
                evidence.append(len(rows))
            rows.append(row[turn["content"]])
            is_user.append(turn["role"] == "user")
            times.append(start + j)
            session.append(s)
    latest = frozenset()
    if q["question_type"] == "knowledge-update" and evidence:
        newest = max(session[p] for p in evidence)
        latest = frozenset(p for p in evidence if session[p] == newest)
    return Plan(q["question_type"], rows, is_user, times, session, frozenset(evidence),
                frozenset(answer_sessions), latest, row[q["question"]],
                max(_timestamp(q["question_date"]), times[-1] + 1))


def fill(p: Plan, policy: Policy, budget: int | None, live_k: int, emb: np.ndarray) -> tuple[MemoryStore, float]:
    """Replay the history into a store. Returns it and the mean ms of the agent's recalls."""
    store = MemoryStore(policy, budget)
    recall_seconds, recalls = 0.0, 0
    for i, row in enumerate(p.rows):
        vector = emb[row]
        if p.is_user[i]:  # recall before storing, or the turn would find itself
            started = time.perf_counter()
            store.recall(vector, live_k, p.times[i])
            recall_seconds += time.perf_counter() - started
            recalls += 1
        store.add("", vector, p.times[i], source={"turn": i})
    return store, 1000 * recall_seconds / max(recalls, 1)


def ask(store: MemoryStore, q: Plan, emb: np.ndarray) -> dict:
    """Score the store's ranking for a question. Only looks: nothing is strengthened."""
    hits = store.recall(emb[q.question_row], len(store.memories), q.question_time, refresh=False)
    kept = {m.source["turn"] for m in store.memories}
    return {
        **score([m.source["turn"] for m, _ in hits], q),
        "evidence_kept": len(q.evidence & kept) / len(q.evidence) if q.evidence else None,
        "memories": len(store.memories),
    }


def replay(p: Plan, policy: Policy, budget: int | None, live_k: int, emb: np.ndarray) -> dict:
    store, recall_ms = fill(p, policy, budget, live_k, emb)
    return {**ask(store, p, emb), "recall_ms": recall_ms}


def score(ranked: list[int], p: Plan) -> dict:
    """LongMemEval's retrieval metrics for one ranking of turns, best first. recall_all
    needs every target in the top k, recall_any one of them. Session level reads down
    the ranking until k distinct sessions, as evaluate_retrieval_turn2session does."""
    out = {}
    sessions = list(dict.fromkeys(p.session[t] for t in ranked))
    for k in KS:
        top, top_sessions = set(ranked[:k]), set(sessions[:k])
        if p.evidence:
            out[f"turn_any@{k}"] = float(bool(p.evidence & top))
            out[f"turn_all@{k}"] = float(p.evidence <= top)
        out[f"session_any@{k}"] = float(bool(p.answer_sessions & top_sessions))
        out[f"session_all@{k}"] = float(p.answer_sessions <= top_sessions)
        if p.latest:
            out[f"latest@{k}"] = float(bool(p.latest & top))
    return out


def dev_ids(data: list[dict]) -> set[str]:
    """Every 5th question after sorting by type, then by SHA-1 of the id: 100 dev
    questions with the types in proportion. The other 400 are the test set."""
    ordered = sorted(data, key=lambda q: (q["question_type"], hashlib.sha1(q["question_id"].encode()).hexdigest()))
    return {q["question_id"] for q in ordered[::5]}


_PLANS: list[Plan] = []  # set before the worker pool forks, so workers share them
_TEST_INDEX: list[int] = []  # the test questions' plans, in the order of their results
_EMB: np.ndarray | None = None


def _replay_task(task: tuple) -> dict:
    i, policy, fraction, live_k = task
    p = _PLANS[i]
    budget = None if fraction is None else max(1, round(fraction * len(p.rows)))
    return replay(p, policy, budget, live_k, _EMB)


def evaluate(configs: dict, questions: list[int], live_k: int) -> dict[object, list[dict]]:
    """Replay every (policy, budget fraction) in `configs` on every question, in parallel."""
    tasks = [(i, policy, fraction, live_k) for policy, fraction in configs.values() for i in questions]
    with get_context("fork").Pool() as pool:
        results = pool.map(_replay_task, tasks, chunksize=16)
    n = len(questions)
    return {key: results[j * n:(j + 1) * n] for j, key in enumerate(configs)}


def mean(results: list[dict], metric: str) -> float | None:
    values = [r[metric] for r in results if r.get(metric) is not None]
    return sum(values) / len(values) if values else None


def tune(dev: list[int]) -> dict[tuple, tuple[Policy, float]]:
    """For each decay policy and budget, the grid setting with the best PRIMARY on dev.
    Ties go to the first in grid order, which tries no decay ranking (weight 0) first."""
    grid = {
        (name, fraction, fusion, weight, scale): (replace(base, fusion=fusion, weight=weight, scale_hours=scale), fraction)
        for name, base in TUNED.items()
        for fraction in ((None,) if base.evict is None else BUDGETS)
        for fusion, weights in WEIGHTS.items()
        for weight in weights
        for scale in SCALES
    }
    results = evaluate(grid, dev, LIVE_K)
    best: dict[tuple, tuple[Policy, float]] = {}
    for key, (policy, fraction) in grid.items():
        value = mean(results[key], PRIMARY)
        if key[:2] not in best or value > best[key[:2]][1]:
            best[key[:2]] = (policy, value)
    return best


def _bootstrap(diffs: list[float], seed: int = 0) -> tuple[float, float]:
    """95% paired bootstrap interval of a mean difference over questions."""
    rng = np.random.default_rng(seed)
    values = np.asarray(diffs)
    means = values[rng.integers(0, len(values), (10_000, len(values)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{100 * value:.1f}"


ORDER = ["keep-all", "keep-all, decay-ranked", "recency", "lru", "decay-only", "engram-count", "engram-spaced"]


def label(key: tuple) -> str:
    return key[0] if key[1] is None else f"{key[0]} @ {key[1]:.0%}"


def table(header: list[str], lines: list[list[str]]) -> str:
    return "\n".join([f"| {' | '.join(header)} |", f"|{'---|' * len(header)}", *(f"| {' | '.join(line)} |" for line in lines)])


def by_budget(results: dict, metric: str) -> str:
    """One row per policy, one column per budget; keep-all's single result repeats."""
    lines = []
    for name in ORDER:
        keys = sorted((k for k in results if k[0] == name), key=lambda k: k[1] or 0)
        cells = [_pct(mean(results[k], metric)) for k in keys]
        lines.append([name, *(cells * len(BUDGETS) if len(keys) == 1 else cells)])
    return table(["policy", *(f"{f:.0%} budget" for f in BUDGETS)], lines)


def _report(counts: dict, chosen: dict, configs: dict, results: dict, minutes: float) -> str:
    rows = sorted(configs, key=lambda key: (ORDER.index(key[0]), key[1] or 0))  # the policy ladder
    test = results[LIVE_K]
    types = sorted({p.qtype for p in _PLANS})

    metrics = [f"turn_all@{k}" for k in KS] + [f"turn_any@{k}" for k in KS] + ["session_all@10", "session_any@10",
               "evidence_kept", "latest@10"]
    detail = table(["policy", *metrics, "memories", "recall ms"], [
        [label(k), *(_pct(mean(test[k], m)) for m in metrics),
         f"{mean(test[k], 'memories'):.0f}", f"{mean(test[k], 'recall_ms'):.2f}"]
        for k in rows
    ])
    per_type = table(["policy", *types], [
        [label(k), *(_pct(mean([r for r, i in zip(test[k], _TEST_INDEX) if _PLANS[i].qtype == t], PRIMARY)) for t in types)]
        for k in rows if k[1] in (None, 0.25)
    ])

    # Losses: engram-spaced against the better of the two budgeted baselines, per type.
    loss_lines, losses = [], []
    for t in [*types, "all"]:
        cells = []
        for f in BUDGETS:
            idx = [j for j, i in enumerate(_TEST_INDEX) if t == "all" or _PLANS[i].qtype == t]
            pick = [j for j in idx if test[("engram-spaced", f)][j].get(PRIMARY) is not None]
            base = max(("recency", "lru"), key=lambda n: mean([test[(n, f)][j] for j in pick], PRIMARY))
            diffs = [test[("engram-spaced", f)][j][PRIMARY] - test[(base, f)][j][PRIMARY] for j in pick]
            d, (lo, hi) = sum(diffs) / len(diffs), _bootstrap(diffs)
            cells.append(f"{100 * d:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] vs {base}")
            if d < 0:
                losses.append(f"{t} at {f:.0%}")
        loss_lines.append([t, *cells])

    def against_lru(name, metric, f):
        diffs = [a[metric] - b[metric] for a, b in zip(test[(name, f)], test[("lru", f)]) if a.get(metric) is not None]
        lo, hi = _bootstrap(diffs)
        return f"{100 * sum(diffs) / len(diffs):+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]"

    posthoc = table(["variant", "metric", *(f"{f:.0%} budget" for f in BUDGETS)], [
        [name, metric, *(against_lru(name, metric, f) for f in BUDGETS)]
        for name in ("engram-count", "engram-spaced")
        for metric in (PRIMARY, "session_all@10", "evidence_kept", "latest@10")
    ])

    settings = table(["policy", "budget", "fusion", "weight", "decay scale (h)", f"dev {PRIMARY}"], [
        [n, "none" if f is None else f"{f:.0%}", p.fusion, f"{p.weight:g}", f"{p.scale_hours:g}", _pct(v)]
        for (n, f), (p, v) in sorted(chosen.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[0][1] or 0))
    ])

    return f"""# LongMemEval: should an agent forget?

Generated by `python -m bench.longmemeval run` on {date.today().isoformat()} (about {minutes:.0f} minutes on a
laptop CPU). Scores are percentages over the test questions. Settings were picked on the dev
questions only, and fixed before the test set was first scored.

**Data.** LongMemEval-S, cleaned (MIT), revision `98d7416`: 500 questions, each with a chat
history of about 48 sessions and 490 turns. Dev is every 5th question after sorting by type
and the SHA-1 of the id ({counts['dev']} questions); test is the other {counts['test']}. The
{counts['abstention']} abstention questions are not scored, which leaves {counts['dev_scored']} dev and
{counts['test_scored']} test questions.

**Replay.** Sessions in date order, every turn stored as a memory. At each user turn the agent
first recalls its top {LIVE_K} memories for that turn, which strengthens them. The budget is a
fraction of the history's turns and holds throughout. The question is asked after the last
turn. Embeddings: all-MiniLM-L6-v2, which reads the first 256 tokens of a turn.

**Metrics.** LongMemEval's own: turn `all@k` means every evidence turn is in the top k,
`any@k` at least one; session metrics read down the ranking until k distinct sessions.
Settings were picked on {PRIMARY}. Two differences from the official retrieval evaluation:
memories include assistant turns, so single-session-assistant questions are scored here and
skipped there. And two metrics are added, fixed before any run: *evidence_kept*, the share of
evidence turns still in memory when the question comes, and, for knowledge-update only,
*latest@10*, whether the newest evidence turn is in the top 10. Knowledge-update's `all@k` also
needs the outdated fact, which a forgetting memory should drop.

## {PRIMARY} by budget

{by_budget(test, PRIMARY)}

keep-all ignores the budget, so its row repeats.

## Every metric

{detail}

## {PRIMARY} by question type, at a 25% budget

{per_type}

## Where engram-spaced loses

engram-spaced was named in advance as the headline. Each cell is engram-spaced minus whichever
of recency and LRU did better in that cell, in {PRIMARY} points, with a 95% paired bootstrap
interval:

{table(["question type", *(f"{f:.0%} budget" for f in BUDGETS)], loss_lines)}

{"engram-spaced trails in: " + ", ".join(losses) + "." if losses else "engram-spaced trails nowhere."}

## Added after seeing the results: both variants against LRU

engram-count did better than the headline variant, so both are compared with LRU here, the
strongest baseline, on the metrics that separate them, with the same 95% paired intervals.
These comparisons were not named in advance and many were made, so read them as exploratory.

{posthoc}

## Settings picked on dev

{settings}

## Check: the agent recalls 10 per turn instead of {LIVE_K}

Same settings, same test questions.

{by_budget(results[10], PRIMARY)}
"""


def run(data: list[dict]) -> None:
    global _PLANS, _EMB, _TEST_INDEX
    all_texts = texts(data)
    _EMB = np.load(EMBEDDINGS, mmap_mode="r")
    if _EMB.shape[0] != len(all_texts):
        raise SystemExit("the embeddings don't match the data; run the embed command again")
    row = {t: i for i, t in enumerate(all_texts)}
    in_dev = dev_ids(data)
    scored = [q for q in data if not q["question_id"].endswith("_abs")]
    _PLANS = [plan(q, row) for q in scored]
    dev = [i for i, q in enumerate(scored) if q["question_id"] in in_dev]
    test = _TEST_INDEX = [i for i, q in enumerate(scored) if q["question_id"] not in in_dev]
    counts = {"dev": len(in_dev), "test": len(data) - len(in_dev), "abstention": len(data) - len(scored),
              "dev_scored": len(dev), "test_scored": len(test)}
    del data, scored, all_texts, row

    started = time.time()
    chosen = tune(dev)
    configs = {("keep-all", None): (POLICIES["keep-all"], None)}
    configs |= {(name, f): (POLICIES[name], f) for name in ("recency", "lru") for f in BUDGETS}
    configs |= {key: (policy, key[1]) for key, (policy, _) in chosen.items()}
    results = {k: evaluate(configs, test, k) for k in (LIVE_K, 10)}
    minutes = (time.time() - started) / 60

    (DATA / "results").mkdir(exist_ok=True)
    raw = {
        "counts": counts,
        "chosen": {f"{n} {f}": {**asdict(p), "dev": v} for (n, f), (p, v) in chosen.items()},
        "test": {str(k): {f"{n} {f}": r for (n, f), r in res.items()} for k, res in results.items()},
    }
    (DATA / "results" / "longmemeval.json").write_text(json.dumps(raw))
    report = _report(counts, chosen, configs, results, minutes)
    (ROOT / "bench" / "RESULTS.md").write_text(report)
    print(report)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m bench.longmemeval", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["embed", "run"])
    args = parser.parse_args()
    if args.command == "embed":
        data = load()
        embed(texts(data), EMBEDDINGS)
    else:
        run(load())  # no reference kept here, so run() can free the JSON before it forks


if __name__ == "__main__":
    main()
