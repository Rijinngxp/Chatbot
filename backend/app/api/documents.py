import asyncio
import json
import logging
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..rag.loaders import check_supported, extract_text
from ..rag.progress import Progress, no_progress
from ..rag.store import get_store
from ..schemas import DocumentInfo

router = APIRouter(prefix="/api/documents", tags=["documents"])
log = logging.getLogger("chatbot")
_ingest_tasks: set[asyncio.Task] = set()  # strong refs so an ingestion survives a browser disconnect


def _require_rag() -> None:
    if not get_settings().enable_rag:
        raise HTTPException(400, "RAG is disabled (ENABLE_RAG=false)")


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Validate type and size before any processing starts."""
    filename = file.filename or "upload.txt"
    try:
        check_supported(filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    max_mb = get_settings().max_upload_mb
    data = await file.read()
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {max_mb} MB")
    return filename, data


def ingest(filename: str, data: bytes, progress: Progress = no_progress) -> dict:
    """Extract -> semantic chunking -> embed -> ChromaDB -> BM25. Runs in a worker thread."""
    text = extract_text(filename, data, progress)
    return get_store().add_document(text, filename, progress)


@router.get("", response_model=list[DocumentInfo], summary="List indexed documents")
async def list_documents() -> list[dict]:
    _require_rag()
    return await asyncio.to_thread(get_store().list_documents)


@router.post("", response_model=DocumentInfo, summary="Upload, semantically chunk and index a document")
async def upload_document(file: UploadFile = File(...)) -> dict:
    _require_rag()
    filename, data = await _read_upload(file)
    try:
        return await asyncio.to_thread(ingest, filename, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/stream", summary="Upload a document and stream each ingestion step live (Server-Sent Events)")
async def upload_document_stream(file: UploadFile = File(...)) -> StreamingResponse:
    _require_rag()
    filename, data = await _read_upload(file)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(stage: str, status: str, detail: str = "", value: float | None = None) -> None:
        # Called from the worker thread: hand the event to the event loop safely.
        event = {"type": "stage", "stage": stage, "status": status, "detail": detail, "value": value, "t": time.time()}
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def worker() -> None:
        try:
            document = await asyncio.to_thread(ingest, filename, data, progress)
            await queue.put({"type": "done", "document": document})
        except ValueError as exc:
            await queue.put({"type": "error", "message": str(exc)})
        except Exception as exc:
            log.exception("ingestion failed")
            await queue.put({"type": "error", "message": f"Ingestion failed: {exc}"})
        finally:
            await queue.put(None)

    async def events():
        size_kb = len(data) / 1024
        size = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
        yield f"data: {json.dumps({'type': 'stage', 'stage': 'upload', 'status': 'done', 'detail': f'Received {size}'})}\n\n"
        task = asyncio.create_task(worker())  # keeps running even if the browser disconnects
        _ingest_tasks.add(task)
        task.add_done_callback(_ingest_tasks.discard)
        while (event := await queue.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"
        await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.delete("/{doc_id}", summary="Delete a document and all its chunks")
async def delete_document(doc_id: str) -> dict:
    _require_rag()
    await asyncio.to_thread(get_store().delete_document, doc_id)
    return {"deleted": doc_id}
