"""Request / response models shared by the API routers."""
from typing import Any, Literal

from pydantic import BaseModel, Field


# Opaque ids created by the browser (a UUID). They scope long-term memory, so keep them to safe characters.
ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[Message] = []
    web_search: bool = False
    user_id: str | None = Field(None, pattern=ID_PATTERN, description="Scopes long-term memory to one user")
    conversation_id: str | None = Field(None, pattern=ID_PATTERN, description="Groups this chat's turns in memory")


class Source(BaseModel):
    id: int
    type: Literal["document", "web"]
    title: str
    url: str | None = None
    content: str
    score: float
    meta: dict[str, Any] = {}


class ChatResponse(BaseModel):
    answer: str
    blocked: bool = False
    sources: list[Source] = []
    verification: dict[str, Any] | None = None
    stages: list[dict[str, Any]] = []


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class SearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunks: int
    uploaded_at: str


class MemoryItem(BaseModel):
    id: str
    text: str
    kind: Literal["fact", "recent", "related", "conversation"]


class MemoryResponse(BaseModel):
    memories: list[MemoryItem]


class ForgetResponse(BaseModel):
    deleted_memories: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    documents: int | None = None
