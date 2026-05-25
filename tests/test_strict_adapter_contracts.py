"""Tests for adapter semantic contract validation (tooling/contract_semantics.py)."""
from __future__ import annotations

import pytest

from tooling.contract_semantics import (
    ContractDiagnostic,
    validate_ir_contracts,
    format_diagnostics,
)


def _make_ir(labels: dict) -> dict:
    return {"labels": labels, "ir_version": "test"}


def _step(adapter: str, args: list | None = None) -> dict:
    return {"op": "R", "adapter": adapter, "args": args or []}


class TestValidateIrContracts:
    def test_empty_ir_no_diagnostics(self):
        assert validate_ir_contracts(_make_ir({})) == []

    def test_known_adapter_valid_verb(self):
        ir = _make_ir({"L1": [_step("http.GET", ["https://example.com"])]})
        diags = validate_ir_contracts(ir)
        assert diags == []

    def test_unknown_verb_warning(self):
        ir = _make_ir({"L1": [_step("http.FOOBAR", ["url"])]})
        diags = validate_ir_contracts(ir, strict=False)
        assert len(diags) == 1
        assert diags[0].severity == "warning"
        assert "FOOBAR" in diags[0].message

    def test_unknown_verb_error_strict(self):
        ir = _make_ir({"L1": [_step("http.FOOBAR", ["url"])]})
        diags = validate_ir_contracts(ir, strict=True)
        assert len(diags) == 1
        assert diags[0].severity == "error"

    def test_arity_too_few(self):
        ir = _make_ir({"L1": [_step("http.GET", [])]})
        diags = validate_ir_contracts(ir, strict=True)
        assert any("at least" in d.message for d in diags)

    def test_arity_too_many(self):
        ir = _make_ir({"L1": [_step("http.GET", ["u", "h", "t", "extra"])]})
        diags = validate_ir_contracts(ir, strict=True)
        assert any("at most" in d.message for d in diags)

    def test_unknown_adapter_no_diagnostics(self):
        ir = _make_ir({"L1": [_step("exotic.DO_THING", ["arg"])]})
        diags = validate_ir_contracts(ir, strict=True)
        assert diags == []

    def test_queue_put_valid(self):
        ir = _make_ir({"L1": [_step("queue.Put", ["channel", "payload"])]})
        diags = validate_ir_contracts(ir)
        assert diags == []

    def test_wasm_call_valid(self):
        ir = _make_ir({"L1": [_step("wasm.CALL", ["metrics.add", "10", "20"])]})
        diags = validate_ir_contracts(ir)
        assert diags == []

    def test_cache_get_valid(self):
        ir = _make_ir({"L1": [_step("cache.get", ["mykey"])]})
        diags = validate_ir_contracts(ir)
        assert diags == []

    def test_multiple_labels(self):
        ir = _make_ir({
            "L1": [_step("http.GET", ["https://a.com"])],
            "L2": [_step("http.NOPE")],
        })
        diags = validate_ir_contracts(ir, strict=True)
        assert len(diags) == 1
        assert diags[0].label == "L2"

    def test_non_request_ops_ignored(self):
        ir = _make_ir({"L1": [
            {"op": "Set", "var": "x", "value": 1},
            {"op": "J", "var": "x"},
        ]})
        assert validate_ir_contracts(ir) == []


class TestFormatDiagnostics:
    def test_empty(self):
        result = format_diagnostics([])
        assert "verified" in result

    def test_with_issues(self):
        diags = [ContractDiagnostic("http", "FOOBAR", "L1", "error", "bad verb", "use GET")]
        result = format_diagnostics(diags)
        assert "ERROR" in result
        assert "bad verb" in result


class TestContractDiagnostic:
    def test_to_dict(self):
        d = ContractDiagnostic("http", "GET", "L1", "warning", "msg", "fix")
        out = d.to_dict()
        assert out["adapter"] == "http"
        assert out["suggested_fix"] == "fix"

    def test_to_dict_no_fix(self):
        d = ContractDiagnostic("http", "GET", "L1", "warning", "msg")
        out = d.to_dict()
        assert "suggested_fix" not in out
