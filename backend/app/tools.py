"""Tools available to the research agent: RAG retrieval and Tavily web search."""
import asyncio

from tavily import AsyncTavilyClient

from .config import get_settings
from .rag.store import get_store


async def rag_tool(query: str) -> list[dict]:
    store = get_store()
    if await asyncio.to_thread(store.count) == 0:
        return []
    hits = await asyncio.to_thread(store.hybrid_search, query)
    return [
        {
            "type": "document",
            "title": f"{h['filename']} (chunk {h['chunk_index'] + 1})",
            "url": None,
            "content": h["text"],
            "score": h.get("rerank_score", h["rrf_score"]),
            "meta": {"matched_by": h["matched_by"], "rrf_score": h["rrf_score"]},
        }
        for h in hits
    ]


# Planner freshness -> Tavily time filter (by publish date)
TIME_RANGES = {"realtime": "day", "recent": "week"}


async def web_search(query: str, freshness: str = "any", topic: str = "general") -> tuple[list[dict], str]:
    """Tavily search tuned for freshness. Returns (results, description of the filter actually used)."""
    s = get_settings()
    if not s.web_search_available:
        return [], "web search unavailable"
    client = AsyncTavilyClient(api_key=s.tavily_api_key)

    async def run(time_range: str | None) -> dict:
        return await client.search(
            query=query,
            topic=topic,
            time_range=time_range,
            max_results=s.tavily_max_results,
            search_depth=s.tavily_search_depth,
            include_answer=s.tavily_include_answer,
        )

    time_range = TIME_RANGES.get(freshness)
    resp = await run(time_range)
    used = f"{topic}, last {time_range}" if time_range else topic
    # Many live pages (weather, prices) carry no publish date, so a date filter can return nothing.
    # Retry without it; the date in the query and the verifier's freshness check still apply.
    if time_range and not resp.get("results"):
        resp = await run(None)
        used = f"{topic}, no date filter (nothing published in the last {time_range})"

    results = [
        {
            "type": "web",
            "title": r.get("title") or r.get("url"),
            "url": r.get("url"),
            "content": r.get("content", ""),
            "score": round(float(r.get("score", 0.0)), 4),
            "published": r.get("published_date"),
            "meta": {},
        }
        for r in resp.get("results", [])
    ]
    if s.tavily_include_answer and resp.get("answer"):
        results.insert(0, {"type": "web", "title": "Tavily summary", "url": None,
                           "content": resp["answer"], "score": 1.0, "published": None, "meta": {}})
    return results, used


async def web_search_tool(query: str) -> list[dict]:
    results, _ = await web_search(query)
    return results
