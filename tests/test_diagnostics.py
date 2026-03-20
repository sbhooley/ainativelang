"""Tests for structured compiler diagnostics (compiler_diagnostics module + wiring)."""

from __future__ import annotations

import json

import pytest

from compiler_diagnostics import (
    CompilationDiagnosticError,
    CompilerContext,
    Diagnostic,
    error_strings_to_diagnostics,
)
from compiler_v2 import AICodeCompiler


def test_diagnostic_round_trip_dict() -> None:
    d = Diagnostic(
        lineno=2,
        col_offset=1,
        kind="strict_validation_failure",
        message="op 'X' requires at least 3 slots, got 1",
        span=(10, 20),
        label_id="L1",
        node_id="n2",
        contract_violation_reason=None,
        suggested_fix="Add missing slots",
        related_span=None,
    )
    back = Diagnostic.from_dict(d.to_dict())
    assert back == d


def test_error_strings_to_diagnostics_line_and_suggestion() -> None:
    errs = [
        "Line 3: op 'R' requires at least 2 slots, got 0 Suggestion: Check arity",
    ]
    diags = error_strings_to_diagnostics(errs)
    assert len(diags) == 1
    assert diags[0].lineno == 3
    assert "requires at least" in diags[0].message
    assert diags[0].suggested_fix == "Check arity"


def test_strict_compile_raises_structured_when_context() -> None:
    # Unknown module in strict mode always yields validation errors
    code = "S core web /api\nL1: R badmodule.op 1 2 ->x\n"
    ctx = CompilerContext()
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as ei:
        c.compile(code, emit_graph=True, context=ctx)
    exc = ei.value
    assert exc.diagnostics
    assert len(exc.diagnostics) >= 1


def test_phase2_native_diag_arity_min_slots_and_legacy_string() -> None:
    code = "S core\n"
    ctx = CompilerContext()
    ctx.reset_for_compile(code)
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as exc_info:
        c.compile(code, emit_graph=True, context=ctx)

    diags = exc_info.value.diagnostics
    assert len(diags) >= 1
    # Prefer native row (has real span) over string-derived duplicate after merge.
    arity_diags = [d for d in diags if "requires at least 2 slots" in d.message]
    assert arity_diags, "Arity diagnostic not found"
    d = next((x for x in arity_diags if x.span == (0, 1)), arity_diags[0])
    assert d.kind == "strict_validation_failure"
    assert "satisfy the contract" in (d.suggested_fix or "")
    assert d.lineno == 1
    assert d.col_offset == 1
    assert d.span == (0, 1)

    ir_no_ctx = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    original_msg = "Line 1: op 'S' requires at least 2 slots, got 1"
    assert any(original_msg in err for err in ir_no_ctx.get("errors", []))


def test_phase2_native_diag_unknown_module_and_legacy_string() -> None:
    code = "unknown.F x y\n"
    ctx = CompilerContext()
    ctx.reset_for_compile(code)
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as exc_info:
        c.compile(code, emit_graph=True, context=ctx)

    diags = exc_info.value.diagnostics
    original_msg = "Line 1: unknown module 'unknown' in 'unknown.F'"
    mod_diags = [d for d in diags if original_msg in d.message or d.message == original_msg]
    assert mod_diags, "Unknown-module diagnostic not found"
    d = next((x for x in mod_diags if x.span is not None), mod_diags[0])
    assert d.kind == "strict_validation_failure"
    assert d.lineno == 1
    assert d.col_offset == 1
    assert "supported module prefixes" in (d.suggested_fix or "").lower()

    ir_no_ctx = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert any(original_msg in err for err in ir_no_ctx.get("errors", []))


def test_non_strict_returns_structured_diagnostics_in_ir() -> None:
    code = "S core web /api\n"
    ctx = CompilerContext()
    c = AICodeCompiler(strict_mode=False)
    ir = c.compile(code, emit_graph=True, context=ctx)
    assert ir.get("errors") == []
    assert ir.get("structured_diagnostics") == []


def test_langserver_maps_structured_range() -> None:
    from langserver import _lsp_diagnostic_from_structured, _lsp_range_from_structured

    src = "line1\nline2\n"
    d = Diagnostic(
        lineno=2,
        col_offset=1,
        kind="strict_validation_failure",
        message="bad",
    )
    r = _lsp_range_from_structured(d, src)
    assert r.start.line == 1
    assert r.start.character == 0
    lsp = _lsp_diagnostic_from_structured(d, src)
    assert "strict_validation_failure" in lsp.message
    assert lsp.source == "AINL Compiler"


def test_validate_script_json_diagnostics_flag() -> None:
    from scripts.validate_ainl import compile_and_validate

    bad = "S core web /api\nL1: R badmodule.op 1 2 ->x\n"
    r = compile_and_validate(bad, strict=True, use_structured=True)
    assert not r["ok"]
    assert r.get("structured")
    payload = [d.to_dict() for d in r["diagnostics"]]
    json.dumps(payload)


