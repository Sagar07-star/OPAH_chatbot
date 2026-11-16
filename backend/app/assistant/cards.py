"""Builds the reply cards from real tool results.

The model never writes card markup: every card below is derived from what the
mock kit returned (and from the saved proposal for staging tools).
"""
from __future__ import annotations

from typing import Iterable

from ..services.mock_service import get_mock
from .tool_executor import ToolResult

PROPOSAL_APPLIES = {
    "create_project": "Approving creates this draft project on your account.",
    "update_project": "Approving writes these values to the project.",
    "add_talent_to_project": "Approving invites the creative. They can accept, decline or counter.",
    "respond_to_counter_offer": "Approving records your answer and updates the booking rate.",
    "review_deliverable": "Approving records this review decision on the folder.",
    "share_document": "Approving makes the document visible to the booked creative.",
    "create_board": "Approving creates this inspiration board on your account.",
}

HANDOFF_TITLES = {
    "checkout": "Checkout summary",
    "package_checkout": "Package checkout",
    "cancel_project": "Cancellation preview",
    "project_messages": "Draft message",
    "review_form": "Draft review",
}

PROJECT_FIELDS = (
    "id", "name", "status", "payment_status", "source", "project_type", "description",
    "start_date", "end_date", "scheduled_time", "duration_hours", "location", "role",
    "specialty", "budget", "budget_range", "deliverables", "lighting_styles",
    "point_of_contact", "priority", "client_notes", "deliverables_due_date", "package_id",
)


def _summary_card(result: dict) -> dict:
    """Enrich the kit's summary so the card shows names and places, not ids.

    The kit's proposal entries carry only a project id and its shoot summaries
    omit the location, so both are filled from the project record the tool
    already authorised for this client.
    """
    from ..services.mock_service import get_mock

    mock = get_mock()
    upcoming = []
    for shoot in result.get("upcoming_shoots", []):
        project = mock.project(shoot.get("id")) or {}
        raw_location = project.get("location")
        location = raw_location.get("display") if isinstance(raw_location, dict) else raw_location
        upcoming.append({**shoot, "location": location, "display_location": location})
    attention = []
    for item in result.get("needs_attention", []):
        project = mock.project(item["project_id"]) if item.get("project_id") else None
        attention.append({**item, "project": item.get("project") or (project or {}).get("name")})
    counts = result.get("project_counts", {}) or {}
    return {
        "type": "account_summary",
        "summary": {
            "client": result.get("client"),
            "today": result.get("today"),
            "upcoming_shoots": upcoming,
            "needs_attention": attention,
            "project_counts": counts,
            "totals": {"projects": sum(counts.values())},
            "open_support_tickets": result.get("open_support_tickets", 0),
        },
    }


def _project_card(project: dict) -> dict:
    data = {key: project.get(key) for key in PROJECT_FIELDS}
    data["bookings"] = project.get("bookings", [])
    data["deliverable_folders"] = project.get("deliverable_folders", [])
    data["documents"] = project.get("documents", [])
    data["missing_fields"] = project.get("missing_fields", [])
    data["editable_fields"] = project.get("editable_fields", [])
    payment = project.get("payment") or {}
    data["payment"] = {k: payment.get(k) for k in ("subtotal", "fee", "total", "status", "currency")} if payment else None
    data["open_proposals"] = project.get("open_proposals", [])
    return {"type": "project_details", "project": data}


def _proposal_card(result: dict) -> dict | None:
    if not result.get("proposal_id") or result.get("status") not in (None, "pending"):
        return None
    mock = get_mock()
    saved = mock.proposal(result["proposal_id"])
    proposal = saved or result
    project = mock.project(proposal.get("project_id")) if proposal.get("project_id") else None
    kind = proposal.get("kind", "")
    return {
        "type": "action_proposal",
        "proposal": {
            "proposal_id": proposal["proposal_id"],
            "kind": kind,
            "project_id": proposal.get("project_id"),
            "project_name": project.get("name") if project else None,
            "summary": proposal.get("summary"),
            "changes": proposal.get("changes", []),
            "status": proposal.get("status", "pending"),
            "created_at": proposal.get("created_at"),
            "applies": PROPOSAL_APPLIES.get(kind, "Approving applies this change."),
        },
    }


