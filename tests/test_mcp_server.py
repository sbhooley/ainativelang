"""Tests for the AINL MCP server tool and resource functions.

These test the tool functions directly as Python callables so the MCP SDK
is not required at test time.  Transport-level integration (stdio round-trip)
is deferred to manual testing with the MCP Inspector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from scripts.ainl_mcp_server import (
    ainl_validate,
    ainl_compile,
    ainl_capabilities,
    ainl_security_report,
    ainl_run,
    ainl_fitness_report,
    ainl_ir_diff,
    ainl_ptc_signature_check,
    ainl_trace_export,
    ainl_ptc_run,
    _load_json,
    _merge_policy,
    _merge_limits,
)


VALID_CODE = "S app api /api\nL1:\nR core.ADD 2 3 ->sum\nJ sum"
INVALID_CODE = "S app api /api\nL1:\nR !!!invalid!!!"
NETWORK_CODE = "S app api /api\nL1:\nR http.Get \"https://example.com\" ->resp\nJ resp"


# ---------------------------------------------------------------------------
# ainl-validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_code_returns_ok(self):
        result = ainl_validate(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert result["errors"] == []

    def test_invalid_code_returns_errors(self):
        result = ainl_validate(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert len(result["errors"]) > 0

    def test_validate_returns_llm_native_diagnostics(self):
        result = ainl_validate(INVALID_CODE, strict=True)
        assert "diagnostics" in result
        for d in result["diagnostics"]:
            assert "llm_repair_hint" in d


# ---------------------------------------------------------------------------
# ainl-compile
# ---------------------------------------------------------------------------

class TestCompile:
    def test_compile_valid_returns_ir(self):
        result = ainl_compile(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert "ir" in result
        ir = result["ir"]
        assert "labels" in ir

    def test_compile_invalid_returns_errors(self):
        result = ainl_compile(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert "errors" in result

    def test_compile_nonstrict(self):
        result = ainl_compile(VALID_CODE, strict=False)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# ainl-capabilities
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_capabilities_shape(self):
        caps = ainl_capabilities()
        assert "schema_version" in caps
        assert "runtime_version" in caps
        assert "policy_support" in caps
        assert caps["policy_support"] is True
        adapters = caps["adapters"]
        assert isinstance(adapters, dict)
        assert "core" in adapters

    def test_capabilities_adapter_has_privilege_tier(self):
        caps = ainl_capabilities()
        for name, info in caps["adapters"].items():
            assert "privilege_tier" in info, f"{name} missing privilege_tier"


# ---------------------------------------------------------------------------
# ainl-security-report
# ---------------------------------------------------------------------------

class TestSecurityReport:
    def test_security_report_for_core_workflow(self):
        result = ainl_security_report(VALID_CODE)
        assert result["ok"] is True
        report = result["report"]
        assert "summary" in report
        assert "labels" in report
        tiers = report["summary"]["privilege_tiers"]
        assert "pure" in tiers

    def test_security_report_for_network_workflow(self):
        result = ainl_security_report(NETWORK_CODE)
        assert result["ok"] is True
        tiers = set(result["report"]["summary"]["privilege_tiers"])
        assert "network" in tiers

    def test_security_report_lenient_parsing(self):
        """Security report uses non-strict compilation, so only truly
        unparseable input would produce errors."""
        result = ainl_security_report(INVALID_CODE)
        assert result["ok"] is True
        assert "report" in result


# ---------------------------------------------------------------------------
# ainl-run
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_core_only_succeeds(self):
        result = ainl_run(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert "trace_id" in result
        assert "out" in result
        assert "runtime_version" in result

    def test_run_network_workflow_not_blocked_by_default_policy(self):
        """Default MCP grant matches runner: http is allowed at policy layer (may fail at runtime if adapter missing)."""
        result = ainl_run(NETWORK_CODE, strict=True)
        assert result.get("error") != "policy_violation"

    def test_run_invalid_code_returns_errors(self):
        result = ainl_run(INVALID_CODE)
        assert result["ok"] is False
        assert "errors" in result

    def test_run_caller_can_add_restrictions(self):
        result = ainl_run(
            VALID_CODE,
            policy={"forbidden_adapters": ["core"]},
        )
        assert result["ok"] is False
        assert result.get("error") == "policy_violation"

    def test_run_caller_cannot_widen_defaults(self, monkeypatch: pytest.MonkeyPatch):
        import scripts.ainl_mcp_server as mcp_mod
        from tooling.capability_grant import merge_grants

        tight = merge_grants(
            mcp_mod._MCP_SERVER_GRANT,
            {"forbidden_privilege_tiers": ["network"]},
        )
        monkeypatch.setattr(mcp_mod, "_MCP_SERVER_GRANT", tight)
        result = mcp_mod.ainl_run(
            NETWORK_CODE,
            policy={"forbidden_privilege_tiers": []},
        )
        assert result["ok"] is False
        assert result.get("error") == "policy_violation"


# ---------------------------------------------------------------------------
# ainl_fitness_report / ainl_ir_diff
# ---------------------------------------------------------------------------

class TestResearchTools:
    def test_fitness_report(self, tmp_path: Path):
        f = tmp_path / "ok.ainl"
        f.write_text(VALID_CODE, encoding="utf-8")
        result = ainl_fitness_report(str(f), runs=2, strict=True)
        assert "metrics" in result
        assert result["metrics"]["latency_ms"]["avg"] >= 0
        assert "adapter_calls" in result["metrics"]
        assert result["metrics"]["memory_deltas"]["tracked"] is True
        assert "operation_histogram" in result["metrics"]
        assert "fitness_score" in result["metrics"]
        assert 0.0 <= result["metrics"]["fitness_score"] <= 1.0
        assert "fitness_components" in result["metrics"]

    def test_ir_diff(self, tmp_path: Path):
        f1 = tmp_path / "a.ainl"
        f2 = tmp_path / "b.ainl"
        f1.write_text(VALID_CODE, encoding="utf-8")
        f2.write_text("S app api /api\nL1:\nR core.ADD 2 4 ->sum\nJ sum", encoding="utf-8")
        result = ainl_ir_diff(str(f1), str(f2), strict=True)
        assert result["ok"] is True
        assert "diff" in result
        assert isinstance(result["diff"]["changed_nodes"], list)

    def test_ptc_signature_check(self):
        code = "L1: R core.ADD 1 2 ->x # signature: {x :int}\n"
        result = ainl_ptc_signature_check(code, strict=True)
        assert result["ok"] is True
        assert result["count"] >= 1

    def test_trace_export(self, tmp_path: Path):
        src = tmp_path / "trace.jsonl"
        dst = tmp_path / "ptc.jsonl"
        src.write_text(
            json.dumps(
                {
                    "step_id": 1,
                    "label": "1",
                    "operation": "R",
                    "inputs": {"_private": "x", "node_id": "n1"},
                    "output": {"ok": True},
                    "outcome": "success",
                    "timestamp": "2026-03-26T00:00:00.000Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        out = ainl_trace_export(str(src), str(dst))
        assert out["ok"] is True
        assert dst.exists()

    def test_ptc_run_mock(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AINL_PTC_RUNNER_MOCK", "1")
        result = ainl_ptc_run("(+ 1 2)", signature="{value :string}", max_attempts=2)
        assert result["ok"] is True
        assert "result" in result

    def test_fitness_score_zero_when_reliability_zero(self, tmp_path: Path):
        # Uses db adapter so safe-profile (core-only) fitness runs reliably fail.
        failing = tmp_path / "failing.ainl"
        failing.write_text(
            "S app api /api\nL1:\nR db.F User * ->rows\nJ rows\n",
            encoding="utf-8",
        )
        result = ainl_fitness_report(str(failing), runs=3, strict=True)
        assert result["metrics"]["reliability_score"] == 0.0
        assert result["metrics"]["fitness_score"] == 0.0


# ---------------------------------------------------------------------------
# MCP resources
# ---------------------------------------------------------------------------

class TestResources:
    def test_adapter_manifest_resource(self):
        data = _load_json("adapter_manifest.json")
        assert "adapters" in data
        assert "core" in data["adapters"]

    def test_security_profiles_resource(self):
        data = _load_json("security_profiles.json")
        assert "profiles" in data
        assert "local_minimal" in data["profiles"]


# ---------------------------------------------------------------------------
# Policy / limits merge helpers
# ---------------------------------------------------------------------------

class TestMergeHelpers:
    def test_merge_policy_unions_restrictions(self):
        merged = _merge_policy({"forbidden_adapters": ["http"]})
        assert "http" in merged["forbidden_adapters"]
        assert not merged.get("forbidden_privilege_tiers")

    def test_merge_policy_none_preserves_defaults(self):
        merged = _merge_policy(None)
        assert not merged.get("forbidden_privilege_tiers")

    def test_merge_limits_takes_minimum(self):
        merged = _merge_limits({"max_steps": 100})
        assert merged["max_steps"] == 100

    def test_merge_limits_cannot_widen(self):
        # Caller tries to pass a value larger than the server default (500000);
        # _merge_limits takes the minimum, so the server ceiling wins.
        from scripts.ainl_mcp_server import _MCP_DEFAULT_LIMITS
        server_default = _MCP_DEFAULT_LIMITS["max_steps"]
        over_ceiling = server_default + 1_000_000
        merged = _merge_limits({"max_steps": over_ceiling})
        assert merged["max_steps"] == server_default
