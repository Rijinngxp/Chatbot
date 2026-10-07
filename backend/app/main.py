import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routers
from .config import get_settings
from .rag.models import reranker
from .rag.store import get_store

logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load embedding models + open the vector DB up front so the first request isn't slow.
    if settings.enable_rag:
        await asyncio.to_thread(get_store)
        if settings.enable_reranker:
            await asyncio.to_thread(reranker)
    yield


app = FastAPI(
    title="Multi-Agent RAG Chatbot",
    description="Research agent → RAG / Web tools → Verifier agent → Synthesizer agent",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"]
)
for router in routers:
    app.include_router(router)
