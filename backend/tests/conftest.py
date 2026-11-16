"""Test harness.

Tests never call the real OpenAI API: the scripted model below stands in for the
provider so the orchestration, tool loop, guards, cards and approval path are
exercised deterministically. Model *quality* is covered by the live scenario
runner (scripts/run_scenarios.py), which needs a real OPENAI_API_KEY.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="createchat-tests-"))
os.environ.setdefault("DATABASE_PATH", str(TEST_DIR / "test.db"))
os.environ.setdefault("UPLOAD_DIR", str(TEST_DIR / "uploads"))
os.environ.setdefault("APP_ENV", "test")
os.environ.pop("OPENAI_API_KEY", None)
# backend/.env may hold a real key; keep the suite offline and free of provider calls.
os.environ["MODERATION_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.assistant.llm import LLMReply, ToolCall  # noqa: E402
from app.main import app  # noqa: E402

MAYA, JORDAN, SAM = "clt_001", "clt_002", "clt_003"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(client):
    client.post("/api/demo/reset", json={"conversations": True})
    yield


def login(client: TestClient, user_id: str, role: str | None = None) -> dict:
    payload = {"user_id": user_id}
    if role:
        payload["role"] = role
    response = client.post("/api/session/switch", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def logout(client: TestClient) -> dict:
    response = client.post("/api/session/switch", json={"user_id": "anonymous"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def maya(client):
    login(client, MAYA)
    return client


@pytest.fixture
def jordan(client):
    login(client, JORDAN)
    return client


@pytest.fixture
def visitor(client):
    logout(client)
    return client


class ScriptedLLM:
    """A model stand-in: returns the queued replies and records the messages."""

    configured = True

    def __init__(self, responses: list[LLMReply]):
        self.responses = list(responses)
        self.messages: list[list[dict]] = []
        self.tools: list[list[dict]] = []

    def _next(self) -> LLMReply:
        if not self.responses:
            return LLMReply(content=json.dumps({"message": "No more scripted replies. Anything else?",
                                                "reply_type": "text"}))
        return self.responses.pop(0)

    async def complete(self, messages, tools=None, tool_choice="auto", response_format=None,
                       temperature=0.2, max_tokens=1100):
        self.messages.append(messages)
        self.tools.append(tools or [])
        return self._next()

    async def stream(self, messages, tools=None, tool_choice="auto", response_format=None,
                     temperature=0.2, max_tokens=None):
        self.messages.append(messages)
        self.tools.append(tools or [])
        reply = self._next()
        if reply.content:
            yield "delta", reply.content
        yield "reply", reply


def text_reply(message: str, reply_type: str = "text", planning: dict | None = None) -> LLMReply:
    payload = {"message": message, "reply_type": reply_type, "planning": planning}
    return LLMReply(content=json.dumps(payload), model="scripted-model")


def tool_reply(*calls: tuple[str, dict], content: str = "") -> LLMReply:
    tool_calls = [ToolCall(id=f"call_{index}", name=name, arguments=args)
                  for index, (name, args) in enumerate(calls, start=1)]
    return LLMReply(
        content=content,
        tool_calls=tool_calls,
        assistant_message={
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"id": call.id, "type": "function",
                 "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
                for call in tool_calls
            ],
        },
        finish_reason="tool_calls",
        model="scripted-model",
    )


@pytest.fixture
def script_model(monkeypatch):
    """Replace the module-level model the assistant core uses."""
    holder: dict = {}

    def install(*responses: LLMReply) -> ScriptedLLM:
        model = ScriptedLLM(list(responses))
        import app.assistant.core as core

        monkeypatch.setattr(core, "llm", model)
        holder["model"] = model
        return model

    return install
