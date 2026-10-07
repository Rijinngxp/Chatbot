"""Call the research agent's tools directly — useful for debugging retrieval quality."""
from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..schemas import SearchRequest, SearchResponse
from ..tools import rag_tool, web_search_tool

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/rag", response_model=SearchResponse, summary="Hybrid search + rerank over the knowledge base")
async def rag_search(req: SearchRequest) -> SearchResponse:
    if not get_settings().enable_rag:
        raise HTTPException(400, "RAG is disabled (ENABLE_RAG=false)")
    return SearchResponse(query=req.query, results=await rag_tool(req.query))


@router.post("/web", response_model=SearchResponse, summary="Tavily web search")
async def web_search(req: SearchRequest) -> SearchResponse:
    if not get_settings().web_search_available:
        raise HTTPException(400, "Web search is disabled (ENABLE_WEB_SEARCH / TAVILY_API_KEY)")
    try:
        return SearchResponse(query=req.query, results=await web_search_tool(req.query))
    except Exception as exc:
        raise HTTPException(502, f"Tavily error: {exc}") from exc
