from __future__ import annotations

from compiler_v2 import grammar_active_label_scope, grammar_apply_candidate_to_prefix
from grammar_constraint import next_token_mask
from langserver import (
    _diagnostic_range_for_location,
    _document_anchor_range,
    _find_first_line_for_op,
    _line_range,
    active_label_scope_from_prefix,
    apply_completion_candidate,
    build_prefix,
    compiler_diagnostics,
    completion_candidates_from_prefix,
    hover_contents_for_position,
    resolve_diagnostic_location,
    token_under_cursor,
)


def test_contract_resolve_diagnostic_location_precedence() -> None:
    source_lines = ["S core web /api", "E /users G ->1", "L1:", "  J data"]
    ir = {"labels": {"1": {"nodes": [{"id": "n1", "data": {"lineno": 3}}]}}}

    assert resolve_diagnostic_location({"span": {"line": 4}, "lineno": 2}, ir, source_lines) == (3, "span")
    assert resolve_diagnostic_location({"lineno": 2}, ir, source_lines) == (1, "lineno")
    assert resolve_diagnostic_location({"label_id": "1", "node_id": "n1"}, ir, source_lines) == (2, "node")
    assert resolve_diagnostic_location("Line 4: boom", ir, source_lines) == (3, "message")
    assert resolve_diagnostic_location("E: slot 3 must be ->L<number>", ir, source_lines) == (1, "op-fallback")
    assert resolve_diagnostic_location("unknown format", ir, source_lines) == (0, "document")


def test_contract_find_first_line_for_op_uniqueness_and_alias_behavior() -> None:
    assert _find_first_line_for_op("ops.Env", ["ops.Env A required"]) == 0
    assert _find_first_line_for_op("ops.Env", ["ops.Env A required", "ops.Env B required"]) is None
    # Alias token "Env" canonicalizes to ops.Env and is still ambiguous here.
    assert _find_first_line_for_op("ops.Env", ["Env A required", "ops.Env B required"]) is None


def test_contract_resolve_diagnostic_location_ambiguous_op_does_not_claim_precision() -> None:
    src = ["Env DATABASE_URL required", "ops.Env API_KEY required"]
    assert resolve_diagnostic_location("Env: malformed declaration", {"labels": {}}, src) == (0, "document")


def test_contract_regression_no_fake_precision_for_document_provenance() -> None:
    # Even with a non-zero candidate line, document provenance must anchor to
    # the coarse document range (line 0), never a guessed later line.
    lines = ["L0", "L1", "L2"]
    rng = _diagnostic_range_for_location(lines, 2, "document")
    assert rng.start.line == 0
    assert rng.end.line == 0


def test_contract_regression_ambiguous_op_message_falls_back_to_document() -> None:
    src = [
        "ops.Env DATABASE_URL required",
        "Env API_KEY required",
    ]
    # Message references only op name; both lines canonicalize to ops.Env.
    assert _find_first_line_for_op("ops.Env", src) is None
    line_idx, prov = resolve_diagnostic_location("ops.Env: malformed declaration", {"labels": {}}, src)
    assert (line_idx, prov) == (0, "document")


def test_contract_resolve_diagnostic_location_malformed_dict_no_crash() -> None:
    item = {"span": "bad", "lineno": "bad", "message": None}
    assert resolve_diagnostic_location(item, {"labels": {}}, ["A", "B"]) == (0, "document")


def test_contract_diagnostic_range_policy_document_vs_trusted_provenance() -> None:
    lines = ["first", "second"]
    # Trusted provenance => exact single line.
    exact = _diagnostic_range_for_location(lines, 1, "lineno")
    assert exact.start.line == 1 and exact.end.line == 1
    assert exact.end.character == len("second")

    # Document provenance => coarse document anchor policy.
    coarse = _diagnostic_range_for_location(lines, 1, "document")
    anchor = _document_anchor_range(lines)
    assert coarse.start.line == anchor.start.line == 0
    assert coarse.end.line == anchor.end.line == 0


