"""The three agents: Planner, Verifier and Synthesizer. Prompts live in prompt.py."""
from collections.abc import AsyncIterator
from datetime import date

from . import llm
from .config import get_settings
from .memory import format_memories
from .prompt import (
    PLANNER_SYSTEM,
    PLANNER_USER,
    SMALLTALK_SYSTEM,
    SMALLTALK_USER,
    SYNTHESIZER_SYSTEM,
    SYNTHESIZER_USER,
    VERIFIER_SYSTEM,
    VERIFIER_USER,
)

# Synthesizer notes when the planner found the answer in the remembered user facts.
FROM_MEMORY_NOTES = (
    "question about the user: answer it from what you remember about the user (no search was run); "
    "if those facts don't contain the answer, say you don't remember that yet"
)

# The planner returns a small JSON plan, but reasoning models (gpt-oss) spend part of the token budget
# thinking before they answer, so it needs headroom beyond the JSON itself.
PLANNER_MAX_TOKENS = 800


def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "(no sources were retrieved)"
    blocks = []
    for s in sources:
        origin = s["url"] or s["title"]
        published = f" (published {s['published']})" if s.get("published") else ""
        blocks.append(f"[{s['id']}] ({s['type']}) {s['title']} — {origin}{published}\n{s['content']}")
    return "\n\n".join(blocks)


def today_str() -> str:
    """Today's date in a form both people and search engines understand, e.g. "Saturday, 3 October 2026 (2026-10-03)"."""
    d = date.today()
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')} ({d.isoformat()})"


def format_history(history: list[dict]) -> str:
    n = get_settings().history_turns
    turns = history[-n:] if n > 0 else []
    return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in turns) or "(no prior conversation)"


# ---------------------------------------------------------------- Planner agent
class PlannerAgent:
    async def plan(self, question: str, history: list[dict], memories: list[dict] = ()) -> dict:
        """Decide "unsafe", "greeting", "memory" (the remembered facts already answer it) or "search", and write
        a standalone search query, using the memories to resolve personal references ("my city")."""
        s = get_settings()
        prompt = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": PLANNER_USER.format(
                today=today_str(), user_context=format_memories(memories), history=format_history(history),
                question=question,
            )},
        ]
        try:
            plan = await llm.complete_json("planner", prompt, s.planner_temperature, PLANNER_MAX_TOKENS)
        except Exception as exc:  # if planning fails, search with the original question
            return {
                "route": "search", "search_query": question, "freshness": "any", "topic": "general",
                "unsafe_categories": [], "reasoning": f"Planning failed ({exc}); searching.",
            }

        route = plan.get("route") if plan.get("route") in ("unsafe", "greeting", "memory") else "search"
        if route == "memory" and not memories:  # nothing remembered, so memory can't be the answer
            route = "search"
        query = (plan.get("search_query") or "").strip()
        if route == "search" and (not query or not s.enable_query_rewrite):
            query = question
        return {
            "route": route,
            "search_query": query if route == "search" else "",
            "unsafe_categories": (plan.get("unsafe_categories") or []) if route == "unsafe" else [],
            "freshness": plan.get("freshness") if plan.get("freshness") in ("realtime", "recent") else "any",
            "topic": plan.get("topic") if plan.get("topic") in ("news", "finance") else "general",
            "reasoning": (plan.get("reasoning") or "").strip(),
        }


# ---------------------------------------------------------------- Verifier agent
class VerifierAgent:
    async def verify(
        self, question: str, sources: list[dict], freshness: str = "any", memories: list[dict] = ()
    ) -> dict:
        """Check the question against the retrieved chunks: relevance, freshness, sufficiency, explicit content."""
        s = get_settings()
        user = VERIFIER_USER.format(
            today=today_str(), freshness=freshness, user_context=format_memories(memories), question=question,
            sources=format_sources(sources),
        )
        result = await llm.complete_json(
            "verifier",
            [{"role": "system", "content": VERIFIER_SYSTEM}, {"role": "user", "content": user}],
            s.verifier_temperature,
            s.verifier_max_tokens,
        )
        result.setdefault("verdict", "insufficient")  # strict: no explicit verdict is not an approval
        result.setdefault("missing", "")
        result.setdefault("contains_explicit_content", False)
        result.setdefault("explicit_categories", [])
        result.setdefault("is_sufficient", result["verdict"] == "approve")
        valid_ids = {src["id"] for src in sources}
        unsafe = {i for i in result.get("unsafe_sources") or [] if i in valid_ids}
        result["unsafe_sources"] = sorted(unsafe)
        # A source flagged unsafe can never be used, even if the model also listed it as relevant.
        result["relevant_sources"] = [i for i in result.get("relevant_sources") or [] if i in valid_ids and i not in unsafe]
        try:
            result["confidence"] = float(result.get("confidence", 1.0))
        except (TypeError, ValueError):
            result["confidence"] = 0.0
        return result


# ---------------------------------------------------------------- Synthesizer agent
class SynthesizerAgent:
    async def stream(
        self, question: str, history: list[dict], sources: list[dict], verification: dict | None,
        memories: list[dict] = (), from_memory: bool = False,
    ) -> AsyncIterator[str]:
        """Think, then write the final answer from the verified sources (or, with from_memory, from the user's
        memories). Reasoning depth comes from SYNTHESIZER_REASONING_EFFORT."""
        s = get_settings()
        notes = FROM_MEMORY_NOTES if from_memory else "(not verified)"
        if verification:
            notes = f"sufficient={verification.get('is_sufficient')}; missing={verification.get('missing') or 'nothing'}"
        user = SYNTHESIZER_USER.format(
            today=today_str(), user_context=format_memories(memories), history=format_history(history),
            question=question, sources=format_sources(sources), notes=notes,
        )
        async for token in llm.stream(
            "synthesizer",
            [{"role": "system", "content": SYNTHESIZER_SYSTEM}, {"role": "user", "content": user}],
            s.synthesizer_temperature,
            s.synthesizer_max_tokens,
        ):
            yield token

    async def smalltalk(self, question: str, history: list[dict], memories: list[dict] = ()) -> AsyncIterator[str]:
        """Friendly reply to greetings — no search, no verification."""
        s = get_settings()
        user = SMALLTALK_USER.format(
            user_context=format_memories(memories), history=format_history(history), question=question
        )
        async for token in llm.stream(
            "synthesizer",
            [{"role": "system", "content": SMALLTALK_SYSTEM}, {"role": "user", "content": user}],
            s.synthesizer_temperature,
            400,
            effort="low",  # a greeting needs no deep thinking
        ):
            yield token
