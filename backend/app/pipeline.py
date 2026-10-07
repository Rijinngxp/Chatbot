"""Orchestrates the agents and yields event dicts that the API streams to the UI as Server-Sent Events.

Supermemory first recalls what it remembers about the user (fails soft); the planner then decides with those
memories in view. Every answered turn is saved back to memory in the background:

    unsafe:              Memory -> Planner -> blocked
    greeting:            Memory -> Planner -> Synthesizer
    answer in memory:    Memory -> Planner -> Synthesizer            (no RAG / web / verifier)
    search (web off):    Memory -> Planner -> RAG search -> Verifier (question + chunks) -> Synthesizer
    search (web on):     Memory -> Planner -> Web search -> Verifier (question + results) -> Synthesizer
    unsafe (late):       Verifier -> blocked

The planner uses the memories to turn personal references ("weather in my city") into concrete search queries.
The verifier and the synthesizer are reasoning agents: they think (VERIFIER_/SYNTHESIZER_REASONING_EFFORT)
before they answer.

Explicit content is stopped in three layers: the planner (before any search), the verifier (question + every
source; unsafe sources are dropped), and the synthesizer/greeting prompts (never produce explicit content).
Blocked turns are never saved to memory.
"""
from collections.abc import AsyncIterator

from . import memory
from .agents import PlannerAgent, SynthesizerAgent, VerifierAgent
from .config import get_settings
from .tools import rag_tool, web_search

BLOCKED_MESSAGE = (
    "I can't help with that request because it involves explicit or unsafe content. "
    "Feel free to ask me something else about your documents or another topic."
)
SELF_HARM_MESSAGE = (
    "I'm not able to help with that, but I'm really sorry you're going through something difficult. "
    "You don't have to face it alone — please consider reaching out to someone you trust or a local crisis "
    "line or emergency service right now. If you'd like, I'm happy to help with something else."
)

planner, verifier, synthesizer = PlannerAgent(), VerifierAgent(), SynthesizerAgent()


def stage(name: str, status: str, detail: str = "", **data) -> dict:
    return {"type": "stage", "stage": name, "status": status, "detail": detail, **data}


def numbered(sources: list[dict]) -> list[dict]:
    return [{**src, "id": i} for i, src in enumerate(sources, start=1)]


def blocked_events(categories: list[str], skip: tuple[str, ...]) -> list[dict]:
    message = SELF_HARM_MESSAGE if "self_harm" in categories else BLOCKED_MESSAGE
    events = [stage(name, "skipped", "Request blocked") for name in skip]
    events += [{"type": "token", "content": message}, {"type": "done", "answer": message, "blocked": True}]
    return events


async def write_answer(
    question: str,
    history: list[dict],
    sources: list[dict],
    verification: dict | None,
    memories: list[dict],
    from_memory: bool = False,
) -> AsyncIterator[dict]:
    """The synthesizer thinks (SYNTHESIZER_REASONING_EFFORT), then streams the answer. Ends with the "done" event."""
    yield stage("synthesizer", "running", "Answering from memory" if from_memory else "Thinking, then writing the answer")
    answer = ""
    async for token in synthesizer.stream(question, history, sources, verification, memories, from_memory):
        answer += token
        yield {"type": "token", "content": token}
    yield stage("synthesizer", "done")
    yield {"type": "done", "answer": answer}


