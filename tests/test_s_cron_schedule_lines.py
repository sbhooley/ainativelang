"""Guardrail: `S <adapter> cron "<expr>"` — extra tokens before `cron` break IR `services.path`."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_s_cron_schedules import run_check  # noqa: E402


def test_no_malformed_s_cron_lines_in_repo() -> None:
    errors, n = run_check()
    assert n == 0, "S+cron violations:\n" + "\n".join(errors)