def test_contract_compiler_diagnostics_prefers_structured_then_compat_fallback() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_structured(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [{"severity": "warning", "message": "structured warn", "lineno": 2}],
            "errors": ["Line 1: legacy err should not surface"],
            "warnings": ["Line 1: legacy warn should not surface"],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_structured  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert len(diags) == 1
    assert diags[0].message == "structured warn"
    assert diags[0].severity == 2
    assert diags[0].range.start.line == 1

    def fake_legacy(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {"errors": ["Line 2: legacy error"], "warnings": ["Line 1: legacy warning"], "labels": {}}

    try:
        ls.AICodeCompiler.compile = fake_legacy  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert any(d.severity == 1 and d.range.start.line == 1 for d in diags)
    assert any(d.severity == 2 and d.range.start.line == 0 for d in diags)


def test_contract_compiler_diagnostics_conservative_document_anchor_and_exception_path() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_no_location(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {"diagnostics": [{"severity": "error", "message": "no location"}], "labels": {}}

    try:
        ls.AICodeCompiler.compile = fake_no_location  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    anchor = _document_anchor_range(["A", "B", ""])
    assert diags and diags[0].range.start.line == anchor.start.line == 0
    assert diags[0].range.end.line == anchor.end.line == 0

    def fake_exc(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unstructured compiler failure")

    try:
        ls.AICodeCompiler.compile = fake_exc  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags and diags[0].range.start.line == 0 and diags[0].range.end.line == 0


def test_contract_compiler_diagnostics_structured_item_without_message_no_crash() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {"diagnostics": [{"severity": "error", "lineno": 1}], "labels": {}}

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags and diags[0].severity == 1
    assert isinstance(diags[0].message, str)


def test_contract_completions_masking_and_registry_enrichment_boundaries() -> None:
    top = completion_candidates_from_prefix("S core web /api\n")
    label = completion_candidates_from_prefix("L1:\n")
    assert "E" in top and "If" not in top
    assert "If" in label

    r_ctx = completion_candidates_from_prefix("R ")
    non_r_ctx = completion_candidates_from_prefix("If cond ")
    assert any(c.startswith("db.") or c.startswith("http.") for c in r_ctx)
    assert not any(c.startswith("db.") or c.startswith("http.") for c in non_r_ctx)

    partial_arrow = completion_candidates_from_prefix("If cond ->")
    partial_label = completion_candidates_from_prefix("If cond ->L")
    partial_module = completion_candidates_from_prefix("ops.")
    assert "L" in partial_arrow
    assert any(c.startswith("->L") for c in partial_label)
    assert "ops.Env" in partial_module

    assert "\n" not in r_ctx
    # Returned candidates must remain grammar-masked.
    assert set(r_ctx) <= set(next_token_mask("R ", set(r_ctx)))


def test_contract_hover_expected_cases_and_non_bare_behavior() -> None:
    src_label = "L1:\n"
    assert "Label declaration" in (hover_contents_for_position(src_label, 0, 1) or "")

    src_op = "If cond ->L1"
    assert "Scope:" in (hover_contents_for_position(src_op, 0, 1) or "")

    src_mod = "ops.Env DATABASE_URL required"
    assert "Module-prefixed op" in (hover_contents_for_position(src_mod, 0, 2) or "")

    src_adapter = "R http.GET /users ->res"
    assert "http" in (hover_contents_for_position(src_adapter, 0, src_adapter.index("http.GET") + 1) or "")
    assert "http.GET" in (hover_contents_for_position(src_adapter, 0, src_adapter.index("GET") + 1) or "")

    src_str = 'Desc /x "http.GET"'
    assert hover_contents_for_position(src_str, 0, src_str.index("http.GET") + 1) is None
    assert hover_contents_for_position("R unknown.token /x", 0, 3) is None

    # Cursor at token end still resolves.
    src_end = "R db.F User * ->users"
    end_pos = src_end.index("db.F") + len("db.F")
    assert "db.F" in (hover_contents_for_position(src_end, 0, end_pos) or "")


def test_contract_prefix_and_helper_delegation() -> None:
    src = "S core web /api\nE /users G ->L1\nL1:\n  R http.GET /x ->res\n"
    pref = build_prefix(src, 1, 10)
    assert pref.endswith("E /users G")

    tok = token_under_cursor("R db.F User * ->users", 0, 3)
    assert tok and tok.get("kind") == "bare" and tok.get("value") == "db.F"

    prefix = "If cond ->L"
    cand = "->L2"
    assert apply_completion_candidate(prefix, cand) == grammar_apply_candidate_to_prefix(prefix, cand)

    p_top = "S core web /api\n\n"
    p_label = "L1:\n\n"
    assert active_label_scope_from_prefix(p_top) == grammar_active_label_scope(p_top)
    assert active_label_scope_from_prefix(p_label) == grammar_active_label_scope(p_label)
