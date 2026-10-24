"""
Ebbinghaus forgetting curve: the decay scale and stability rule the agent memory store
(agent.py) is built on.

Formula:  R(t) = e^( -t / (S * BASE_HOURS) )
  t          = hours since the memory was last recalled, or since it was added
  S          = stability: 1.0 for a memory never recalled; under the count rule,
               1.0 + 0.5 * ln(1 + recalls)
  BASE_HOURS = 216 h (9 days), the decay time scale of a memory never recalled

Typical behaviour:
  - Never recalled, added 3 days ago                   → R ≈ 0.72
  - Never recalled, added 30 days ago                  → R ≈ 0.04
  - Recalled 3 times (count rule), the last 3 days ago → R ≈ 0.82
"""

import math

_BASE_HOURS = 24 * 9  # 216 hours: the 9-day time scale of a memory never recalled


def stability(recall_count: int) -> float:
    return 1.0 + 0.5 * math.log1p(recall_count)
