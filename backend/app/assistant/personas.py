"""Persona selection.

The client never picks a persona: it follows the active project's state, with
Creative planner and Support as detours that return to the previous persona.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..services.mock_service import REQUIRED_FOR_BOOKING, get_mock

INTRO = "intro"
PROJECT_BUILDER = "project_builder"
TALENT_SCOUT = "talent_scout"
PROJECT_MANAGER = "project_manager"
CREATIVE_PLANNER = "creative_planner"
SUPPORT_AGENT = "support_agent"

LABELS = {
    INTRO: "Intro",
    PROJECT_BUILDER: "Project builder",
    TALENT_SCOUT: "Talent scout",
    PROJECT_MANAGER: "Project manager",
    CREATIVE_PLANNER: "Creative planner",
    SUPPORT_AGENT: "Support",
}

PLANNING_KEYWORDS = (
    "shot list", "shotlist", "shot plan", "mood board", "moodboard", "treatment",
    "storyboard", "script outline", "creative direction", "shoot schedule",
    "call sheet", "plan the shoot", "planning document",
)
SUPPORT_KEYWORDS = (
    "broken", "not working", "doesn't work", "does not work", "stopped working", "can't download",
    "cannot download", "can't upload", "error message", "getting an error", "support ticket",
    "contact support", "file a ticket", "charged twice", "double charged", "refund never",
    "receipt is wrong", "notifications are muted", "muted my notifications", "receipt",
)

DRAFT_MISSING_LABELS = {
    "name": "a project name",
    "description": "what you're shooting",
    "start_date": "the shoot date",
    "end_date": "the end date",
    "scheduled_time": "the call time",
    "duration_hours": "how many hours you need",
    "location": "the location",
    "role": "the kind of creative",
    "budget": "your budget",
}


@dataclass
class PersonaDecision:
    name: str
    label: str
    base: str
    detour: str | None
    reason: str

    def as_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "detour": self.detour, "reason": self.reason}


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    for phrase in phrases:
        if " " in phrase:
            if phrase in lowered:
                return True
        elif re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return True
    return False


def missing_fields(project: dict) -> list[str]:
    return [f for f in REQUIRED_FOR_BOOKING if project.get(f) in (None, "", [])]


def base_persona(project: dict | None, anonymous: bool) -> tuple[str, str]:
    if anonymous:
        return INTRO, "Visitors get talent search and package information only."
    if project is None:
        return INTRO, "No project is selected, so the focus is what to make next."
    status = project.get("status")
    if status == "draft":
        missing = missing_fields(project)
        if missing:
            return PROJECT_BUILDER, "The draft is missing " + ", ".join(missing) + "."
        return TALENT_SCOUT, "The draft has everything a creative needs, so the next step is talent."
    if status == "review" or status in ("completed", "cancelled"):
        return PROJECT_MANAGER, f"The project is {status}, so the focus is review and history."
    return PROJECT_MANAGER, f"The project is {status}, so the focus is running it."


def select_persona(message: str, project: dict | None, anonymous: bool) -> PersonaDecision:
    base, reason = base_persona(project, anonymous)
    detour: str | None = None
    if not anonymous and _has_phrase(message, SUPPORT_KEYWORDS):
        detour = SUPPORT_AGENT
    elif not anonymous and _has_phrase(message, PLANNING_KEYWORDS):
        detour = CREATIVE_PLANNER
    name = detour or base
    return PersonaDecision(name=name, label=LABELS[name], base=base, detour=detour, reason=reason)


def next_question(name: str, project: dict | None) -> str:
    """Fallback next-step question so every reply ends with exactly one ask."""
    if name == SUPPORT_AGENT:
        return "Want me to prepare a support ticket with these details?"
    if name == CREATIVE_PLANNER:
        return "Want me to save this to the project when it looks right?"
    if name == PROJECT_MANAGER:
        return "Want me to take the next step on this project?"
    if name == PROJECT_BUILDER:
        missing = missing_fields(project) if project else []
        if missing:
            return f"Shall we start with {DRAFT_MISSING_LABELS.get(missing[0], missing[0])}?"
        return "Shall I look for a creative for these dates?"
    if name == TALENT_SCOUT:
        return "Want me to shortlist a creative for these dates?"
    return "What are you looking to shoot?"


def suggested_prompts(name: str, project: dict | None, anonymous: bool) -> list[str]:
    if anonymous:
        return [
            "Show me videographers in Miami Beach",
            "What packages do you offer for a listing?",
            "What kind of project should I create?",
        ]
    if name == CREATIVE_PLANNER:
        return ["Draft a shot list for this shoot", "Make a mood board from my references"]
    if name == SUPPORT_AGENT:
        return ["My deliverables won't download", "Did support answer my receipt question?"]
    if name == PROJECT_BUILDER:
        return [
            "Help me fill in what's missing",
            "Set the shoot date, location and budget",
            "What do you still need from me?",
        ]
    if name == TALENT_SCOUT:
        return [
            "Compare the top two creatives for this date",
            "Who is free on the shoot date?",
            "Add the best match to the project",
        ]
    if name == PROJECT_MANAGER:
        if project and project.get("status") == "review":
            return ["What was delivered?", "Approve the beach selects"]
        if project and project.get("status") in ("completed", "cancelled"):
            return ["Draft a review of this project", "What did this project include?"]
        return ["What needs my attention on this project?", "What's the shoot-day plan?"]
    return ["What needs my attention?", "I need photos of my new menu next month", "Find me a photographer in Miami"]


__all__ = [
    "PersonaDecision", "select_persona", "base_persona", "missing_fields", "next_question",
    "suggested_prompts", "LABELS", "INTRO", "PROJECT_BUILDER", "TALENT_SCOUT",
    "PROJECT_MANAGER", "CREATIVE_PLANNER", "SUPPORT_AGENT",
]
