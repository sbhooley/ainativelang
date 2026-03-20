from __future__ import annotations

from compiler_grammar import compiler_prefix_completable, parse_prefix_state
from compiler_v2 import grammar_active_label_scope, grammar_apply_candidate_to_prefix
from grammar_constraint import next_token_mask, next_token_priors
from langserver import (
    _find_first_line_for_op,
    _diagnostic_range_for_location,
    _document_anchor_range,
    _line_range,
    active_label_scope_from_prefix,
    apply_completion_candidate,
    build_prefix,
    compiler_diagnostics,
    completion_candidates_from_prefix,
    hover_contents_for_position,
    resolve_diagnostic_location,
)


def test_completion_e_label_refs_are_canonical() -> None:
    cands = completion_candidates_from_prefix("E /users G ")
    assert any(c.startswith("->L") for c in cands)
    assert "->1" not in cands


def test_completion_empty_file() -> None:
    cands = completion_candidates_from_prefix("")
    assert cands
    assert "S" in cands
    assert len(cands) == len(set(cands))


def test_completion_scope_top_level_vs_label_scope() -> None:
    top = completion_candidates_from_prefix("S core web /api\n")
    label = completion_candidates_from_prefix("L1:\n")
    assert "E" in top
    assert "If" not in top
    assert "If" in label


def test_completion_partial_arrow_variants() -> None:
    c1 = completion_candidates_from_prefix("E /users G -")
    c2 = completion_candidates_from_prefix("E /users G ->")
    c3 = completion_candidates_from_prefix("E /users G ->L")
    assert ">" in c1
    assert "L" in c2
    assert any(x.startswith("->L") for x in c3)


def test_partial_application_uses_compiler_transition() -> None:
    assert apply_completion_candidate("If cond -", ">") == "If cond ->"
    assert apply_completion_candidate("If cond ->", "L") == "If cond ->L"
    assert apply_completion_candidate("If cond ->L", "->L2") == "If cond ->L2"
    assert apply_completion_candidate("ops.", "ops.Env") == "ops.Env"
    assert apply_completion_candidate("rag.", "rag.Src") == "rag.Src"
    assert apply_completion_candidate("L12", "L12:") == "L12:"
    assert apply_completion_candidate('Desc /x "', '"') == 'Desc /x ""'


def test_completion_partial_label_decl_progress() -> None:
    cands = completion_candidates_from_prefix("L12")
    assert "L12:" in cands or any(c.startswith("L12") and c.endswith(":") for c in cands)


def test_completion_module_prefix_forms() -> None:
    ops = completion_candidates_from_prefix("ops.")
    rag = completion_candidates_from_prefix("rag.")
    assert "ops.Env" in ops
    assert "rag.Src" in rag


def test_completion_comment_and_quote_behavior() -> None:
    in_comment = completion_candidates_from_prefix("# comment")
    in_quote = completion_candidates_from_prefix('Desc /x "')
    tail_comment = completion_candidates_from_prefix("R db.F User * ->users # trailing")
    assert in_comment == []
    assert '"' in in_quote
    assert tail_comment == []


def test_completion_no_duplicates() -> None:
    cands = completion_candidates_from_prefix("R ")
    assert len(cands) == len(set(cands))


def test_completion_no_unrelated_starters_during_partial_progress() -> None:
    cands = completion_candidates_from_prefix("If cond ->L")
    assert any(c.startswith("->L") for c in cands)
    assert "S" not in cands
    assert "E" not in cands


def test_completion_cursor_modes_parity() -> None:
    src = "E /users G ->L1\nL1:\n  R http.GET /x ->res\n"
    line2 = src.splitlines()[2]
    token_start = line2.index("http.GET")
    # end of token
    p_end = build_prefix(src, 2, token_start + len("http.GET"))
    # middle of token (http.GET at index 2..10)
    p_mid = build_prefix(src, 2, token_start + 2)
    # after whitespace
    p_ws = build_prefix(src, 2, token_start + len("http.GET") + 1)
    assert p_end.endswith("R http.GET")
    assert p_mid.endswith("R ht")
    assert p_ws.endswith("R http.GET ")


