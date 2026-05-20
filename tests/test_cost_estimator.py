"""
Tests for tooling/cost_estimator.py
"""
import pytest
from tooling.cost_estimator import (
    estimate_graph_cost,
    GraphCostReport,
    MODEL_PRICING,
    DEFAULT_MODEL,
)


def _make_ir(labels: dict) -> dict:
    return {"labels": labels}


def test_empty_ir_returns_report():
    report = estimate_graph_cost({})
    assert isinstance(report, GraphCostReport)
    assert report.total_tokens == 0
    assert len(report.warnings) > 0


def test_single_llm_node():
    ir = _make_ir({
        "L1": {
            "nodes": [{"id": "n1", "op": "llm.call"}]
        }
    })
    report = estimate_graph_cost(ir, model="gpt-4o")
    assert report.total_llm_nodes == 1
    assert report.total_input_tokens == 800
    assert report.total_output_tokens == 300
    assert report.total_cost_usd > 0


def test_non_llm_node_zero_cost():
    ir = _make_ir({
        "L1": {
            "nodes": [{"id": "n1", "op": "x.search"}]
        }
    })
    report = estimate_graph_cost(ir)
    assert report.total_cost_usd == 0.0
    assert report.total_llm_nodes == 0


def test_mixed_graph():
    ir = _make_ir({
        "L1": {
            "nodes": [
                {"id": "search", "op": "x.search"},
                {"id": "classify", "op": "llm.classify"},
                {"id": "gate", "op": "gate_eval"},
                {"id": "reply", "op": "llm.call"},
            ]
        }
    })
    report = estimate_graph_cost(ir)
    assert report.total_llm_nodes == 2
    assert report.total_nodes == 4
    # Only 2 LLM nodes contribute cost
    assert report.total_cost_usd > 0


def test_multi_label_graph():
    ir = _make_ir({
        "L1": {"nodes": [{"id": "n1", "op": "llm.call"}]},
        "L2": {"nodes": [{"id": "n2", "op": "llm.summarize"}]},
    })
    report = estimate_graph_cost(ir)
    assert len(report.labels) == 2
    assert report.total_llm_nodes == 2


def test_unknown_model_falls_back():
    ir = _make_ir({"L1": {"nodes": [{"id": "n1", "op": "llm.call"}]}})
    report = estimate_graph_cost(ir, model="nonexistent-model-xyz")
    assert any("Unknown model" in w for w in report.warnings)
    assert report.total_cost_usd > 0  # still estimates with fallback


def test_all_known_models_have_pricing():
    for model_name in MODEL_PRICING:
        ir = _make_ir({"L1": {"nodes": [{"id": "n1", "op": "llm.call"}]}})
        report = estimate_graph_cost(ir, model=model_name)
        assert report.total_cost_usd > 0, f"Zero cost for model: {model_name}"


def test_format_table():
    ir = _make_ir({"L1": {"nodes": [{"id": "n1", "op": "llm.call"}]}})
    report = estimate_graph_cost(ir)
    output = report.format("table")
    assert "AINL Graph Cost Estimate" in output
    assert "GRAPH TOTAL" in output


def test_format_summary():
    ir = _make_ir({"L1": {"nodes": [{"id": "n1", "op": "llm.call"}]}})
    report = estimate_graph_cost(ir)
    output = report.format("summary")
    assert "Estimated cost" in output


def test_format_json():
    import json
    ir = _make_ir({"L1": {"nodes": [{"id": "n1", "op": "llm.call"}]}})
    report = estimate_graph_cost(ir)
    output = report.format("json")
    data = json.loads(output)
    assert "totals" in data
    assert "labels" in data
    assert data["totals"]["llm_nodes"] == 1


def test_legacy_steps_shape():
    """IR with 'steps' array instead of 'nodes'."""
    ir = _make_ir({
        "L1": {
            "steps": [
                {"op": "llm.call"},
                {"op": "x.post"},
            ]
        }
    })
    report = estimate_graph_cost(ir)
    assert report.total_nodes == 2
    assert report.total_llm_nodes == 1


def test_nodes_dict_shape():
    """IR with 'nodes' as a dict keyed by node_id."""
    ir = _make_ir({
        "L1": {
            "nodes": {
                "search_node": {"op": "x.search"},
                "llm_node": {"op": "llm.classify"},
            }
        }
    })
    report = estimate_graph_cost(ir)
    assert report.total_nodes == 2
    assert report.total_llm_nodes == 1
