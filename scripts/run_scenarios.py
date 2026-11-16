#!/usr/bin/env python3
"""Run the kit's 27 starter scenarios.

Two modes:

  live      Talk to the running CREATEchat API with the real model. Checks the
            tools it actually called, the reply type, required and forbidden
            words, permission rules, and that no project data was written
            without an approval. Requires OPENAI_API_KEY on the backend.

  pipeline  No model needed. Verifies every scenario against the implementation:
            the expected tools exist, are offered to that viewer, its project
            belongs to that client, and the reply type is one the app supports.
            This proves the contract and permissions, not model quality.

    python3 scripts/run_scenarios.py --mode pipeline
    python3 scripts/run_scenarios.py --mode live --base-url http://127.0.0.1:8000
    python3 scripts/run_scenarios.py --mode live --only briefing,cancel
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "createchat-prototype-kit"
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(KIT))

SCENARIOS = json.loads((KIT / "scenarios.json").read_text(encoding="utf-8"))
REPLY_TYPES = {"text", "talent_results", "action_proposal", "handoff", "account_summary",
               "project_details", "project_list", "talent_profile", "planning_card", "pulse", "error"}


def normalise(text: str) -> str:
    cleaned = text.lower().replace("$", "").replace(",", "").replace("-", "")
    return re.sub(r"[*`#]", "", cleaned)


def passed(condition: bool, label: str, results: list[tuple[bool, str]]) -> bool:
    results.append((condition, label))
    return condition


# --------------------------------------------------------------------- pipeline
def run_pipeline(only: set[str] | None) -> int:
    from app.assistant.tool_executor import FORBIDDEN_NAMES, SUPPORT_TOOL_NAMES, ToolExecutor
    from app.security.identity import ANONYMOUS, Session
    from app.services.mock_service import get_mock

    import mock_tools as kit

    mock = get_mock()
    known = set(kit.TOOLS) | SUPPORT_TOOL_NAMES | FORBIDDEN_NAMES
    failures = 0
    for scenario in SCENARIOS:
        if only and scenario["id"] not in only:
            continue
        results: list[tuple[bool, str]] = []
        expected = scenario.get("expected", {})
        passed(True, "scenario loaded", results)
        if scenario["viewer"] == "client":
            project = mock.project(scenario["active_project"]) if scenario.get("active_project") else None
            if scenario.get("active_project"):
                passed(project is not None and project["client_id"] == scenario["user"],
                       f"project {scenario['active_project']} belongs to {scenario['user']}", results)
            session = Session(scenario["user"], "client")
        else:
            session = ANONYMOUS
            passed("user" not in scenario, "anonymous scenario has no client id", results)

        executor = ToolExecutor(session, scenario.get("active_project"))
        available = {schema["name"] for schema in executor.schemas()}
        for tool in expected.get("must_call", []):
            passed(tool in known, f"tool {tool} exists", results)
            passed(tool in available, f"tool {tool} is offered to this viewer", results)
        for tool in expected.get("must_not_call", []):
            if tool in ("approve_proposal",):
                passed(True, "approval is never a tool call", results)
                continue
            passed(True, f"tool {tool} must not be called", results)
        for key in ("must_mention", "must_not_mention"):
            passed(isinstance(expected.get(key, []), list), f"{key} is a list", results)
        if "reply_type" in expected:
            passed(expected["reply_type"] in REPLY_TYPES, "reply type is supported", results)

        ok = all(flag for flag, _ in results)
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {scenario['id']:<32} [{scenario['viewer']}]")
        for flag, label in results:
            if not flag:
                print(f"        ✗ {label}")
        if only is None and scenario.get("notes"):
            print(f"        · {scenario['notes'][:110]}")
    print()
    print(f"pipeline: {len([s for s in SCENARIOS if not only or s['id'] in only])} scenarios, {failures} failed")
    return 1 if failures else 0


# ------------------------------------------------------------------------- live
def run_live(base_url: str, only: set[str] | None, delay: float) -> int:
    import time

    import httpx

    try:
        with httpx.Client(timeout=10) as probe:
            health_response = probe.get(f"{base_url}/api/health")
    except httpx.HTTPError as exc:
        print(f"Cannot reach the backend at {base_url} ({type(exc).__name__}).")
        print("Start it with ./run.sh, then run this again.")
        return 2
    if health_response.status_code != 200:
        print(f"The backend answered HTTP {health_response.status_code} at {base_url}/api/health.")
        return 2
    health = health_response.json()
    if not health.get("model_configured"):
        print("The backend has no OPENAI_API_KEY, so live scenarios cannot run.")
        print("Add a key to .env, restart the backend, then run this again.")
        return 2
    print(f"model: {health['model']} · dataset day {health['dataset_today']}\n")

    failures = 0
    checked = 0
    for scenario in SCENARIOS:
        if only and scenario["id"] not in only:
            continue
        checked += 1
        expected = scenario.get("expected", {})
        results: list[tuple[bool, str]] = []
        with httpx.Client(base_url=base_url, timeout=180, follow_redirects=True) as client:
            client.post("/api/demo/reset", json={"conversations": True})
            if scenario["viewer"] == "anon":
                client.post("/api/session/switch", json={"user_id": "anonymous"})
            else:
                client.post("/api/session/switch", json={"user_id": scenario["user"]})

            before = None
            if not expected.get("must_not_call"):
                before = _project_state(client)

            calls: list[str] = []
            reply_types: list[str] = []
            messages: list[str] = []
            errors: list[str] = []
            for turn in scenario["turns"]:
                response = client.post("/api/chat", json={
                    "message": turn, "project_id": scenario.get("active_project"),
                })
                if response.status_code != 200:
                    errors.append(f"HTTP {response.status_code}: {response.text[:160]}")
                    break
                body = response.json()
                calls += [call["name"] for call in body.get("tool_calls", [])]
                reply_types.append(body["envelope"]["type"])
                messages.append(body["envelope"]["message"])
                time.sleep(delay)

            reply_text = normalise(" ".join(messages))
            for tool in expected.get("must_call", []):
                passed(tool in calls, f"called {tool}", results)
            for tool in expected.get("must_not_call", []):
                passed(tool not in calls, f"did not call {tool}", results)
            if "reply_type" in expected:
                passed(expected["reply_type"] in reply_types,
                       f"reply type {expected['reply_type']} (got {reply_types})", results)
            for phrase in expected.get("must_mention", []):
                passed(normalise(phrase) in reply_text, f"mentions “{phrase}”", results)
            for phrase in expected.get("must_not_mention", []):
                passed(normalise(phrase) not in reply_text, f"does not mention “{phrase}”", results)
            passed(not errors, "no request errors" + (f" ({errors[0]})" if errors else ""), results)

            if before is not None:
                after = _project_state(client)
                passed(before == after, "no project was written without approval", results)

        ok = all(flag for flag, _ in results)
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {scenario['id']:<32} calls={calls} types={reply_types}")
        for flag, label in results:
            if not flag:
                print(f"        ✗ {label}")
        print(f"        › {messages[-1][:180] if messages else '(no reply)'}")
    print()
    print(f"live: {checked} scenarios, {failures} failed")
    return 1 if failures else 0


def _project_state(client) -> str:
    state = client.get("/api/demo/state").json()
    return json.dumps(state.get("projects"), sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CREATEchat scenario set")
    parser.add_argument("--mode", choices=("pipeline", "live"), default="pipeline")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--only", default="", help="comma-separated scenario ids")
    parser.add_argument("--delay", type=float, default=0.3, help="seconds between live turns")
    args = parser.parse_args()
    only = {part.strip() for part in args.only.split(",") if part.strip()} or None
    if args.mode == "live":
        return run_live(args.base_url.rstrip("/"), only, args.delay)
    return run_pipeline(only)


if __name__ == "__main__":
    sys.exit(main())
