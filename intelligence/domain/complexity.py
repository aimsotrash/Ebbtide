"""
Complexity scorer for knowledge chunks.
Returns a float in [0, 1] used as the k-modifier in the decay formula.

Components:
  - length_score   (0.4 weight): normalized word count, capped at 400 words
  - vocab_score    (0.4 weight): unique-word ratio (vocabulary richness)
  - code_score     (0.2 weight): 1.0 if chunk contains code, else 0.0
"""

import re


_CODE_PATTERNS = re.compile(
    r"(```|~~~|^\s{4,}\S|def |class |function |import |#include|SELECT |INSERT |<[a-zA-Z]+>)",
    re.MULTILINE,
)


def score(text: str) -> float:
    words = text.split()
    if not words:
        return 0.5

    length_score = min(len(words) / 400.0, 1.0)
    vocab_score = len(set(w.lower() for w in words)) / len(words)
    code_score = 1.0 if _CODE_PATTERNS.search(text) else 0.0

    return (length_score * 0.4) + (vocab_score * 0.4) + (code_score * 0.2)
