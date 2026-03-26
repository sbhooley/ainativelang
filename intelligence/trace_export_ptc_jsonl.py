from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _strip_private_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_private_keys(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_strip_private_keys(v) for v in value]
    return value


def _to_ptc_event(record: Dict[str, Any]) -> Dict[str, Any]:
    inputs = _strip_private_keys(record.get("inputs"))
    output = _strip_private_keys(record.get("output"))
    outcome = str(record.get("outcome") or "")
    err = None
    if outcome == "fail" and isinstance(output, dict):
        err = output.get("error")
    return {
        "ts": record.get("timestamp"),
        "step_id": record.get("step_id"),
        "label": record.get("label"),
        "op": record.get("operation"),
        "status": outcome,
        "input": inputs,
        "output": output,
        "error": err,
    }


def export_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        out.append(_to_ptc_event(rec))
    out.sort(key=lambda x: (int(x.get("step_id") or 0), str(x.get("label") or "")))
    return out


def export_file(src_path: str, dst_path: str) -> Dict[str, Any]:
    src = Path(src_path)
    dst = Path(dst_path)
    if not src.exists():
        return {"ok": False, "error": f"missing source: {src}"}
    records: List[Dict[str, Any]] = []
    with src.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                records.append(row)
    exported = export_records(records)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as out:
        for row in exported:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "source": str(src), "dest": str(dst), "count": len(exported)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Export AINL trajectory to PTC-compatible JSONL")
    ap.add_argument("source_jsonl")
    ap.add_argument("dest_jsonl")
    args = ap.parse_args()
    print(json.dumps(export_file(args.source_jsonl, args.dest_jsonl), indent=2))


if __name__ == "__main__":
    main()
