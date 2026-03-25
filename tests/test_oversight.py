"""
Tests for tooling/oversight.py: compile-time and runtime oversight reports.
Run: pytest tests/test_oversight.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.oversight import compile_oversight_report, runtime_oversight_report


def _simple_ir():
    c = AICodeCompiler()
    return c.compile("S core web /api\nE /x G ->L1 ->data\nL1: R db.F User * ->data J data\n")


def test_compile_oversight_report_basic_structure():
    ir = _simple_ir()
    assert not ir.get("errors"), ir.get("errors")
    rep = compile_oversight_report(ir)
    assert rep["schema"]["ir_version"] == ir.get("ir_version")
    assert rep["schema"]["graph_schema_version"] == ir.get("graph_schema_version")
    assert rep["summary"]["labels"] >= 1
    assert rep["summary"]["nodes"] >= 2
    assert rep["summary"]["edges"] >= 1
    assert rep["summary"]["endpoints"] >= 1
    assert "frame_rw" in rep["labels"]
    assert rep["effects"]["node_effects"].get("io") >= 1
    # Adapter summary should see db usage in label "1"
    assert "db" in rep["adapters"]
    assert any(n["label_id"] == "1" for n in rep["adapters"]["db"]["nodes"])


def test_compile_oversight_report_with_diff():
    ir1 = _simple_ir()
    c = AICodeCompiler()
    ir2 = c.compile("S core web /api\nE /x G ->L1 ->data\nL1: R db.F User * ->data Set flag 1 J data\n")
    rep = compile_oversight_report(ir2, previous_ir=ir1)
    assert "graph_diff" in rep
    gd = rep["graph_diff"]
    assert gd["added_nodes"] or gd["added_edges"] or gd["changed_nodes"]


def test_runtime_oversight_report_uses_trace_and_adapters():
    ir = _simple_ir()
    # Single run payload with minimal trace and adapter calls
    run_payload = {
        "ok": True,
        "label": "1",
        "out": {"data": []},
        "duration_ms": 12.3,
        "runtime_version": "1.2.8",
        "ir_version": ir.get("ir_version"),
        "trace": [
            {"label": "1", "node_id": "n1", "duration_ms": 5.0},
            {"label": "1", "node_id": "n2", "duration_ms": 1.0},
        ],
        "adapter_calls": [
            {"adapter": "db", "verb": "F"},
            {"adapter": "db", "verb": "F"},
        ],
        "adapter_p95_ms": {"db": 7.5},
    }
    rep = runtime_oversight_report(ir, run_payload)
    assert rep["schema"]["runtime_version"] == "1.2.8"
    assert rep["summary"]["ok"] is True
    assert rep["summary"]["label"] == "1"
    # Trace coverage should mention n1 and n2
    coverage = rep["trace"]["coverage"]
    assert coverage.get("n1") == 1
    assert coverage.get("n2") == 1
    # Adapter counts and p95 must be present
    assert rep["adapters"]["counts"]["db"] == 2
    assert rep["adapters"]["p95_ms"]["db"] == 7.5
