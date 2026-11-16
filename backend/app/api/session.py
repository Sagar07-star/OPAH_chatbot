"""Session and demo-account endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..assistant import memory
from ..config import settings
from ..schemas.chat import ActiveProjectRequest, SwitchRequest
from ..security.identity import (
    COOKIE_NAME,
    Session,
    check_same_origin,
    clear_session_cookie,
    get_session,
    set_session_cookie,
    validate_demo_identity,
)
from ..services.mock_service import demo_accounts, get_mock

router = APIRouter(prefix="/api/session", tags=["session"])
VISITOR_COOKIE = "createchat_visitor"


def _public_session(session: Session, request: Request) -> dict:
    mock = get_mock()
    payload = {
        "user_id": session.user_id,
        "role": session.role,
        "authenticated": session.is_client,
        "display_name": "Visitor",
        "company": None,
        "initials": "V",
        "member_since": None,
    }
    if session.is_client:
        client = mock.client(session.user_id) or {}
        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        payload.update({
            "display_name": name,
            "company": client.get("company"),
            "initials": "".join(part[0] for part in name.split()[:2]).upper() or "C",
            "member_since": client.get("member_since"),
        })
    elif session.is_talent:
        talent = mock.public_talent(session.user_id) or {}
        payload.update({
            "display_name": talent.get("name") or "Creative",
            "company": talent.get("role"),
            "initials": (talent.get("name") or "C")[0].upper(),
        })
    return payload


def _meta(session: Session) -> dict:
    mock = get_mock()
    active = memory.wm_get(session.user_id, None, "active_project") if session.is_client else None
    return {
        "session": _public_session(session, None),
        "accounts": demo_accounts(),
        "dataset_today": mock.today,
        "assistance_fee_rate": mock.fee_rate,
        "model": {
            "configured": settings.model_configured,
            "name": settings.openai_model,
            "env": "OPENAI_API_KEY",
        },
        "active_project_id": active,
        "conversations": memory.list_conversations(session.user_id) if session.is_client else [],
    }


@router.get("")
def read_session(request: Request, response: Response) -> dict:
    session = get_session(request)
    if not request.cookies.get(VISITOR_COOKIE):
        response.set_cookie(VISITOR_COOKIE, uuid.uuid4().hex, max_age=7 * 86400,
                            httponly=True, samesite="lax", path="/")
    return _meta(session)


@router.post("/switch")
def switch_account(payload: SwitchRequest, request: Request, response: Response) -> dict:
    check_same_origin(request)
    session = validate_demo_identity(payload.user_id, payload.role or "")
    if session.is_anonymous:
        clear_session_cookie(response)
    else:
        set_session_cookie(response, session)
    return _meta(session)


@router.post("/sign-out")
def sign_out(request: Request, response: Response) -> dict:
    check_same_origin(request)
    clear_session_cookie(response)
    from ..security.identity import ANONYMOUS

    return _meta(ANONYMOUS)


@router.get("/conversations")
def conversations(request: Request) -> dict:
    session = get_session(request)
    if not session.is_client:
        return {"conversations": []}
    mock = get_mock()
    rows = memory.list_conversations(session.user_id)
    for row in rows:
        project = mock.project(row["project_id"]) if row.get("project_id") else None
        row["project_name"] = project.get("name") if project else None
        row["project_status"] = project.get("status") if project else None
    return {"conversations": rows}


@router.post("/active-project")
def set_active_project(payload: ActiveProjectRequest, request: Request) -> dict:
    check_same_origin(request)
    session = get_session(request)
    if not session.is_client:
        raise HTTPException(status_code=401, detail={
            "error": "auth_required", "message": "Please sign in to do that."})
    mock = get_mock()
    project = None
    if payload.project_id:
        result = mock.call("get_project", {"project_id": payload.project_id}, user=session.user_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail={
                "error": "not_found",
                "message": result.get("message") or "I can't find that project on your account."})
        project = result
        previous = memory.wm_get(session.user_id, None, "active_project")
        if previous and previous != payload.project_id:
            memory.wm_clear(session.user_id, previous)
        memory.wm_set(session.user_id, None, "active_project", payload.project_id)
    conversation = memory.ensure_conversation(
        session.user_id, project["id"] if project else None,
        project["name"] if project else "All projects",
    )
    return {
        "project": {"id": project["id"], "name": project["name"], "status": project["status"]} if project else None,
        "conversation": conversation,
        "messages": memory.messages_for(conversation["id"]),
    }
