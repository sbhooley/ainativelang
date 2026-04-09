"""Surgical compiler diagnostics: suggested_fix + stable kind on common agent mistakes."""

from __future__ import annotations

import pytest

from compiler_diagnostics import CompilationDiagnosticError, CompilerContext
from compiler_v2 import AICodeCompiler


def _find_kind(exc: CompilationDiagnosticError, kind: str):
    return [d for d in exc.diagnostics if d.kind == kind]


class TestSuggestedFixKinds:
    def test_unknown_adapter_verb_top_level(self):
        ctx = CompilerContext()
        code = "S app core noop\ncore.NotARealTopLevelVerb 1\n"
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "unknown_adapter_verb")
        assert hits, "expected unknown_adapter_verb diagnostic"
        assert hits[0].suggested_fix
        assert "ainl_capabilities" in hits[0].suggested_fix

    def test_label_scope_top_level(self):
        ctx = CompilerContext()
        # Set is label-scoped; R at top-level is stored under _anon and does not hit this check.
        code = "S app core noop\nSet x y\n"
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "label_scope_top_level")
        assert hits, "expected label_scope_top_level diagnostic"
        assert "L1:" in hits[0].suggested_fix

    def test_call_return_binding(self):
        ctx = CompilerContext()
        code = (
            "S app core noop\n"
            "L1:\n"
            "Call L2 result\n"
            "J 0\n"
            "L2:\n"
            "J 0\n"
        )
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "call_return_binding")
        assert hits, "expected call_return_binding diagnostic"
        assert "->" in hits[0].suggested_fix

    def test_queue_put_undefined_queue(self):
        ctx = CompilerContext()
        code = (
            "S app core noop\n"
            "L1:\n"
            'QueuePut myqueue "v" ->_\n'
            "J x\n"
        )
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "undefined_queue_legacy")
        assert hits, "expected undefined_queue_legacy diagnostic"
        assert "Q " in hits[0].suggested_fix or "queue" in hits[0].suggested_fix.lower()

    def test_e_line_requires_arrow_l_label(self):
        ctx = CompilerContext()
        code = "S app core noop\nE /api GET L1\n"
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "endpoint_label_target")
        assert hits, "expected endpoint_label_target diagnostic"
        assert "->L" in hits[0].suggested_fix

    def test_endpoint_handler_requires_exactly_one_j(self):
        ctx = CompilerContext()
        code = (
            "S app core noop\n"
            "E /api GET ->L1\n"
            "L1:\n"
            "R core.ADD 1 2 ->s\n"
            "J s\n"
            "J s\n"
        )
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "endpoint_j_count")
        assert hits, "expected endpoint_j_count diagnostic"
        assert "one J" in hits[0].suggested_fix or "J" in hits[0].message

    def test_graph_err_unknown_at_node(self):
        ctx = CompilerContext()
        code = (
            "S app core noop\n"
            "L1:\n"
            "R core.ADD 1 2 ->s\n"
            "Err @n99 ->L2\n"
            "J s\n"
            "L2:\n"
            "J s\n"
        )
        with pytest.raises(CompilationDiagnosticError) as ei:
            AICodeCompiler(strict_mode=True).compile(code, context=ctx)
        hits = _find_kind(ei.value, "graph_err_at_node_unknown")
        assert hits, "expected graph_err_at_node_unknown diagnostic"
        assert hits[0].suggested_fix
