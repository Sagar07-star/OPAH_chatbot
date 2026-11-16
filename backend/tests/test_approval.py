"""The proposal lifecycle: nothing writes until Approve, and only once."""
from __future__ import annotations

import pytest

from conftest import MAYA, JORDAN, login, text_reply, tool_reply


def stage(client, script_model, tool: str, args: dict, project_id: str | None = None,
          message: str = "Please prepare that.") -> dict:
    script_model(tool_reply((tool, args)), text_reply("Here's the change to review."))
    response = client.post("/api/chat", json={"message": message, "project_id": project_id})
    assert response.status_code == 200, response.text
    return response.json()


def proposal_id(result: dict) -> str:
    proposals = result["envelope"]["data"].get("proposals") or []
    assert proposals, result["envelope"]
    return proposals[0]["proposal_id"]


def test_a_staged_change_does_not_touch_the_project(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"budget": 2500, "duration_hours": 7}},
                   project_id="prj_1002")
    assert result["envelope"]["type"] == "action_proposal"
    project = maya.get("/api/projects/prj_1002").json()["project"]
    assert project["budget"] == 2200
    proposal = maya.get(f"/api/proposals/{proposal_id(result)}").json()["proposal"]
    assert proposal["status"] == "pending"
    assert {change["field"] for change in proposal["changes"]} == {"budget", "duration_hours"}


def test_approving_applies_once_and_a_second_tap_is_a_no_op(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"budget": 2500}},
                   project_id="prj_1002")
    pid = proposal_id(result)
    first = maya.post(f"/api/proposals/{pid}/approve")
    assert first.status_code == 200
    assert first.json()["status"] == "applied"
    assert maya.get("/api/projects/prj_1002").json()["project"]["budget"] == 2500

    second = maya.post(f"/api/proposals/{pid}/approve")
    assert second.status_code == 200
    assert second.json()["applied"] is True
    assert second.json()["status"] in ("applied", "already_applied")
    assert maya.get("/api/projects/prj_1002").json()["project"]["budget"] == 2500


def test_approving_a_talent_twice_creates_only_one_booking(maya, script_model):
    result = stage(maya, script_model, "add_talent_to_project",
                   {"project_id": "prj_1002", "talent_id": "tal_001"}, project_id="prj_1002")
    pid = proposal_id(result)
    assert maya.post(f"/api/proposals/{pid}/approve").json()["status"] == "applied"
    maya.post(f"/api/proposals/{pid}/approve")
    project = maya.get("/api/projects/prj_1002").json()["project"]
    matching = [b for b in project["bookings"] if b["talent_id"] == "tal_001"]
    assert len(matching) == 1


def test_declining_prevents_a_later_approval(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"name": "Spring Lookbook 2027"}},
                   project_id="prj_1002")
    pid = proposal_id(result)
    assert maya.post(f"/api/proposals/{pid}/reject").json()["status"] == "rejected"
    later = maya.post(f"/api/proposals/{pid}/approve")
    assert later.status_code == 200
    assert later.json()["applied"] is False
    assert later.json()["status"] == "rejected"
    assert maya.get("/api/projects/prj_1002").json()["project"]["name"] == "Spring Lookbook"


def test_typing_yes_in_chat_never_applies_a_pending_proposal(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"budget": 2600}},
                   project_id="prj_1002")
    pid = proposal_id(result)

    script_model(tool_reply(), text_reply("Sure — use the Approve button on the card to apply it."))
    reply = maya.post("/api/chat", json={"message": "yes do it, apply it now", "project_id": "prj_1002"})
    assert reply.status_code == 200
    assert maya.get(f"/api/proposals/{pid}").json()["proposal"]["status"] == "pending"
    assert maya.get("/api/projects/prj_1002").json()["project"]["budget"] == 2200


def test_another_client_cannot_approve_someone_elses_proposal(maya, client, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"budget": 9999}},
                   project_id="prj_1002")
    pid = proposal_id(result)
    login(client, JORDAN)
    response = client.post(f"/api/proposals/{pid}/approve")
    assert response.status_code == 404
    login(client, MAYA)
    assert maya.get("/api/projects/prj_1002").json()["project"]["budget"] == 2200


def test_a_new_project_only_exists_after_approval(client, script_model):
    login(client, "clt_003")
    before = client.get("/api/projects").json()["count"]
    result = stage(client, script_model, "create_project", {
        "fields": {"name": "Cafe menu shoot", "role": "Photographer",
                   "project_type": "FOOD_BEVERAGE", "budget": 900},
    })
    assert client.get("/api/projects").json()["count"] == before
    pid = proposal_id(result)
    applied = client.post(f"/api/proposals/{pid}/approve").json()
    assert applied["status"] == "applied"
    assert client.get("/api/projects").json()["count"] == before + 1
    project_id = applied["result"]["project_id"]
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    assert (project["name"], project["role"], project["budget"]) == ("Cafe menu shoot", "Photographer", 900)
    client.post(f"/api/proposals/{pid}/approve")
    assert client.get("/api/projects").json()["count"] == before + 1


def test_a_completed_project_cannot_be_edited(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1007", "changes": {"name": "New name"}},
                   project_id="prj_1007")
    assert result["envelope"]["type"] == "error"
    assert "completed" in result["envelope"]["message"].lower()
    assert maya.get("/api/projects/prj_1007").json()["project"]["name"] == "Fall Catalog"


