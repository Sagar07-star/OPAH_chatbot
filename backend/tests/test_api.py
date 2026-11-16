"""API contract, permissions and uploads."""
from __future__ import annotations

import io

import pytest

from conftest import JORDAN, MAYA, SAM, login, logout

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00"
    b"\x00\x00IEND\xaeB`\x82"
)


def test_health_reports_the_dataset_day(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["dataset_today"] == "2026-11-16"
    assert body["model"] in (None, "") or isinstance(body["model"], str)


def test_session_lists_the_three_demo_accounts(client):
    body = client.get("/api/session").json()
    assert [a["id"] for a in body["accounts"]] == ["clt_001", "clt_002", "clt_003"]
    assert body["session"]["role"] == "anonymous"


def test_switching_identity_changes_the_session(client):
    body = login(client, MAYA)
    assert body["session"]["display_name"] == "Maya Torres"
    assert body["session"]["company"] == "Coral Bloom Skincare"
    body = login(client, JORDAN)
    assert body["session"]["display_name"] == "Jordan Pike"


def test_invalid_demo_identity_is_rejected(client):
    response = client.post("/api/session/switch", json={"user_id": "clt_999"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_identity"


def test_summary_matches_the_mock_data(maya):
    body = maya.get("/api/account/summary").json()
    assert body["client"]["id"] == MAYA
    assert body["totals"]["projects"] == 8
    kinds = {item["kind"] for item in body["needs_attention"]}
    assert {"counter_offer", "deliverables_to_review", "draft_incomplete"} <= kinds
    assert any(shoot["id"] == "prj_1004" for shoot in body["upcoming_shoots"])


def test_one_client_cannot_read_anothers_project(maya):
    response = maya.get("/api/projects/prj_2001")
    assert response.status_code == 404
    assert "Palm" not in response.text
    response = maya.get("/api/projects/prj_does_not_exist")
    assert response.status_code == 404


def test_anonymous_visitors_cannot_read_projects(visitor):
    assert visitor.get("/api/projects").status_code == 401
    assert visitor.get("/api/account/summary").status_code == 401
    assert visitor.get("/api/documents").status_code == 401
    assert visitor.get("/api/boards").status_code == 401
    assert visitor.get("/api/proposals").status_code == 401


def test_anonymous_visitors_can_search_talent_and_see_packages(visitor):
    search = visitor.get("/api/talent/search", params={"role": "videographer", "location": "miami beach"})
    assert search.status_code == 200
    assert search.json()["count"] > 0
    assert visitor.get("/api/packages").status_code == 200
    assert visitor.get("/api/options").status_code == 200
    assert visitor.get("/api/talent/tal_001").status_code == 401


def test_blocked_creative_never_appears_to_maya(maya):
    result = maya.get("/api/talent/search", params={"role": "videographer", "limit": 10}).json()
    assert "tal_018" not in result["talent_ids"]
    assert maya.get("/api/talent/tal_018").status_code == 404


def test_creative_accounts_are_blocked(client):
    login(client, "tal_001", role="talent")
    assert client.get("/api/projects").status_code == 403
    assert client.get("/api/account/summary").status_code == 403
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 403
    assert client.get("/api/talent/search").status_code == 403


def test_creating_a_creative_session_requires_the_talent_role(client):
    response = client.post("/api/session/switch", json={"user_id": "tal_001"})
    assert response.status_code == 400


def test_foreign_conversation_is_not_readable(client):
    login(client, MAYA)
    conversation = client.post("/api/chat", json={"message": "hello"}).json()["conversation_id"]
    login(client, JORDAN)
    assert client.get(f"/api/conversations/{conversation}/messages").status_code == 404


def test_project_options_come_from_the_dataset(maya):
    body = maya.get("/api/options").json()
    codes = {option["value"] for option in body["catalogs"]["project_type"]["options"]}
    assert "PRODUCT" in codes and "LIFESTYLE" not in codes


def test_packages_and_documents(maya):
    packages = maya.get("/api/packages").json()
    assert {p["id"] for p in packages["packages"]} >= {"pkg_listing_starter", "pkg_event_reel"}
    documents = maya.get("/api/documents").json()
    assert documents["count"] >= 1
    assert documents["documents"][0]["project_name"] == "Product Launch Video"
    boards = maya.get("/api/boards").json()
    assert boards["count"] == 2


def test_saving_a_planning_document_creates_a_project_document(maya):
    before = maya.get("/api/documents").json()["count"]
    response = maya.post("/api/projects/prj_1004/documents", json={
        "type": "shot_list",
        "title": "Launch film shot list",
        "content_md": "# Shot list\n1. Pool deck wide\n2. Studio hero\n3. Macro serum drip",
    })
    assert response.status_code == 200, response.text
    document = response.json()["document"]
    assert document["project_id"] == "prj_1004"
    assert document["version"] == 3  # the kit already has version 2 of this type
    assert maya.get("/api/documents").json()["count"] == before + 1


def test_a_client_cannot_save_a_document_on_anothers_project(maya):
    response = maya.post("/api/projects/prj_2001/documents", json={
        "type": "shot_list", "title": "Nope", "content_md": "not allowed on this project at all",
    })
    assert response.status_code == 404


def test_anonymous_cannot_save_documents(visitor):
    response = visitor.post("/api/projects/prj_1004/documents", json={
        "type": "shot_list", "title": "Nope", "content_md": "anonymous visitors have no projects",
    })
    assert response.status_code == 401


def test_upload_accepts_a_real_png(client):
    login(client, MAYA)
    response = client.post("/api/uploads", files={
        "files": ("ref.png", io.BytesIO(PNG_1PX), "image/png"),
    })
    assert response.status_code == 200, response.text
    upload = response.json()["uploads"][0]
    assert upload["mime"] == "image/png"
    raw = client.get(f"/api/uploads/{upload['id']}/raw")
    assert raw.status_code == 200
    assert raw.content.startswith(b"\x89PNG")


def test_upload_rejects_wrong_content_not_just_the_name(client):
    login(client, MAYA)
    response = client.post("/api/uploads", files={
        "files": ("brief.pdf", io.BytesIO(b"<html>not a pdf</html>"), "application/pdf"),
    })
    assert response.status_code == 400
    assert response.json()["error"] == "upload_rejected"
    assert "PDF" in response.json()["message"] or "content" in response.json()["message"]


def test_upload_rejects_more_than_ten_files(client):
    login(client, MAYA)
    files = [("files", (f"ref{i}.png", io.BytesIO(PNG_1PX), "image/png")) for i in range(11)]
    response = client.post("/api/uploads", files=files)
    assert response.status_code == 400
    assert "10" in response.json()["message"]


def test_uploaded_file_text_is_passed_to_the_model_as_untrusted_data(client, script_model):
    from conftest import text_reply

    login(client, MAYA)
    pdf = _minimal_pdf("Shoot the new serum in Wynwood on 2026-12-02, budget $2,000.")
    upload = client.post("/api/uploads", files={
        "files": ("brief.pdf", io.BytesIO(pdf), "application/pdf"),
    }).json()["uploads"][0]
    assert upload["has_text"] is True
    model = script_model(text_reply("Thanks — I read your brief. What time should we start?"))
    response = client.post("/api/chat", json={"message": "Use this brief", "upload_ids": [upload["id"]]})
    assert response.status_code == 200, response.text
    sent = str(model.messages[0][-1]["content"])
    assert "<<<UPLOADED_FILE" in sent and "Wynwood" in sent
    assert "untrusted data" in sent


def test_uploads_are_private_to_the_client(client):
    login(client, MAYA)
    upload_id = client.post("/api/uploads", files={
        "files": ("ref.png", io.BytesIO(PNG_1PX), "image/png"),
    }).json()["uploads"][0]["id"]
    login(client, JORDAN)
    assert client.get(f"/api/uploads/{upload_id}/raw").status_code == 404


def _minimal_pdf(text: str) -> bytes:
    """A tiny single-page PDF (Helvetica) with extractable text."""
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
