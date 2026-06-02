"""Knowledge domain primitives: chunking + complexity scoring."""

from intelligence.domain.chunking import chunk_text
from intelligence.domain.complexity import score as complexity_score

__all__ = ["chunk_text", "complexity_score"]