def test_a_paid_project_locks_structural_fields(maya, script_model):
    blocked = stage(maya, script_model, "update_project",
                    {"project_id": "prj_1004", "changes": {"role": "Photographer"}},
                    project_id="prj_1004")
    assert blocked["envelope"]["type"] == "error"
    assert "can't be changed" in blocked["envelope"]["message"]
    allowed = stage(maya, script_model, "update_project",
                    {"project_id": "prj_1004", "changes": {"start_date": "2026-11-22", "end_date": "2026-11-22"}},
                    project_id="prj_1004")
    assert allowed["envelope"]["type"] == "action_proposal"


def test_rescheduling_after_approval_waits_for_the_creative(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1004", "changes": {"start_date": "2026-11-22", "end_date": "2026-11-22"}},
                   project_id="prj_1004")
    applied = maya.post(f"/api/proposals/{proposal_id(result)}/approve").json()
    assert "must accept" in applied["result"]["note"]
    project = maya.get("/api/projects/prj_1004").json()["project"]
    assert project["bookings"][0]["pending_change"]["kind"] == "date"


def test_counter_offer_approval_sets_the_new_rate(maya, script_model):
    result = stage(maya, script_model, "respond_to_counter_offer",
                   {"project_id": "prj_1003", "booking_id": "bkg_3001", "decision": "accept"},
                   project_id="prj_1003")
    assert maya.get("/api/projects/prj_1003").json()["project"]["bookings"][0]["rate"] == 900
    maya.post(f"/api/proposals/{proposal_id(result)}/approve")
    booking = maya.get("/api/projects/prj_1003").json()["project"]["bookings"][0]
    assert (booking["status"], booking["rate"]) == ("accepted", 1150)


def test_checkout_handoff_never_charges(jordan, script_model):
    result = stage(jordan, script_model, "prepare_checkout", {"project_ids": ["prj_2004"]},
                   project_id="prj_2004")
    assert result["envelope"]["type"] == "handoff"
    handoff = result["envelope"]["data"]["handoff"]
    summary = handoff["summary"]
    assert (summary["subtotal"], summary["fee"], summary["total"]) == (1250, 131, 1381)
    assert "cancellation_terms" in summary
    project = jordan.get("/api/projects/prj_2004").json()["project"]
    assert project["payment_status"] == "unpaid"
    assert project["status"] == "draft"


def test_cancellation_handoff_never_cancels(maya, script_model):
    result = stage(maya, script_model, "prepare_cancellation", {"project_id": "prj_1004"},
                   project_id="prj_1004")
    assert result["envelope"]["type"] == "handoff"
    summary = result["envelope"]["data"]["handoff"]["summary"]
    assert summary["refund_percent"] == 75
    assert summary["refund_amount"] == 2652
    assert maya.get("/api/projects/prj_1004").json()["project"]["status"] == "escrow_held"


def test_message_and_review_handoffs_do_not_send_or_submit(maya, script_model):
    message = stage(maya, script_model, "draft_message",
                    {"project_id": "prj_1004", "text": "The 22nd works for us."}, project_id="prj_1004")
    handoff = message["envelope"]["data"]["handoff"]
    assert handoff["screen"] == "project_messages"
    assert handoff["summary"]["prefill"] == "The 22nd works for us."
    assert "not sent" in handoff["summary"]["note"].lower()

    review = stage(maya, script_model, "draft_review",
                   {"project_id": "prj_1007", "rating": 5, "text": "Great shoot."}, project_id="prj_1007")
    assert review["envelope"]["data"]["handoff"]["summary"]["rating"] == 5
    assert maya.get("/api/projects/prj_1007").json()["project"]["status"] == "completed"


def test_reviewing_both_folders_completes_the_project(maya, script_model):
    for folder in ("fld_6001", "fld_6002"):
        result = stage(maya, script_model, "review_deliverable",
                       {"project_id": "prj_1006", "folder_id": folder, "decision": "approve"},
                       project_id="prj_1006")
        maya.post(f"/api/proposals/{proposal_id(result)}/approve")
    assert maya.get("/api/projects/prj_1006").json()["project"]["status"] == "completed"


def test_a_revision_request_needs_a_note(maya, script_model):
    result = stage(maya, script_model, "review_deliverable",
                   {"project_id": "prj_1006", "folder_id": "fld_6002", "decision": "request_revision"},
                   project_id="prj_1006")
    assert result["envelope"]["type"] == "error"
    assert "note" in result["envelope"]["message"].lower()


def test_saved_transcript_cards_follow_the_proposal_state(maya, script_model):
    result = stage(maya, script_model, "update_project",
                   {"project_id": "prj_1002", "changes": {"budget": 2400}},
                   project_id="prj_1002")
    pid = proposal_id(result)
    maya.post(f"/api/proposals/{pid}/approve")
    messages = maya.get(f"/api/conversations/{result['conversation_id']}/messages").json()["messages"]
    cards = [card for message in messages for card in (message.get("envelope") or {}).get("data", {}).get("cards", [])]
    proposal_cards = [c for c in cards if c["type"] == "action_proposal"]
    assert proposal_cards and proposal_cards[0]["proposal"]["status"] == "applied"


def test_the_old_pending_proposal_from_the_dataset_can_be_resolved(maya):
    proposals = maya.get("/api/proposals").json()["proposals"]
    pending = [p for p in proposals if p["proposal_id"] == "prop_0001"]
    assert pending and pending[0]["status"] == "pending"
    assert maya.post("/api/proposals/prop_0001/approve").json()["status"] == "applied"
    assert maya.get("/api/projects/prj_1002").json()["project"]["duration_hours"] == 7