def test_validate_ainl_strict_structured_without_json_flag() -> None:
    """CLI enables structured diagnostics for every --strict run (same as json-diagnostics path)."""
    from scripts.validate_ainl import compile_and_validate

    bad = "S core web /api\nL1: R badmodule.op 1 2 ->x\n"
    r = compile_and_validate(bad, strict=True, use_structured=True)
    assert not r["ok"] and r.get("structured")


def test_validate_ainl_diagnostic_plain_formatter() -> None:
    from scripts.validate_ainl import _format_structured_diagnostics_human

    src = "line1\nline2\nline3\n"
    d = Diagnostic(
        lineno=2,
        col_offset=1,
        kind="undeclared_reference",
        message="Targeted label 'x' does not exist",
        span=None,
        suggested_fix="Declare L1: or retarget.",
        contract_violation_reason="Missing label body.",
        related_span=(12, 14),
    )
    out = _format_structured_diagnostics_human([d], src, use_color=False)
    assert "2:1" in out
    assert "[undeclared_reference]" in out
    assert "suggestion:" in out
    assert "reason:" in out
    assert "related: line" in out


def test_validate_ainl_diagnostic_print_smoke() -> None:
    from io import StringIO

    from scripts.validate_ainl import _print_diagnostics_pretty

    buf = StringIO()
    d = Diagnostic(
        lineno=1,
        col_offset=1,
        kind="strict_validation_failure",
        message="op broken",
        span=(0, 1),
        suggested_fix="fix it",
    )
    _print_diagnostics_pretty([d], "X\n", file=buf, use_color=False)
    body = buf.getvalue()
    assert "1. 1:1" in body
    assert "op broken" in body
    assert "suggestion:" in body


def test_phase2_duplicate_label_strict_native_and_legacy() -> None:
    # Single duplicate pair: two L1: declarations (no endpoint noise).
    code = (
        "S core web /api\n"
        "L1: R db.F User * ->x J x\n"
        "L1: R db.F User * ->y J y\n"
    )
    ctx = CompilerContext()
    ctx.reset_for_compile(code)
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as ei:
        c.compile(code, emit_graph=True, context=ctx)
    dup = [d for d in ei.value.diagnostics if d.kind == "duplicate_label"]
    assert dup, "duplicate_label diagnostic expected"
    d = dup[0]
    assert d.kind == "duplicate_label"
    assert d.label_id == "1"
    assert "duplicate label declaration" in d.message
    assert "previously declared on line" in d.message
    assert d.suggested_fix
    assert "merge" in d.suggested_fix.lower() or "L2" in d.suggested_fix
    assert str(2) in d.suggested_fix  # first L1: is on line 2
    assert d.related_span is not None

    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert any("duplicate label declaration" in err for err in ir.get("errors", []))


def test_phase2_undeclared_endpoint_reference_span_and_legacy() -> None:
    code = (
        "S core web /api\n"
        "E /x G ->L41 ->d\n"
        "L40: R db.F User * ->x J x\n"
    )
    ctx = CompilerContext()
    ctx.reset_for_compile(code)
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as ei:
        c.compile(code, emit_graph=True, context=ctx)
    u = [d for d in ei.value.diagnostics if d.kind == "undeclared_reference" and "Endpoint" in d.message]
    assert u, "endpoint undeclared_reference expected"
    # Native rows (label_id + span) are appended after string-derived merge duplicates.
    native = next(x for x in u if x.label_id == "41")
    assert native.label_id == "41"
    assert native.span is not None
    assert native.suggested_fix
    assert "Did you mean" in native.suggested_fix
    assert native.related_span is not None

    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert any("label '41' does not exist" in err for err in ir.get("errors", []))


def test_phase2_undeclared_targeted_control_flow_v1_col_and_legacy() -> None:
    code = (
        "S core web /api\n"
        "E /x G ->L1 ->d\n"
        "L1: If 1 ->L42 R db.F User * ->x J x\n"
        "L41: R db.F User * ->y J y\n"
    )
    ctx = CompilerContext()
    ctx.reset_for_compile(code)
    c = AICodeCompiler(strict_mode=True)
    with pytest.raises(CompilationDiagnosticError) as ei:
        c.compile(code, emit_graph=True, context=ctx)
    u = [d for d in ei.value.diagnostics if d.kind == "undeclared_reference" and "Targeted label" in d.message]
    assert u, "targeted undeclared_reference expected"
    d = next(x for x in u if x.label_id == "42")
    assert d.col_offset == 1
    assert d.span is None
    assert d.suggested_fix and "Did you mean" in d.suggested_fix
    assert d.related_span is not None

    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert any("Targeted label '42'" in err for err in ir.get("errors", []))
