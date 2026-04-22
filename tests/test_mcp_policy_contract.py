"""Cross-runtime conformance: Python tooling contract JSON matches documented shape."""

from __future__ import annotations

import json
from pathlib import Path


def test_ainl_policy_contract_json() -> None:
    root = Path(__file__).resolve().parent.parent
    p = root / "tooling" / "ainl_policy_contract.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert "telemetry_field_names" in data
    telem = data["telemetry_field_names"]
    assert telem["capability_profile_state"] == "capability_profile_state"
    assert telem["freshness_state_at_decision"] == "freshness_state_at_decision"
    assert telem["impact_checked_before_write"] == "impact_checked_before_write"
    chain = data["golden_recommended_next_tools_chain"]
    assert chain == ["ainl_validate", "ainl_compile", "ainl_ir_diff", "ainl_run"]
    assert set(data["context_freshness"]) == {"fresh", "stale", "unknown"}


def test_contract_fixture_alignment_with_armaraos_if_present() -> None:
    """When this repo is checked out next to armaraos, golden steps match ainl-contracts fixture."""
    root = Path(__file__).resolve().parent.parent
    fixture = (
        root.parent / "armaraos" / "crates" / "ainl-contracts" / "tests" / "fixtures" / "contract_v1.json"
    )
    if not fixture.is_file():
        return
    policy = json.loads((root / "tooling" / "ainl_policy_contract.json").read_text(encoding="utf-8"))
    rust = json.loads(fixture.read_text(encoding="utf-8"))
    golden = policy["golden_recommended_next_tools_chain"]
    steps = [s["tool"] for s in rust["RecommendedNextTools"]["steps"]]
    assert steps == golden, "Python policy contract chain must match ainl-contracts fixture tool order"
