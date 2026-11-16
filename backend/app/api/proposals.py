"""Approval endpoints.

This is the only path that writes a project change, and the model has no tool
for it. Identity and ownership come from the session; the mock kit enforces the
rest. Approving twice never applies twice.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..assistant import memory
from ..security.identity import check_same_origin, get_session, require_client
from ..services.mock_service import get_mock

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _owned_proposal(session, proposal_id: str) -> dict:
    proposal = get_mock().proposal(proposal_id)
    if not proposal or proposal.get("client_id") != session.user_id:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "I can't find that proposal."})
    return proposal


def _enrich(proposal: dict) -> dict:
    mock = get_mock()
    project = mock.project(proposal["project_id"]) if proposal.get("project_id") else None
    return {
        "proposal_id": proposal["proposal_id"],
        "kind": proposal["kind"],
        "project_id": proposal.get("project_id"),
        "project_name": project.get("name") if project else None,
        "summary": proposal.get("summary"),
        "changes": proposal.get("changes", []),
        "status": proposal.get("status"),
        "created_at": proposal.get("created_at"),
        "resolved_at": proposal.get("resolved_at"),
        "result": proposal.get("result"),
    }


@router.get("/{proposal_id}")
def get_proposal(proposal_id: str, request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    return {"proposal": _enrich(_owned_proposal(session, proposal_id))}


@router.post("/{proposal_id}/approve")
def approve(proposal_id: str, request: Request) -> dict:
    check_same_origin(request)
    session = get_session(request)
    require_client(session)
    proposal = _owned_proposal(session, proposal_id)
    if proposal["status"] != "pending":
        # Idempotent: a second tap is a no-op with a clear answer.
        status = proposal["status"]
        return {
            "proposal_id": proposal_id,
            "status": status,
            "applied": status == "applied",
            "already": True,
            "message": ("That change was already applied — nothing changed this time."
                        if status == "applied" else
                        "That change was declined, so it can't be applied."),
            "proposal": _enrich(proposal),
        }

    result = get_mock().approve(proposal_id, session.user_id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "I can't find that proposal."})
    status = result.get("status") or result.get("error") or "pending"
    memory.update_proposal_cards(proposal_id, status, result.get("result"))
    refreshed = get_mock().proposal(proposal_id) or proposal
    return {
        "proposal_id": proposal_id,
        "status": status,
        "applied": status == "applied",
        "already": status == "already_applied",
        "error": result.get("error"),
        "message": result.get("message"),
        "result": result.get("result"),
        "proposal": _enrich(refreshed),
    }


@router.post("/{proposal_id}/reject")
def reject(proposal_id: str, request: Request) -> dict:
    check_same_origin(request)
    session = get_session(request)
    require_client(session)
    proposal = _owned_proposal(session, proposal_id)
    if proposal["status"] != "pending":
        return {
            "proposal_id": proposal_id,
            "status": proposal["status"],
            "rejected": proposal["status"] == "rejected",
            "already": True,
            "message": ("That change is already " + proposal["status"] + "."),
            "proposal": _enrich(proposal),
        }
    result = get_mock().reject(proposal_id, session.user_id)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "I can't find that proposal."})
    status = result.get("status") or "rejected"
    memory.update_proposal_cards(proposal_id, status)
    refreshed = get_mock().proposal(proposal_id) or proposal
    return {
        "proposal_id": proposal_id,
        "status": status,
        "rejected": status == "rejected",
        "message": result.get("message"),
        "proposal": _enrich(refreshed),
    }
