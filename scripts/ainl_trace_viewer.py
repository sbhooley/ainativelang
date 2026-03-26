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


def main() -> None:
    ap = argparse.ArgumentParser(description="View or export AINL trajectory JSONL")
    ap.add_argument("trace_jsonl", help="Path to AINL trajectory JSONL")
    ap.add_argument("--summary", action="store_true", help="Print compact summary")
    ap.add_argument("--ptc-export", default="", help="Write PTC-compatible JSONL export to path")
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
        for r in rows:
            op = str(r.get("operation") or "")
            lb = str(r.get("label") or "")
            if op:
                ops[op] = ops.get(op, 0) + 1
            if lb:
                labels[lb] = labels.get(lb, 0) + 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "count": len(rows),
                    "ops": dict(sorted(ops.items())),
                    "labels": dict(sorted(labels.items())),
                },
                indent=2,
            )
        )
        return

    print(json.dumps({"ok": True, "count": len(rows), "rows": rows[:20]}, indent=2))


if __name__ == "__main__":
    main()
