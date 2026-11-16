"""CREATEchat FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .api import account, chat, proposals, session as session_api, support
from .config import settings
from .db import get_conn, init_db
from .security.identity import get_session
from .services.mock_service import get_mock
from .services.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("createchat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_mock()
    logger.info("CREATEchat API ready (dataset day %s, model %s, key %s)",
                get_mock().today, settings.openai_model,
                "configured" if settings.model_configured else "missing")
    yield


app = FastAPI(
    title="CREATEchat API",
    version="1.0.0",
    description="Prototype assistant for OPAH clients, running over the supplied mock kit.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        body = {"error": detail.get("error", "error"), "message": detail.get("message", ""), **detail}
    else:
        body = {"error": "error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "That request wasn't valid.")
    return JSONResponse(status_code=422, content={
        "error": "invalid_fields",
        "message": f"{location}: {message}" if location else message,
        "details": exc.errors()[:5],
    })


app.include_router(session_api.router)
app.include_router(chat.router)
app.include_router(account.router)
app.include_router(proposals.router)
app.include_router(support.router)


@app.get("/api/health")
def health() -> dict:
    mock = get_mock()
    return {
        "status": "ok",
        "app": settings.app_name,
        "dataset_today": mock.today,
        "model_configured": settings.model_configured,
        "model": settings.openai_model,
        "tools": 22,
        "environment": settings.environment,
    }


@app.get("/api/demo/state")
def demo_state(request: Request) -> dict:
    """Debug view for the demo, limited to the signed-in client's own records."""
    session = get_session(request)
    if not session.is_client:
        raise HTTPException(status_code=401, detail={
            "error": "auth_required", "message": "Please sign in to do that."})
    mock = get_mock()
    return {
        "projects": [p for p in mock.projects_for(session.user_id)],
        "proposals": mock.proposals_for(session.user_id),
    }


class ResetRequest(BaseModel):
    conversations: bool = False


@app.post("/api/demo/reset")
def demo_reset(payload: ResetRequest | None = None) -> dict:
    """Reload the mock dataset. Demo/testing only."""
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "message": "Reset is disabled in production."})
    get_mock().reset()
    limiter.reset()
    if payload and payload.conversations:
        with get_conn() as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM working_memory")
            conn.execute("DELETE FROM uploads")
            conn.execute("DELETE FROM support_tickets")
            conn.execute("DELETE FROM app_errors")
            conn.execute("DELETE FROM anon_usage")
    return {"status": "reset", "dataset_today": get_mock().today}