def test_completion_empty_line_scope_top_and_label() -> None:
    top = completion_candidates_from_prefix("S core web /api\n\n")
    label = completion_candidates_from_prefix("L1:\n\n")
    assert "E" in top
    assert "If" in label


def test_registry_adapter_suggestions_only_when_admissible() -> None:
    admissible = completion_candidates_from_prefix("R ")
    inadmissible = completion_candidates_from_prefix("E /users G ->L1 ")
    assert any(c.startswith("http.") for c in admissible)
    assert not any(c.startswith("http.") for c in inadmissible)


def test_registry_never_leaks_in_non_r_contexts() -> None:
    if_ctx = completion_candidates_from_prefix("If cond ")
    top_ctx = completion_candidates_from_prefix("E /users G ->L1 ")
    assert not any(c.startswith("db.") or c.startswith("http.") for c in if_ctx)
    assert not any(c.startswith("db.") or c.startswith("http.") for c in top_ctx)


def test_registry_enrichment_bounded_to_first_r_slot() -> None:
    first_slot = completion_candidates_from_prefix("R ")
    second_slot = completion_candidates_from_prefix("R db.F ")
    assert any(c.startswith("db.") or c.startswith("http.") for c in first_slot)
    assert not any(c.startswith("db.") or c.startswith("http.") for c in second_slot)


def test_mask_filters_invalid_adapter_tokens() -> None:
    prefix = "R "
    raw = {"http.GET", "bad adapter", "http..GET", "db.F", "http/GET"}
    masked = set(next_token_mask(prefix, raw))
    assert "http.GET" in masked
    assert "db.F" in masked
    assert "bad adapter" not in masked
    assert "http..GET" not in masked
    assert "http/GET" not in masked


def test_completion_candidates_are_admissible_after_application() -> None:
    prefixes = [
        "E /users G ",
        "If cond ->L",
        "ops.",
        "rag.",
        "R ",
    ]
    for prefix in prefixes:
        cands = completion_candidates_from_prefix(prefix)
        for cand in cands:
            applied = apply_completion_candidate(prefix, cand)
            assert compiler_prefix_completable(applied), (prefix, cand, applied)


def test_completion_excludes_newline_candidate() -> None:
    cands = completion_candidates_from_prefix("E /users G ")
    assert "\n" not in cands


def test_hover_adapter_and_adapter_target() -> None:
    src = "R http.GET /users ->res"
    on_http = hover_contents_for_position(src, 0, src.index("http.GET") + 1) or ""
    on_target = hover_contents_for_position(src, 0, src.index("GET") + 1) or ""
    assert "http" in on_http
    assert "http.GET" in on_target


def test_hover_core_op() -> None:
    src = "E /users G ->L1"
    content = hover_contents_for_position(src, 0, 0) or ""
    assert "Scope:" in content
    assert "Minimum slots:" in content


def test_hover_core_op_if() -> None:
    src = "If cond ->L1"
    content = hover_contents_for_position(src, 0, 1) or ""
    assert "Scope:" in content
    assert "Minimum slots:" in content


def test_hover_module_prefixed_op() -> None:
    src = "ops.Env DATABASE_URL required"
    content = hover_contents_for_position(src, 0, src.index("ops.Env") + 2) or ""
    assert "Module-prefixed op" in content


def test_hover_label_decl_and_not_label_ref() -> None:
    src = "L1:\nIf cond ->L2\n"
    on_decl = hover_contents_for_position(src, 0, 1) or ""
    on_ref = hover_contents_for_position(src, 1, src.splitlines()[1].index("->L2") + 1)
    assert "Label declaration" in on_decl
    assert on_ref is None


def test_hover_ignores_dotted_string_literals() -> None:
    src = 'Desc /x "http.GET"'
    assert hover_contents_for_position(src, 0, src.index("http.GET") + 2) is None


