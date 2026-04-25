"""Smoke test: local 402 demo + two-step payment frame (stdlib server in-process)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_run_http_machine_payment_roundtrip_demo_script():
    script = ROOT / "scripts" / "run_http_machine_payment_roundtrip_demo.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert '"ok": true' in proc.stdout
    assert "step2_status" in proc.stdout
