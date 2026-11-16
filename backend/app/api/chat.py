"""Chat endpoint, conversation history and uploads."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from ..assistant import memory
from ..assistant.core import TurnInput, run_turn
from ..config import settings
from ..schemas.chat import ChatRequest
from ..security.identity import Session, check_same_origin, get_session
from ..services.rate_limit import limiter
from ..services.uploads import store_upload, validate_upload

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("createchat.chat")
VISITOR_COOKIE = "createchat_visitor"


def owner_key(session: Session, request: Request) -> str:
    if session.is_client:
        return session.user_id
    visitor = request.cookies.get(VISITOR_COOKIE) or "shared-visitor"
    return f"anon:{visitor}"


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request) -> dict:
    check_same_origin(request)
    session = get_session(request)
    visitor = request.cookies.get(VISITOR_COOKIE) or "shared-visitor"
    network = request.client.host if request.client else "local"
    turn = TurnInput(
        message=payload.message,
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        upload_ids=payload.upload_ids,
        visitor_key=visitor,
        network_key=network,
        regenerate=payload.regenerate,
    )
    result = await run_turn(session, turn)
    result["conversation"] = memory.get_conversation(
        result["conversation_id"], result.get("owner_key") or session.user_id)
    result.pop("owner_key", None)
    return result


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    """The same turn as /api/chat, streamed as Server-Sent Events.

    Events: `status` (which phase/tool is running), `delta` (raw model tokens),
    `done` (the finished envelope with server-built cards), `error`.
    """
    check_same_origin(request)
    session = get_session(request)
    visitor = request.cookies.get(VISITOR_COOKIE) or "shared-visitor"
    network = request.client.host if request.client else "local"
    turn = TurnInput(
        message=payload.message,
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        upload_ids=payload.upload_ids,
        visitor_key=visitor,
        network_key=network,
        regenerate=payload.regenerate,
    )
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def worker() -> None:
        try:
            result = await run_turn(session, turn, emit=emit)
            result["conversation"] = memory.get_conversation(
                result["conversation_id"], result.get("owner_key") or session.user_id)
            result.pop("owner_key", None)
            await queue.put({"type": "done", "result": result})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            await queue.put({
                "type": "error",
                "message": detail.get("message", "That request was refused."),
                "code": detail.get("error", "error"),
                "status": exc.status_code,
            })
        except Exception:
            logger.exception("streamed turn failed")
            await queue.put({
                "type": "error",
                "message": "The assistant couldn't finish that just now. Nothing was changed — try again.",
                "code": "internal_error",
                "status": 500,
            })
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())

    async def events():
        try:
            yield ": connected\n\n"
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, request: Request) -> dict:
    session = get_session(request)
    if not session.is_client:
        raise HTTPException(status_code=401, detail={
            "error": "auth_required", "message": "Please sign in to see your conversation."})
    client_id = session.user_id
    conversation = memory.get_conversation(conversation_id, client_id)
    if not conversation:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "I can't find that conversation."})
    return {"conversation": conversation, "messages": memory.messages_for(conversation_id)}


@router.post("/uploads")
async def upload(request: Request, response: Response,
                 files: list[UploadFile] = File(default=[])) -> dict:
    check_same_origin(request)
    session = get_session(request)
    if session.is_talent:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "message": "The client assistant is not available to creative accounts."})
    if not files:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_fields", "message": "No files were attached."})
    if len(files) > settings.max_upload_files:
        raise HTTPException(status_code=400, detail={
            "error": "upload_rejected",
            "message": f"At most {settings.max_upload_files} files per message.",
        })
    identity = session.user_id if session.is_client else owner_key(session, request)
    decision = limiter.check(identity, "upload", session.role)
    if not decision.allowed:
        raise HTTPException(status_code=429, detail={"error": decision.code, "message": decision.message})
    if session.is_anonymous:
        visitor = request.cookies.get(VISITOR_COOKIE) or "shared-visitor"
        usage = memory.bump_anon_usage(visitor, uploads=len(files))
        if usage.get("uploads", 0) > settings.anon_lifetime_uploads:
            raise HTTPException(status_code=429, detail={
                "error": "rate_limited",
                "message": "Visitors can attach a few files in this prototype. Sign in to attach more.",
            })

    stored = []
    key = owner_key(session, request)
    for file in files:
        validated = await validate_upload(file)
        row = store_upload(key, validated)
        if row.get("mime") == "image/png":
            pass
        stored.append(row)
    return {"uploads": stored, "count": len(stored),
            "limits": {"files": settings.max_upload_files,
                       "image_mb": settings.max_image_bytes // (1024 * 1024),
                       "pdf_mb": settings.max_pdf_bytes // (1024 * 1024),
                       "pdf_pages": settings.max_pdf_pages}}


@router.get("/uploads/{upload_id}/raw")
def upload_raw(upload_id: str, request: Request) -> Response:
    session = get_session(request)
    key = owner_key(session, request)
    row = memory.get_upload(upload_id, key)
    if not row:
        raise HTTPException(status_code=404, detail={"error": "not_found",
                                                    "message": "I can't find that file."})
    try:
        raw = open(row["path"], "rb").read()
    except OSError:
        raise HTTPException(status_code=410, detail={"error": "not_found",
                                                    "message": "That file is no longer stored."})
    return Response(content=raw, media_type=row["mime"], headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'inline; filename="{row["filename"]}"',
    })
