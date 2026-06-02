"""
Semantic text chunker.

Target: 200–400 tokens per chunk, 50-token overlap.
Uses word count as a token approximation (word_count * 0.75 ≈ tokens).
No external tokenizer dependency.

Strategy:
  1. Split on double-newline paragraph boundaries.
  2. Merge short paragraphs until the target window is reached.
  3. Split oversized paragraphs by sentence.
  4. Apply overlap by prepending the last N words of the previous chunk.
"""

import re

TARGET_WORDS = 280      # ~373 tokens (280 / 0.75)
MAX_WORDS = 530         # ~400 tokens ceiling
OVERLAP_WORDS = 38      # ~50 tokens


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) / 0.75)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def chunk_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    def flush(buf: list[str]) -> None:
        joined = " ".join(buf).strip()
        if joined:
            chunks.append(joined)

    for para in paragraphs:
        words = para.split()

        if len(words) > MAX_WORDS:
            # Oversized paragraph: split by sentence first
            if buffer:
                flush(buffer)
                buffer, buffer_words = [], 0
            sentences = _split_sentences(para)
            for sent in sentences:
                sw = len(sent.split())
                if buffer_words + sw > MAX_WORDS and buffer:
                    flush(buffer)
                    buffer, buffer_words = [], 0
                buffer.append(sent)
                buffer_words += sw
            continue

        if buffer_words + len(words) > MAX_WORDS and buffer:
            flush(buffer)
            buffer, buffer_words = [], 0

        buffer.append(para)
        buffer_words += len(words)

        if buffer_words >= TARGET_WORDS:
            flush(buffer)
            buffer, buffer_words = [], 0

    if buffer:
        flush(buffer)

    return _apply_overlap(chunks)


def _apply_overlap(chunks: list[str]) -> list[str]:
    if len(chunks) <= 1:
        return chunks
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_words = chunks[i - 1].split()
        overlap_prefix = " ".join(prev_words[-OVERLAP_WORDS:]) if len(prev_words) >= OVERLAP_WORDS else " ".join(prev_words)
        result.append(overlap_prefix + " " + chunks[i] if overlap_prefix else chunks[i])
    return result
