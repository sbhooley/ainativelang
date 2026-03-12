#!/usr/bin/env python3
"""
Migrate legacy MEMORY.md and memory/YYYY-MM-DD.md files into AINL memory.

This is a one-shot, conservative migration tool to help bootstrap the v1
memory store from older note patterns. It is not a generic markdown ingestion
or sync engine.
"""

import argparse
import os
from pathlib import Path
from typing import List, Optional

from tooling.memory_bridge import DEFAULT_DB_PATH
from tooling.memory_migrate import migrate_legacy_memory


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate legacy MEMORY.md and memory/YYYY-MM-DD.md files into the "
            "SQLite-backed memory store (long_term.project_fact and "
            "daily_log.note)."
        )
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to the SQLite memory database (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    parser.add_argument(
        "--memory-md",
        type=str,
        default="MEMORY.md",
        help="Path to legacy MEMORY.md (default: ./MEMORY.md). Use 'none' to skip.",
    )
    parser.add_argument(
        "--daily-log-dir",
        type=str,
        default="memory",
        help="Directory containing legacy YYYY-MM-DD.md daily logs (default: ./memory). Use 'none' to skip.",
    )

    args = parser.parse_args(argv)

    memory_md_path: Optional[Path]
    if args.memory_md.lower() == "none":
        memory_md_path = None
    else:
        p = Path(args.memory_md)
        memory_md_path = p if p.exists() else None

    daily_log_dir: Optional[Path]
    if args.daily_log_dir.lower() == "none":
        daily_log_dir = None
    else:
        d = Path(args.daily_log_dir)
        daily_log_dir = d if d.exists() else None

    result = migrate_legacy_memory(args.db_path, memory_md_path, daily_log_dir)

    if not result.ok:
        print(f"Migration failed with {len(result.errors)} validation error(s):")
        for issue in result.errors:
            print(f"- {issue.kind}: {issue.message}")
        return 1

    print(
        f"Legacy memory migration complete: inserted={result.inserted}, "
        f"updated={result.updated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

