"""Read-only account, project, talent, board and document endpoints for the UI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..assistant import memory
from ..config import settings
from ..schemas.chat import SaveDocumentRequest
from ..security.identity import check_same_origin, get_session, require_client
from ..services.mock_service import FIELD_LABELS, PAID_STATUSES, get_mock

router = APIRouter(prefix="/api", tags=["account"])


def _location(project: dict) -> str | None:
    location = project.get("location")
    if isinstance(location, dict):
        return location.get("display")
    return location


def _summary_row(project: dict) -> dict:
    mock = get_mock()
    booking = next((b for b in mock.bookings_for(project["id"]) if b["status"] == "accepted"), None)
    return {
        "id": project["id"],
        "name": project["name"],
        "status": project["status"],
        "payment_status": project["payment_status"],
        "source": project["source"],
        "start_date": project.get("start_date"),
        "end_date": project.get("end_date"),
        "scheduled_time": project.get("scheduled_time"),
        "duration_hours": project.get("duration_hours"),
        "role": project.get("role"),
        "specialty": project.get("specialty"),
        "budget": project.get("budget"),
        "location": _location(project),
        "talent": booking["talent_name"] if booking else None,
        "deliverables": project.get("deliverables") or [],
    }


def _project_or_404(session, project_id: str) -> dict:
    result = get_mock().call("get_project", {"project_id": project_id}, user=session.user_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail={
            "error": result.get("error", "not_found"),
            "message": result.get("message") or "I can't find that project on your account.",
        })
    return result


@router.get("/account/summary")
def account_summary(request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    summary = mock.call("get_account_summary", {}, user=session.user_id)
    if summary.get("error"):
        raise HTTPException(status_code=400, detail=summary)

    upcoming = []
    for shoot in summary.get("upcoming_shoots", []):
        project = mock.project(shoot["id"]) or {}
        upcoming.append({**shoot, "location": _location(project),
                         "scheduled_time": project.get("scheduled_time"),
                         "duration_hours": project.get("duration_hours"),
                         "specialty": project.get("specialty")})

    attention = summary.get("needs_attention", [])
    for item in attention:
        if item.get("project_id") and not item.get("project"):
            project = mock.project(item["project_id"]) or {}
            item["project"] = project.get("name")

    projects = [_summary_row(p) for p in mock.projects_for(session.user_id)]
    projects.sort(key=lambda row: (row["start_date"] or "9999", row["name"]))
    proposals = [p for p in mock.proposals_for(session.user_id) if p["status"] == "pending"]
    open_proposals = []
    for proposal in proposals:
        project = mock.project(proposal["project_id"]) if proposal.get("project_id") else None
        open_proposals.append({
            "proposal_id": proposal["proposal_id"],
            "kind": proposal["kind"],
            "summary": proposal["summary"],
            "project_id": proposal.get("project_id"),
            "project_name": project.get("name") if project else None,
            "changes": proposal.get("changes", []),
            "status": proposal["status"],
            "created_at": proposal.get("created_at"),
        })

    return {
        **summary,
        "upcoming_shoots": upcoming,
        "needs_attention": attention,
        "projects": projects,
        "open_proposals": open_proposals,
        "totals": {
            "projects": len(projects),
            "boards": len(mock.boards_for(session.user_id)),
            "documents": len(mock.documents_for(session.user_id)),
            "pending_proposals": len(open_proposals),
        },
    }


@router.get("/projects")
def list_projects(request: Request, status: str = Query(default="")) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    if status and status not in ("draft", "dispatching", "escrow_held", "assigned", "initiated",
                                 "in_progress", "captured", "review", "completed", "cancelled"):
        raise HTTPException(status_code=422, detail={
            "error": "invalid_fields", "message": "That project status doesn't exist."})
    rows = [_summary_row(p) for p in mock.projects_for(session.user_id)]
    if status:
        rows = [r for r in rows if r["status"] == status]
    counts: dict[str, int] = {}
    for project in mock.projects_for(session.user_id):
        counts[project["status"]] = counts.get(project["status"], 0) + 1
    rows.sort(key=lambda row: (row["start_date"] or "9999", row["name"]))
    return {"count": len(rows), "projects": rows, "counts": counts}


@router.get("/projects/{project_id}")
def project_detail(project_id: str, request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    project = _project_or_404(session, project_id)
    project["talent"] = project.get("bookings", [])
    project["folders"] = project.get("deliverable_folders", [])
    project["display_location"] = _location(project)
    project["field_labels"] = FIELD_LABELS
    return {"project": project, "today": get_mock().today}


@router.post("/projects/{project_id}/documents")
def save_document(project_id: str, payload: SaveDocumentRequest, request: Request) -> dict:
    """The client's own Save tap — never a model tool."""
    check_same_origin(request)
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    _project_or_404(session, project_id)
    try:
        document = mock.add_document(session.user_id, project_id, payload.type, payload.title,
                                     payload.content_md)
    except PermissionError:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "I can't find that project on your account."})
    document.pop("client_id", None)
    return {"document": document, "saved": True}


