"""Agent memory store: eviction policies, ranking and strengthening.

Deterministic: every call passes an explicit `now`, and the vectors are hand-made.
"""

import math

import pytest

from intelligence.memory import POLICIES, MemoryStore, Policy, stability

DAY = 24 * 3600.0
X, Y = [1.0, 0.0], [0.0, 1.0]


def test_recall_ranks_by_similarity_and_refreshes_hits():
    store = MemoryStore(POLICIES["keep-all"])
    store.add("x", X, now=0)
    store.add("y", Y, now=0)
    store.add("xy", [1.0, 1.0], now=0)
    hits = store.recall(X, k=2, now=DAY)
    assert [(m.text, round(score, 3)) for m, score in hits] == [("x", 1.0), ("xy", 0.707)]
    assert [(m.recall_count, m.last_recalled_at) for m in store.memories] == [(1, DAY), (0, None), (1, DAY)]
    assert store.recall(X, k=1, now=2 * DAY, refresh=False)[0][0].recall_count == 1  # a look changes nothing
    assert MemoryStore(POLICIES["lru"]).recall(X, k=3, now=0) == []


@pytest.mark.parametrize("name, victim_a, victim_b", [
    ("keep-all", None, None),
    ("recency", "m1", "m1"),
    ("lru", "m2", "m1"),
    ("decay-only", "m2", "m1"),     # LRU's evictions, since S stays 1
    ("ebbtide-count", "m2", "m2"),   # the recall made m1 outlast the newer m2
    ("ebbtide-spaced", "m2", "m2"),
])
def test_eviction_by_policy(name, victim_a, victim_b):
    # A: m1 is recalled after m2 is added, so m1 was used more recently.
    a = MemoryStore(POLICIES[name], budget=2)
    a.add("m1", X, now=0)
    a.add("m2", Y, now=1 * DAY)
    a.recall(X, k=1, now=2 * DAY)
    a.add("m3", Y, now=3 * DAY)
    # B: m1 is recalled once, then m2 is added and never recalled.
    b = MemoryStore(POLICIES[name], budget=2)
    b.add("m1", X, now=0)
    b.recall(X, k=1, now=3 * DAY)
    b.add("m2", Y, now=4 * DAY)
    named = b.next_eviction(10 * DAY)
    b.add("m3", Y, now=10 * DAY)
    assert (named and named.text) == victim_b  # it names exactly what the add then removed
    for store, victim in ((a, victim_a), (b, victim_b)):
        assert {m.text for m in store.memories} == {"m1", "m2", "m3"} - {victim}
    assert a.stats(now=3 * DAY)["budget"] == (None if name == "keep-all" else 2)


def test_spaced_strengthening_rewards_spacing_and_count_does_not():
    def recalled(rule, gap):
        store = MemoryStore(Policy(evict=None, strengthen=rule))
        memory = store.add("m", X, now=0)
        store.recall(X, k=1, now=gap)
        return store, memory

    assert recalled("spaced", 0)[1].stability == 1.0  # recalled at R = 1: no gain
    spaced_store, spaced = recalled("spaced", 3 * DAY)
    assert spaced.stability == pytest.approx(15.6, abs=0.1)
    count_store, counted = recalled("count", 3 * DAY)
    assert counted.stability == recalled("count", 0)[1].stability == stability(1)
    # A month after that recall, the spaced memory is still strong.
    month_later = 33 * DAY
    assert spaced_store.stats(month_later)["mean_retrievability"] == pytest.approx(0.81, abs=0.01)
    assert count_store.stats(month_later)["mean_retrievability"] == pytest.approx(0.08, abs=0.01)


def test_count_rule_stability_grows_more_slowly_with_each_recall():
    assert [round(stability(n), 3) for n in range(4)] == [1.0, 1.347, 1.549, 1.693]  # 1 + 0.5 ln(1 + n)


@pytest.mark.parametrize("fusion", ["add", "mul"])
def test_decay_ranking_prefers_the_stronger_of_equal_matches(fusion):
    def order(weight):
        store = MemoryStore(Policy(evict=None, weight=weight, fusion=fusion))
        store.add("old", X, now=0)
        store.add("new", X, now=5 * DAY)
        return [m.text for m, _ in store.recall(X, k=2, now=6 * DAY)]

    assert order(0.0) == ["old", "new"]  # similarity alone: ties keep insertion order
    assert order(0.5) == ["new", "old"]


def test_budget_forget_stats_and_guards():
    store = MemoryStore(POLICIES["ebbtide-spaced"], budget=3)
    for day in range(10):
        store.add(f"m{day}", X, now=day * DAY)
    assert [m.text for m in store.memories] == ["m7", "m8", "m9"]
    same_session = MemoryStore(POLICIES["recency"], budget=2)
    for text in ("t1", "t2", "t3"):  # one timestamp: the earliest turn goes first
        same_session.add(text, X, now=0)
    assert [m.text for m in same_session.memories] == ["t2", "t3"]
    assert store.forget(store.memories[0].id) and not store.forget(-1)
    assert store.stats(now=18 * DAY) == {
        "count": 2,
        "budget": 3,
        "evicted": 7,
        "mean_retrievability": pytest.approx((math.exp(-10 / 9) + math.exp(-1)) / 2),
    }
    with pytest.raises(ValueError):
        MemoryStore(POLICIES["lru"], budget=0)
    with pytest.raises(ValueError):
        Policy(evict="oldest")


def test_similar_peeks_and_update_corrects_in_place():
    store = MemoryStore(POLICIES["ebbtide-count"], budget=10)
    old = store.add("coffee black", X, now=0)
    store.add("other", Y, now=0)
    store.recall(X, k=1, now=DAY)  # old earns a little stability
    earned = old.stability

    close = store.similar([1.0, 0.2], k=3, threshold=0.5)
    assert [(m.text, round(s, 2)) for m, s in close] == [("coffee black", 0.98)]  # "other" is below 0.5
    assert old.recall_count == 1  # a look: nothing strengthened

    fixed = store.update(old.id, "coffee with oat milk", [1.0, 0.1], now=5 * DAY)
    assert fixed is old and old.text == "coffee with oat milk"
    assert old.stability == earned and old.last_recalled_at == 5 * DAY  # full strength again
    assert store.update(99, "nothing", X, now=5 * DAY) is None


def test_hybrid_recall_lifts_a_keyword_match():
    store = MemoryStore(POLICIES["keep-all"])
    store.add("deploys use python 3.12", X, now=0)                       # cosine 1.0
    store.add("lunch is at noon", [0.9, math.sqrt(1 - 0.81)], now=0)       # cosine 0.9
    store.add("the staging database is postgres 16", [0.8, 0.6], now=0)  # cosine 0.8, the only keyword match
    by_vector = [m.text for m, _ in store.recall(X, k=3, now=0, refresh=False)]
    fused = [m.text for m, _ in store.recall(X, k=3, now=0, refresh=False, query_text="which postgres version")]
    assert by_vector == ["deploys use python 3.12", "lunch is at noon", "the staging database is postgres 16"]
    assert fused == ["deploys use python 3.12", "the staging database is postgres 16", "lunch is at noon"]
