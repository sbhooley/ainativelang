import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.ptc_to_langgraph_bridge import generate_bridge


def test_bridge_generates_snippet_from_trajectory(tmp_path: Path):
    tr = tmp_path / "trace.jsonl"
    row = {
        "step_id": 7,
        "label": "1",
        "operation": "R",
        "inputs": {
            "step": {
                "adapter": "ptc_runner",
                "target": "run",
                "args": ["(+ 1 2)", "{total :float}"],
            }
        },
    }
    tr.write_text(json.dumps(row) + "\n", encoding="utf-8")
    out = generate_bridge(trajectory=str(tr))
    assert out["ok"] is True
    assert out["count"] == 1
    snippet = out["snippet"]
    assert "create_ptc_tool_node" in snippet
    assert "StateGraph" in snippet
    assert "(+ 1 2)" in snippet


def test_bridge_returns_identity_when_no_ptc_steps(tmp_path: Path):
    tr = tmp_path / "trace_empty.jsonl"
    tr.write_text(json.dumps({"operation": "Set"}) + "\n", encoding="utf-8")
    out = generate_bridge(trajectory=str(tr))
    assert out["ok"] is True
    assert out["count"] == 0
    assert "No ptc_runner RUN steps detected" in out["snippet"]


def test_bridge_output_is_deterministic(tmp_path: Path):
    src = tmp_path / "sample.ainl"
    src.write_text(
        "\n".join(
            [
                "L1:",
                '  R ptc_runner run "(+ 3 4)" "{total :float}" 2 ->out',
                "  J out",
            ]
        ),
        encoding="utf-8",
    )
    out1 = generate_bridge(source=str(src))
    out2 = generate_bridge(source=str(src))
    assert out1["snippet"] == out2["snippet"]


def test_bridge_source_parses_complex_ptc_lisp_literal(tmp_path: Path):
    src = tmp_path / "complex.ainl"
    src.write_text(
        "\n".join(
            [
                "L1:",
                '  R ptc_runner run "(->> (tool/get_orders {:status \\"pending\\"}) (filter #(> (:amount %) 100)) (sum-by :amount))" "{total :float}" 3 ->out',
                "  J out",
            ]
        ),
        encoding="utf-8",
    )
    out = generate_bridge(source=str(src))
    assert out["count"] == 1
    assert "sum-by :amount" in out["snippet"]
