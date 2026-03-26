import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.trace_export_ptc_jsonl import export_file


def test_trace_export_file_filters_private_keys(tmp_path: Path):
    src = tmp_path / "trace.jsonl"
    dst = tmp_path / "ptc.jsonl"
    rec = {
        "step_id": 1,
        "label": "1",
        "operation": "R",
        "inputs": {"node_id": "n1", "_secret": "x", "step": {"adapter": "ptc_runner", "_tok": "y"}},
        "output": {"ok": True, "_private": "z"},
        "outcome": "success",
        "timestamp": "2026-03-26T00:00:00.000Z",
    }
    src.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    out = export_file(str(src), str(dst))
    assert out["ok"] is True
    lines = [ln for ln in dst.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert "_secret" not in json.dumps(obj)
    assert "_private" not in json.dumps(obj)
