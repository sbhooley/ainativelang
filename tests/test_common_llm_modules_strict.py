"""Strict-mode compile smoke tests for new common/llm subgraph modules (include contract)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "rel",
    [
        "modules/common/merge_llm_scores_into_items.ainl",
        "modules/common/executor_bridge_unwrap_payload.ainl",
        "modules/llm/llm_prompt_builder.ainl",
        "modules/llm/llm_safe_json_parse.ainl",
        "modules/llm/llm_classify_request_builder.ainl",
        "modules/common/heuristic_keyword_score.ainl",
        "modules/common/promoter_decision_gate.ainl",
    ],
)
def test_module_strict_compile_standalone(rel):
    from compiler_v2 import AICodeCompiler

    p = ROOT / rel
    src = p.read_text(encoding="utf-8")
    ir = AICodeCompiler(strict_mode=True, strict_reachability=False).compile(
        src, source_path=str(p)
    )
    assert not ir.get("errors"), ir.get("errors")


def test_modules_strict_include_bundle():
    from compiler_v2 import AICodeCompiler

    code = """
include "modules/common/merge_llm_scores_into_items.ainl" as m
include "modules/common/executor_bridge_unwrap_payload.ainl" as u
include "modules/llm/llm_prompt_builder.ainl" as p
include "modules/llm/llm_safe_json_parse.ainl" as sjp
include "modules/llm/llm_classify_request_builder.ainl" as crb
include "modules/common/heuristic_keyword_score.ainl" as hkw
include "modules/common/promoter_decision_gate.ainl" as pg
S core web /t
E /t G ->L0 ->z
L0:
  R core.parse "{}" -> merge_llm_base_item
  R core.parse "{}" -> merge_llm_score_row
  Call m/ENTRY ->x
  R core.parse "{}" -> unwrap_bridge_body
  Call u/ENTRY ->y
  X llm_batch_instruction_text "hi"
  X llm_batch_items_label "Items"
  X llm_batch_items_json "[]"
  Call p/ENTRY ->z
  R core.echo "[]" -> llm_raw_text
  Call sjp/ENTRY ->_
  R core.echo "[]" -> llm_batch_items_json
  Call crb/ENTRY ->_
  R core.echo "[]" -> heuristic_keywords_json
  R core.echo "x" -> heuristic_haystack
  Call hkw/ENTRY ->_
  R core.echo "1" -> gate_tweet_id
  R core.echo "u" -> gate_user_id
  Call pg/ENTRY ->_
  J z
"""
    ir = AICodeCompiler(strict_mode=True, strict_reachability=False).compile(code)
    assert not ir.get("errors"), ir.get("errors")
