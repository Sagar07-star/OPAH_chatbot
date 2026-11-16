"""Transcript memory, working memory and upload records in SQLite."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..db import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ------------------------------------------------------------------ conversations
def ensure_conversation(client_id: str, project_id: str | None, title: str | None = None) -> dict:
    """One thread per client and project, safe under concurrent requests.

    Two tabs (or React StrictMode's double effect) can ask at the same moment,
    so the insert is idempotent and the row is read back afterwards.
    """
    scope = project_id or ""
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, client_id, project_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (_new_id("conv"), client_id, project_id, title, now, now),
        )
        row = conn.execute(
            "SELECT * FROM conversations WHERE client_id = ? AND IFNULL(project_id, '') = ?",
            (client_id, scope),
        ).fetchone()
        if row is None:  # pragma: no cover - the insert above guarantees a row
            raise RuntimeError("conversation could not be created")
        return dict(row)


def get_conversation(conversation_id: str, client_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND client_id = ?",
            (conversation_id, client_id),
        ).fetchone()
        return dict(row) if row else None


def list_conversations(client_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count "
            "FROM conversations c WHERE c.client_id = ? ORDER BY c.updated_at DESC",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def touch_conversation(conversation_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conversation_id))


def append_message(conversation_id: str, role: str, content: str,
                   envelope: dict | None = None) -> dict:
    now = _now()
    record = {
        "id": _new_id("msg"),
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "envelope": json.dumps(envelope) if envelope is not None else None,
        "created_at": now,
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, envelope, created_at) "
            "VALUES (:id, :conversation_id, :role, :content, :envelope, :created_at)",
            record,
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        # Keep the stored thread bounded at TRANSCRIPT_KEEP messages.
        conn.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND id NOT IN ("
            "  SELECT id FROM messages WHERE conversation_id = ? "
            "  ORDER BY created_at DESC, rowid DESC LIMIT ?)",
            (conversation_id, conversation_id, settings.transcript_keep),
        )
    record.pop("envelope", None)
    return record


def messages_for(conversation_id: str, limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, conversation_id, role, content, envelope, created_at FROM ("
            "  SELECT *, rowid AS _rid FROM messages WHERE conversation_id = ? "
            "  ORDER BY created_at DESC, rowid DESC LIMIT ?"
            ") ORDER BY created_at ASC, _rid ASC",
            (conversation_id, limit),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        if item.get("envelope"):
            try:
                item["envelope"] = json.loads(item["envelope"])
            except json.JSONDecodeError:
                item["envelope"] = None
        out.append(item)
    return out


def transcript_for_model(conversation_id: str, limit: int | None = None,
                         char_budget: int | None = None) -> list[dict]:
    """Recent turns only, newest kept, trimmed to a character budget.

    Long conversations cost latency and tokens on every turn, so the oldest
    messages are dropped rather than the newest context.
    """
    rows = messages_for(conversation_id, limit or settings.transcript_limit)
    budget = settings.transcript_char_budget if char_budget is None else char_budget
    out: list[dict] = []
    used = 0
    for row in reversed(rows):
        if row["role"] not in ("user", "assistant"):
            continue
        content = row["content"]
        envelope = row.get("envelope") or {}
        if row["role"] == "assistant" and envelope.get("message"):
            content = envelope["message"]
        if not content:
            continue
        if out and used + len(content) > budget:
            break
        used += len(content)
        out.append({"role": row["role"], "content": content})
    out.reverse()
    return out


def delete_message(message_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))


def update_proposal_cards(proposal_id: str, status: str, result: dict | None = None) -> None:
    """Keep saved transcript cards in step with the proposal's real state."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, envelope FROM messages WHERE envelope LIKE ?", (f"%{proposal_id}%",)
        ).fetchall()
        for row in rows:
            try:
                envelope = json.loads(row["envelope"])
            except (TypeError, json.JSONDecodeError):
                continue
            changed = False
            for card in (envelope.get("data", {}) or {}).get("cards", []) or []:
                if card.get("type") == "action_proposal" and card.get("proposal", {}).get("proposal_id") == proposal_id:
                    card["proposal"]["status"] = status
                    if result:
                        card["proposal"]["result"] = result
                    changed = True
            if changed:
                envelope.setdefault("data", {})["proposal_status"] = status
                conn.execute("UPDATE messages SET envelope = ? WHERE id = ?",
                             (json.dumps(envelope), row["id"]))


