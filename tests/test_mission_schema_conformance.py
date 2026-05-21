"""JSON Schema conformance for mission substrate contracts (Phase 0)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLING = ROOT / "tooling"

pytest.importorskip("jsonschema")

from tooling.mission_mcp import (  # noqa: E402
    lint_handoff,
    validate_instance,
    validate_mission_dag,
    mission_plan,
)


def _fixture(name: str) -> dict:
    return json.loads((TOOLING / name).read_text(encoding="utf-8"))


@pytest.fixture
def sample_mission() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "mission_id": "mission-test-001",
        "objective_md": "Ship mission substrate Phase 0.",
        "state": "AwaitingInput",
        "milestone_ids": ["m1"],
        "mission_root": "/tmp/mission-root",
        "created_at": now,
        "capability_flags": {"mission_enabled": True, "coding_domain": True},
    }


@pytest.fixture
def sample_features() -> list:
    return [
        {
            "feature_id": "feat-a",
            "description": "First feature",
            "status": "pending",
            "milestone": "m1",
            "skill_name": "coding-agent",
            "touches_files": ["src/"],
            "preconditions": [],
            "expected_behavior": "A works",
            "verification_steps": ["pytest -q"],
            "fulfills": ["assert-a"],
        },
        {
            "feature_id": "feat-b",
            "description": "Second feature",
            "status": "pending",
            "milestone": "m1",
            "skill_name": "coding-agent",
            "touches_files": ["tests/"],
            "preconditions": ["feat-a"],
            "expected_behavior": "B works",
            "verification_steps": ["pytest -q"],
            "fulfills": ["assert-b"],
        },
    ]


@pytest.fixture
def sample_assertions() -> list:
    return [
        {
            "assertion_id": "assert-a",
            "description": "A passes",
            "verification_steps": ["pytest tests/test_a.py"],
            "state": "Pending",
            "milestone": "m1",
            "failed_count": 0,
        },
        {
            "assertion_id": "assert-b",
            "description": "B passes",
            "verification_steps": ["pytest tests/test_b.py"],
            "state": "Pending",
            "milestone": "m1",
            "failed_count": 0,
        },
    ]


class TestSchemaFilesExist:
    @pytest.mark.parametrize(
        "filename",
        [
            "mission.schema.json",
            "feature.schema.json",
            "assertion.schema.json",
            "handoff.schema.json",
            "progress_event.schema.json",
        ],
    )
    def test_schema_file_loads(self, filename: str) -> None:
        data = json.loads((TOOLING / filename).read_text(encoding="utf-8"))
        assert "$schema" in data
        assert data.get("title") or data.get("$id")


class TestValidateInstance:
    def test_valid_mission(self, sample_mission: dict) -> None:
        assert validate_instance("mission", sample_mission) == []

    def test_invalid_mission_state(self, sample_mission: dict) -> None:
        bad = dict(sample_mission)
        bad["state"] = "NotAState"
        errs = validate_instance("mission", bad)
        assert errs
        assert any("state" in e for e in errs)

    def test_valid_handoff(self) -> None:
        handoff = {
            "feature_id": "feat-a",
            "agent_id": "agent-1",
            "salient_summary": "Done",
            "what_was_implemented_md": "Implemented A",
            "what_was_left_undone_md": "",
            "verification": {"status": "passed"},
            "tests": [],
            "discovered_issues": [],
            "skill_feedback": [],
        }
        assert validate_instance("handoff", handoff) == []

    def test_progress_event_variant(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        event = {
            "event_type": "mission_accepted",
            "mission_id": "mission-test-001",
            "ts": now,
            "detail": {"objective_md": "Test", "milestone_ids": ["m1"]},
        }
        assert validate_instance("progress_event", event) == []


class TestMissionDagValidation:
    def test_valid_dag(self, sample_mission, sample_features, sample_assertions) -> None:
        out = validate_mission_dag(sample_mission, sample_features, sample_assertions)
        assert out["ok"] is True
        assert out["errors"] == []

    def test_cycle_detected(self, sample_mission, sample_features, sample_assertions) -> None:
        features = [dict(f) for f in sample_features]
        features[0]["preconditions"] = ["feat-b"]
        features[1]["preconditions"] = ["feat-a"]
        out = validate_mission_dag(sample_mission, features, sample_assertions)
        assert out["ok"] is False
        assert any("cycle" in e for e in out["errors"])

    def test_uncovered_assertion(self, sample_mission, sample_features, sample_assertions) -> None:
        features = [dict(sample_features[0])]
        features[0]["fulfills"] = []
        out = validate_mission_dag(sample_mission, features, sample_assertions)
        assert out["ok"] is False


class TestHandoffLint:
    def test_lint_ok(self, sample_features) -> None:
        handoff = {
            "feature_id": "feat-a",
            "agent_id": "agent-1",
            "salient_summary": "Summary",
            "what_was_implemented_md": "Implemented A",
            "what_was_left_undone_md": "",
            "verification": {"status": "passed"},
            "tests": [{"name": "t1", "status": "passed"}],
            "discovered_issues": [],
            "skill_feedback": [],
        }
        out = lint_handoff(handoff, features=sample_features)
        assert out["ok"] is True


class TestMissionPlan:
    def test_plan_validates(self) -> None:
        out = mission_plan("Add mission substrate schemas and MCP tools")
        assert out["ok"] is True
        assert out["mission"]["mission_id"]
        assert len(out["features"]) >= 2
        assert out["validation"]["ok"] is True


class TestMissionHostAdapterContracts:
    def test_adapter_contracts_include_mission_host_tools(self) -> None:
        from tooling.ainl_get_started import ADAPTER_CONTRACTS

        for key in (
            "mission_dispatch",
            "mission_handoff_record",
            "mission_assertion_check",
            "git_snapshot",
            "git_rollback",
            "ask_user",
        ):
            assert key in ADAPTER_CONTRACTS, f"missing ADAPTER_CONTRACTS[{key!r}]"
            assert ADAPTER_CONTRACTS[key].get("status") == "host_tool"
