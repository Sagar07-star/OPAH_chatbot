"""Support-ticket stubs and client-reported app errors."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..assistant import memory
from ..schemas.chat import AppErrorRequest, SupportTicketRequest
from ..security.identity import check_same_origin, get_session, require_client
from ..services.mock_service import get_mock

router = APIRouter(prefix="/api/support", tags=["support"])


@router.get("/tickets")
def tickets(request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    rows = [{"id": t["id"], "subject": t["subject"], "category": t["category"], "status": t["status"],
             "status_label": t.get("status_label"), "created_at": t["created_at"], "source": "opah_mock"}
            for t in mock.list_tickets(session.user_id)]
    rows += [{"id": t["id"], "subject": t["subject"], "category": t["category"],
              "status": "queued in prototype", "status_label": "Prototype queue",
              "created_at": t["created_at"], "source": "prototype_stub"}
             for t in memory.local_support_tickets(session.user_id)]
    return {"tickets": rows, "count": len(rows),
            "note": "Prototype tickets are queued locally; no OPAH support system receives them."}


@router.post("/tickets")
def create_ticket(payload: SupportTicketRequest, request: Request) -> dict:
    check_same_origin(request)
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    ticket = mock.add_ticket(session.user_id, payload.subject, payload.topic, payload.details,
                             "Created from the app's support screen.")
    memory.save_support_ticket(session.user_id, payload.subject, payload.topic, payload.details,
                               "Created from the app's support screen.")
    ticket.pop("client_id", None)
    return {"ticket": ticket, "stub": True,
            "message": "Queued in this prototype only — no OPAH support system received it."}


@router.post("/app-errors")
def report_app_error(payload: AppErrorRequest, request: Request) -> dict:
    session = get_session(request)
    key = session.user_id if session.is_client else "anonymous"
    memory.log_app_error(key, payload.route, payload.message, payload.status)
    return {"logged": True}
