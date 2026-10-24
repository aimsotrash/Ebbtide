"""
Do the LongMemEval findings hold on LoCoMo? The same replay, on 10 two-person
conversations that span 5 to 10 months, with the settings LongMemEval's dev split picked.
Nothing is tuned on LoCoMo.

  python -m bench.locomo   # after python -m bench.longmemeval run -> bench/RESULTS-locomo.md

Data: data/locomo10.json at a pinned commit, checked by SHA-256, in the git-ignored data/
folder. LoCoMo is CC BY-NC 4.0, non-commercial use with attribution: Maharana et al.,
"Evaluating Very Long-Term Conversational Memory of LLM Agents", ACL 2024.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timezone

import numpy as np

from bench.longmemeval import (BUDGETS, DATA, KS, LIVE_K, ORDER, PRIMARY, ROOT, Plan, _pct, ask, by_budget, embed,
                               fetch, fill, label, mean, table)
from intelligence.memory import POLICIES, Policy

FILE = DATA / "locomo10.json"
URL = "https://raw.githubusercontent.com/snap-research/locomo/3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376/data/locomo10.json"
SHA256 = "79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4"
EMBEDDINGS = DATA / "locomo10_minilm.npy"  # one row per text, in texts() order
# The repo's task_eval/evaluation.py scores 1 as multi-hop and 5 as adversarial, and splits
# category-3 answers at ";" as open-domain ones; 77% of category-2 questions ask "When".
CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}  # 5, adversarial: not scored
DATE_FORMAT = "%I:%M %p on %d %B, %Y"


def turn_text(t: dict) -> str:
    """A turn as LoCoMo's own retrieval code writes it: who said it, plus any shared image."""
    text = f'{t["speaker"]} said, "{t["text"]}"'
    return f'{text} [shares {t["blip_caption"]}]' if t.get("blip_caption") else text


def sessions(c: dict) -> list[int]:
    return sorted(int(k.split("_")[1]) for k in c if re.fullmatch(r"session_\d+", k))


def texts(data: list[dict]) -> list[str]:
    """Every distinct turn and question, in a fixed order."""
    turns = (turn_text(t) for d in data for n in sessions(d["conversation"]) for t in d["conversation"][f"session_{n}"])
    return list(dict.fromkeys([*turns, *(qa["question"] for d in data for qa in d["qa"])]))


def dia_ids(evidence: list[str]) -> list[str]:
    """Evidence turn ids, tolerating the dataset's typos: 'D8:6; D9:17', 'D:11:26', 'D30:05'."""
    return [f"D{s}:{t}" for e in evidence for s, t in re.findall(r"D:?(\d+):0*(\d+)", e)]


def conversation(d: dict, row: dict[str, int]) -> tuple[Plan, list[Plan], int]:
    """One conversation's replay plan, its scored questions, and how many questions were
    skipped because none of their evidence ids names a turn."""
    c = d["conversation"]
    rows, times, session, position = [], [], [], {}
    for s, n in enumerate(sessions(c)):
        when = datetime.strptime(c[f"session_{n}_date_time"], DATE_FORMAT).replace(tzinfo=timezone.utc).timestamp()
        start = max(when, times[-1] + 1) if times else when
        for j, t in enumerate(c[f"session_{n}"]):
            position[t["dia_id"]] = len(rows)
            rows.append(row[turn_text(t)])
            times.append(start + j)
            session.append(s)
    everyone = [True] * len(rows)  # both speakers are users, so the agent recalls at every turn
    turns = Plan("conversation", rows, everyone, times, session, frozenset(), frozenset(), frozenset(), 0, 0.0)
    questions, skipped = [], 0
    for qa in d["qa"]:
        if qa["category"] not in CATEGORIES:
            continue
        evidence = frozenset(position[i] for i in dia_ids(qa.get("evidence", [])) if i in position)
        if not evidence:
            skipped += 1
            continue
        questions.append(Plan(CATEGORIES[qa["category"]], rows, everyone, times, session, evidence,
                              frozenset(session[p] for p in evidence), frozenset(), row[qa["question"]], times[-1] + 1))
    return turns, questions, skipped


def configs() -> dict:
    """keep-all, recency and LRU, plus each decay policy as LongMemEval's dev split set it."""
    picked = DATA / "results" / "longmemeval.json"
    if not picked.exists():
        raise SystemExit("run `python -m bench.longmemeval run` first: LoCoMo reuses its dev-picked settings")
    out = {("keep-all", None): (POLICIES["keep-all"], None)}
    out |= {(name, f): (POLICIES[name], f) for name in ("recency", "lru") for f in BUDGETS}
    for key, settings in json.loads(picked.read_text())["chosen"].items():
        name, fraction = key.rsplit(" ", 1)
        f = None if fraction == "None" else float(fraction)
        out[(name, f)] = (Policy(**{k: v for k, v in settings.items() if k != "dev"}), f)
    return out