def _handoff_card(result: dict) -> dict | None:
    handoff = result.get("handoff")
    if not isinstance(handoff, dict):
        return None
    screen = handoff.get("screen", "")
    return {
        "type": "handoff",
        "handoff": {
            "screen": screen,
            "title": HANDOFF_TITLES.get(screen, "Hand-off"),
            "params": handoff.get("params", {}),
            "summary": handoff.get("summary", {}),
            "disclaimer": "Demo hand-off: nothing is charged, sent or cancelled from this prototype.",
        },
    }


def cards_for(records: Iterable[ToolResult]) -> list[dict]:
    cards: list[dict] = []
    seen_proposals: set[str] = set()

    for record in records:
        if not record.ok:
            continue
        result = record.result
        name = record.name

        if name in ("create_project", "update_project", "add_talent_to_project",
                    "respond_to_counter_offer", "review_deliverable", "share_document", "create_board"):
            card = _proposal_card(result)
            if card and card["proposal"]["proposal_id"] not in seen_proposals:
                seen_proposals.add(card["proposal"]["proposal_id"])
                cards.append(card)
        elif name in ("prepare_checkout", "prepare_package_booking", "prepare_cancellation",
                      "draft_message", "draft_review"):
            card = _handoff_card(result)
            if card:
                cards.append(card)
        elif name == "search_talent":
            cards.append({
                "type": "talent_results",
                "count": result.get("count", 0),
                "talents": result.get("talents", []),
                "applied": result.get("applied", {}),
                "relaxed": result.get("relaxed", []),
                "role_notice": result.get("role_notice"),
            })
        elif name == "get_talent_profile":
            cards.append({"type": "talent_profile", "talent": result})
        elif name == "get_account_summary":
            cards.append(_summary_card(result))
        elif name == "get_project":
            cards.append(_project_card(result))
        elif name == "list_projects":
            cards.append({"type": "project_list", "count": result.get("count", 0),
                          "projects": result.get("projects", [])})
        elif name == "list_deliverables":
            cards.append({"type": "deliverables", "project_id": result.get("project_id"),
                          "folders": result.get("folders", [])})
        elif name == "get_project_messages":
            cards.append({"type": "messages", "project_id": result.get("project_id"),
                          "messages": result.get("messages", [])})
        elif name == "list_packages":
            cards.append({"type": "packages", "packages": result.get("packages", []),
                          "service_area": result.get("service_area", []),
                          "assistance_fee_rate": result.get("assistance_fee_rate")})
        elif name == "list_boards":
            cards.append({"type": "boards", "boards": result.get("boards", [])})
        elif name == "get_cancellation_preview":
            cards.append({"type": "cancellation_preview", "preview": result})
        elif name == "get_project_options":
            cards.append({"type": "project_options", "catalogs": result.get("catalogs", {})})
        elif name in ("diagnose_account_issue",):
            cards.append({"type": "diagnosis", "diagnosis": result})
        elif name == "list_support_tickets":
            cards.append({"type": "support_tickets", "tickets": result.get("tickets", []),
                          "note": result.get("note")})
        elif name == "create_support_ticket":
            cards.append({"type": "support_ticket_created", "ticket": result.get("ticket"),
                          "stub": True, "note": result.get("note")})
        elif name == "restore_notifications":
            cards.append({"type": "stub_notice", "title": "Notifications",
                          "message": result.get("message"),
                          "connected": result.get("connected", False)})
    return cards


def envelope_type(cards: list[dict], model_type: str) -> str:
    if any(c["type"] == "action_proposal" for c in cards):
        return "action_proposal"
    if any(c["type"] == "handoff" for c in cards):
        return "handoff"
    if any(c["type"] == "talent_results" for c in cards):
        return "talent_results"
    if any(c["type"] == "talent_profile" for c in cards):
        return "talent_profile"
    if model_type == "planning_card":
        return "planning_card"
    if any(c["type"] == "account_summary" for c in cards):
        return "account_summary"
    if any(c["type"] == "project_details" for c in cards):
        return "project_details"
    if any(c["type"] == "project_list" for c in cards):
        return "project_list"
    return model_type or "text"
