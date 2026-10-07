"""Long-term user memory backed by Supermemory.

Every user gets their own Supermemory namespace.
  recall  (before the planner): the user's profile — durable facts and recent context that Supermemory keeps up
          to date — plus memories that match the question, fetched in parallel.
  save    (after the answer, in the background): the turn is appended to one document per conversation;
          Supermemory extracts the facts worth keeping from it on its side.

Memory is best-effort: calls are bounded by MEMORY_TIMEOUT and a failure never breaks the chat.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone

from supermemory import AsyncSupermemory, NotFoundError

from .config import get_settings

log = logging.getLogger("chatbot")

NAMESPACE_PREFIX = "chatbot_user_"
SAVE_TIMEOUT = 30.0          # background writes aren't on the user's critical path
MAX_SAVED_ANSWER_CHARS = 1500  # memory is about the user; the full answer adds little
MAX_EXCERPTS = 3             # raw conversation excerpts added to recall (cover the gap before extraction)
MAX_EXCERPT_CHARS = 300
_USER_LINE_RE = re.compile(r"USER:\s*(.*?)(?=\s*ASSISTANT:|\s*\[\d{4}-\d{2}-\d{2}|\Z)", re.DOTALL)

# Steers what Supermemory extracts from saved conversations (max 1500 chars).
EXTRACTION_CONTEXT = (
    "Conversations between one user and a research assistant that answers from the user's documents and the web. "
    "Remember durable facts about the user (name, role, organisation, location, projects, preferences, goals) and "
    "what they have been researching. Do not store general world knowledge from the assistant's answers as facts "
    "about the user."
)

_client: AsyncSupermemory | None = None
_save_tasks: set[asyncio.Task] = set()  # strong refs so background saves aren't garbage-collected


def client() -> AsyncSupermemory:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncSupermemory(
            # A self-hosted server may not check the key, but the SDK requires one.
            api_key=s.supermemory_api_key or "self-hosted",
            base_url=s.supermemory_base_url or None,
            timeout=s.memory_timeout,
            max_retries=1,
        )
    return _client


def namespace(user_id: str) -> str:
    return NAMESPACE_PREFIX + user_id


# ---------------------------------------------------------------- recall
async def profile(user_id: str) -> list[dict]:
    """Everything Supermemory currently knows about the user: durable facts, then recent context."""
    try:
        resp = await client().profile(namespace(user_id))
    except NotFoundError:  # a user who has never saved anything has no namespace yet
        return []
    return [{"id": f.id, "text": f.memory, "kind": "fact"} for f in resp.profile.static] + [
        {"id": f.id, "text": f.memory, "kind": "recent"} for f in resp.profile.dynamic
    ]


def _user_words(chunk: str) -> str:
    """The user's own lines from a saved conversation chunk (assistant replies are left out: they add noise
    such as "I don't know your name")."""
    said = [m.strip() for m in _USER_LINE_RE.findall(chunk) if m.strip()]
    return " / ".join(said)[:MAX_EXCERPT_CHARS]


async def _related(user_id: str, question: str, limit: int) -> list[dict]:
    """Memories that match this question, plus the user's own words from matching saved conversations.

    Extraction takes ~30 s after a save, so the raw conversation covers what was said moments ago."""
    s = get_settings()
    try:
        resp = await client().search(namespace(user_id), query=question, search_mode="hybrid", limit=limit)
    except NotFoundError:
        return []
    related, excerpts = [], []
    for r in resp.results:
        if r.memory and r.is_latest and r.similarity >= s.memory_min_similarity:
            related.append({"id": r.id, "text": r.memory, "kind": "related"})
        elif r.chunk and len(excerpts) < MAX_EXCERPTS and (said := _user_words(r.chunk)):
            excerpts.append({"id": r.id, "text": f"Earlier the user said: {said}", "kind": "conversation"})
    return related + excerpts


async def recall(user_id: str, question: str) -> list[dict]:
    """Profile + question-matched memories, de-duplicated. Raises on failure or after MEMORY_TIMEOUT."""
    s = get_settings()
    facts, related = await asyncio.wait_for(
        asyncio.gather(profile(user_id), _related(user_id, question, s.memory_max_items)),
        timeout=s.memory_timeout,
    )
    durable = [m for m in facts if m["kind"] == "fact"]
    recent = [m for m in facts if m["kind"] == "recent"]
    seen: set[str] = set()
    memories = []
    for m in durable + related + recent:  # identity facts first, then what matches the question
        key = m["text"].strip().lower()
        if m["id"] in seen or key in seen:
            continue
        seen.update((m["id"], key))
        memories.append(m)
    return memories[: s.memory_max_items]


def format_memories(memories: list[dict]) -> str:
    """The user-context block placed in the agents' prompts."""
    if not memories:
        return "(nothing remembered about this user yet)"
    return "\n".join(f"- {m['text']}" for m in memories)


# ---------------------------------------------------------------- save
async def save_turn(user_id: str, conversation_id: str | None, question: str, answer: str) -> None:
    if len(answer) > MAX_SAVED_ANSWER_CHARS:
        answer = answer[:MAX_SAVED_ANSWER_CHARS].rsplit(" ", 1)[0] + " …"
    now = datetime.now(timezone.utc)
    # Same id for every turn of a conversation: Supermemory appends to the document and keeps its history.
    doc = {"id": f"conversation_{conversation_id}"} if conversation_id else {}
    await client().add(
        namespace(user_id),
        content=f"[{now:%Y-%m-%d %H:%M} UTC]\nUSER: {question}\nASSISTANT: {answer}",
        **doc,
        supporting_context=EXTRACTION_CONTEXT,
        task_type="memory",
        # "dynamic" (the API default) waits to group related documents, so short chat turns can sit
        # unextracted for a long time; "instant" extracts each turn right away (one extra billed operation).
        dreaming="instant" if get_settings().memory_instant_extraction else "dynamic",
        date=now.isoformat(),
        metadata={"source": "chat"},
        timeout=SAVE_TIMEOUT,
    )


def save_turn_in_background(user_id: str, conversation_id: str | None, question: str, answer: str) -> None:
    """Fire-and-forget save, so writing memory never delays the answer."""

    async def run() -> None:
        try:
            await save_turn(user_id, conversation_id, question, answer)
        except Exception:
            log.warning("saving memory failed", exc_info=True)

    task = asyncio.create_task(run())
    _save_tasks.add(task)
    task.add_done_callback(_save_tasks.discard)


async def close() -> None:
    """Finish pending background saves and close the HTTP client (on shutdown)."""
    global _client
    if _save_tasks:
        await asyncio.wait(_save_tasks, timeout=SAVE_TIMEOUT)
    if _client is not None:
        await _client.close()
        _client = None


# ---------------------------------------------------------------- forget
async def forget(user_id: str) -> int:
    """Delete the user's namespace and everything in it. Returns the number of memories deleted."""
    try:
        result = await client().namespaces.delete(namespace(user_id), timeout=SAVE_TIMEOUT)
    except NotFoundError:
        return 0
    return getattr(result, "deleted_memories_count", 0)
