import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grammar_constraint import (
    is_prefix_anti_drift_clean,
    is_structurally_plausible_ainl_prefix,
    is_valid_ainl_prefix_strict,
    next_token_mask,
    next_token_priors,
    next_valid_tokens,
)
from compiler_grammar import (
    apply_candidate_to_prefix,
    filter_admissible_candidates,
    formal_next_token_classes,
    parse_prefix_state,
)
from grammar_priors import sample_tokens_for_classes
from compiler_v2 import (
    AICodeCompiler,
    grammar_active_label_scope,
    grammar_apply_candidate_to_prefix,
    grammar_matches_token_class,
    grammar_prefix_completable,
)


def test_e_label_target_suggestions_are_canonical():
    allowed = next_valid_tokens("E /users G")
    assert "->L1" in allowed
    assert "->1" not in allowed


def test_if_branch_suggestions_are_label_targets_only():
    allowed_then = next_valid_tokens("If cond")
    allowed_else = next_valid_tokens("If cond ->L1")
    assert "->done" not in allowed_then
    assert "->manual_review" not in allowed_then
    assert "->unauthorized" not in allowed_else


def test_strict_prefix_accepts_if_without_else_branch():
    prefix = "L1:\nIf cond ->L2\nL2: J ok\n"
    assert is_valid_ainl_prefix_strict(prefix)


def test_strict_prefix_allows_braces_inside_quoted_strings():
    prefix = 'Desc /users "shape {json}"\n'
    assert is_valid_ainl_prefix_strict(prefix)


def test_scope_aware_starters_prefer_top_level_ops_at_root():
    allowed = next_valid_tokens("")
    assert "If" not in allowed
    assert "S" in allowed


def test_partial_arrow_states_are_understood():
    assert next_valid_tokens("If cond -") == {">"}
    assert next_valid_tokens("If cond ->") == {"L"}
    assert "->L1" in next_valid_tokens("If cond ->L")


def test_partial_label_and_module_prefix_states_are_understood():
    allowed_label = next_valid_tokens("L12")
    assert "L12:" in allowed_label
    allowed_module = next_valid_tokens("rag.")
    assert any(tok.startswith("rag.") for tok in allowed_module)


def test_comment_and_quote_states_are_understood():
    assert next_valid_tokens('Desc /x "unterminated') == {'"'}
    assert next_valid_tokens("S core web /api # trailing note") == {"\n"}


def test_strict_prefix_rejects_label_only_op_at_top_level():
    assert not is_valid_ainl_prefix_strict("If cond ->L1\n")


def test_anti_drift_is_separate_from_grammar_checks():
    assert is_prefix_anti_drift_clean('Desc /x "json payload"\n')
    assert not is_prefix_anti_drift_clean("```python\nprint('x')\n```")


def test_e_slot_schema_supports_optional_return_type_and_description():
    # E path method label return_var return_type description
    assert "->data" in next_valid_tokens("E /users G ->L1")
    # after return var, schema should still allow additional tokens (return type/description starter)
    cands = next_valid_tokens("E /users G ->L1 ->data")
    assert "I" in cands or "A[User]" in cands


def test_if_slot_schema_allows_optional_else():
    assert "->L1" in next_valid_tokens("If cond")
    # with then already present, else is optional and still suggested
    assert "->L2" in next_valid_tokens("If cond ->L1")


def test_r_slot_schema_models_adapter_target_args_and_optional_out():
    assert "db.F" in next_valid_tokens("R")
    assert "User" in next_valid_tokens("R db.F")
    cands = next_valid_tokens("R db.F User")
    assert "->data" in cands
    assert "name" in cands or "id" in cands


def test_compiler_assisted_prefix_validation_accepts_partial_last_line():
    assert is_valid_ainl_prefix_strict("L1:\nIf cond ->L2\nR db.")


def test_strict_alias_matches_structural_plausibility_function():
    prefix = "L1:\nIf cond ->L2\nR db."
    assert is_valid_ainl_prefix_strict(prefix) == is_structurally_plausible_ainl_prefix(prefix)


def test_compiler_assisted_semantic_checks_reject_bad_completed_lines():
    assert not is_valid_ainl_prefix_strict("S core web /api\nE /x G ->1\n")
    assert not is_valid_ainl_prefix_strict("L1:\nIf cond done\n")
    assert not is_valid_ainl_prefix_strict("L1:\nCall L2 nope\n")
    assert not is_valid_ainl_prefix_strict("L1:\nErr @n1\n")
    assert not is_valid_ainl_prefix_strict("L1:\nR db.F User ->L2\n")


def test_newline_candidate_handled_before_spacing_logic():
    assert next_valid_tokens('Desc /x "unterminated') == {'"'}
    assert "\n" in next_valid_tokens("S core web /api # trailing")


