"""Session-based identity for the prototype.

The backend — never the model, never a tool argument — decides who is talking.
A signed, http-only cookie carries the demo identity. Tool calls receive the
identifier from this module only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from ..config import settings
from ..services.mock_service import ROLE_ANONYMOUS, ROLE_CLIENT, ROLE_TALENT, demo_accounts, known_talent, known_client


COOKIE_NAME = "createchat_session"
ROLES = (ROLE_CLIENT, ROLE_TALENT, ROLE_ANONYMOUS)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_token(user_id: str, role: str) -> str:
    payload = {"uid": user_id, "role": role, "exp": int(time.time()) + settings.session_days * 86400}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"v1.{body}.{signature}"


def read_token(token: str | None) -> dict | None:
    if not token or not token.startswith("v1."):
        return None
    try:
        _, body, signature = token.split(".", 2)
    except ValueError:
        return None
    expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    if payload.get("role") not in ROLES:
        return None
    return payload


@dataclass(frozen=True)
class Session:
    user_id: str          # client id, talent id, or "anonymous"
    role: str             # client | talent | anonymous

    @property
    def is_client(self) -> bool:
        return self.role == ROLE_CLIENT

    @property
    def is_anonymous(self) -> bool:
        return self.role == ROLE_ANONYMOUS

    @property
    def is_talent(self) -> bool:
        return self.role == ROLE_TALENT

    @property
    def mock_user(self) -> str | None:
        """The identity handed to the mock kit, or None for a visitor."""
        return self.user_id if self.is_client else None


ANONYMOUS = Session(user_id="anonymous", role=ROLE_ANONYMOUS)


def resolve_session(request: Request) -> Session:
    payload = read_token(request.cookies.get(COOKIE_NAME))
    if not payload:
        return ANONYMOUS
    uid, role = str(payload.get("uid")), str(payload.get("role"))
    if role == ROLE_CLIENT:
        return Session(uid, role) if known_client(uid) else ANONYMOUS
    if role == ROLE_TALENT:
        return Session(uid, role) if known_talent(uid) else ANONYMOUS
    return ANONYMOUS


def get_session(request: Request) -> Session:
    return resolve_session(request)


def set_session_cookie(response: Response, session: Session) -> str:
    token = issue_token(session.user_id, session.role)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/",
    )
    return token


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def validate_demo_identity(user_id: str, role: str = "") -> Session:
    """Accept only identities that exist in the provided dataset."""
    if user_id in ("anonymous", "visitor", ""):
        return ANONYMOUS
    if known_client(user_id) and role in ("", ROLE_CLIENT):
        return Session(user_id, ROLE_CLIENT)
    if known_talent(user_id) and role == ROLE_TALENT:
        return Session(user_id, ROLE_TALENT)
    raise HTTPException(status_code=400, detail={
        "error": "invalid_identity",
        "message": "That demo identity is not part of the prototype dataset.",
        "accounts": [a["id"] for a in demo_accounts()],
    })


def require_client(session: Session) -> None:
    if session.is_talent:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": "The client assistant is not available to creative accounts.",
        })
    if not session.is_client:
        raise HTTPException(status_code=401, detail={
            "error": "auth_required",
            "message": "Please sign in to do that.",
        })


def check_same_origin(request: Request) -> None:
    """Reject cross-site state changes on the demo origin."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    allowed = set(settings.cors_origins)
    host = request.headers.get("host", "")
    allowed |= {f"http://{host}", f"https://{host}"}
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in allowed:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden_origin",
            "message": "That request came from an unexpected origin.",
        })
