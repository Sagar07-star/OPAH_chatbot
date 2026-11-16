"""Turn guards: honesty checks, redaction and the single-question rule."""
from __future__ import annotations

import re

WRITE_TOOLS = {
    "create_project", "update_project", "add_talent_to_project", "respond_to_counter_offer",
    "review_deliverable", "share_document", "create_board",
    "prepare_checkout", "prepare_package_booking", "prepare_cancellation", "draft_message",
    "draft_review", "create_support_ticket",
}

CHANGE_CLAIM = re.compile(
    r"\b(?:i(?:'ve| have| just)?|we(?:'ve| have))\s+"
    r"(?:now\s+)?(?:updated|changed|created|added|booked|cancelled|canceled|saved|applied|shared|"
    r"approved|requested|accepted|sent|charged|paid|rescheduled|moved)\b"
    r"|\b(?:has|have)\s+been\s+(?:updated|changed|created|added|booked|cancelled|canceled|saved|applied|"
    r"shared|approved|sent|charged|paid|rescheduled)\b",
    re.IGNORECASE,
)
HONEST_QUALIFIERS = re.compile(
    r"\b(?:proposal|propose|approve|approval|approve button|pending|once you|when you|"
    r"ready to review|not sent|not charged|typed, not|can't|cannot|won't|will not|"
    r"need your|your tap|on approval)\b",
    re.IGNORECASE,
)

CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SECURITY_CODE = re.compile(
    r"\b((?:start|end|entry|exit)\s*code\s*(?:is|:)?\s*)([A-Za-z0-9-]{4,10})\b", re.IGNORECASE)
CVV = re.compile(r"\b(?:cvv|cvc|security code)\s*(?:is|:)?\s*\d{3,4}\b", re.IGNORECASE)
PASSWORD_LINK = re.compile(r"https?://\S*(?:reset|password)\S*", re.IGNORECASE)

LONG_QUESTION = re.compile(r"[^.!?\n]*\?")


def claims_change(text: str) -> bool:
    if not text:
        return False
    if not CHANGE_CLAIM.search(text):
        return False
    return not HONEST_QUALIFIERS.search(text)


def redact_sensitive(text: str) -> str:
    cleaned = CARD_NUMBER.sub("[card number removed]", text or "")
    cleaned = CVV.sub("security code removed", cleaned)
    cleaned = SECURITY_CODE.sub(lambda m: m.group(1) + "[code hidden]", cleaned)
    cleaned = PASSWORD_LINK.sub("[link removed]", cleaned)
    return cleaned


def question_count(text: str) -> int:
    return len(re.findall(r"\?", text or ""))


def ensure_single_question(text: str, fallback_question: str) -> str:
    """Every reply ends with exactly one next-step question."""
    body = (text or "").strip()
    if not body:
        return fallback_question
    matches = list(LONG_QUESTION.finditer(body))
    if not matches:
        return f"{body} {fallback_question}".strip()
    if len(matches) == 1:
        return body
    # Keep the final question; drop earlier question sentences but keep their facts.
    for match in matches[:-1]:
        fragment = match.group(0)
        body = body.replace(fragment, "", 1)
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body or fallback_question


ALLOWED_TYPES = {
    "text", "talent_results", "action_proposal", "handoff", "account_summary", "project_details",
    "project_list", "talent_profile", "planning_card", "pulse", "error",
}

PLANNING_TYPES = {"treatment", "shot_list", "schedule", "script_outline", "storyboard", "mood_board"}


def valid_envelope_type(value: str, default: str = "text") -> str:
    return value if value in ALLOWED_TYPES else default


def validate_planning(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    doc_type = str(value.get("type") or "").strip()
    title = str(value.get("title") or "").strip()[:120]
    content = str(value.get("content_md") or "").strip()
    if doc_type not in PLANNING_TYPES or not title or len(content) < 20:
        return None
    return {"type": doc_type, "title": title, "content_md": content[:12000]}
