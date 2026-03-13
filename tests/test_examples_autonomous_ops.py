#!/usr/bin/env python3
"""Smoke test: all autonomous_ops examples must compile with strict=False."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler

EXAMPLES = [
    "examples/autonomous_ops/infrastructure_watchdog.lang",
    "examples/autonomous_ops/tiktok_sla_monitor.lang",
    "examples/autonomous_ops/lead_quality_audit.lang",
    "examples/autonomous_ops/token_cost_tracker.lang",
    "examples/autonomous_ops/canary_sampler.lang",
    "examples/autonomous_ops/token_budget_tracker.lang",
    "examples/autonomous_ops/session_continuity.lang",
]

def main():
    bad = False
    for path in EXAMPLES:
        code = Path(path).read_text()
        c = AICodeCompiler(strict_mode=False)
        ir = c.compile(code, emit_graph=True)
        if ir.get("errors"):
            print(f"FAIL {path}: {ir['errors']}")
            bad = True
        else:
            print(f"OK {path}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()