def test_hover_ignores_comment_tokens_and_boundary_behavior() -> None:
    src = "R db.F User * ->users  # db.F\n"
    # On comment-side dotted token
    assert hover_contents_for_position(src, 0, src.index("#") + 3) is None
    # Boundary at end of db.F token should still hover that token.
    pos = src.index("db.F") + len("db.F")
    hover = hover_contents_for_position(src, 0, pos) or ""
    assert "db.F" in hover
    assert hover_contents_for_position(src, 0, src.index("#") + 1) is None


def test_hover_uses_token_under_cursor_not_nearest() -> None:
    src = "R db.F User * ->users"
    # Cursor on "User" should not hover db.F.
    pos_user = src.index("User") + 1
    assert hover_contents_for_position(src, 0, pos_user) is None


def test_diagnostics_line_mapping_uses_compiler_line_numbers() -> None:
    src = 'S core web /api\nDesc /x "oops\n'
    diags = compiler_diagnostics(src, strict_mode=True)
    assert diags
    assert any(d.range.start.line == 1 for d in diags)


def test_diagnostics_compile_exception_line_extraction() -> None:
    src = 'S core web /api\nDesc /x "oops\n'
    diags = compiler_diagnostics(src, strict_mode=True)
    assert any(d.range.start.line == 1 for d in diags if d.severity == 1)


def test_diagnostics_include_warnings() -> None:
    src = "S core web /api\nBogus x\n"
    diags = compiler_diagnostics(src, strict_mode=False)
    assert any(d.severity == 2 for d in diags)  # Warning
    assert not all(d.severity == 1 for d in diags)


def test_diagnostics_valid_program_no_errors() -> None:
    src = "S core web /api\nE /users G ->L1\nL1:\n  R db.F User * ->users\n  J users\n"
    diags = compiler_diagnostics(src, strict_mode=True)
    assert not [d for d in diags if d.severity == 1]


def test_diagnostics_bad_e_label_target_and_scope_and_call_and_err() -> None:
    bad_e = compiler_diagnostics("S core web /api\nE /users G ->1\n", strict_mode=True)
    assert any("->1" in d.message for d in bad_e if d.severity == 1)
    # First E line is line index 1 in source.
    assert any(d.range.start.line == 1 for d in bad_e if d.severity == 1)

    top_if = compiler_diagnostics("If cond ->L1\n", strict_mode=True)
    assert any("label-only op 'If' used at top-level" in d.message for d in top_if)
    assert any(d.range.start.line == 0 for d in top_if if d.severity == 1)

    bad_call = compiler_diagnostics("L1:\n  Call\n", strict_mode=True)
    assert any("op 'Call' requires at least 1 slots" in d.message for d in bad_call if d.severity == 1)
    assert any(d.range.start.line == 1 for d in bad_call if d.severity == 1)

    bad_err = compiler_diagnostics("L1:\n  Err @n1\n", strict_mode=True)
    assert any("Err @node_id requires handler" in d.message for d in bad_err if d.severity == 1)
    assert any(d.range.start.line == 1 for d in bad_err if d.severity == 1)


def test_diagnostics_runtime_contract_strict_failures_surface() -> None:
    src = "L1:\n  Set out ok\n  J out\n"
    diags = compiler_diagnostics(src, strict_mode=True)
    msgs = [d.message for d in diags if d.severity == 1]
    assert any("may be undefined on this path" in m for m in msgs)
    # Strict graph/node dataflow errors should attribute to the failing step line.
    assert any(d.range.start.line == 1 for d in diags if d.severity == 1)


def test_diagnostics_fallback_range_when_no_line_available() -> None:
    src = "S core web /api\nE /users G ->1\n"
    diags = compiler_diagnostics(src, strict_mode=True)
    # Some messages include no explicit line; ensure safe bounded range.
    assert all(d.range.start.line >= 0 and d.range.end.line >= d.range.start.line for d in diags)


