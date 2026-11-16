"""Context blocks built fresh every turn from the database."""
from __future__ import annotations

import json
from datetime import date

from ..services.mock_service import FIELD_LABELS, get_mock
from ..security.identity import Session
from . import memory
from .personas import SUPPORT_AGENT, missing_fields

MAX_BLOCK_CHARS = 6000


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)[:MAX_BLOCK_CHARS]


def _active_project_block(project: dict) -> dict:
    keys = ("id", "name", "status", "payment_status", "source", "project_type", "description",
            "start_date", "end_date", "scheduled_time", "duration_hours", "location", "role",
            "specialty", "budget", "budget_range", "deliverables", "lighting_styles",
            "point_of_contact", "priority", "client_notes", "deliverables_due_date", "package_id")
    data = {k: project.get(k) for k in keys if k in project}
    data["missing_fields"] = missing_fields(project) if project.get("status") == "draft" else []
    data["bookings"] = [
        {k: b.get(k) for k in ("id", "talent_name", "role", "status", "rate", "counter_rate",
                               "counter_message", "pending_change")}
        for b in project.get("bookings", [])
    ]
    data["deliverable_folders"] = [
        {k: f.get(k) for k in ("id", "name", "review_status", "review_due_at", "revisions_used",
                               "revisions_included", "revision_note", "file_count")}
        for f in project.get("deliverable_folders", [])
    ]
    data["documents"] = [
        {k: d.get(k) for k in ("id", "type", "title", "version", "shared_with_talent")}
        for d in project.get("documents", [])
    ]
    data["open_proposals"] = project.get("open_proposals", [])
    return data


def client_profile(session: Session) -> dict:
    mock = get_mock()
    client = mock.client(session.user_id) or {}
    projects = mock.projects_for(session.user_id)
    counts: dict[str, int] = {}
    for project in projects:
        counts[project["status"]] = counts.get(project["status"], 0) + 1
    past_talent = []
    for project in projects:
        for booking in mock.bookings_for(project["id"]):
            if booking["status"] == "accepted" and booking["talent_name"] not in past_talent:
                past_talent.append(booking["talent_name"])
    member_since = client.get("member_since")
    days = None
    if member_since:
        try:
            days = (date.fromisoformat(mock.today) - date.fromisoformat(member_since)).days
        except ValueError:
            days = None
    return {
        "first_name": client.get("first_name"),
        "company": client.get("company"),
        "member_since": member_since,
        "member_days": days,
        "projects_by_status": counts,
        "typical_budget": client.get("typical_budget"),
        "preferred_roles": client.get("preferred_roles"),
        "past_talent": past_talent[:8],
    }


def build_context(session: Session, project: dict | None, persona: str,
                  block_id: str = "") -> str:
    mock = get_mock()
    blocks: list[str] = []

    scope = project["id"] if project else None
    working = memory.wm_all(session.user_id, scope) if session.is_client else {}

    context = {
        "viewer_role": session.role,
        "client_app": "web",
        "active_project_id": project["id"] if project else None,
        "dataset_day": mock.today,
        "known_filters": working.get("last_search_filters") or {},
    }
    blocks.append("<context>\n" + _json(context) + "\n</context>")

    if project:
        blocks.append("<active_project>\n" + _json(_active_project_block(project)) + "\n</active_project>")

    if session.is_client:
        blocks.append("<client_profile>\n" + _json(client_profile(session)) + "\n</client_profile>")

        notes = []
        if working.get("last_search"):
            last = working["last_search"]
            notes.append(f"Last search: {last.get('count')} matches for "
                         f"{json.dumps(last.get('filters') or {})}; top ids {last.get('talent_ids', [])[:5]}.")
        if working.get("last_profile"):
            notes.append(f"Last profile opened: {working['last_profile']}.")
        if working.get("current_artifact"):
            notes.append(f"Planning document in progress: {working['current_artifact'].get('title')}.")
        if working.get("priorities"):
            notes.append(f"Client's stated priorities: {working['priorities']}.")
        if notes:
            blocks.append("<creative_context>\n" + "\n".join(notes) + "\n</creative_context>")

        if working.get("last_search"):
            last = working["last_search"]
            blocks.append("<last_search>\n" + _json({
                "filters": last.get("filters"), "talent_ids": last.get("talent_ids"),
                "names": last.get("names"), "count": last.get("count"),
            }) + "\n</last_search>")

        artifact = working.get("current_artifact")
        if artifact and project:
            blocks.append("<current_artifact>\n" + _json(artifact) + "\n</current_artifact>")

        if persona == SUPPORT_AGENT:
            errors = memory.recent_app_errors(session.user_id)
            if errors:
                blocks.append("<recent_app_errors>\n" + _json(errors) + "\n</recent_app_errors>")

    if block_id:
        blocks.append(f"<turn>{block_id}</turn>")
    return "\n\n".join(blocks)


def missing_field_labels(project: dict) -> list[str]:
    return [FIELD_LABELS.get(f, f) for f in missing_fields(project)]
