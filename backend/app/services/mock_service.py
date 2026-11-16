"""Thin adapter over the supplied mock kit.

``createchat-prototype-kit/mock_tools.py`` is imported unchanged: it remains the
only place that knows the business rules and the JSON dataset. This module adds
a process-wide instance, locking, and read helpers the UI needs.
"""
from __future__ import annotations

import copy
import logging
import sys
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import KIT_DIR

logger = logging.getLogger("createchat.mock")

if str(KIT_DIR) not in sys.path:
    sys.path.insert(0, str(KIT_DIR))

import mock_tools as kit  # noqa: E402  (path set above)

ROLE_CLIENT = "client"
ROLE_TALENT = "talent"
ROLE_ANONYMOUS = "anonymous"

CLOSED_STATUSES = tuple(kit.CLOSED_STATUSES)
PAID_STATUSES = tuple(kit.PAID_STATUSES)
FIELD_LABELS: dict[str, str] = dict(kit.FIELD_LABELS)
REQUIRED_FOR_BOOKING = tuple(kit.REQUIRED_FOR_BOOKING)


class MockService:
    """Every request shares one dataset, like a single OPAH account server."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._api = kit.MockOPAH()
        self._repair_seeded_proposals()

    def _repair_seeded_proposals(self) -> None:
        """The kit's pre-seeded prop_0001 has `changes` but no `payload`.

        Staging tools save both, and approval reads `payload`; without this the
        unanswered proposal from the dataset would raise instead of applying.
        The change values are taken from the proposal's own diff — nothing new
        is invented.
        """
        for proposal in self._api.proposals.values():
            if proposal.get("payload"):
                continue
            proposal["payload"] = {change["field"]: change.get("new")
                                   for change in proposal.get("changes", [])}

    @property
    def api(self) -> Any:
        return self._api

    @property
    def today(self) -> str:
        return self._api.meta["dataset_today"]

    @property
    def now(self) -> datetime:
        return self._api.now

    @property
    def fee_rate(self) -> float:
        return float(self._api.meta["assistance_fee_rate"])

    def call(self, tool: str, args: dict | None = None, user: str | None = None) -> dict:
        with self._lock:
            return self._api.call(tool, args or {}, user=user)

    def approve(self, proposal_id: str, user: str) -> dict:
        with self._lock:
            try:
                return self._api.approve_proposal(proposal_id, user)
            except Exception as exc:  # the kit only maps ToolError; never leak a 500
                logger.exception("proposal approval failed: %s", exc)
                return {"error": "apply_failed",
                        "message": "That change couldn't be applied. Nothing was changed."}

    def reject(self, proposal_id: str, user: str) -> dict:
        with self._lock:
            try:
                return self._api.reject_proposal(proposal_id, user)
            except Exception as exc:
                logger.exception("proposal rejection failed: %s", exc)
                return {"error": "apply_failed",
                        "message": "That change couldn't be declined. Nothing was changed."}

    def proposal(self, proposal_id: str) -> dict | None:
        with self._lock:
            prop = self._api.proposals.get(proposal_id)
            return copy.deepcopy(prop) if prop else None

    def proposals_for(self, client_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._api.proposals.values() if p["client_id"] == client_id]

    def project(self, project_id: str) -> dict | None:
        with self._lock:
            project = self._api.projects.get(project_id)
            return copy.deepcopy(project) if project else None

    def projects_for(self, client_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._api.projects.values()
                    if p["client_id"] == client_id and not p.get("archived")]

    def bookings_for(self, project_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(b) for b in self._api.bookings.values() if b["project_id"] == project_id]

    def folders_for(self, project_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(f) for f in self._api.folders.values() if f["project_id"] == project_id]

    def documents_for(self, client_id: str) -> list[dict]:
        with self._lock:
            owned = {p["id"] for p in self._api.projects.values() if p["client_id"] == client_id}
            return [copy.deepcopy(d) for d in self._api.documents.values() if d["project_id"] in owned]

    def boards_for(self, client_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(b) for b in self._api.boards.values() if b["client_id"] == client_id]

    def talent(self, talent_id: str) -> dict | None:
        with self._lock:
            row = self._api.talent.get(talent_id)
            return copy.deepcopy(row) if row else None

    def public_talent(self, talent_id: str) -> dict | None:
        with self._lock:
            row = self._api.talent.get(talent_id)
            return self._api._public_talent(row) if row else None

    def client(self, client_id: str) -> dict | None:
        with self._lock:
            row = self._api.clients.get(client_id)
            return copy.deepcopy(row) if row else None

    def client_project_ids(self, client_id: str) -> set[str]:
        with self._lock:
            return {p["id"] for p in self._api.projects.values() if p["client_id"] == client_id}

    def add_document(self, client_id: str, project_id: str, doc_type: str, title: str,
                     content_md: str) -> dict:
        """Save a planning document the client chose to keep (client action, not a model tool)."""
        with self._lock:
            project = self._api.projects.get(project_id)
            if not project or project["client_id"] != client_id:
                raise PermissionError("not_found")
            existing = [d for d in self._api.documents.values()
                        if d["project_id"] == project_id and d["type"] == doc_type]
            version = max((d["version"] for d in existing), default=0) + 1
            doc_id = f"doc_{self._api._next('doc').split('_')[-1]}"
            record = {
                "id": doc_id,
                "project_id": project_id,
                "type": doc_type,
                "title": title,
                "version": version,
                "shared_with_talent": False,
                "content_md": content_md,
                "created_at": self._api.now.isoformat(),
                "source": "createchat",
            }
            self._api.documents[doc_id] = record
            return copy.deepcopy(record)

    def list_tickets(self, client_id: str) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(t) for t in self._api.tickets if t["client_id"] == client_id]

    def add_ticket(self, client_id: str, subject: str, category: str, body: str, diagnosis: str) -> dict:
        with self._lock:
            ticket_id = self._api._next("tkt")
            record = {
                "id": ticket_id,
                "client_id": client_id,
                "subject": subject,
                "category": category,
                "status": "open",
                "status_label": "With our team",
                "created_at": self._api.today.isoformat(),
                "updated_at": self._api.today.isoformat(),
                "body": body,
                "diagnosis": diagnosis,
                "stub": True,
            }
            self._api.tickets.append(record)
            return copy.deepcopy(record)

    def reset(self) -> None:
        with self._lock:
            self._api.reset()
            self._repair_seeded_proposals()

    def snapshot(self) -> dict:
        with self._lock:
            return self._api.snapshot()


_service: MockService | None = None
_service_lock = threading.Lock()


def get_mock() -> MockService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = MockService()
    return _service


@lru_cache(maxsize=1)
def client_directory() -> dict[str, dict]:
    """Public demo accounts, straight from the kit's clients.json."""
    mock = get_mock()
    out: dict[str, dict] = {}
    for client in mock.api.clients.values():
        out[client["id"]] = {
            "id": client["id"],
            "name": f"{client['first_name']} {client['last_name']}",
            "first_name": client["first_name"],
            "company": client["company"],
            "email": client["email"],
            "member_since": client["member_since"],
            "kind": "client",
        }
    return out


def demo_accounts() -> list[dict]:
    return list(client_directory().values())


def known_client(client_id: str) -> bool:
    return client_id in client_directory()


def known_talent(talent_id: str) -> bool:
    return get_mock().talent(talent_id) is not None


def skill_labels() -> dict[str, dict]:
    """Option catalogs for the UI, from project_options.json."""
    return copy.deepcopy(get_mock().api.options)


def dataset_path() -> Path:
    return KIT_DIR / "data"
