"""Server-side tool execution.

Only tools that exist in the mock kit (plus the clearly labelled support stubs)
can run. Identity comes from the session — never from tool arguments — and the
approval endpoints are deliberately absent from this registry.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from ..services.mock_service import get_mock

import mock_tools as kit  # noqa: E402  (mock_service puts the kit on sys.path)

from ..assistant import memory
from ..config import settings
from ..security.identity import Session

STAGE_TOOLS = {"create_project", "update_project", "add_talent_to_project", "respond_to_counter_offer",
               "review_deliverable", "share_document", "create_board"}
HANDOFF_TOOLS = {"prepare_checkout", "prepare_package_booking", "prepare_cancellation",
                 "draft_message", "draft_review"}
READ_TOOLS = {"get_account_summary", "list_projects", "get_project", "search_talent",
              "get_talent_profile", "get_project_options", "list_packages", "get_project_messages",
              "list_deliverables", "get_cancellation_preview", "list_boards"}

SUPPORT_TOPICS = ["account", "payment", "notifications", "uploads", "deliverables", "project", "app", "other"]

SUPPORT_SCHEMAS: list[dict] = [
    {
        "name": "diagnose_account_issue",
        "description": "[read] Prototype support diagnosis: reads the client's real account records for a "
                       "topic and returns facts, fixes and the app's help steps.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": SUPPORT_TOPICS},
                "project_id": {"type": "string", "description": "Optional project id, e.g. prj_1006"},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_support_tickets",
        "description": "[read] The client's support tickets and their status.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "create_support_ticket",
        "description": "[stub write] Queue a support ticket in this prototype after the client agrees. "
                       "It does not reach a real OPAH support system.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "topic": {"type": "string", "enum": SUPPORT_TOPICS},
                "details": {"type": "string"},
            },
            "required": ["subject", "topic", "details"],
            "additionalProperties": False,
        },
    },
    {
        "name": "restore_notifications",
        "description": "[stub write] Notification settings are not connected in this prototype; this "
                       "reports that honestly instead of changing anything.",
        "parameters": {
            "type": "object",
            "properties": {"types": {"type": "array", "items": {"type": "string"}}},
            "additionalProperties": False,
        },
    },
]

SUPPORT_TOOL_NAMES = {schema["name"] for schema in SUPPORT_SCHEMAS}
FORBIDDEN_NAMES = {"approve_proposal", "reject_proposal", "charge", "refund", "send_message",
                   "submit_review", "cancel_project", "reset", "snapshot"}


@dataclass
class ToolResult:
    name: str
    arguments: dict
    result: dict
    ok: bool
    error_code: str | None = None
    error_message: str | None = None

    def as_model_payload(self) -> str:
        import json

        return json.dumps(self.result, default=str)[:12000]

    def summary(self) -> dict:
        return {"name": self.name, "ok": self.ok, "error": self.error_code,
                "arguments": self.arguments, "result": self.result}


def _check_arguments(schema: dict, arguments: dict) -> str | None:
    params = schema.get("parameters", {}) or {}
    required = params.get("required", []) or []
    props = params.get("properties", {}) or {}
    for key in required:
        if key not in arguments or arguments[key] in (None, ""):
            return f"'{key}' is required for {schema['name']}."
    for key, value in arguments.items():
        spec = props.get(key)
        if spec is None:
            if params.get("additionalProperties") is False:
                return f"'{key}' is not an argument of {schema['name']}."
            continue
        kind = spec.get("type")
        if kind == "string" and not isinstance(value, str):
            return f"'{key}' must be text."
        if kind == "number" and not isinstance(value, (int, float)):
            return f"'{key}' must be a number."
        if kind == "integer" and not isinstance(value, int):
            return f"'{key}' must be a whole number."
        if kind == "array" and not isinstance(value, list):
            return f"'{key}' must be a list."
        if kind == "object" and not isinstance(value, dict):
            return f"'{key}' must be an object."
        if spec.get("enum") and value not in spec["enum"]:
            return f"'{key}' must be one of {', '.join(spec['enum'])}."
    return None


class ToolExecutor:
    def __init__(self, session: Session, project_id: str | None = None) -> None:
        self.session = session
        self.project_id = project_id
        self.mock = get_mock()
        self.records: list[ToolResult] = []
        self._schemas: list[dict] | None = None
        self._by_name: dict[str, dict] = {}
        self._wm_lock = threading.Lock()

    # ------------------------------------------------------------------ schemas
    def schemas(self) -> list[dict]:
        """Built once per turn: schema generation ran on every tool lookup before."""
        if self._schemas is None:
            self._schemas = self._build_schemas()
            self._by_name = {schema["name"]: schema for schema in self._schemas}
        return self._schemas

    def _build_schemas(self) -> list[dict]:
        if self.session.is_talent:
            return []
        allowed = set()
        for name, spec in kit.TOOLS.items():
            if name in FORBIDDEN_NAMES:
                continue
            if spec["access"] == kit.CLIENT and not self.session.is_client:
                continue
            if spec["access"] == kit.ANYONE:
                if self.session.is_anonymous and name not in ("search_talent", "get_project_options", "list_packages"):
                    continue
            allowed.add(name)
        schemas = [s for s in kit.tool_schemas() if s["name"] in allowed]
        if self.session.is_client:
            schemas.extend(SUPPORT_SCHEMAS)
        return schemas

    def _schema(self, name: str) -> dict | None:
        self.schemas()
        return self._by_name.get(name)

    # ----------------------------------------------------------------- execute
    def execute(self, name: str, arguments: dict | None) -> ToolResult:
        arguments = dict(arguments or {})
        if name in FORBIDDEN_NAMES:
            return self._record(name, arguments, {
                "error": "forbidden",
                "message": "That action is not available to the assistant. The client approves it themselves.",
            })
        schema = self._schema(name)
        if schema is None:
            return self._record(name, arguments, {
                "error": "forbidden",
                "message": "That tool isn't available for this viewer.",
            })
        if "__invalid__" in arguments:
            return self._record(name, {"raw": arguments["__invalid__"]}, {
                "error": "invalid_fields",
                "message": "Those tool arguments were not valid JSON. Call the tool again with proper arguments.",
            })
        problem = _check_arguments(schema, arguments)
        if problem:
            return self._record(name, arguments, {"error": "invalid_fields", "message": problem})

        if name in SUPPORT_TOOL_NAMES:
            result = self._support(name, arguments)
            return self._record(name, arguments, result)

        result = self.mock.call(name, arguments, user=self.session.mock_user)
        if isinstance(result, dict) and "error" not in result:
            self._remember(name, arguments, result)
        return self._record(name, arguments, result)

    def _record(self, name: str, arguments: dict, result: dict) -> ToolResult:
        ok = not (isinstance(result, dict) and result.get("error"))
        record = ToolResult(
            name=name,
            arguments=arguments,
            result=result if isinstance(result, dict) else {"value": result},
            ok=ok,
            error_code=result.get("error") if isinstance(result, dict) else None,
            error_message=result.get("message") if isinstance(result, dict) else None,
        )
        self.records.append(record)
        return record

    # -------------------------------------------------------- working memory
    def _scope(self) -> str | None:
        return self.project_id if self.session.is_client else None

    def _remember(self, name: str, arguments: dict, result: dict) -> None:
        if not self.session.is_client:
            return
        with self._wm_lock:
            self._remember_unlocked(name, arguments, result)

    def _remember_unlocked(self, name: str, arguments: dict, result: dict) -> None:
        scope = self._scope()
        if name == "search_talent":
            memory.wm_set(self.session.user_id, scope, "last_search_filters", result.get("applied") or {})
            ids = result.get("talent_ids") or []
            names = [t.get("name") for t in result.get("talents", [])]
            memory.wm_set(self.session.user_id, scope, "last_search", {
                "filters": result.get("applied") or {},
                "talent_ids": ids,
                "names": names,
                "count": result.get("count"),
                "relaxed": result.get("relaxed") or [],
            })
        elif name == "get_talent_profile":
            memory.wm_set(self.session.user_id, scope, "last_profile",
                          {"id": result.get("id"), "name": result.get("name"), "role": result.get("role")})
        elif name == "get_project":
            if result.get("id"):
                memory.wm_set(self.session.user_id, scope, "last_project_view",
                              {"id": result["id"], "name": result.get("name")})
        elif name == "get_project_options":
            memory.wm_set(self.session.user_id, scope, "options_seen", True)

    # --------------------------------------------------------------- support
    def _support(self, name: str, arguments: dict) -> dict:
        if name == "list_support_tickets":
            kit_tickets = self.mock.list_tickets(self.session.user_id)
            local = memory.local_support_tickets(self.session.user_id)
            tickets = [{"id": t["id"], "subject": t["subject"], "category": t["category"],
                        "status": t["status"], "status_label": t.get("status_label"),
                        "created_at": t["created_at"], "source": "opah_mock"}
                       for t in kit_tickets]
            tickets += [{"id": t["id"], "subject": t["subject"], "category": t["category"],
                         "status": "queued in prototype", "created_at": t["created_at"],
                         "source": "prototype_stub"} for t in local]
            return {"tickets": tickets, "count": len(tickets),
                    "note": "Prototype tickets are queued locally and do not reach OPAH support."}

        if name == "create_support_ticket":
            subject = str(arguments.get("subject") or "").strip()
            topic = str(arguments.get("topic") or "other")
            details = str(arguments.get("details") or "").strip()
            if not subject or not details:
                return {"error": "invalid_fields", "message": "A ticket needs a subject and details."}
            diagnosis = self._diagnose(topic, arguments.get("project_id"))
            ticket = self.mock.add_ticket(self.session.user_id, subject, topic, details,
                                          str(diagnosis.get("facts", [])))
            memory.save_support_ticket(self.session.user_id, subject, topic, details,
                                       str(diagnosis.get("facts", [])))
            return {"ticket": {k: v for k, v in ticket.items() if k != "client_id"},
                    "stub": True,
                    "note": "Queued in this prototype only. No OPAH support system received it."}

        if name == "restore_notifications":
            return {
                "stub": True,
                "connected": False,
                "message": "Notification settings are not connected in this prototype, so nothing was "
                           "changed. The client can turn them back on in the app's Settings screen.",
            }

        topic = str(arguments.get("topic") or "other")
        return self._diagnose(topic, arguments.get("project_id"))

    def _diagnose(self, topic: str, project_id: Any = None) -> dict:
        """Real reads over the account, plus an honest note about stubs."""
        client_id = self.session.user_id
        client = self.mock.client(client_id) or {}
        facts: list[str] = []
        fixes: list[str] = []
        steps: list[str] = []
        stub = False

        if self.session.is_anonymous:
            return {
                "topic": topic,
                "facts": [],
                "fixes": [],
                "help_steps": [
                    "Sign in to your OPAH account to see your projects and tickets.",
                    "For a missing file, open the project's Deliverables tab and download again.",
                    "For a payment question, open Payments in your account to see the receipt.",
                ],
                "stub": False,
                "note": "Anonymous visitors get generic help steps only.",
            }

        projects = self.mock.projects_for(client_id)
        if topic == "payment":
            payments = []
            for project in projects:
                pay = self.mock.api.payments.get(project["id"])
                if pay:
                    payments.append(f"{project['name']}: ${pay['total']} {pay['status']} "
                                    f"(${pay['subtotal']} + ${pay['fee']} fee)")
            facts += payments or ["No payments are recorded on this account."]
            refunded = [p for p in payments if "refunded" in p]
            if refunded:
                facts.append("Refunds on record: " + "; ".join(refunded))
            fixes += ["Open Payments to download the receipt for any charge.",
                      "If a receipt shows the wrong company name, a support ticket is the fix."]
        elif topic == "deliverables":
            waiting = [f for f in self.mock.api.folders.values()
                       if any(p["id"] == f["project_id"] for p in projects)
                       and f["review_status"] == "pending_client"]
            for folder in waiting:
                project = self.mock.project(folder["project_id"]) or {}
                facts.append(f"{project.get('name')}: {folder['name']} has {len(folder['files'])} files, "
                             f"review window closes {folder['review_due_at']}")
            if not waiting:
                facts.append("No deliverable folders are waiting for review.")
            fixes += ["Open the project's Deliverables tab; previews are demo images in this prototype.",
                      "If a download fails, try the browser's own download rather than the preview."]
        elif topic == "notifications":
            stub = True
            facts.append("Notification preferences live in the app's Settings screen; they are not "
                         "exposed to this prototype.")
            fixes.append("Use Settings → Notifications in the app to unmute a type.")
        elif topic == "uploads":
            facts.append(f"Upload limit here: {settings.max_upload_files} files per message, "
                         f"{settings.max_image_bytes // (1024 * 1024)} MB images, "
                         f"{settings.max_pdf_bytes // (1024 * 1024)} MB PDFs, {settings.max_pdf_pages} pages.")
            fixes += ["Check the file is JPEG, PNG, WebP or PDF by its content, not just its name.",
                      "For a long PDF, send the first pages only."]
        elif topic == "project":
            target = self.mock.project(str(project_id)) if project_id else None
            if target and target.get("client_id") == client_id:
                facts.append(f"{target['name']} is {target['status']} and payment is {target['payment_status']}.")
                from .personas import missing_fields
                missing = missing_fields(target)
                if missing:
                    facts.append("Still missing: " + ", ".join(kit.FIELD_LABELS[m] for m in missing))
                pending = [b for b in self.mock.bookings_for(target["id"]) if b.get("pending_change")]
                for booking in pending:
                    change = booking["pending_change"]
                    facts.append(f"{booking['talent_name']} hasn't accepted the {change['kind']} change "
                                 f"{change['old']} → {change['new']} yet.")
            else:
                facts.append(f"This account has {len(projects)} projects; no project was specified.")
            fixes.append("Tell me the project name and I'll read its current state.")
        elif topic == "account":
            facts.append(f"Signed in as {client.get('first_name', 'a client')}"
                         f"{' at ' + client['company'] if client.get('company') else ''}, "
                         f"member since {client.get('member_since')}.")
            facts.append(f"{len(projects)} projects on the account.")
            fixes.append("I can't change account email, phone or password; those live in Account settings.")
        elif topic == "app":
            errors = memory.recent_app_errors(client_id)
            for error in errors:
                facts.append(f"{error['route']} returned {error['status'] or 'an error'}: {error['message']}")
            if not errors:
                facts.append("No failed requests have been reported from the app in this session.")
            fixes.append("Reload the page and repeat the action; if it fails again, file a ticket.")
        else:
            facts.append("I don't have a specific diagnosis for that; tell me what you were doing.")
            fixes.append("Describe the last screen you were on and what you expected to happen.")

        tickets = self.mock.list_tickets(client_id)
        open_tickets = [t for t in tickets if t.get("status") != "resolved"]
        if open_tickets:
            facts.append("Open tickets: " + "; ".join(
                f"{t['id']} {t['subject']} ({t.get('status_label') or t['status']})" for t in open_tickets))

        steps = [
            "Open the relevant tab in OPAH and retry the action once.",
            "If it still fails, file a ticket with the details above.",
        ]
        return {"topic": topic, "facts": facts, "fixes": fixes, "help_steps": steps,
                "stub": stub, "today": date.today().isoformat()}
