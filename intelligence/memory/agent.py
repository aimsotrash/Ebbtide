"""
Long-term memory for AI agents, on the forgetting curve.

Each memory fades as  R = e^( -t / (S * scale) )
  t      = time since it was last recalled, or since it was added
  S      = stability: starts at 1 and grows on recall if the policy strengthens
  scale  = decay time scale, 216 h by default (the 9-day base the notes app used)

recall() ranks memories by similarity combined with R, then refreshes each one it
returns: t starts over, and S may grow. When an add would go over the budget, the
policy evicts one memory first.

Pure: no I/O and no wall clock. Every call that depends on time takes `now` in Unix
seconds, so a replay can drive time from a dataset's session dates and tests are
deterministic. Embeddings are inputs; the caller computes them.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

from intelligence.memory.ebbinghaus import _BASE_HOURS, stability

# The "spaced" rule is FSRS-6's stability update after a successful recall,
#   S' = S * (1 + e^w8 * (11 - D) * S^-w9 * (e^(w10 * (1 - R)) - 1)),
# with FSRS-6's default weights as shipped in fsrs 6.3.1, and the difficulty D fixed
# at FSRS's starting value after a "Good" first review, so it adds no knob. They are
# hardcoded rather than imported so a dependency bump can't move the results. On the
# 216 h scale, S is about the days until R falls to 0.9, the unit FSRS uses.
_W4, _W5, _W8, _W9, _W10 = 6.4133, 0.8334, 1.8722, 0.1666, 0.796
_D = _W4 - math.exp(2 * _W5) + 1          # ≈ 2.12
_SPACED_GAIN = math.exp(_W8) * (11 - _D)  # ≈ 57.8


@dataclass(frozen=True)
class Policy:
    """How a store forgets, ranks and strengthens.

    evict        what goes first when the store is full: "created" (oldest added),
                 "used" (least recently recalled or added), "retrievability"
                 (lowest R), or None to never evict (keep-all ignores the budget)
    weight       how much R counts in ranking; 0 ranks by similarity alone
    fusion       "add": sim + weight * log R, or "mul": sim * R ** weight
    strengthen   None, "count" (S grows with the recall count, as it did in the
                 notes app) or "spaced" (FSRS-6: the lower R was, the more S grows)
    scale_hours  decay time scale
    """

    evict: str | None
    weight: float = 0.0
    fusion: str = "add"
    strengthen: str | None = None
    scale_hours: float = _BASE_HOURS

    def __post_init__(self):
        if (
            self.evict not in (None, "created", "used", "retrievability")
            or self.fusion not in ("add", "mul")
            or self.strengthen not in (None, "count", "spaced")
            or self.scale_hours <= 0
        ):
            raise ValueError(f"invalid policy: {self}")


# Picked on the LongMemEval dev split: similarity alone ranked best almost everywhere, so
# fading decides what is evicted, not the order of a recall (bench/RESULTS.md).
DECAY_WEIGHT = 0.0

# Each step down the list changes one thing. With S fixed at 1, lowest-R eviction is
# exactly LRU's order, so decay-only vs lru measures the ranking term alone, and
# engram-* vs decay-only measures strengthening alone.
POLICIES = {
    "keep-all": Policy(evict=None),
    "recency": Policy(evict="created"),
    "lru": Policy(evict="used"),
    "decay-only": Policy(evict="retrievability", weight=DECAY_WEIGHT),
    "engram-count": Policy(evict="retrievability", weight=DECAY_WEIGHT, strengthen="count"),
    "engram-spaced": Policy(evict="retrievability", weight=DECAY_WEIGHT, strengthen="spaced"),
}


@dataclass(eq=False)  # compare by identity: the embedding is an array
class Memory:
    id: int
    text: str
    embedding: np.ndarray  # unit length
    created_at: float
    last_recalled_at: float | None = None
    stability: float = 1.0
    recall_count: int = 0
    source: dict | None = None  # opaque to the store, e.g. session and turn ids

    @property
    def used_at(self) -> float:
        return self.created_at if self.last_recalled_at is None else self.last_recalled_at


class MemoryStore:
    """At most `budget` memories (None = no limit), managed by one policy."""

    def __init__(self, policy: Policy, budget: int | None = None, memories=(), next_id: int = 1):
        """`memories` (in insertion order) and `next_id` restore a saved store; new ids
        start past both, so a deleted id is never handed out again."""
        if budget is not None and budget < 1:
            raise ValueError(f"budget must be at least 1, got {budget!r}")
        self.policy = policy
        self.budget = None if policy.evict is None else budget  # keep-all has no budget
        self.memories: list[Memory] = list(memories)  # insertion order, which breaks every tie
        self.evicted = 0
        self._ids = itertools.count(max([next_id, *(m.id + 1 for m in self.memories)]))

    def add(self, text: str, embedding, now: float, source: dict | None = None) -> Memory:
        """Store a memory, evicting first if the store is full."""
        if self.budget is not None:
            while len(self.memories) >= self.budget:
                self._evict(now)
        memory = Memory(next(self._ids), text, _unit(embedding), now, source=source)
        self.memories.append(memory)
        return memory

    def recall(self, query, k: int, now: float, refresh: bool = True) -> list[tuple[Memory, float]]:
        """The k best memories for a query embedding as (memory, score), best first.
        Each one returned is refreshed, and strengthened if the policy says so, unless
        `refresh` is False: a look that leaves every memory as it was."""
        if not self.memories or k < 1:
            return []
        # ponytail: restacks every embedding per call, O(n·d); keep one growing
        # matrix if the benchmark replay gets slow.
        sims = np.stack([m.embedding for m in self.memories]) @ _unit(query)
        log_r = self._log_r(now)
        if self.policy.fusion == "add":
            scores = sims + self.policy.weight * log_r
        else:  # clipped, or a weak memory would climb by shrinking a negative similarity
            scores = np.maximum(sims, 0.0) * np.exp(self.policy.weight * log_r)
        hits = []
        for i in np.argsort(-scores, kind="stable")[:k]:
            memory = self.memories[i]
            if refresh:
                self._refresh(memory, math.exp(log_r[i]), now)
            hits.append((memory, float(scores[i])))
        return hits

    def forget(self, memory_id: int) -> bool:
        """Delete a memory by id. Returns whether it was there."""
        for i, m in enumerate(self.memories):
            if m.id == memory_id:
                del self.memories[i]
                return True
        return False

    def retrievability(self, now: float) -> np.ndarray:
        """R of every memory at `now`, in insertion order."""
        return np.exp(self._log_r(now))

    def stats(self, now: float) -> dict:
        r = self.retrievability(now)
        return {
            "count": len(self.memories),
            "budget": self.budget,
            "evicted": self.evicted,
            "mean_retrievability": float(r.mean()) if r.size else None,
        }

    def _log_r(self, now: float) -> np.ndarray:
        hours = np.array([max(now - m.used_at, 0.0) for m in self.memories]) / 3600
        return -hours / (np.array([m.stability for m in self.memories]) * self.policy.scale_hours)

    def next_eviction(self, now: float) -> Memory | None:
        """The memory the policy would evict at `now`, or None if it never evicts."""
        if self.policy.evict is None or not self.memories:
            return None
        if self.policy.evict == "created":
            keys = [m.created_at for m in self.memories]
        elif self.policy.evict == "used":
            keys = [m.used_at for m in self.memories]
        else:
            keys = self._log_r(now)
        return self.memories[int(np.argmin(keys))]  # first minimum: the oldest insert loses ties

    def _evict(self, now: float) -> None:
        self.memories.remove(self.next_eviction(now))
        self.evicted += 1

    def _refresh(self, memory: Memory, r: float, now: float) -> None:
        if self.policy.strengthen == "count":
            memory.stability = stability(memory.recall_count + 1)
        elif self.policy.strengthen == "spaced":
            memory.stability *= 1 + _SPACED_GAIN * memory.stability**-_W9 * math.expm1(_W10 * (1 - r))
        memory.recall_count += 1
        memory.last_recalled_at = now


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    norm = np.linalg.norm(v)
    return v / norm if norm else v