async def run_pipeline(
    question: str,
    history: list[dict],
    use_web: bool,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> AsyncIterator[dict]:
    s = get_settings()

    def remember(answer: str) -> None:
        if user_id and answer.strip() and s.memory_available and s.memory_save_conversations:
            memory.save_turn_in_background(user_id, conversation_id, question, answer)

    # 1. Memory: what do we already know about this user?
    memories: list[dict] = []
    if not s.memory_available:
        yield stage("memory", "skipped", "Disabled (ENABLE_MEMORY / SUPERMEMORY_API_KEY)")
    elif not user_id:
        yield stage("memory", "skipped", "No user id sent")
    else:
        yield stage("memory", "running", "Recalling what I know about you")
        try:
            memories = await memory.recall(user_id, question)
            n = len(memories)
            detail = f"{n} memor{'y' if n == 1 else 'ies'} recalled" if n else "Nothing remembered yet"
            yield stage("memory", "done", detail, memories=memories)
        except TimeoutError:
            yield stage("memory", "warning", f"Timed out after {s.memory_timeout:g}s; continuing without memory")
        except Exception as exc:  # memory is a nice-to-have: never let it break the answer
            yield stage("memory", "warning", f"Unavailable, continuing without memory ({exc})")

    # 2. Planner (sees the memories): unsafe, greeting, answered by memory, or search?
    yield stage("planner", "running", "Understanding the request")
    plan = await planner.plan(question, history, memories)
    route = plan["route"]

    if route == "unsafe" and s.block_explicit_content:
        categories = plan["unsafe_categories"]
        label = ", ".join(categories) or "explicit content"
        yield stage("planner", "blocked", f"Unsafe request ({label})", route="unsafe", reasoning=plan["reasoning"])
        yield {"type": "sources", "sources": []}
        for event in blocked_events(categories, skip=("rag", "web", "verifier", "synthesizer")):
            yield event
        return

    # 3a. The answer is already in memory: straight to the synthesizer, no search
    if route == "memory":
        yield stage("planner", "done", "Answer found in memory: straight to synthesizer", route="memory",
                    reasoning=plan["reasoning"])
        for name in ("rag", "web", "verifier"):
            yield stage(name, "skipped", "Answered from memory")
        yield {"type": "sources", "sources": []}
        async for event in write_answer(question, history, [], None, memories, from_memory=True):
            if event["type"] == "done":
                remember(event["answer"])
            yield event
        return

    if route == "greeting":
        yield stage("planner", "done", "Greeting: straight to synthesizer", route="greeting", reasoning=plan["reasoning"])
        for name in ("rag", "web", "verifier"):
            yield stage(name, "skipped", "Not needed for a greeting")
        yield {"type": "sources", "sources": []}
        yield stage("synthesizer", "running", "Replying")
        answer = ""
        async for token in synthesizer.smalltalk(question, history, memories):
            answer += token
            yield {"type": "token", "content": token}
        yield stage("synthesizer", "done")
        remember(answer)  # greetings often carry facts worth keeping ("Hi, I'm Rijin from Kochi")
        yield {"type": "done", "answer": answer}
        return

    # 3b. Search, with the query the planner wrote (personal references already resolved from memory)
    query, freshness = plan["search_query"] or question, plan["freshness"]
    detail = "Search needed" + {"realtime": " (today's info)", "recent": " (latest info)"}.get(freshness, "")
    yield stage("planner", "done", detail, route="search", reasoning=plan["reasoning"], query=query, freshness=freshness)

    # Search: the web when the toggle is on, otherwise the knowledge base
    use_web = use_web and s.web_search_available
    sources: list[dict] = []
    if use_web:
        yield stage("rag", "skipped", "Web search is on")
        yield stage("web", "running", f"Searching the web for: {query}")
        try:
            sources, used = await web_search(query, freshness=freshness, topic=plan["topic"])
            yield stage("web", "done", f"{len(sources)} results ({used})", count=len(sources))
        except Exception as exc:
            yield stage("web", "error", f"Search failed: {exc}")
    else:
        yield stage("web", "skipped", "Web search off")
        if not s.enable_rag:
            yield stage("rag", "skipped", "Disabled via ENABLE_RAG")
        else:
            yield stage("rag", "running", "Searching the knowledge base")
            try:
                sources = await rag_tool(query)
                yield stage("rag", "done", f"{len(sources)} chunks", count=len(sources))
            except Exception as exc:
                yield stage("rag", "error", f"Search failed: {exc}")
    sources = numbered(sources)
    yield {"type": "sources", "sources": sources}

    # 4. Verifier: strict check of the question and every source. It runs even when nothing was found,
    #    so the question itself always gets a safety check.
    verification = None
    if not s.enable_verifier:
        yield stage("verifier", "skipped", "Disabled via ENABLE_VERIFIER")
    else:
        checking = f"Checking {len(sources)} sources against the question" if sources else "Checking the question"
        yield stage("verifier", "running", checking)
        try:
            verification = await verifier.verify(question, sources, freshness=freshness, memories=memories)
        except Exception as exc:  # a verifier failure shouldn't kill the answer; the synthesizer still refuses explicit content
            yield stage("verifier", "error", str(exc))
        if verification:
            yield {"type": "verification", "result": verification, "round": 1}

            explicit = verification["contains_explicit_content"] or verification["verdict"] == "block"
            if explicit and s.block_explicit_content:
                categories = verification["explicit_categories"]
                label = ", ".join(categories) or "explicit content"
                yield stage("verifier", "blocked", f"Unsafe request ({label})")
                yield {"type": "sources", "sources": []}
                for event in blocked_events(categories, skip=("synthesizer",)):
                    yield event
                return

            # Keep only safe, relevant sources (renumbered). An approval that lists none keeps every safe source.
            total = len(sources)
            relevant = set(verification["relevant_sources"])
            unsafe = set(verification["unsafe_sources"])
            if relevant or verification["verdict"] != "approve":
                sources = [src for src in sources if src["id"] in relevant]
            else:
                sources = [src for src in sources if src["id"] not in unsafe]
            sources = numbered(sources)
            yield {"type": "sources", "sources": sources}

            dropped = f", {len(unsafe)} unsafe dropped" if unsafe else ""
            if not total and memories and verification["verdict"] == "approve":
                yield stage("verifier", "done", "Answerable from what I remember about you")
            elif not total:
                yield stage("verifier", "warning", "Question is safe; nothing was found to answer it")
            elif verification["verdict"] == "approve" and verification["confidence"] >= s.verifier_min_confidence:
                yield stage("verifier", "done", f"{len(sources)} of {total} sources relevant{dropped}")
            else:
                verification["is_sufficient"] = False
                yield stage("verifier", "warning", f"Not enough information: {len(sources)} of {total} relevant{dropped}")

    # 5. Synthesizer: thinks, then answers from the verified sources
    async for event in write_answer(question, history, sources, verification, memories):
        if event["type"] == "done":
            remember(event["answer"])
        yield event