def test_diagnostics_line_resolution_structured_then_lineno_then_node_then_message_then_op_fallback() -> None:
    source_lines = ["S core web /api", "E /users G ->1", "L1:", "  J data"]
    ir = {
        "labels": {
            "1": {
                "nodes": [
                    {"id": "n1", "data": {"lineno": 3}},
                ]
            }
        }
    }

    # 1) Structured span
    assert resolve_diagnostic_location({"message": "x", "span": {"line": 4}}, ir, source_lines) == (3, "span")
    # 2) Structured lineno
    assert resolve_diagnostic_location({"lineno": 2, "message": "x"}, ir, source_lines) == (1, "lineno")
    # 3) Structured label/node via IR lookup
    assert resolve_diagnostic_location({"label_id": "1", "node_id": "n1", "message": "x"}, ir, source_lines) == (2, "node")
    # 4) Regex fallback from message text
    assert resolve_diagnostic_location("Line 4: boom", ir, source_lines) == (3, "message")
    # 5) Message label/node mapping
    assert resolve_diagnostic_location("Label '1': node 'n1' reads 'x'", ir, source_lines) == (2, "node")
    # 6) Op-prefix mapping fallback
    assert resolve_diagnostic_location("E: slot 3 must be ->L<number>", ir, source_lines) == (1, "op-fallback")
    # 7) Unresolved document fallback
    assert resolve_diagnostic_location("totally unknown format", ir, source_lines) == (0, "document")


def test_find_first_line_for_op_is_heuristic_only_when_multiple_matches() -> None:
    src = [
        "ops.Env A required",
        "ops.Env B required",
    ]
    assert _find_first_line_for_op("ops.Env", src) is None
    line_idx, prov = resolve_diagnostic_location("ops.Env: malformed declaration", {"labels": {}}, src)
    assert (line_idx, prov) == (0, "document")


def test_alias_module_prefixed_message_does_not_misattribute_with_multiple_matches() -> None:
    src = [
        "Env DATABASE_URL required",
        "ops.Env API_KEY required",
    ]
    # "Env:" alias canonicalizes to ops.Env, but there are multiple matches.
    line_idx, prov = resolve_diagnostic_location("Env: malformed declaration", {"labels": {}}, src)
    assert (line_idx, prov) == (0, "document")


def test_diagnostics_no_crash_on_unexpected_compiler_formats() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [
                {"severity": "error", "message": "dict style error", "span": {"line": 2}},
                None,
                {"severity": "warning", "message": "w", "lineno": 1},
            ],
            "errors": [],
            "warnings": [],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags
    assert any(d.severity == 1 for d in diags)
    assert any(d.severity == 2 for d in diags)


def test_resolve_diagnostic_location_handles_malformed_dict_without_crash() -> None:
    # Missing/invalid fields should fall back safely.
    item = {"span": "bad", "lineno": "bad", "message": None}
    line_idx, prov = resolve_diagnostic_location(item, {"labels": {}}, ["A", "B"])
    assert (line_idx, prov) == (0, "document")


def test_diagnostic_range_policy_document_uses_document_anchor() -> None:
    lines = ["first", "second"]
    expected = _document_anchor_range(lines)
    actual = _diagnostic_range_for_location(lines, 1, "document")
    assert actual.start.line == expected.start.line
    assert actual.end.line == expected.end.line
    assert actual.end.character == expected.end.character


def test_diagnostic_range_policy_non_document_uses_exact_line_range() -> None:
    lines = ["first", "second"]
    expected = _line_range(lines, 1)
    actual = _diagnostic_range_for_location(lines, 1, "lineno")
    assert actual.start.line == expected.start.line == 1
    assert actual.end.line == expected.end.line == 1
    assert actual.end.character == expected.end.character


