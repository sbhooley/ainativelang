#!/usr/bin/env python3
"""
Import AINL memory records from canonical JSON or JSONL files into the
SQLite-backed memory store.

This is a tooling-only bridge on top of the v1 memory adapter. It does not
change runtime semantics or the memory contract.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from tooling.memory_bridge import import_records, DEFAULT_DB_PATH
from tooling.memory_validator import ValidationIssue


def _load_json_file(path: Path, jsonl: bool) -> List[dict]:
    if jsonl:
        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
    else:
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return obj
        return [obj]


def _print_issues(issues: List[ValidationIssue]) -> None:
    for i in issues:
        prefix = "ERROR" if i.kind == "error" else "WARN"
        location = i.path or "<root>"
        print(f"{prefix} [{location}]: {i.message}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import AINL memory records from canonical JSON/JSONL files into "
            "the SQLite-backed memory store."
        )
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to the SQLite memory database (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        required=True,
        help="Path to a JSON or JSONL file containing memory records.",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Treat input as JSONL (one record per line).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary instead of human-readable text.",
    )

    args = parser.parse_args(argv)

    path = Path(args.json_file)
    if not path.exists():
        print(f"ERROR: input file does not exist: {path}")
        return 1

    records = _load_json_file(path, args.jsonl)
    result = import_records(args.db_path, records)

    if args.json:
        payload = {
            "ok": result.ok,
            "inserted": result.inserted,
            "updated": result.updated,
            "errors": [vars(e) for e in result.errors],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not result.ok:
            print("Import failed due to validation errors:")
            _print_issues(result.errors)
        else:
            print(f"Import succeeded: inserted={result.inserted}, updated={result.updated}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

