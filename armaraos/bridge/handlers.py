#!/usr/bin/env python3
"""Shell-friendly entry: forwards to run_wrapper_ainl (same argv).

Use from cron, Node, or systemd without embedding a long python -c.

Usage:
  python3 armaraos/bridge/trigger_ainl_wrapper.py supervisor --dry-run
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent
_RUNNER = _BRIDGE / "run_wrapper_ainl.py"


def main() -> None:
    rc = subprocess.call([sys.executable, str(_RUNNER)] + sys.argv[1:])
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
