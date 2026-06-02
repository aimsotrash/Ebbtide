from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ratelimit import rate_limit
from routers.deps import get_current_user_id
from intelligence.llm import get_llm

router = APIRouter()

# LLM endpoints are gated by both auth and a rate limit (paid-API spend control).
_ai_guard = [Depends(rate_limit("ai"))]


class SummarizeRequest(BaseModel):
    content: str


class ExpandRequest(BaseModel):
    content: str


class OptimizeRequest(BaseModel):
    original: str
    expanded: str


@router.post("/ai/summarize", dependencies=_ai_guard)
def summarize_note(body: SummarizeRequest, user_id: str = Depends(get_current_user_id)):
    llm = get_llm()
    result = llm.complete(
        f"Summarize these study notes in 3-5 clear, concise sentences. Return only the summary, no preamble:\n\n{body.content[:4000]}",
        system="You are a concise study assistant. Create clear, accurate summaries that capture the key points.",
    )
    return {"summary": result.strip()}


@router.post("/ai/expand", dependencies=_ai_guard)
def expand_note(body: ExpandRequest, user_id: str = Depends(get_current_user_id)):
    llm = get_llm()
    result = llm.complete(
        f"""Generate comprehensive, detailed study notes on the topic covered in these notes.
Include: definitions, key concepts, examples, common patterns, edge cases, and deeper insights.
Format with ## headers and bullet points for clarity. Be thorough and educational.

Original notes:
{body.content[:3000]}

Write detailed study notes on this topic:""",
        system="You are an expert educator. Create comprehensive, well-structured study notes that go deep into the topic.",
    )
    return {"expanded": result.strip()}


@router.post("/ai/optimize", dependencies=_ai_guard)
def optimize_note(body: OptimizeRequest, user_id: str = Depends(get_current_user_id)):
    llm = get_llm()
    result = llm.complete(
        f"""You have two notes on the same topic. Combine them into one optimized study note.

Rules:
- Keep the best insights and examples from both
- Remove redundancy
- Structure with ## headers and bullet points
- Be concise but comprehensive
- Preserve any specific facts, formulas, or code from the original

ORIGINAL NOTE:
{body.original[:2000]}

AI-EXPANDED NOTE:
{body.expanded[:2000]}

Write the optimized combined note:""",
        system="You are an expert at synthesizing study notes. Create the best possible combined note.",
    )
    return {"optimized": result.strip()}
