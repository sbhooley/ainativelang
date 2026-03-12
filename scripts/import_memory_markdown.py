#!/usr/bin/env python3
"""
Import curated markdown notes into AINL memory.

This is a one-shot, explicit, frontmatter-based bridge for selected
long_term.* kinds only. It is not a sync engine or broad markdown
ingestion feature.
"""

import argparse
import os
from pathlib import Path
from typing import List, Optional

from tooling.memory_bridge import DEFAULT_DB_PATH
from tooling.memory_markdown_import import import_markdown_to_memory


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import curated markdown notes with AINL frontmatter into the "
            "SQLite-backed memory store (long_term.project_fact and "
            "long_term.user_preference only)."
        )
    )
    parser.add_argument(
        "path",
        nargs="+",
        help="One or more markdown files or directories to scan.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to the SQLite memory database (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )

    args = parser.parse_args(argv)

    inputs = [Path(p) for p in args.path]
    result = import_markdown_to_memory(args.db_path, inputs)

    if not result.ok:
        print(f"Import failed with {len(result.errors)} validation error(s):")
        for issue in result.errors:
            print(f"- {issue.kind}: {issue.message}")
        return 1

    print(
        f"Imported markdown into memory: inserted={result.inserted}, "
        f"updated={result.updated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