def test_partial_token_candidates_complete_current_token_not_new_one():
    cands = next_valid_tokens("If cond ->L")
    assert "->L1" in cands
    # Should not offer unrelated starter tokens while a token is in-progress.
    assert "S" not in cands


def test_next_token_mask_allows_pattern_family_for_label_ref_and_out_var():
    raw = {"->L12", "->Lx", "->result", "done"}
    masked_if = next_token_mask("If cond", raw)
    assert "->L12" in masked_if
    assert "->Lx" not in masked_if

    masked_e = next_token_mask("E /users G ->L1", raw)
    assert "->result" in masked_e
    assert "->L12" not in masked_e


def test_next_token_mask_allows_pattern_family_for_path_and_field_type():
    raw_path = {"/custom", "users", "/x/y"}
    masked_e = next_token_mask("E", raw_path)
    assert "/custom" in masked_e and "/x/y" in masked_e
    assert "users" not in masked_e

    raw_field = {"score:F", "bad", "created:D?"}
    masked_d = next_token_mask("D User", raw_field)
    assert "score:F" in masked_d
    assert "created:D?" in masked_d
    assert "bad" not in masked_d


def test_next_token_priors_and_mask_apis_are_exposed():
    priors = next_token_priors("E /users G")
    assert "->L1" in priors
    masked = next_token_mask("E /users G", {"->L9", "->9", "random"})
    assert "->L9" in masked
    assert "->9" not in masked


def test_label_ref_rejects_declaration_form_in_reference_context():
    masked = next_token_mask("L1:\nCall", {"L2", "L2:", "->L2"})
    assert "L2" in masked
    assert "->L2" in masked
    assert "L2:" not in masked


def test_lexer_parity_with_compiler_on_complete_line():
    prefix = 'Desc /x "hello world"'
    st = parse_prefix_state(prefix)
    toks = AICodeCompiler().tokenize_line_lossless(prefix, 1)
    compiler_vals = [t["value"] for t in toks if t.get("kind") in ("bare", "string")]
    assert st.lex.tokens == compiler_vals


def test_lexer_single_quoted_string_keeps_json_seeds_one_token():
    """DERIVE_PDA seeds_json: '["a","b"]' must not split on inner double quotes (regression)."""
    line = '  R solana.DERIVE_PDA \'["m","1"]\' "11111111111111111111111111111111" ->pda'
    toks = AICodeCompiler().tokenize_line_lossless(line, 1)
    vals = [t["value"] for t in toks if t.get("kind") in ("bare", "string")]
    assert vals == ["R", "solana.DERIVE_PDA", '["m","1"]', "11111111111111111111111111111111", "->pda"]


def test_legacy_tokenize_line_matches_lossless_single_quoted_json():
    c = AICodeCompiler()
    line = '  R solana.DERIVE_PDA \'["m","1"]\' "11111111111111111111111111111111" ->pda'
    lossy = c.tokenize_line(line)
    lossless_vals = [t["value"] for t in c.tokenize_line_lossless(line, 1) if t.get("kind") in ("bare", "string")]
    assert lossy == lossless_vals


def test_formally_admissible_candidates_are_compiler_completable():
    prefix = "E /users G"
    raw = {"->L1", "->L2", "->1", "users"}
    masked = filter_admissible_candidates(prefix, raw)
    assert "->L1" in masked and "->L2" in masked
    assert "->1" not in masked and "users" not in masked
    # Every remaining candidate keeps prefix compiler-completable.
    for cand in masked:
        assert is_valid_ainl_prefix_strict(apply_candidate_to_prefix(prefix, cand))


def test_line_starters_differ_between_top_level_and_active_label_scope():
    top = next_token_priors("")
    inside = next_token_priors("L1:\n")
    assert "S" in top and "If" not in top
    assert "If" in inside


def test_alias_and_canonical_op_handling_accepts_prefixed_ops():
    priors = next_token_priors("ops.")
    assert "ops.Env" in priors or "ops.Sec" in priors


def test_formal_classes_and_samples_are_separated():
    classes = formal_next_token_classes("E /users G")
    assert "LABEL_REF" in classes
    samples = sample_tokens_for_classes(classes)
    assert "->L1" in samples


def test_compiler_owned_prefix_apply_matches_grammar_wrapper():
    prefix = "If cond ->L"
    cand = "->L2"
    assert apply_candidate_to_prefix(prefix, cand) == grammar_apply_candidate_to_prefix(prefix, cand)


def test_compiler_owned_scope_and_completable_match_grammar_wrapper():
    prefix = "L1:\nIf cond ->L2\nR db."
    st = parse_prefix_state(prefix)
    assert st.in_label_scope == grammar_active_label_scope(prefix)
    assert is_valid_ainl_prefix_strict(prefix) == grammar_prefix_completable(prefix)


