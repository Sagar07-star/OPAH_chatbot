#!/usr/bin/env python3
"""In-memory mock of the CREATEchat prototype tool contract.

Implements every read, staging and hand-off tool in the contractor brief over
the synthetic dataset in ./data, plus proposal approval. Standard library only.

    from mock_tools import MockOPAH
    api = MockOPAH()
    api.call("search_talent", {"role": "photographer", "location": "Miami"}, user="clt_001")
    p = api.call("update_project", {"project_id": "prj_1002", "changes": {"budget": 2500}}, user="clt_001")
    api.approve_proposal(p["proposal_id"], user="clt_001")

    python mock_tools.py --schemas > tool_schemas.json
    python mock_tools.py call get_account_summary '{}' --user clt_001

Identity is the `user` argument (a client id, or None for an anonymous
visitor). It is never read from tool arguments, the same rule as production.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

ROLES = ("Photographer", "Videographer", "AI Artist")
_ROLE_ALIASES = {
    "photographer": "Photographer", "photographers": "Photographer", "photo": "Photographer",
    "photog": "Photographer", "photography": "Photographer",
    "videographer": "Videographer", "videographers": "Videographer", "video": "Videographer",
    "videography": "Videographer", "filmmaker": "Videographer", "videoographer": "Videographer",
    "ai artist": "AI Artist", "ai": "AI Artist", "ai artists": "AI Artist",
}
_CITY_ALIASES = {"ft lauderdale": "Fort Lauderdale", "ftl": "Fort Lauderdale", "wpb": "West Palm Beach",
                 "south beach": "Miami Beach", "brickell": "Miami", "wynwood": "Miami"}

FIELD_LABELS = {
    "name": "Name", "description": "Description", "client_notes": "Notes for the creative",
    "point_of_contact": "Point of contact", "start_date": "Start date", "end_date": "End date",
    "scheduled_time": "Call time", "duration_hours": "Duration (hours)",
    "deliverables_due_date": "Deliverables due", "location": "Location", "role": "Role needed",
    "specialty": "Specialty", "budget": "Budget (USD)", "priority": "Priority",
    "project_type": "Project type", "budget_range": "Budget range", "deliverables": "Deliverables",
    "lighting_styles": "Lighting",
}
EDITABLE_FIELDS = set(FIELD_LABELS)
#: Fields that may still change once a project is paid.
PAID_EDITABLE_FIELDS = {"name", "description", "client_notes", "point_of_contact", "start_date",
                        "end_date", "scheduled_time", "duration_hours", "deliverables_due_date",
                        "location", "budget"}
#: A project needs all of these before a creative can be added or it can be paid for.
REQUIRED_FOR_BOOKING = ("name", "description", "start_date", "end_date", "scheduled_time",
                        "duration_hours", "location", "role", "budget")
PAID_STATUSES = ("dispatching", "escrow_held", "assigned", "initiated")
CLOSED_STATUSES = ("completed", "cancelled")
PRIORITIES = ("budget", "style", "availability", "experience", "location")

READ, STAGE, HANDOFF = "read", "stage", "handoff"
ANYONE, CLIENT = "anyone", "client"


class ToolError(Exception):
    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra

    def as_dict(self) -> dict:
        return {"error": self.code, "message": self.message, **self.extra}


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _miles(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return round(3958.8 * 2 * math.asin(math.sqrt(h)), 1)


class MockOPAH:
    def __init__(self, now: datetime | None = None):
        self.reset(now)

    # ------------------------------------------------------------------ state
    def reset(self, now: datetime | None = None) -> None:
        self.meta = _load("meta.json")
        self.today = date.fromisoformat(self.meta["dataset_today"])
        self.now = now or datetime.combine(self.today, datetime.min.time()).replace(hour=12)
        self.options = _load("project_options.json")["catalogs"]
        self.clients = {c["id"]: c for c in _load("clients.json")}
        self.talent = {t["id"]: t for t in _load("talent.json")}
        self.packages = {p["id"]: p for p in _load("packages.json")}
        self.projects = {p["id"]: p for p in _load("projects.json")}
        self.bookings = {b["id"]: b for b in _load("bookings.json")}
        self.folders = {f["id"]: f for f in _load("deliverables.json")}
        self.messages = _load("messages.json")
        self.documents = {d["id"]: d for d in _load("documents.json")}
        self.payments = {p["project_id"]: p for p in _load("payments.json")}
        self.proposals = {p["proposal_id"]: p for p in _load("proposals.json")}
        self.boards = {b["id"]: b for b in _load("boards.json")}
        self.tickets = _load("support_tickets.json")
        self._seq = 1000

    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq}"

    def snapshot(self) -> dict:
        """Everything, for debugging a conversation (not a model tool)."""
        return copy.deepcopy({
            "projects": list(self.projects.values()), "bookings": list(self.bookings.values()),
            "deliverables": list(self.folders.values()), "documents": list(self.documents.values()),
            "proposals": list(self.proposals.values()), "boards": list(self.boards.values()),
        })

    # ------------------------------------------------------------- dispatch
    def call(self, tool: str, args: dict | None = None, user: str | None = None) -> dict:
        spec = TOOLS.get(tool)
        if spec is None:
            return {"error": "unknown_tool", "message": f"There is no tool called {tool}."}
        args = dict(args or {})
        try:
            if spec["access"] == CLIENT:
                self._client(user)
            return getattr(self, "_t_" + tool)(user, **args)
        except ToolError as exc:
            return exc.as_dict()
        except TypeError as exc:
            return {"error": "invalid_fields", "message": f"Bad arguments for {tool}: {exc}"}

    def approve_proposal(self, proposal_id: str, user: str | None) -> dict:
        try:
            prop = self._proposal(proposal_id, user)
            if prop["status"] == "applied":
                raise ToolError("already_applied", "That change was already applied.")
            if prop["status"] == "rejected":
                raise ToolError("already_rejected", "That change was declined, so it can't be applied.")
            result = getattr(self, "_apply_" + prop["kind"])(prop, user)
            prop.update(status="applied", resolved_at=self.now.isoformat(), result=result)
            return {"proposal_id": proposal_id, "status": "applied", "result": result}
        except ToolError as exc:
            return exc.as_dict()

    def reject_proposal(self, proposal_id: str, user: str | None) -> dict:
        try:
            prop = self._proposal(proposal_id, user)
            if prop["status"] != "pending":
                raise ToolError("already_" + prop["status"], f"That change is already {prop['status']}.")
            prop.update(status="rejected", resolved_at=self.now.isoformat())
            return {"proposal_id": proposal_id, "status": "rejected"}
        except ToolError as exc:
            return exc.as_dict()

    # -------------------------------------------------------------- helpers
    def _client(self, user):
        if not user or user == "anonymous":
            raise ToolError("auth_required", "Please sign in to do that.")
        client = self.clients.get(user)
        if client is None:
            raise ToolError("auth_required", "That account isn't signed in.")
        return client

    def _project(self, user, project_id) -> dict:
        self._client(user)
        p = self.projects.get(str(project_id))
        if not p or p["client_id"] != user:
            # Someone else's project looks exactly like a missing one.
            raise ToolError("not_found", "I can't find that project on your account.")
        return p

    def _proposal(self, proposal_id, user) -> dict:
        self._client(user)
        prop = self.proposals.get(str(proposal_id))
        if not prop or prop["client_id"] != user:
            raise ToolError("not_found", "I can't find that proposal.")
        return prop

    def _bookings_for(self, project_id) -> list[dict]:
        return [b for b in self.bookings.values() if b["project_id"] == project_id]

    def _accepted(self, project_id):
        return next((b for b in self._bookings_for(project_id) if b["status"] == "accepted"), None)

    def _missing(self, p: dict) -> list[str]:
        return [f for f in REQUIRED_FOR_BOOKING if p.get(f) in (None, "", [])]

    def _busy_dates(self, talent_id) -> set[str]:
        busy = set(self.talent[talent_id]["booked_dates"])
        for b in self.bookings.values():
            if b["talent_id"] == talent_id and b["status"] == "accepted":
                p = self.projects[b["project_id"]]
                if p["status"] not in CLOSED_STATUSES and p.get("start_date"):
                    busy |= set(self._date_span(p))
        return busy

    def _date_span(self, p: dict) -> list[str]:
        start = date.fromisoformat(p["start_date"])
        end = date.fromisoformat(p.get("end_date") or p["start_date"])
        return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]

    def _city(self, text: str | None):
        if not text:
            return None
        t = text.strip().lower()
        t = _CITY_ALIASES.get(t, t)
        for name, coords in self.meta["cities"].items():
            city = name.split(",")[0].lower()
            if t.lower() == city or t.lower().startswith(city) or city.startswith(t.lower()):
                return name, coords
        return None

    def _public_talent(self, t: dict) -> dict:
        hidden = {"booked_dates", "account_ready", "portfolio_published"}
        out = {k: v for k, v in t.items() if k not in hidden}
        out["name"] = t["display_name"]
        return out

    def _summary(self, p: dict) -> dict:
        b = self._accepted(p["id"])
        return {"id": p["id"], "name": p["name"], "status": p["status"],
                "payment_status": p["payment_status"], "source": p["source"],
                "start_date": p.get("start_date"), "role": p.get("role"), "budget": p.get("budget"),
                "talent": b["talent_name"] if b else None}

    def _stage(self, user, kind, project_id, summary, changes, payload) -> dict:
        pid = self._next("prop")
        prop = {"proposal_id": pid, "kind": kind, "client_id": user, "project_id": project_id,
                "summary": summary, "changes": changes, "payload": payload, "status": "pending",
                "created_at": self.now.isoformat()}
        self.proposals[pid] = prop
        return {k: v for k, v in prop.items() if k not in ("client_id", "payload")}

    def _normalize(self, fields: dict, current: dict | None) -> dict:
        unknown = sorted(set(fields) - EDITABLE_FIELDS)
        if unknown:
            raise ToolError("invalid_fields", f"These fields can't be set: {', '.join(unknown)}.",
                            field_errors={f: "not an editable field" for f in unknown})
        out, errors = {}, {}
        for field, value in fields.items():
            try:
                out[field] = self._normalize_one(field, value)
            except ValueError as exc:
                errors[field] = str(exc)
        merged = {**(current or {}), **out}
        if merged.get("start_date") and merged.get("end_date") and merged["end_date"] < merged["start_date"]:
            errors["end_date"] = "must be on or after the start date"
        if "start_date" in out and out["start_date"] and out["start_date"] < self.today.isoformat():
            errors["start_date"] = "can't be in the past"
        if errors:
            raise ToolError("invalid_fields", "; ".join(f"{FIELD_LABELS[f]}: {m}" for f, m in errors.items()),
                            field_errors=errors)
        return out

    def _normalize_one(self, field, value):
        if field in ("start_date", "end_date", "deliverables_due_date"):
            try:
                return date.fromisoformat(str(value)).isoformat()
            except ValueError:
                raise ValueError("use a date like 2026-12-01")
        if field == "budget":
            try:
                amount = float(re.sub(r"[^0-9.]", "", str(value)))
            except ValueError:
                raise ValueError("must be a number of dollars")
            if amount <= 0:
                raise ValueError("must be more than zero")
            return int(amount) if amount.is_integer() else amount
        if field == "duration_hours":
            try:
                hours = int(value)
            except (TypeError, ValueError):
                raise ValueError("must be a whole number of hours")
            if not 1 <= hours <= 24:
                raise ValueError("must be between 1 and 24 hours")
            return hours
        if field == "scheduled_time":
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(value)):
                raise ValueError("use 24-hour time like 09:30")
            return str(value)
        if field == "role":
            role = _ROLE_ALIASES.get(str(value).strip().lower())
            if role is None:
                raise ValueError("must be Photographer, Videographer or AI Artist")
            return role
        if field == "priority":
            if value not in PRIORITIES:
                raise ValueError(f"must be one of {', '.join(PRIORITIES)}")
            return value
        if field in ("project_type", "budget_range"):
            codes = {o["value"] for o in self.options[field]["options"]}
            if value not in codes:
                raise ValueError("call get_project_options and use one of its codes")
            return value
        if field in ("deliverables", "lighting_styles"):
            codes = {o["value"] for o in self.options[field]["options"]}
            values = value if isinstance(value, list) else [value]
            bad = [v for v in values if v not in codes]
            if bad:
                raise ValueError(f"unknown codes {bad}; call get_project_options")
            return values
        if field == "location":
            if isinstance(value, dict):
                if not value.get("display"):
                    raise ValueError("needs a display address")
                return value
            text = str(value).strip()
            if not text:
                raise ValueError("can't be empty")
            return {"display": text}
        text = str(value).strip()
        if not text:
            raise ValueError("can't be empty")
        return text

    def _diff(self, current: dict, new: dict) -> list[dict]:
        return [{"field": f, "label": FIELD_LABELS[f], "old": current.get(f), "new": v}
                for f, v in new.items() if current.get(f) != v]

    def _hours_until_start(self, p: dict) -> float:
        start = datetime.fromisoformat(f"{p['start_date']}T{p.get('scheduled_time') or '09:00'}")
        return (start - self.now).total_seconds() / 3600

    # ------------------------------------------------------------ read tools
    def _t_get_account_summary(self, user):
        client = self._client(user)
        mine = [p for p in self.projects.values() if p["client_id"] == user]
        today = self.today.isoformat()
        upcoming = sorted(
            (self._summary(p) for p in mine
             if p["status"] in PAID_STATUSES + ("in_progress",) and (p.get("start_date") or "") >= today),
            key=lambda s: s["start_date"])
        attention = []
        for p in mine:
            for b in self._bookings_for(p["id"]):
                if b["status"] == "countered":
                    attention.append({"kind": "counter_offer", "project_id": p["id"], "project": p["name"],
                                      "booking_id": b["id"], "talent": b["talent_name"],
                                      "detail": f"Asks ${b['counter_rate']} instead of ${b['rate']}"})
                if b.get("pending_change"):
                    c = b["pending_change"]
                    attention.append({"kind": "change_awaiting_talent", "project_id": p["id"],
                                      "project": p["name"], "talent": b["talent_name"],
                                      "detail": f"{c['kind']} change {c['old']} to {c['new']} waits for the creative"})
            for f in self.folders.values():
                if f["project_id"] == p["id"] and f["review_status"] == "pending_client":
                    attention.append({"kind": "deliverables_to_review", "project_id": p["id"], "project": p["name"],
                                      "folder_id": f["id"], "detail": f"{f['name']}: {len(f['files'])} files, "
                                                                      f"auto-approves {f['review_due_at']}"})
            if p["status"] == "draft":
                missing = self._missing(p)
                if missing:
                    attention.append({"kind": "draft_incomplete", "project_id": p["id"], "project": p["name"],
                                      "detail": "Missing " + ", ".join(FIELD_LABELS[m] for m in missing)})
                elif self._accepted(p["id"]):
                    attention.append({"kind": "ready_to_pay", "project_id": p["id"], "project": p["name"],
                                      "detail": "Creative accepted; ready for checkout"})
            if p["status"] == "dispatching":
                attention.append({"kind": "finding_creative", "project_id": p["id"], "project": p["name"],
                                  "detail": "Offered to nearby creatives"})
        for prop in self.proposals.values():
            if prop["client_id"] == user and prop["status"] == "pending":
                attention.append({"kind": "proposal_pending", "proposal_id": prop["proposal_id"],
                                  "project_id": prop["project_id"], "detail": prop["summary"]})
        counts: dict[str, int] = {}
        for p in mine:
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        return {"client": {"id": client["id"], "first_name": client["first_name"], "company": client["company"]},
                "today": today, "upcoming_shoots": upcoming, "needs_attention": attention,
                "project_counts": counts, "open_support_tickets": sum(
                    1 for t in self.tickets if t["client_id"] == user and t["status"] != "resolved")}

    def _t_list_projects(self, user, status: str = ""):
        self._client(user)
        rows = [self._summary(p) for p in self.projects.values()
                if p["client_id"] == user and not p.get("archived") and (not status or p["status"] == status)]
        return {"count": len(rows), "projects": rows}

    def _t_get_project(self, user, project_id):
        p = self._project(user, project_id)
        out = copy.deepcopy(p)
        out["bookings"] = copy.deepcopy(self._bookings_for(p["id"]))
        out["deliverable_folders"] = [
            {k: v for k, v in f.items() if k != "files"} | {"file_count": len(f["files"])}
            for f in self.folders.values() if f["project_id"] == p["id"]]
        out["documents"] = [{k: v for k, v in d.items() if k != "content_md"}
                            for d in self.documents.values() if d["project_id"] == p["id"]]
        out["open_proposals"] = [{k: v for k, v in pr.items() if k not in ("client_id", "payload")}
                                 for pr in self.proposals.values()
                                 if pr["project_id"] == p["id"] and pr["status"] == "pending"]
        out["payment"] = self.payments.get(p["id"])
        out["missing_fields"] = self._missing(p) if p["status"] == "draft" else []
        out["editable_fields"] = ([] if p["status"] in CLOSED_STATUSES else
                                  sorted(EDITABLE_FIELDS if p["status"] == "draft" else PAID_EDITABLE_FIELDS))
        return out

    def _t_search_talent(self, user, role="", location="", specialty="", style="", budget_max=None,
                         date="", limit=5):
        blocked = set(self.clients[user]["blocked_talent_ids"]) if user in self.clients else set()
        want_role = _ROLE_ALIASES.get(role.strip().lower()) if role else None
        if role and not want_role:
            return {"count": 0, "talents": [], "applied": {}, "relaxed": [],
                    "role_notice": f"OPAH doesn't offer {role} yet. Try Photographer, Videographer or AI Artist."}
        city = self._city(location)
        applied = {"role": want_role, "location": city[0] if city else None,
                   "specialty": specialty or None, "style": style or None,
                   "budget_max": budget_max, "date": date or None}
        unrecognized = {"location": location} if location and not city else {}

        def run(radius, use_budget):
            found = []
            for t in self.talent.values():
                if t["id"] in blocked or (want_role and t["role"] != want_role):
                    continue
                if date and date in self._busy_dates(t["id"]):
                    continue
                reasons, score = [], 0.0
                distance = None
                if city:
                    distance = _miles(city[1], self.meta["cities"][t["city"]])
                    if distance > radius:
                        continue
                    score += max(0, 30 - distance) / 10
                    reasons.append(f"{distance:g} miles from {city[0].split(',')[0]}" if distance else
                                   f"Based in {city[0].split(',')[0]}")
                if budget_max:
                    if use_budget and t["day_rate"] > float(budget_max):
                        continue
                    if t["day_rate"] <= float(budget_max):
                        score += 2
                        reasons.append(f"Day rate ${t['day_rate']} fits your ${budget_max} budget")
                if specialty:
                    s = specialty.lower()
                    if t["specialty"].lower() == s:
                        score += 3
                        reasons.append(f"Specializes in {t['specialty']}")
                    elif s in (x.lower() for x in t["secondary_specialties"]):
                        score += 1.5
                        reasons.append(f"Also shoots {specialty}")
                if style:
                    hits = [x for x in t["styles"] if any(w in x for w in style.lower().split())]
                    if hits:
                        score += 2
                        reasons.append(f"Known for a {hits[0]} look")
                if date:
                    reasons.append(f"Free on {date}")
                score += (t["rating"] or 4.0) / 5
                found.append((score, t, distance, reasons))
            return found

        relaxed = []
        results = run(30, True)
        if len(results) < 3 and city:
            results, relaxed = run(60, True), ["widened the search to 60 miles"]
        if len(results) < 3 and budget_max:
            results = run(60 if city else 9999, False)
            relaxed.append("included creatives above your budget")
        results.sort(key=lambda r: (-r[0], r[1]["day_rate"]))
        limit = max(1, min(int(limit or 5), 10))
        talents = [{**{k: t[k] for k in ("id", "role", "specialty", "city", "day_rate", "rating",
                                         "experience_years", "styles")},
                    "name": t["display_name"], "distance_miles": distance,
                    "thumbnail": t["portfolio"][0]["url"],
                    "match": {"score": round(score, 2), "reasons": reasons}}
                   for score, t, distance, reasons in results[:limit]]
        return {"count": len(results), "returned": len(talents), "applied": applied,
                "relaxed": relaxed, "unrecognized": unrecognized, "talents": talents,
                "talent_ids": [t["id"] for t in talents]}

    def _t_get_talent_profile(self, user, talent_id):
        self._client(user)
        t = self.talent.get(str(talent_id))
        if not t or t["id"] in self.clients[user]["blocked_talent_ids"]:
            raise ToolError("not_found", "I can't find that creative.")
        out = self._public_talent(t)
        out["unavailable_dates"] = sorted(d for d in self._busy_dates(t["id"]) if d >= self.today.isoformat())
        return out

    def _t_get_project_options(self, user):
        return {"catalogs": self.options}

    def _t_list_packages(self, user, category=""):
        rows = [p for p in self.packages.values() if not category or p["category"].lower() == category.lower()]
        return {"count": len(rows), "packages": rows, "service_area": sorted(self.meta["cities"]),
                "assistance_fee_rate": self.meta["assistance_fee_rate"]}

    def _t_get_project_messages(self, user, project_id, limit=20):
        p = self._project(user, project_id)
        rows = [m for m in self.messages if m["project_id"] == p["id"]]
        return {"project_id": p["id"], "messages": rows[-int(limit):]}

    def _t_list_deliverables(self, user, project_id):
        p = self._project(user, project_id)
        return {"project_id": p["id"], "folders": [f for f in self.folders.values() if f["project_id"] == p["id"]]}

    def _t_get_cancellation_preview(self, user, project_id):
        p = self._project(user, project_id)
        if p["status"] in CLOSED_STATUSES:
            raise ToolError("non_editable", f"This project is {p['status']}, so it can't be cancelled.")
        if p["status"] in ("in_progress", "captured", "review"):
            raise ToolError("rule_blocked", "The shoot has started, so cancelling goes to the OPAH team for review.")
        pay = self.payments.get(p["id"])
        if p["status"] == "draft" or not pay:
            return {"project_id": p["id"], "tier": "unpaid", "refund_percent": None, "refund_amount": 0,
                    "message": "Nothing has been paid, so cancelling costs nothing."}
        hours = self._hours_until_start(p)
        if not self._accepted(p["id"]):
            tier, pct = "no_creative_yet", 100
        elif hours > 7 * 24:
            tier, pct = "early", 100
        elif hours > 3:
            tier, pct = "standard", 75
        elif hours > 1:
            tier, pct = "late", 0
        else:
            raise ToolError("rule_blocked", "Under an hour before the shoot, cancelling goes to the OPAH team for review.")
        return {"project_id": p["id"], "tier": tier, "refund_percent": pct,
                "hours_until_start": round(hours, 1), "paid_total": pay["total"],
                "refund_amount": round(pay["total"] * pct / 100)}

    def _t_list_boards(self, user):
        self._client(user)
        return {"boards": [b for b in self.boards.values() if b["client_id"] == user]}

    # -------------------------------------------------------- staging tools
    def _t_create_project(self, user, fields):
        self._client(user)
        if not isinstance(fields, dict) or not str(fields.get("name") or "").strip():
            raise ToolError("invalid_fields", "A new project needs at least a name.",
                            field_errors={"name": "required"})
        new = self._normalize(fields, None)
        changes = self._diff({}, new)
        return self._stage(user, "create_project", None, f"Create project {new['name']}", changes, new)

    def _t_update_project(self, user, project_id, changes):
        p = self._project(user, project_id)
        if not isinstance(changes, dict) or not changes:
            raise ToolError("invalid_fields", "Pass the fields to change.")
        if p["status"] in CLOSED_STATUSES:
            raise ToolError("non_editable", f"This project is {p['status']}, so it can't be edited anymore.")
        if p["status"] != "draft":
            locked = sorted(set(changes) - PAID_EDITABLE_FIELDS)
            if locked:
                raise ToolError("field_locked", ", ".join(FIELD_LABELS.get(f, f) for f in locked)
                                + f" can't be changed once the project is {p['status']}.")
        new = self._normalize(changes, p)
        diff = self._diff(p, new)
        if not diff:
            raise ToolError("no_changes", "Those values already match what's on the project.")
        n = len(diff)
        return self._stage(user, "update_project", p["id"],
                           f"Change {n} field{'s' if n > 1 else ''} on {p['name']}", diff, new)

    def _t_add_talent_to_project(self, user, project_id, talent_id):
        p = self._project(user, project_id)
        t = self.talent.get(str(talent_id))
        if t is None:
            raise ToolError("not_found", "I can't find that creative.")
        self._check_can_add(user, p, t)
        return self._stage(user, "add_talent_to_project", p["id"],
                           f"Invite {t['display_name']} to {p['name']}",
                           [{"field": "talent", "label": "Creative", "old": None,
                             "new": f"{t['display_name']} ({t['role']}, ${t['day_rate']}/day)"}],
                           {"talent_id": t["id"]})

    def _check_can_add(self, user, p, t):
        if p["status"] != "draft":
            raise ToolError("rule_blocked", "Creatives can only be added while the project is a draft.")
        missing = self._missing(p)
        if missing:
            raise ToolError("rule_blocked", "Fill in " + ", ".join(FIELD_LABELS[m] for m in missing)
                            + " before adding a creative.", missing_fields=missing)
        if t["id"] in self.clients[user]["blocked_talent_ids"]:
            raise ToolError("not_found", "I can't find that creative.")
        if p["role"] and t["role"] != p["role"]:
            raise ToolError("rule_blocked", f"This project needs a {p['role']}; {t['display_name']} is a {t['role']}.")
        if not t["account_ready"] or not t["portfolio_published"]:
            raise ToolError("rule_blocked", f"{t['display_name']} can't take bookings yet.")
        if self._accepted(p["id"]):
            raise ToolError("rule_blocked", "This project already has an accepted creative; a project books one.")
        if any(b["talent_id"] == t["id"] and b["status"] in ("added", "countered")
               for b in self._bookings_for(p["id"])):
            raise ToolError("no_changes", f"{t['display_name']} is already invited to this project.")
        clash = sorted(set(self._date_span(p)) & self._busy_dates(t["id"]))
        if clash:
            raise ToolError("rule_blocked", f"{t['display_name']} is booked on {', '.join(clash)}.",
                            conflict_dates=clash)

    def _t_respond_to_counter_offer(self, user, project_id, booking_id, decision):
        p = self._project(user, project_id)
        b = self.bookings.get(str(booking_id))
        if not b or b["project_id"] != p["id"]:
            raise ToolError("not_found", "I can't find that booking on this project.")
        if b["status"] != "countered":
            raise ToolError("rule_blocked", "There's no open counter-offer on that booking.")
        if decision not in ("accept", "deny"):
            raise ToolError("invalid_fields", "decision must be accept or deny.")
        verb = "Accept" if decision == "accept" else "Decline"
        return self._stage(user, "respond_to_counter_offer", p["id"],
                           f"{verb} {b['talent_name']}'s counter-offer",
                           [{"field": "rate", "label": "Rate (USD)", "old": b["rate"],
                             "new": b["counter_rate"] if decision == "accept" else b["rate"]}],
                           {"booking_id": b["id"], "decision": decision})

    def _t_review_deliverable(self, user, project_id, folder_id, decision, note=""):
        p = self._project(user, project_id)
        f = self.folders.get(str(folder_id))
        if not f or f["project_id"] != p["id"]:
            raise ToolError("not_found", "I can't find that folder on this project.")
        if f["review_status"] != "pending_client":
            raise ToolError("rule_blocked", f"That folder isn't waiting for review (it is {f['review_status']}).")
        if decision == "request_revision":
            if not (note or "").strip():
                raise ToolError("invalid_fields", "A revision request needs a note for the creative.")
            if f["revisions_used"] >= f["revisions_included"]:
                raise ToolError("rule_blocked", "All included revision rounds are used on this folder.")
            change = {"field": "review", "label": f["name"], "old": "Waiting for you",
                      "new": f"Revision requested: {note.strip()}"}
        elif decision == "approve":
            change = {"field": "review", "label": f["name"], "old": "Waiting for you", "new": "Approved"}
        else:
            raise ToolError("invalid_fields", "decision must be approve or request_revision.")
        return self._stage(user, "review_deliverable", p["id"], f"{change['new'].split(':')[0]}: {f['name']}",
                           [change], {"folder_id": f["id"], "decision": decision, "note": (note or "").strip()})

    def _t_share_document(self, user, project_id, document_id):
        p = self._project(user, project_id)
        d = self.documents.get(str(document_id))
        if not d or d["project_id"] != p["id"]:
            raise ToolError("not_found", "I can't find that document on this project.")
        if d["shared_with_talent"]:
            raise ToolError("no_changes", "That document is already shared.")
        b = self._accepted(p["id"])
        if not b:
            raise ToolError("rule_blocked", "There's no booked creative to share it with yet.")
        return self._stage(user, "share_document", p["id"], f"Share {d['title']} with {b['talent_name']}",
                           [{"field": "shared_with_talent", "label": d["title"], "old": "Private", "new": "Shared"}],
                           {"document_id": d["id"]})

    def _t_create_board(self, user, title, project_id=None, items=None):
        self._client(user)
        if not str(title or "").strip():
            raise ToolError("invalid_fields", "A board needs a title.")
        if project_id:
            self._project(user, project_id)
        items = [i if isinstance(i, dict) else {"url": str(i)} for i in (items or [])]
        return self._stage(user, "create_board", project_id, f"Create board {title.strip()}",
                           [{"field": "board", "label": "New board", "old": None,
                             "new": f"{title.strip()} ({len(items)} items)"}],
                           {"title": title.strip(), "items": items})

    # ------------------------------------------------------ apply (approve)
    def _apply_create_project(self, prop, user):
        pid = self._next("prj")
        p = {"id": pid, "client_id": user, "status": "draft", "payment_status": "unpaid", "source": "custom",
             "package_id": None, "board_ids": [], "created_at": self.today.isoformat(), "archived": False,
             **{f: None for f in FIELD_LABELS}, "deliverables": [], "lighting_styles": []}
        p.update(prop["payload"])
        self.projects[pid] = p
        prop["project_id"] = pid
        return {"project_id": pid}

    def _apply_update_project(self, prop, user):
        p = self._project(user, prop["project_id"])
        if p["status"] in CLOSED_STATUSES:
            raise ToolError("non_editable", f"This project is {p['status']} now, so the change wasn't applied.")
        before = {c["field"]: p.get(c["field"]) for c in prop["changes"]}
        p.update(prop["payload"])
        b = self._accepted(p["id"])
        if b and p["status"] != "draft" and any(f in prop["payload"] for f in ("start_date", "end_date", "budget")):
            kind = "budget" if "budget" in prop["payload"] else "date"
            field = "budget" if kind == "budget" else "start_date"
            b["pending_change"] = {"kind": kind, "old": before.get(field), "new": p[field], "awaiting": "talent"}
            return {"project_id": p["id"], "note": "The booked creative must accept the new " + kind + "."}
        return {"project_id": p["id"]}

    def _apply_add_talent_to_project(self, prop, user):
        p = self._project(user, prop["project_id"])
        t = self.talent[prop["payload"]["talent_id"]]
        self._check_can_add(user, p, t)   # the project may have changed since staging
        bid = self._next("bkg")
        self.bookings[bid] = {"id": bid, "project_id": p["id"], "talent_id": t["id"],
                              "talent_name": t["display_name"], "role": t["role"], "status": "added",
                              "rate": p["budget"], "counter_rate": None, "counter_message": None,
                              "pending_change": None, "responded_at": None}
        return {"booking_id": bid, "note": f"{t['display_name']} was invited and will accept, decline or counter."}

    def _apply_respond_to_counter_offer(self, prop, user):
        b = self.bookings[prop["payload"]["booking_id"]]
        if b["status"] != "countered":
            raise ToolError("rule_blocked", "That counter-offer is no longer open.")
        if prop["payload"]["decision"] == "accept":
            b.update(status="accepted", rate=b["counter_rate"], responded_at=self.now.isoformat())
        else:
            b.update(status="counter_denied", responded_at=self.now.isoformat())
        return {"booking_id": b["id"], "status": b["status"]}

    def _apply_review_deliverable(self, prop, user):
        f = self.folders[prop["payload"]["folder_id"]]
        if f["review_status"] != "pending_client":
            raise ToolError("rule_blocked", "That folder was already reviewed.")
        p = self.projects[f["project_id"]]
        if prop["payload"]["decision"] == "approve":
            f["review_status"] = "approved"
            if all(x["review_status"] == "approved" for x in self.folders.values() if x["project_id"] == p["id"]):
                p["status"] = "completed"
        else:
            f.update(review_status="revision_requested", revision_note=prop["payload"]["note"],
                     revisions_used=f["revisions_used"] + 1)
        return {"folder_id": f["id"], "review_status": f["review_status"], "project_status": p["status"]}

    def _apply_share_document(self, prop, user):
        d = self.documents[prop["payload"]["document_id"]]
        d["shared_with_talent"] = True
        return {"document_id": d["id"], "shared_with_talent": True}

    def _apply_create_board(self, prop, user):
        bid = self._next("brd")
        payload = prop["payload"]
        self.boards[bid] = {"id": bid, "client_id": user, "title": payload["title"],
                            "project_ids": [prop["project_id"]] if prop["project_id"] else [],
                            "items": [{"id": f"{bid}_i{k}", "type": "image", "note": None, **item}
                                      for k, item in enumerate(payload["items"], start=1)]}
        return {"board_id": bid}

    # ------------------------------------------------------- hand-off tools
    def _t_prepare_checkout(self, user, project_ids):
        if not project_ids:
            raise ToolError("invalid_fields", "Pass at least one project id.")
        lines, problems = [], []
        for pid in project_ids:
            p = self._project(user, pid)
            issues = []
            if p["status"] != "draft" or p["payment_status"] != "unpaid":
                issues.append("already paid or not a draft")
            missing = self._missing(p)
            if missing:
                issues.append("missing " + ", ".join(FIELD_LABELS[m] for m in missing))
            if not self._accepted(p["id"]):
                issues.append("no creative has accepted yet")
            if any(b.get("pending_change") for b in self._bookings_for(p["id"])):
                issues.append("a change is waiting for the creative")
            if issues:
                problems.append({"project_id": p["id"], "name": p["name"], "issues": issues})
            else:
                fee = round(p["budget"] * self.meta["assistance_fee_rate"])
                lines.append({"project_id": p["id"], "name": p["name"], "subtotal": p["budget"], "fee": fee})
        if problems:
            raise ToolError("rule_blocked", "Some projects aren't ready for checkout.", not_ready=problems)
        subtotal = sum(x["subtotal"] for x in lines)
        fee = sum(x["fee"] for x in lines)
        return {"handoff": {"screen": "checkout", "params": {"project_ids": list(project_ids)},
                            "summary": {"lines": lines, "subtotal": subtotal, "fee": fee,
                                        "total": subtotal + fee, "currency": "USD",
                                        "cancellation_terms": CANCELLATION_TERMS}}}

    def _t_prepare_package_booking(self, user, package_id, address, date, call_time, add_ons=None):
        self._client(user)
        pkg = self.packages.get(package_id)
        if not pkg:
            raise ToolError("not_found", "I can't find that package.")
        try:
            day = datetime.fromisoformat(f"{date}T{call_time}")
        except ValueError:
            raise ToolError("invalid_fields", "Use a date like 2026-12-01 and a time like 10:00.")
        if day - self.now < timedelta(hours=24):
            raise ToolError("rule_blocked", "Packages need at least 24 hours' notice.")
        if not self._city(str(address).split(",")[-2] if "," in str(address) else str(address)):
            raise ToolError("rule_blocked", "That address is outside the service area (South Florida).",
                            service_area=sorted(self.meta["cities"]))
        codes = {a["code"]: a for a in pkg["add_ons"]}
        bad = [c for c in (add_ons or []) if c not in codes]
        if bad:
            raise ToolError("invalid_fields", f"Unknown add-ons for this package: {', '.join(bad)}.")
        subtotal = pkg["price"] + sum(codes[c]["price"] for c in (add_ons or []))
        fee = round(subtotal * self.meta["assistance_fee_rate"])
        return {"handoff": {"screen": "package_checkout",
                            "params": {"package_id": package_id, "address": address, "date": date,
                                       "call_time": call_time, "add_ons": list(add_ons or [])},
                            "summary": {"package": pkg["title"], "subtotal": subtotal, "fee": fee,
                                        "total": subtotal + fee, "currency": "USD",
                                        "note": "The card is held, not charged, until a creative accepts."}}}

    def _t_prepare_cancellation(self, user, project_id):
        preview = self._t_get_cancellation_preview(user, project_id)
        return {"handoff": {"screen": "cancel_project", "params": {"project_id": project_id},
                            "summary": preview}}

    def _t_draft_message(self, user, project_id, text):
        p = self._project(user, project_id)
        b = self._accepted(p["id"])
        if not b:
            raise ToolError("rule_blocked", "There's no booked creative to message on this project yet.")
        if not str(text or "").strip():
            raise ToolError("invalid_fields", "The message is empty.")
        return {"handoff": {"screen": "project_messages", "params": {"project_id": p["id"]},
                            "summary": {"to": b["talent_name"], "prefill": text.strip(),
                                        "note": "Typed, not sent. The client sends it."}}}

    def _t_draft_review(self, user, project_id, rating, text):
        p = self._project(user, project_id)
        if p["status"] != "completed":
            raise ToolError("rule_blocked", "Reviews open once the project is completed.")
        if int(rating) not in range(1, 6):
            raise ToolError("invalid_fields", "rating must be 1 to 5.")
        return {"handoff": {"screen": "review_form", "params": {"project_id": p["id"]},
                            "summary": {"rating": int(rating), "prefill": str(text).strip()}}}


CANCELLATION_TERMS = ("More than 7 days before the shoot: full refund. 7 days to 3 hours: 75%. "
                      "3 hours to 1 hour: no refund. Under 1 hour or after the start: reviewed by OPAH.")


def _obj(props: dict, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


_S = {"type": "string"}
_PID = {"type": "string", "description": "Project id, e.g. prj_1002"}
_FIELDS = {"type": "object", "description": "Field name to new value. Fields: " + ", ".join(sorted(FIELD_LABELS))
           + ". Dates YYYY-MM-DD, call time HH:MM (24h), budget in USD, codes from get_project_options."}

TOOLS = {
    "get_account_summary": {"kind": READ, "access": CLIENT, "params": _obj({}),
                            "description": "Everything that needs the client's attention across all their projects."},
    "list_projects": {"kind": READ, "access": CLIENT, "params": _obj({"status": _S}),
                      "description": "The client's projects, optionally filtered by status."},
    "get_project": {"kind": READ, "access": CLIENT, "params": _obj({"project_id": _PID}, ["project_id"]),
                    "description": "One project with bookings, deliverable folders, documents and open proposals."},
    "search_talent": {"kind": READ, "access": ANYONE, "params": _obj({
        "role": {"type": "string", "description": "Photographer, Videographer or AI Artist (any wording)"},
        "location": {"type": "string", "description": "City or neighbourhood"},
        "specialty": _S, "style": _S, "budget_max": {"type": "number", "description": "Max day rate, USD"},
        "date": {"type": "string", "description": "YYYY-MM-DD; excludes creatives booked that day"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10}}),
        "description": "Find and rank creatives; each result explains why it matched."},
    "get_talent_profile": {"kind": READ, "access": CLIENT, "params": _obj({"talent_id": _S}, ["talent_id"]),
                           "description": "One creative's profile, portfolio and unavailable dates."},
    "get_project_options": {"kind": READ, "access": ANYONE, "params": _obj({}),
                            "description": "Allowed codes for project_type, budget_range, deliverables, lighting_styles."},
    "list_packages": {"kind": READ, "access": ANYONE, "params": _obj({"category": _S}),
                      "description": "Fixed-price packages, add-ons and prices."},
    "get_project_messages": {"kind": READ, "access": CLIENT,
                             "params": _obj({"project_id": _PID, "limit": {"type": "integer"}}, ["project_id"]),
                             "description": "The project's conversation between client and creative."},
    "list_deliverables": {"kind": READ, "access": CLIENT, "params": _obj({"project_id": _PID}, ["project_id"]),
                          "description": "Deliverable folders, files and review state."},
    "get_cancellation_preview": {"kind": READ, "access": CLIENT, "params": _obj({"project_id": _PID}, ["project_id"]),
                                 "description": "The refund the cancellation policy gives if cancelled now."},
    "list_boards": {"kind": READ, "access": CLIENT, "params": _obj({}),
                    "description": "The client's inspiration boards."},
    "create_project": {"kind": STAGE, "access": CLIENT, "params": _obj({"fields": _FIELDS}, ["fields"]),
                       "description": "Stage a new draft project. Applies only when the client approves."},
    "update_project": {"kind": STAGE, "access": CLIENT,
                       "params": _obj({"project_id": _PID, "changes": _FIELDS}, ["project_id", "changes"]),
                       "description": "Stage field changes, all fields from one message in one call."},
    "add_talent_to_project": {"kind": STAGE, "access": CLIENT,
                              "params": _obj({"project_id": _PID, "talent_id": _S}, ["project_id", "talent_id"]),
                              "description": "Stage inviting a creative. Checks every booking rule first."},
    "respond_to_counter_offer": {"kind": STAGE, "access": CLIENT, "params": _obj({
        "project_id": _PID, "booking_id": _S, "decision": {"type": "string", "enum": ["accept", "deny"]}},
        ["project_id", "booking_id", "decision"]), "description": "Stage the client's answer to a counter-offer."},
    "review_deliverable": {"kind": STAGE, "access": CLIENT, "params": _obj({
        "project_id": _PID, "folder_id": _S,
        "decision": {"type": "string", "enum": ["approve", "request_revision"]}, "note": _S},
        ["project_id", "folder_id", "decision"]), "description": "Stage approving a folder or requesting a revision."},
    "share_document": {"kind": STAGE, "access": CLIENT,
                       "params": _obj({"project_id": _PID, "document_id": _S}, ["project_id", "document_id"]),
                       "description": "Stage sharing a planning document with the booked creative."},
    "create_board": {"kind": STAGE, "access": CLIENT, "params": _obj({
        "title": _S, "project_id": _PID, "items": {"type": "array", "items": _S}}, ["title"]),
        "description": "Stage a new inspiration board, optionally linked to a project."},
    "prepare_checkout": {"kind": HANDOFF, "access": CLIENT, "params": _obj({
        "project_ids": {"type": "array", "items": _S}}, ["project_ids"]),
        "description": "Open checkout with a price summary. Never charges anything."},
    "prepare_package_booking": {"kind": HANDOFF, "access": CLIENT, "params": _obj({
        "package_id": _S, "address": _S, "date": _S, "call_time": _S, "add_ons": {"type": "array", "items": _S}},
        ["package_id", "address", "date", "call_time"]), "description": "Open package checkout, prefilled."},
    "prepare_cancellation": {"kind": HANDOFF, "access": CLIENT, "params": _obj({"project_id": _PID}, ["project_id"]),
                             "description": "Open the cancel screen with the refund shown."},
    "draft_message": {"kind": HANDOFF, "access": CLIENT,
                      "params": _obj({"project_id": _PID, "text": _S}, ["project_id", "text"]),
                      "description": "Open the project conversation with a message typed but not sent."},
    "draft_review": {"kind": HANDOFF, "access": CLIENT, "params": _obj({
        "project_id": _PID, "rating": {"type": "integer", "minimum": 1, "maximum": 5}, "text": _S},
        ["project_id", "rating", "text"]), "description": "Open the review form, prefilled."},
}


def tool_schemas() -> list[dict]:
    """The tools in OpenAI/Anthropic-style function definitions."""
    return [{"name": name, "description": f"[{spec['kind']}] {spec['description']}",
             "parameters": spec["params"]} for name, spec in TOOLS.items()]


def main() -> int:
    parser = argparse.ArgumentParser(description="CREATEchat mock tools")
    parser.add_argument("--schemas", action="store_true", help="print tool definitions as JSON")
    sub = parser.add_subparsers(dest="cmd")
    c = sub.add_parser("call")
    c.add_argument("tool")
    c.add_argument("args", nargs="?", default="{}")
    c.add_argument("--user", default=None)
    a = sub.add_parser("approve")
    a.add_argument("proposal_id")
    a.add_argument("--user", required=True)
    args = parser.parse_args()
    if args.schemas:
        print(json.dumps(tool_schemas(), indent=2))
        return 0
    api = MockOPAH()
    if args.cmd == "call":
        print(json.dumps(api.call(args.tool, json.loads(args.args), user=args.user), indent=2))
    elif args.cmd == "approve":
        print(json.dumps(api.approve_proposal(args.proposal_id, args.user), indent=2))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
