"""Streaming, regenerate and transcript trimming."""
from __future__ import annotations

import json

from app.assistant import memory
from app.config import settings

from conftest import MAYA, login, text_reply, tool_reply


def _events(body: str) -> list[dict]:
    out = []
    for line in body.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


def test_stream_emits_status_deltas_and_done(client, script_model):
    login(client, MAYA)
    script_model(text_reply("Hello there. What are we shooting?"))

    with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: status" in body
    assert "event: delta" in body
    events = _events(body)
    done = [event for event in events if event["type"] == "done"]
    assert done, body
    assert done[0]["result"]["envelope"]["message"].startswith("Hello there.")
    assert done[0]["result"]["conversation"]["id"]


def test_stream_reports_tool_progress(client, script_model):
    login(client, MAYA)
    script_model(
        tool_reply(("get_account_summary", {})),
        text_reply("You have a counter-offer waiting."),
    )

    with client.stream("POST", "/api/chat/stream",
                       json={"message": "What needs my attention?"}) as response:
        body = "".join(response.iter_text())

    statuses = [event for event in _events(body) if event["type"] == "status"]
    assert any(event.get("phase") == "tools" for event in statuses)
    assert any("get_account_summary" in (event.get("tools") or []) for event in statuses)


def test_stream_reports_permission_errors_as_events(client):
    login(client, "clt_002")
    with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        body = "".join(response.iter_text())
    assert "event: done" in body or "event: error" in body


def test_regenerate_replaces_the_last_answer_without_duplicating_the_question(client, script_model):
    login(client, MAYA)
    model = script_model(text_reply("First answer."), text_reply("Second answer."))
    first = client.post("/api/chat", json={"message": "Tell me something"}).json()
    assert first["envelope"]["message"].startswith("First answer.")

    second = client.post("/api/chat", json={
        "regenerate": True, "conversation_id": first["conversation_id"],
    }).json()
    assert second["envelope"]["message"].startswith("Second answer.")
    assert second["conversation_id"] == first["conversation_id"]
    assert len(model.messages) == 2

    rows = client.get(f"/api/conversations/{first['conversation_id']}/messages").json()["messages"]
    assert [row["role"] for row in rows] == ["user", "assistant"]


def test_regenerate_without_history_is_rejected(client, script_model):
    login(client, MAYA)
    script_model()
    response = client.post("/api/chat", json={"regenerate": True})
    assert response.status_code == 422


def test_transcript_for_model_stays_within_the_character_budget(client):
    conversation = memory.ensure_conversation(MAYA, None, "All projects")
    for index in range(30):
        memory.append_message(conversation["id"], "user", f"question {index} " + "x" * 200)
        memory.append_message(conversation["id"], "assistant", f"answer {index} " + "y" * 200)
    rows = memory.transcript_for_model(conversation["id"], limit=40)
    assert sum(len(row["content"]) for row in rows) <= settings.transcript_char_budget + 400
    assert rows[-1]["content"].startswith("answer 29")


def test_tool_surface_is_built_once_per_turn():
    from app.assistant.tool_executor import ToolExecutor
    from app.security.identity import Session

    executor = ToolExecutor(Session(MAYA, "client"))
    first = executor.schemas()
    assert first is executor.schemas()
    assert "approve_proposal" not in {schema["name"] for schema in first}
