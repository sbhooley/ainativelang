import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import RuntimeEngine


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "tests" / "fixtures" / "snapshots" / "runtime_paths.json"


def _load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_runtime_path_snapshots_match_current_envelope():
    snapshot = _load_snapshot()
    for case in snapshot["cases"]:
        fx = json.loads((ROOT / case["fixture"]).read_text(encoding="utf-8"))
        payload = RuntimeEngine.run(
            fx["code"],
            frame=fx.get("input_frame", {}),
            trace=True,
            strict=bool(fx.get("strict", True)),
            execution_mode="graph-preferred",
        )
        assert payload["ok"] is True
        if "expected_result_contains" in case:
            assert case["expected_result_contains"] in str(payload["result"]), case["name"]
        else:
            assert payload["result"] == case["expected_result"], case["name"]
        trace_ops = [event.get("op") for event in payload.get("trace", [])]
        assert trace_ops == case["expected_trace_ops"], case["name"]