# ---------------------------------------------------------------- working memory
def wm_get(client_id: str, project_id: str | None, key: str, default: Any = None) -> Any:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM working_memory WHERE client_id = ? AND project_id = ? AND key = ?",
            (client_id, project_id or "", key),
        ).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def wm_set(client_id: str, project_id: str | None, key: str, value: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO working_memory (client_id, project_id, key, value, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(client_id, project_id, key) "
            "DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (client_id, project_id or "", key, json.dumps(value), _now()),
        )


def wm_clear(client_id: str, project_id: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM working_memory WHERE client_id = ? AND project_id = ?",
            (client_id, project_id or ""),
        )


def wm_all(client_id: str, project_id: str | None) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, value FROM working_memory WHERE client_id = ? AND project_id = ?",
            (client_id, project_id or ""),
        ).fetchall()
    out = {}
    for row in rows:
        try:
            out[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------- uploads
def save_upload(client_id: str, filename: str, mime: str, size_bytes: int, path: str,
                extracted_text: str | None, pages: int | None = None) -> dict:
    record = {
        "id": _new_id("upl"),
        "client_id": client_id,
        "filename": filename,
        "mime": mime,
        "size_bytes": size_bytes,
        "pages": pages,
        "path": path,
        "extracted_text": extracted_text,
        "created_at": _now(),
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO uploads (id, client_id, filename, mime, size_bytes, pages, path, extracted_text, created_at) "
            "VALUES (:id, :client_id, :filename, :mime, :size_bytes, :pages, :path, :extracted_text, :created_at)",
            record,
        )
    return record


def get_upload(upload_id: str, client_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ? AND client_id = ?", (upload_id, client_id)
        ).fetchone()
        return dict(row) if row else None


# ------------------------------------------------------------------- app errors
def log_app_error(client_id: str, route: str, message: str, status: int | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_errors (client_id, route, message, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (client_id, route[:200], message[:500], status, _now()),
        )


def recent_app_errors(client_id: str, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT route, message, status, created_at FROM app_errors WHERE client_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (client_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------- support stubs
def save_support_ticket(client_id: str, subject: str, category: str, body: str,
                        diagnosis: str) -> dict:
    record = {
        "id": _new_id("tktl"),
        "client_id": client_id,
        "subject": subject[:160],
        "category": category,
        "body": body[:2000],
        "diagnosis": diagnosis[:2000],
        "status": "queued_locally",
        "created_at": _now(),
        "stub": 1,
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO support_tickets (id, client_id, subject, category, body, diagnosis, status, created_at, stub) "
            "VALUES (:id, :client_id, :subject, :category, :body, :diagnosis, :status, :created_at, :stub)",
            record,
        )
    return record


def local_support_tickets(client_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM support_tickets WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ----------------------------------------------------------------- anonymous caps
def bump_anon_usage(session_key: str, messages: int = 0, uploads: int = 0) -> dict:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO anon_usage (session_key, messages, uploads, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_key) DO UPDATE SET messages = messages + excluded.messages, "
            "uploads = uploads + excluded.uploads, updated_at = excluded.updated_at",
            (session_key, messages, uploads, _now()),
        )
        row = conn.execute("SELECT * FROM anon_usage WHERE session_key = ?", (session_key,)).fetchone()
        return dict(row) if row else {"messages": messages, "uploads": uploads}
