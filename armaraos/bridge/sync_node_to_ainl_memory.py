#!/usr/bin/env python3
"""Pipe Node (or any process) output into ArmaraOS daily memory via armaraos_memory.append_today.

Usage:
  echo "note from node" | python3 armaraos/bridge/sync_node_to_ainl_memory.py
  python3 armaraos/bridge/sync_node_to_ainl_memory.py "single line from argv"

Respects AINL_DRY_RUN=1 (no file write).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from adapters.armaraos_memory import OpenFangMemoryAdapter


def main() -> None:
    if len(sys.argv) >= 2:
        text = sys.argv[1]
    else:
        text = sys.stdin.read().strip()
    if not text:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    dry = bool(os.environ.get("AINL_DRY_RUN"))
    ad = OpenFangMemoryAdapter()
    n = ad.call("append_today", [text], {"dry_run": dry})
    print(n)


if __name__ == "__main__":
    main()
