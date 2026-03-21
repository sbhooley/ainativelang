#!/usr/bin/env python3
"""One-liner-friendly append to OpenClaw daily markdown (same logic as openclaw_memory.append_today).

Usage:
  python3 scripts/ainl_memory_append_cli.py "your message"
  AINL_DRY_RUN=1 python3 scripts/ainl_memory_append_cli.py "no-op test"

Shell alias (optional):
  alias ainl-memory-append='python3 /path/to/AI_Native_Lang/scripts/ainl_memory_append_cli.py'
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.openclaw_memory import OpenClawMemoryAdapter


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    text = sys.argv[1]
    dry = bool(os.environ.get("AINL_DRY_RUN"))
    ad = OpenClawMemoryAdapter()
    ctx = {"dry_run": dry}
    n = ad.call("append_today", [text], ctx)
    print(n)


if __name__ == "__main__":
    main()