def _interval(diffs_by_conversation: list[list[float]], seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval of a mean difference that resamples whole conversations:
    questions about one conversation share its replay, so they aren't independent."""
    sums = np.array([sum(d) for d in diffs_by_conversation])
    counts = np.array([len(d) for d in diffs_by_conversation])
    picks = np.random.default_rng(seed).integers(0, len(sums), (10_000, len(sums)))
    means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _report(results: dict, counts: dict, minutes: float) -> str:
    rows = sorted(results, key=lambda key: (ORDER.index(key[0]), key[1] or 0))
    cats = list(CATEGORIES.values())
    metrics = [f"turn_all@{k}" for k in KS] + [f"turn_any@{k}" for k in KS] + ["session_all@10", "session_any@10",
               "evidence_kept"]
    detail = table(["policy", *metrics, "memories", "recall ms"], [
        [label(k), *(_pct(mean(results[k], m)) for m in metrics),
         f"{mean(results[k], 'memories'):.0f}", f"{mean(results[k], 'recall_ms'):.2f}"]
        for k in rows
    ])
    per_category = table(["policy", *cats], [
        [label(k), *(_pct(mean([r for r in results[k] if r["category"] == c], PRIMARY)) for c in cats)]
        for k in rows if k[1] in (None, 0.25)
    ])

    def against_lru(name, metric, f):
        by_conversation = [[] for _ in range(counts["conversations"])]
        for a, b in zip(results[(name, f)], results[("lru", f)]):
            by_conversation[a["conversation"]].append(a[metric] - b[metric])
        diffs = [d for ds in by_conversation for d in ds]
        lo, hi = _interval(by_conversation)
        return f"{100 * sum(diffs) / len(diffs):+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]"

    versus = table(["variant", "metric", *(f"{f:.0%} budget" for f in BUDGETS)], [
        [name, metric, *(against_lru(name, metric, f) for f in BUDGETS)]
        for name in ("engram-count", "engram-spaced")
        for metric in (PRIMARY, "session_all@10", "evidence_kept")
    ])

    return f"""# LoCoMo: does it hold on months-long conversations?

Generated by `python -m bench.locomo` on {date.today().isoformat()} ({'under a minute' if minutes < 1 else f'about {minutes:.0f} minutes'} on a laptop CPU).
Scores are percentages over the scored questions. Nothing was tuned on LoCoMo.

**Data.** LoCoMo (Maharana et al., ACL 2024; CC BY-NC 4.0, used for non-commercial research
with attribution) at commit `3eb6f2c`: {counts['conversations']} conversations between two people,
each 369 to 689 turns over 5 to 10 months. {counts['scored']} questions are scored: multi-hop,
temporal, open-domain and single-hop. The {counts['adversarial']} adversarial questions have no
answer in the conversation and are not scored, and {counts['skipped']} more are skipped because
none of their evidence ids names a turn.

**Replay.** As for LongMemEval (see RESULTS.md), with three changes. Both speakers are users,
so the agent recalls its top {LIVE_K} memories at every turn. Each memory reads
`Name said, "…"` plus any shared image's caption, as LoCoMo's own retrieval code writes turns.
And all of a conversation's questions come after its last turn and only look at the memory, so
their order doesn't matter. Each decay policy keeps the settings LongMemEval's dev split picked.

**Intervals.** Questions about one conversation share its replay, so the 95% intervals resample
whole conversations. With 10 conversations they are wide, and likely still somewhat too narrow.

## {PRIMARY} by budget

{by_budget(results, PRIMARY)}

keep-all ignores the budget, so its row repeats.

## Every metric

{detail}

## {PRIMARY} by category, at a 25% budget

{per_category}

## Both Engram variants against LRU

Chosen after the LongMemEval results and before this run. Each cell is the variant minus LRU, in points, with a 95% interval:

{versus}
"""


def run() -> None:
    data = fetch(FILE, URL, SHA256)
    all_texts = texts(data)
    if not EMBEDDINGS.exists():
        embed(all_texts, EMBEDDINGS)  # about 2 minutes on a laptop CPU
    emb = np.load(EMBEDDINGS)
    if emb.shape[0] != len(all_texts):
        raise SystemExit(f"{EMBEDDINGS} doesn't match the data; delete it and run again")
    row = {t: i for i, t in enumerate(all_texts)}
    plans = [conversation(d, row) for d in data]
    counts = {
        "conversations": len(plans),
        "scored": sum(len(questions) for _, questions, _ in plans),
        "skipped": sum(skipped for _, _, skipped in plans),
        "adversarial": sum(qa["category"] == 5 for d in data for qa in d["qa"]),
    }
    started = time.time()
    results = {}
    for key, (policy, fraction) in configs().items():
        results[key] = []
        for c, (turns, questions, _) in enumerate(plans):
            budget = None if fraction is None else max(1, round(fraction * len(turns.rows)))
            store, recall_ms = fill(turns, policy, budget, LIVE_K, emb)
            results[key] += [{**ask(store, q, emb), "recall_ms": recall_ms, "category": q.qtype, "conversation": c}
                             for q in questions]
    report = _report(results, counts, (time.time() - started) / 60)
    (DATA / "results" / "locomo.json").write_text(json.dumps({f"{n} {f}": r for (n, f), r in results.items()}))
    (ROOT / "bench" / "RESULTS-locomo.md").write_text(report)
    print(report)


if __name__ == "__main__":
    run()
