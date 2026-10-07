"""Request / response models shared by the API routers."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[Message] = []
    web_search: bool = False


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


class HealthResponse(BaseModel):
    status: Literal["ok"]
    documents: int | None = None