def test_valid_and_invalid_complete_program_prefixes():
    valid = "S core web /api\nE /x G ->L1\nL1: J data\n"
    invalid = "S core web /api\nE /x G ->1\nL1: J data\n"
    assert is_valid_ainl_prefix_strict(valid)
    assert not is_valid_ainl_prefix_strict(invalid)


def test_valid_and_invalid_partial_prefixes():
    assert is_valid_ainl_prefix_strict("L1:\nIf cond ->L2\nR db.")
    assert not is_valid_ainl_prefix_strict("L1:\nIf cond nope")


def test_curated_prefix_corpus_matches_structural_plausibility():
    fx = Path(__file__).resolve().parent.parent / "corpus" / "curated" / "grammar_prefix_cases.jsonl"
    rows = [json.loads(line) for line in fx.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    for row in rows:
        got = is_valid_ainl_prefix_strict(row["prefix"])
        assert got == row["structurally_plausible"], row["name"]


def test_corpus_driven_prefix_candidate_transitions():
    cases = [
        ("If cond -", ">", "If cond ->"),
        ("If cond ->", "L", "If cond ->L"),
        ("If cond ->L", "->L2", "If cond ->L2"),
        ("L12", "L12:", "L12:"),
        ("ops.", "ops.Env", "ops.Env"),
        ('Desc /x "unterminated', '"', 'Desc /x "unterminated"'),
        ("E /x G ->L", "->L1", "E /x G ->L1"),
        ("E /x G ->L1", "->data", "E /x G ->L1 ->data"),
    ]
    for prefix, cand, want in cases:
        got = apply_candidate_to_prefix(prefix, cand)
        assert got == want
        # Compiler-owned transition helper must remain identical.
        assert got == grammar_apply_candidate_to_prefix(prefix, cand)
        assert is_valid_ainl_prefix_strict(got), f"transition became non-completable: {prefix!r} + {cand!r}"


def test_curated_corpus_round_trip_classes_samples_and_mask():
    fx = Path(__file__).resolve().parent.parent / "corpus" / "curated" / "grammar_prefix_cases.jsonl"
    rows = [json.loads(line) for line in fx.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        prefix = row["prefix"]
        if not row["structurally_plausible"]:
            continue
        classes = formal_next_token_classes(prefix)
        samples = sample_tokens_for_classes(classes)
        masked = next_token_mask(prefix, samples)
        for cand in masked:
            nxt = apply_candidate_to_prefix(prefix, cand)
            assert is_valid_ainl_prefix_strict(nxt), f"{row['name']} + {cand!r} broke completable prefix"


def test_structural_plausibility_is_not_strict_compile_validity():
    # Structurally plausible as a prefix, but strict compile must reject semantics.
    code = "L1:\nEnf missing_policy\nJ ok\n"
    assert is_structurally_plausible_ainl_prefix(code)
    ir = AICodeCompiler(strict_mode=True).compile(code)
    assert ir.get("errors")
    assert any("undefined policy" in e for e in ir.get("errors", []))


def test_incomplete_semantically_bad_line_can_remain_structurally_plausible():
    # Incomplete line remains a plausible prefix even though the completed line is invalid.
    prefix = "L1:\nCall L2 ->"
    complete_bad = "L1:\nCall L2 ->\n"
    assert is_structurally_plausible_ainl_prefix(prefix)
    assert not is_structurally_plausible_ainl_prefix(complete_bad)


def test_formal_token_matching_is_compiler_owned_only():
    import compiler_grammar as cg

    token_classes = ["METHOD", "LABEL_REF", "OUT_VAR", "PATH", "FIELD_TYPE", "TYPE_REF", "ADAPTER_OP", "TARGET", "COND"]
    tokens = ["G", "api", "->L2", "->x", "/x", "score:F", "A[User]", "db.F", "User", "->Lx", "done"]
    for cls in token_classes:
        for tok in tokens:
            assert cg._matches_token_class(cls, tok) == grammar_matches_token_class(cls, tok)


def test_grammar_apply_candidate_transition_invariants():
    # The compiler-owned transition helper is fragile; keep explicit invariants locked.
    cases = [
        ("If cond -", ">", "If cond ->"),
        ("If cond ->", "L", "If cond ->L"),
        ("If cond ->L", "->L9", "If cond ->L9"),
        ("ops.", "ops.Env", "ops.Env"),
        ('Desc /x "unterminated', '"', 'Desc /x "unterminated"'),
        # Replace when candidate completes token in progress.
        ("E /x G ->L", "->L2", "E /x G ->L2"),
        # Append when token is complete.
        ("E /x G ->L1", "->out", "E /x G ->L1 ->out"),
        # Whitespace boundary should not inject extra spacing artifacts.
        ("E /x G ->L1 ", "->out", "E /x G ->L1 ->out"),
    ]
    for prefix, cand, expected in cases:
        got = grammar_apply_candidate_to_prefix(prefix, cand)
        assert got == expected
