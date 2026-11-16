"""Request/response models for the chat API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ..config import settings

EnvelopeType = Literal[
    "text", "talent_results", "action_proposal", "handoff", "account_summary", "project_details",
    "project_list", "talent_profile", "planning_card", "pulse", "error",
]


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    project_id: str | None = None
    conversation_id: str | None = None
    upload_ids: list[str] = Field(default_factory=list, max_length=10)
    regenerate: bool = False

    @field_validator("message")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()

    @field_validator("project_id", "conversation_id")
    @classmethod
    def _clean_id(cls, value: str | None) -> str | None:
        if value in ("", "all", "general", "null", "undefined"):
            return None
        if value and not value.replace("_", "").isalnum():
            raise ValueError("ids look like prj_1002")
        return value

    @field_validator("upload_ids")
    @classmethod
    def _cap(cls, value: list[str]) -> list[str]:
        if len(value) > settings.max_upload_files:
            raise ValueError(f"At most {settings.max_upload_files} files per message.")
        return value


class Envelope(BaseModel):
    type: EnvelopeType = "text"
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)


class PersonaInfo(BaseModel):
    name: str
    label: str
    detour: str | None = None
    reason: str = ""


class ToolCallInfo(BaseModel):
    name: str
    ok: bool
    error: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    envelope: Envelope
    persona: PersonaInfo
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    model: str = ""
    created_at: str = ""


class SwitchRequest(BaseModel):
    user_id: str
    role: Literal["client", "talent", "anonymous"] | None = None


class ActiveProjectRequest(BaseModel):
    project_id: str | None = None


class SaveDocumentRequest(BaseModel):
    type: Literal["treatment", "shot_list", "schedule", "script_outline", "storyboard", "mood_board"]
    title: str = Field(min_length=1, max_length=120)
    content_md: str = Field(min_length=20, max_length=12000)


class SupportTicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    topic: str = "other"
    details: str = Field(min_length=5, max_length=2000)
    project_id: str | None = None


class AppErrorRequest(BaseModel):
    route: str = Field(max_length=200)
    message: str = Field(max_length=500)
    status: int | None = None


class ProposalResponse(BaseModel):
    proposal_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    message: str | None = None
