"""LLM orchestration: provider abstraction, categorization, quiz generation."""

from intelligence.llm.categorization import CATEGORIES, classify
from intelligence.llm.provider import LLMService, get_llm
from intelligence.llm.quiz_generation import (
    FALLBACK_QUESTIONS,
    MCQ_SYSTEM,
    difficulty,
    generate_mcq,
)

__all__ = [
    "get_llm",
    "LLMService",
    "classify",
    "CATEGORIES",
    "generate_mcq",
    "difficulty",
    "FALLBACK_QUESTIONS",
    "MCQ_SYSTEM",
]
