#!/usr/bin/env python3
"""
Export AINL memory records to a canonical JSON or JSONL file.

This is a tooling-only bridge on top of the v1 memory adapter. It does not
change runtime semantics or the memory contract.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from tooling.memory_bridge import ExportOptions, export_records, DEFAULT_DB_PATH


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export AINL memory records from the SQLite backing store into "
            "canonical JSON or JSONL format."
        )
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to the SQLite memory database (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    parser.add_argument(
        "--namespace",
        action="append",
        help="Namespace to include (can be specified multiple times). Defaults to all.",
    )
    parser.add_argument(
        "--record-kind",
        action="append",
        help="Record kind to include (can be specified multiple times). Defaults to all.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path or '-' for stdout.",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Emit JSONL (one record per line) instead of a JSON array.",
    )

    args = parser.parse_args(argv)

    opts = ExportOptions(
        db_path=args.db_path,
        namespaces=args.namespace,
        record_kinds=args.record_kind,
    )
    records = export_records(opts)

    if args.output == "-":
        out = None
    else:
        out = Path(args.output).open("w", encoding="utf-8")

    try:
        if args.jsonl:
            dest = out or os.sys.stdout
            for rec in records:
                line = json.dumps(rec, separators=(",", ":"))
                dest.write(line + "\n")
        else:
            text = json.dumps(records, indent=2, sort_keys=True)
            if out:
                out.write(text + "\n")
            else:
                print(text)
    finally:
        if out:
            out.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

