"""Tests for Z3-based adapter safety verification (tooling/verification/z3_adapter_safety.py)."""
from __future__ import annotations

import pytest
from tooling.verification.z3_adapter_safety import (
    verify_adapter_safety,
    VerificationResult,
    _extract_adapter_refs,
    _extract_declared_adapters,
    _HAS_Z3,
)

pytestmark = pytest.mark.skipif(not _HAS_Z3, reason="z3-solver not installed")


def _make_ir(labels: dict, meta: list | None = None) -> dict:
    return {"labels": labels, "meta": meta or [], "ir_version": "test"}


def _step(adapter: str, op: str = "R") -> dict:
    return {"op": op, "adapter": adapter}


class TestExtractAdapterRefs:
    def test_simple(self):
        ir = _make_ir({"L1": [_step("http.GET")]})
        refs = _extract_adapter_refs(ir)
        assert len(refs) == 1
        assert refs[0]["adapter"] == "http"
        assert refs[0]["label"] == "L1"

    def test_empty(self):
        assert _extract_adapter_refs(_make_ir({})) == []


class TestVerifyAdapterSafety:
    def test_empty_ir(self):
        result = verify_adapter_safety(_make_ir({}))
        assert result.all_passed

    def test_p1_allowlist_pass(self):
        ir = _make_ir({"L1": [_step("core.ADD"), _step("http.GET")]})
        result = verify_adapter_safety(ir, host_allowlist=frozenset({"core", "http"}))
        p1_violations = [v for v in result.violations if v.property_id == "P1"]
        assert p1_violations == []

    def test_p1_allowlist_violation(self):
        ir = _make_ir({"L1": [_step("core.ADD"), _step("solana.TRANSFER")]})
        result = verify_adapter_safety(ir, host_allowlist=frozenset({"core", "http"}))
        p1_violations = [v for v in result.violations if v.property_id == "P1"]
        assert len(p1_violations) == 1
        assert "solana" in p1_violations[0].adapter

    def test_p2_declared_pass(self):
        ir = _make_ir({"L1": [_step("core.ADD")]})
        result = verify_adapter_safety(ir)
        p2_violations = [v for v in result.violations if v.property_id == "P2"]
        assert p2_violations == []

    def test_p4_acyclic(self):
        ir = _make_ir({
            "L1": [{"op": "CALL", "target": "L2"}],
            "L2": [_step("core.ADD")],
        })
        result = verify_adapter_safety(ir)
        p4_violations = [v for v in result.violations if v.property_id == "P4"]
        assert p4_violations == []

    def test_p4_cycle_detected(self):
        ir = _make_ir({
            "L1": [{"op": "CALL", "target": "L2"}],
            "L2": [{"op": "CALL", "target": "L1"}],
        })
        result = verify_adapter_safety(ir)
        p4_violations = [v for v in result.violations if v.property_id == "P4"]
        assert len(p4_violations) == 1
        assert "Cycle" in p4_violations[0].message

    def test_multiple_labels(self):
        ir = _make_ir({
            "L1": [_step("core.ADD")],
            "L2": [_step("http.GET")],
            "L3": [_step("fs.write")],
        })
        result = verify_adapter_safety(ir, host_allowlist=frozenset({"core", "http", "fs"}))
        assert result.all_passed

    def test_no_allowlist_skips_p1(self):
        ir = _make_ir({"L1": [_step("exotic.UNKNOWN")]})
        result = verify_adapter_safety(ir, host_allowlist=None)
        assert "P1_adapter_allowlist" not in result.properties_checked

    def test_to_dict(self):
        result = verify_adapter_safety(_make_ir({}))
        d = result.to_dict()
        assert d["z3_available"] is True
        assert d["all_passed"] is True

    def test_summary(self):
        result = verify_adapter_safety(_make_ir({}))
        assert "verified" in result.summary().lower()
