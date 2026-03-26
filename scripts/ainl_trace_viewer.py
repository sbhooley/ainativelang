#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from intelligence.trace_export_ptc_jsonl import export_file


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _beam_metrics_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    output = row.get("output")
    if not isinstance(output, dict):
        return out
    raw = output.get("beam_metrics")
    if not isinstance(raw, dict) and isinstance(output.get("result"), dict):
        raw = output["result"].get("beam_metrics")
    if not isinstance(raw, dict):
        return out
    if "heap_bytes" in raw or "heap" in raw:
        out["heap_bytes"] = raw.get("heap_bytes", raw.get("heap"))
    if "reductions" in raw:
        out["reductions"] = raw.get("reductions")
    if "exec_time_ms" in raw or "execution_time_ms" in raw:
        out["exec_time_ms"] = raw.get("exec_time_ms", raw.get("execution_time_ms"))
    if "pid" in raw or "process_id" in raw:
        out["pid"] = raw.get("pid", raw.get("process_id"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="View or export AINL trajectory JSONL")
    ap.add_argument("trace_jsonl", help="Path to AINL trajectory JSONL")
    ap.add_argument("--summary", action="store_true", help="Print compact summary")
    ap.add_argument("--ptc-export", default="", help="Write PTC-compatible JSONL export to path")
    ap.add_argument("--show-beam", action="store_true", help="Include beam_metrics details when available")
    args = ap.parse_args()

    src = Path(args.trace_jsonl).expanduser()
    if args.ptc_export:
        out = export_file(str(src), str(Path(args.ptc_export).expanduser()))
        print(json.dumps(out, indent=2))
        return

    rows = _read_jsonl(src)
    if args.summary:
        ops: Dict[str, int] = {}
        labels: Dict[str, int] = {}
        beam_rows = 0
        beam_samples: List[Dict[str, Any]] = []
        for r in rows:
            op = str(r.get("operation") or "")
            lb = str(r.get("label") or "")
            if op:
                ops[op] = ops.get(op, 0) + 1
            if lb:
                labels[lb] = labels.get(lb, 0) + 1
            bm = _beam_metrics_from_row(r)
            if bm:
                beam_rows += 1
                if len(beam_samples) < 5:
                    beam_samples.append({"step_id": r.get("step_id"), "label": lb, "beam_metrics": bm})
        payload: Dict[str, Any] = {
            "ok": True,
            "count": len(rows),
            "ops": dict(sorted(ops.items())),
            "labels": dict(sorted(labels.items())),
        }
        if args.show_beam:
            payload["beam_rows"] = beam_rows
            payload["beam_samples"] = beam_samples
        print(
            json.dumps(payload, indent=2)
        )
        return

    payload = {"ok": True, "count": len(rows), "rows": rows[:20]}
    if args.show_beam:
        payload["beam_rows"] = [r for r in rows if _beam_metrics_from_row(r)]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
