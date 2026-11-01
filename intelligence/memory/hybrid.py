"""
Keyword search to fuse with the embeddings: BM25, and reciprocal rank fusion.

bench/hybrid.py measured the fusion, untuned, against the embeddings alone: +11.4 points of
turn_all@10 on LongMemEval and +8.7 on LoCoMo, both with intervals above zero.
"""

from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

RRF_K = 60       # the usual constant; never tuned here
K1, B = 1.5, 0.75  # BM25's usual settings; never tuned here


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def bm25(query: list[str], docs: list[list[str]]) -> np.ndarray:
    """BM25 score of each doc for the query, with statistics over these docs only."""
    lengths = np.array([len(d) for d in docs], dtype=float)
    avg = max(lengths.mean(), 1.0) if len(docs) else 1.0
    df = Counter(t for d in docs for t in set(d))
    counts = [Counter(d) for d in docs]
    scores = np.zeros(len(docs))
    for term in set(query):
        if term in df:
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            tf = np.array([c[term] for c in counts], dtype=float)
            scores += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * lengths / avg))
    return scores


def rrf(*rankings: list[int]) -> list[tuple[int, float]]:
    """Reciprocal rank fusion of rankings over the same items, as (item, score) best first.
    Ties keep the first ranking's order."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            fused[item] = fused.get(item, 0.0) + 1 / (RRF_K + rank + 1)
    return [(item, fused[item]) for item in sorted(rankings[0], key=lambda item: -fused[item])]
