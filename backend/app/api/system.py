import asyncio

from fastapi import APIRouter

from ..config import get_settings
from ..rag.store import get_store
from ..schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health() -> HealthResponse:
    docs = await asyncio.to_thread(get_store().count) if get_settings().enable_rag else None
    return HealthResponse(status="ok", documents=docs)


@router.get("/config", summary="Pipeline switches and models from .env (used by the UI)")
def config() -> dict:
    s = get_settings()
    return {
        "rag": s.enable_rag,
        "web_search": s.web_search_available,
        "verifier": s.enable_verifier,
        "reranker": s.enable_reranker,
        "memory": s.memory_available,
        # e.g. {"planner": "ollama · qwen3:4b", "verifier": "groq · openai/gpt-oss-120b", ...}
        "models": {a: " · ".join(s.agent_llm(a)) for a in ("planner", "verifier", "synthesizer")},
        # Only a problem when some agent actually uses Groq.
        "groq_configured": bool(s.groq_api_key) or not s.uses_groq,
    }

