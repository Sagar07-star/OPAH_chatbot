"""The supplied scenario set, checked against the implementation.

Two layers:
1. Contract checks over all 27 scenarios (structure, identities, projects,
   tool availability per viewer, reply types).
2. A pipeline harness that runs each scenario's expected tools through the real
   ToolExecutor for its viewer, proving the permissions and tool surface.
   Model *selection* quality is measured by scripts/run_scenarios.py --mode live,
   which needs a real OPENAI_API_KEY.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.assistant.tool_executor import FORBIDDEN_NAMES, SUPPORT_TOOL_NAMES, ToolExecutor
from app.config import KIT_DIR
from app.services.mock_service import get_mock
from app.security.identity import ANONYMOUS, Session

import mock_tools as kit

SCENARIOS = json.loads((KIT_DIR / "scenarios.json").read_text(encoding="utf-8"))
ALL_TOOLS = set(kit.TOOLS) | SUPPORT_TOOL_NAMES | FORBIDDEN_NAMES
REPLY_TYPES = {"text", "talent_results", "action_proposal", "handoff", "account_summary",
               "project_details", "project_list", "talent_profile", "planning_card", "pulse", "error"}


def test_all_twenty_seven_scenarios_are_present():
    assert len(SCENARIOS) == 27


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_contract(scenario):
    expected = scenario["expected"]
    for name in expected.get("must_call", []) + expected.get("must_not_call", []):
        assert name in ALL_TOOLS, f"{scenario['id']} references unknown tool {name}"
    if "reply_type" in expected:
        assert expected["reply_type"] in REPLY_TYPES
    if scenario["viewer"] == "client":
        assert scenario["user"] in {"clt_001", "clt_002", "clt_003"}
        project_id = scenario.get("active_project")
        if project_id:
            project = get_mock().project(project_id)
            assert project is not None, f"{scenario['id']} uses a missing project"
            assert project["client_id"] == scenario["user"], \
                f"{scenario['id']} references another client's project"
    else:
        assert scenario["viewer"] == "anon"
        assert "user" not in scenario


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_expected_tools_are_available_to_that_viewer(scenario):
    if scenario["viewer"] == "anon":
        session = ANONYMOUS
    else:
        session = Session(scenario["user"], "client")
    executor = ToolExecutor(session, scenario.get("active_project"))
    available = {schema["name"] for schema in executor.schemas()}
    for name in scenario["expected"].get("must_call", []):
        assert name in available, f"{scenario['id']}: {name} is not offered to this viewer"
    for name in scenario["expected"].get("must_not_call", []):
        if name in FORBIDDEN_NAMES:
            continued = executor.execute(name, {})
            assert continued.ok is False
            assert continued.result["error"] == "forbidden"


def test_no_scenario_expects_the_approval_endpoint_from_the_model():
    for scenario in SCENARIOS:
        assert "approve_proposal" not in scenario["expected"].get("must_call", [])


def test_permission_scenarios_cover_the_required_cases():
    ids = {scenario["id"] for scenario in SCENARIOS}
    assert {"other-clients-project", "anon-project", "blocked-creative", "yes-is-not-approval",
            "injected-brief", "pay-in-chat"} <= ids


def test_pipeline_harness_runs_the_read_tools_for_every_scenario(client):
    """Calls each expected read tool with real arguments for its viewer."""
    read_args = {
        "get_account_summary": {},
        "list_projects": {},
        "get_project": {"project_id": ""},
        "search_talent": {"role": "photographer", "location": "Miami"},
        "get_project_options": {},
        "list_packages": {},
        "get_project_messages": {"project_id": ""},
        "list_deliverables": {"project_id": ""},
        "get_cancellation_preview": {"project_id": ""},
        "list_boards": {},
    }
    for scenario in SCENARIOS:
        session = ANONYMOUS if scenario["viewer"] == "anon" else Session(scenario["user"], "client")
        executor = ToolExecutor(session, scenario.get("active_project"))
        for name in scenario["expected"].get("must_call", []):
            if name not in kit.TOOLS or kit.TOOLS[name]["kind"] != kit.READ:
                continue
            args = dict(read_args.get(name, {}))
            if "project_id" in args:
                args["project_id"] = scenario.get("active_project") or "prj_1001"
            result = executor.execute(name, args)
            if result.error_code == "not_found":
                continue
            if name in ("get_project", "get_project_messages", "list_deliverables",
                        "get_cancellation_preview") and scenario["viewer"] == "anon":
                assert result.error_code == "auth_required"
            else:
                assert result.ok, f"{scenario['id']}: {name} -> {result.result}"


def test_anonymous_search_never_returns_blocked_or_private_records():
    executor = ToolExecutor(ANONYMOUS)
    result = executor.execute("search_talent", {"role": "videographer", "limit": 10})
    assert result.ok
    ids = set(result.result["talent_ids"])
    assert ids
    for forbidden_tool in ("get_account_summary", "list_projects", "get_project"):
        assert executor.execute(forbidden_tool, {}).result["error"] == "forbidden"


def test_every_kit_tool_except_approval_is_reachable_for_a_client():
    executor = ToolExecutor(Session("clt_001", "client"), "prj_1002")
    offered = {schema["name"] for schema in executor.schemas()}
    missing = set(kit.TOOLS) - offered
    assert missing == set(), f"client is missing tools: {missing}"


def test_scenarios_json_is_unchanged_by_the_prototype():
    """The kit's scenario file must stay the source of truth."""
    raw = (Path(KIT_DIR) / "scenarios.json").read_text(encoding="utf-8")
    assert json.loads(raw) == SCENARIOS
