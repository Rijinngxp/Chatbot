"""Inspect or erase what the assistant remembers about a user (Supermemory)."""
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from .. import memory
from ..config import get_settings
from ..schemas import ID_PATTERN, ForgetResponse, MemoryResponse

router = APIRouter(prefix="/api/memory", tags=["memory"])
log = logging.getLogger("chatbot")

# The browser's user id. Anyone who knows it can read or erase that user's memory — put real auth in front
# of this API before exposing it publicly.
UserId = Annotated[str, Header(alias="X-User-Id", pattern=ID_PATTERN)]


def _require_memory() -> None:
    if not get_settings().memory_available:
        raise HTTPException(400, "Memory is disabled (ENABLE_MEMORY / SUPERMEMORY_API_KEY)")


@router.get("", response_model=MemoryResponse, summary="Everything the assistant remembers about this user")
async def get_memory(user_id: UserId) -> MemoryResponse:
    _require_memory()
    try:
        return MemoryResponse(memories=await memory.profile(user_id))
    except Exception as exc:
        log.exception("reading memory failed")
        raise HTTPException(502, f"Supermemory error: {exc}") from exc


@router.delete("", response_model=ForgetResponse, summary="Forget everything about this user")
async def forget_memory(user_id: UserId) -> ForgetResponse:
    _require_memory()
    try:
        return ForgetResponse(deleted_memories=await memory.forget(user_id))
    except Exception as exc:
        log.exception("forgetting memory failed")
        raise HTTPException(502, f"Supermemory error: {exc}") from exc
