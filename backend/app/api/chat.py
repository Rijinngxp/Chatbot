import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..pipeline import run_pipeline
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])
log = logging.getLogger("chatbot")


@router.post("", summary="Run the agent pipeline and stream events (Server-Sent Events)")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    history = [m.model_dump() for m in req.history]

    async def events():
        try:
            async for event in run_pipeline(req.message, history, req.web_search, req.user_id, req.conversation_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            log.exception("pipeline failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/complete", response_model=ChatResponse, summary="Run the agent pipeline and return one JSON response")
async def chat_complete(req: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in req.history]
    answer, blocked, sources, verification, stages = "", False, [], None, []
    try:
        async for event in run_pipeline(req.message, history, req.web_search, req.user_id, req.conversation_id):
            match event["type"]:
                case "stage":
                    stages.append(event)
                case "sources":
                    sources = event["sources"]
                case "verification":
                    verification = event["result"]
                case "done":
                    answer, blocked = event["answer"], event.get("blocked", False)
    except Exception as exc:
        log.exception("pipeline failed")
        raise HTTPException(502, str(exc)) from exc
    return ChatResponse(answer=answer, blocked=blocked, sources=sources, verification=verification, stages=stages)
