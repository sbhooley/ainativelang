import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.context_firewall_audit import _audit_source, _audit_trajectory


def test_context_firewall_audit_source_flags_non_private_keys(tmp_path: Path):
    src = tmp_path / "sample.ainl"
    src.write_text(
        "\n".join(
            [
                "L1:",
                '  Set visible_key "x"',
                '  Set _hidden_key "y"',
                '  R ptc_runner run "(+ 1 2)" ->out',
                "  J out",
            ]
        ),
        encoding="utf-8",
    )
    out = _audit_source(str(src))
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["findings"][0]["adapter"] == "ptc_runner"
    assert "visible_key" in out["findings"][0]["keys"]
    assert "_hidden_key" not in out["findings"][0]["keys"]


def test_context_firewall_audit_trajectory_flags_non_private_context_keys(tmp_path: Path):
    tr = tmp_path / "trace.jsonl"
    row = {
        "step_id": 1,
        "label": "1",
        "operation": "R",
        "inputs": {
            "step": {"adapter": "llm_query"},
            "context": {"visible_key": "x", "_hidden_key": "y"},
        },
    }
    tr.write_text(json.dumps(row) + "\n", encoding="utf-8")
    out = _audit_trajectory(str(tr))
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["findings"][0]["adapter"] == "llm_query"
    assert out["findings"][0]["keys"] == ["visible_key"]
