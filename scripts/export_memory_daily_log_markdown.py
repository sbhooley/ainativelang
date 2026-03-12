#!/usr/bin/env python3
"""
Export AINL daily_log.note memory records to markdown files.

This is a one-way, explicit, human-facing bridge on top of the v1 memory
adapter. It does not change runtime semantics or implement any sync behavior.
"""

import argparse
import os
from pathlib import Path
from typing import List, Optional

from tooling.memory_markdown_bridge import export_daily_log_markdown, DEFAULT_DB_PATH


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export AINL memory daily_log.note records to markdown files under "
            "memory/daily_log/<YYYY>/<YYYY-MM-DD>.md."
        )
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to the SQLite memory database (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="memory/daily_log",
        help="Root directory for exported markdown files (default: memory/daily_log).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing markdown files for the same day.",
    )

    args = parser.parse_args(argv)

    root = Path(args.output_root)
    paths = export_daily_log_markdown(args.db_path, root, overwrite=args.overwrite)
    if not paths:
        print("No daily_log.note records exported.")
    else:
        print(f"Exported {len(paths)} daily_log.note records to markdown under {root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