@router.get("/documents")
def documents(request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    rows = []
    for doc in mock.documents_for(session.user_id):
        project = mock.project(doc["project_id"]) or {}
        rows.append({**doc, "project_name": project.get("name"), "project_status": project.get("status")})
    rows.sort(key=lambda d: (d.get("created_at") or "", d["title"]), reverse=True)
    return {"count": len(rows), "documents": rows}


@router.get("/boards")
def boards(request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    rows = []
    for board in mock.boards_for(session.user_id):
        names = [mock.project(pid)["name"] for pid in board.get("project_ids", []) if mock.project(pid)]
        rows.append({**board, "project_names": names})
    return {"count": len(rows), "boards": rows}


@router.get("/packages")
def packages(category: str = Query(default="")) -> dict:
    result = get_mock().call("list_packages", {"category": category} if category else {}, user=None)
    return result


@router.get("/options")
def options() -> dict:
    return {"catalogs": get_mock().api.options, "today": get_mock().today}


@router.get("/talent/search")
def talent_search(
    request: Request,
    role: str = Query(default=""),
    location: str = Query(default=""),
    specialty: str = Query(default=""),
    style: str = Query(default=""),
    budget_max: float | None = Query(default=None, ge=1, le=1_000_000),
    date: str = Query(default=""),
    limit: int = Query(default=6, ge=1, le=10),
) -> dict:
    session = get_session(request)
    if session.is_talent:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": "The client assistant is not available to creative accounts.",
        })
    args = {key: value for key, value in {
        "role": role, "location": location, "specialty": specialty, "style": style,
        "budget_max": budget_max, "date": date, "limit": limit,
    }.items() if value not in ("", None)}
    result = get_mock().call("search_talent", args, user=session.mock_user)
    return result


@router.get("/talent/{talent_id}")
def talent_profile(talent_id: str, request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    result = get_mock().call("get_talent_profile", {"talent_id": talent_id}, user=session.user_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail={
            "error": result.get("error", "not_found"),
            "message": result.get("message") or "I can't find that creative.",
        })
    return {"talent": result}


@router.get("/deliverables")
def pending_deliverables(request: Request) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    rows = []
    for project in mock.projects_for(session.user_id):
        for folder in mock.folders_for(project["id"]):
            if folder["review_status"] == "pending_client":
                rows.append({**folder, "project_name": project["name"]})
    return {"count": len(rows), "folders": rows}


@router.get("/proposals")
def list_proposals(request: Request, status: str = Query(default="pending")) -> dict:
    session = get_session(request)
    require_client(session)
    mock = get_mock()
    rows = []
    for proposal in mock.proposals_for(session.user_id):
        if status and proposal["status"] != status:
            continue
        project = mock.project(proposal["project_id"]) if proposal.get("project_id") else None
        rows.append({
            "proposal_id": proposal["proposal_id"], "kind": proposal["kind"],
            "summary": proposal["summary"], "changes": proposal.get("changes", []),
            "status": proposal["status"], "created_at": proposal.get("created_at"),
            "project_id": proposal.get("project_id"),
            "project_name": project.get("name") if project else None,
            "result": proposal.get("result"),
        })
    rows.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return {"count": len(rows), "proposals": rows}


@router.get("/config")
def public_config() -> dict:
    return {
        "dataset_today": get_mock().today,
        "assistance_fee_rate": get_mock().fee_rate,
        "model_configured": settings.model_configured,
        "model": settings.openai_model,
        "paid_statuses": list(PAID_STATUSES),
        "field_labels": FIELD_LABELS,
        "upload_limits": {
            "files": settings.max_upload_files,
            "image_mb": settings.max_image_bytes // (1024 * 1024),
            "pdf_mb": settings.max_pdf_bytes // (1024 * 1024),
            "pdf_pages": settings.max_pdf_pages,
        },
    }