def test_compile_exception_uses_provenance_based_document_anchor_when_unresolved() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unstructured compiler failure")

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        src = "A\nB\n"
        diags = compiler_diagnostics(src, strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags
    d0 = diags[0]
    expected = _document_anchor_range(src.split("\n"))
    assert d0.range.start.line == expected.start.line == 0
    assert d0.range.end.line == expected.end.line == 0
    assert d0.range.end.character == expected.end.character


def test_compiler_diagnostics_prefers_structured_over_legacy_errors_warnings() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [
                {"severity": "error", "message": "structured failure", "lineno": 2},
            ],
            # Should be ignored because diagnostics is authoritative when present.
            "errors": ["Line 1: legacy failure should not surface"],
            "warnings": ["Line 1: legacy warning should not surface"],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert len(diags) == 1
    assert diags[0].message == "structured failure"
    assert diags[0].range.start.line == 1
    assert diags[0].severity == 1


def test_compiler_diagnostics_structured_warning_severity_mapping() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [{"severity": "warning", "message": "structured warning", "lineno": 1}],
            "errors": [],
            "warnings": [],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert len(diags) == 1
    assert diags[0].severity == 2
    assert diags[0].range.start.line == 0


def test_compiler_diagnostics_structured_item_without_message_is_safe() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [{"severity": "error", "lineno": 1}],
            "errors": [],
            "warnings": [],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags
    assert diags[0].severity == 1
    # Message may be empty string; must not crash.
    assert isinstance(diags[0].message, str)


def test_compiler_diagnostics_legacy_errors_warnings_fallback_still_works() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "errors": ["Line 2: legacy error"],
            "warnings": ["Line 1: legacy warning"],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        diags = compiler_diagnostics("A\nB\n", strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert len(diags) == 2
    assert any(d.severity == 1 and d.range.start.line == 1 for d in diags)
    assert any(d.severity == 2 and d.range.start.line == 0 for d in diags)


def test_diagnostics_op_prefix_mapping_module_op_line() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [{"severity": "error", "message": "ops.Env: malformed declaration"}],
            "errors": [],
            "warnings": [],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        src = "S core web /api\nops.Env DATABASE_URL required\n"
        diags = compiler_diagnostics(src, strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags
    assert any(d.range.start.line == 1 for d in diags if d.severity == 1)


def test_diagnostics_document_level_fallback_when_unresolved() -> None:
    import langserver as ls

    orig_compile = ls.AICodeCompiler.compile

    def fake_compile(self, source: str, emit_graph: bool = True, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            "diagnostics": [{"severity": "error", "message": "unstructured failure with no location info"}],
            "errors": [],
            "warnings": [],
            "labels": {},
        }

    try:
        ls.AICodeCompiler.compile = fake_compile  # type: ignore[method-assign]
        src = "S core web /api\nE /users G ->L1\n"
        diags = compiler_diagnostics(src, strict_mode=True)
    finally:
        ls.AICodeCompiler.compile = orig_compile  # type: ignore[method-assign]

    assert diags
    d0 = diags[0]
    assert d0.range.start.line == 0
    assert d0.range.start.character == 0
    assert d0.range.end.line == 0
    # Explicit document-level policy anchors to first line range.
    assert d0.range.start.line == 0


def test_build_prefix_from_document_and_cursor() -> None:
    src = "S core web /api\nE /users G ->L1\n"
    pref = build_prefix(src, 1, 10)
    assert pref.endswith("E /users G")


def test_parity_completions_with_compiler_helpers() -> None:
    prefix = "E /users G "
    state = parse_prefix_state(prefix)
    assert state.current_op == "E"
    priors = set(next_token_priors(prefix))
    cands = set(completion_candidates_from_prefix(prefix))
    # LSP candidates should include compiler-pruned priors, minus newline.
    assert priors - {"\n"} <= cands


def test_parity_parse_prefix_state_current_op_and_slots() -> None:
    st = parse_prefix_state("E /users G ->L1 ")
    assert st.current_op == "E"
    assert st.slots == ["/users", "G", "->L1"]


def test_parity_apply_candidate_with_compiler_owned_helper() -> None:
    prefix = "If cond ->L"
    cand = "->L2"
    assert apply_completion_candidate(prefix, cand) == grammar_apply_candidate_to_prefix(prefix, cand)


def test_parity_active_label_scope_with_compiler_helper() -> None:
    p_top = "S core web /api\n\n"
    p_label = "L1:\n\n"
    assert active_label_scope_from_prefix(p_top) == grammar_active_label_scope(p_top)
    assert active_label_scope_from_prefix(p_label) == grammar_active_label_scope(p_label)


def test_parity_completion_candidates_mask_roundtrip() -> None:
    prefix = "R "
    cands = set(completion_candidates_from_prefix(prefix))
    remasked = set(next_token_mask(prefix, cands))
    assert cands <= remasked
