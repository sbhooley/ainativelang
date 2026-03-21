"""Smoke-compile ZeroClaw bridge wrappers under zeroclaw/bridge/wrappers/.

Manual dry-run example (exercises fake large cache; no live notify):

    AINL_BRIDGE_FAKE_CACHE_MB=15.7 \\
      python3 zeroclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run

Or after install:

    AINL_BRIDGE_FAKE_CACHE_MB=15.7 zeroclaw-ainl-run token-budget-alert --dry-run

Weekly trends (needs memory/*.md with ## Token Usage Report for rich output):

    ZEROCLAW_WORKSPACE=/path/to/workspace python3 zeroclaw/bridge/run_wrapper_ainl.py weekly-token-trends --dry-run
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from compiler_v2 import AICodeCompiler

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPERS_DIR = REPO_ROOT / "zeroclaw" / "bridge" / "wrappers"
RUN_WRAPPER = REPO_ROOT / "zeroclaw" / "bridge" / "run_wrapper_ainl.py"


def _wrapper_paths() -> list[Path]:
    paths = sorted(WRAPPERS_DIR.glob("*.ainl"))
    assert paths, f"expected at least one .ainl under {WRAPPERS_DIR}"
    return paths


@pytest.mark.parametrize("path", _wrapper_paths(), ids=lambda p: p.name)
def test_zeroclaw_wrapper_compiles(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    ir = AICodeCompiler(strict_mode=False, strict_reachability=False).compile(src, emit_graph=True)
    errs = ir.get("errors") or []
    assert not errs, f"{path.name} compile errors: {errs}"


class TestZeroclawWeeklyTokenTrendsDryRun:
    """End-to-end dry-run via subprocess: JSON payload, clean stderr, expected report lines."""

    def test_weekly_token_trends_dry_run_with_sample_memory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(REPO_ROOT)
        zc = tmp_path / "zc"
        mem = zc / "memory"
        mem.mkdir(parents=True)
        # Seven consecutive daily files → adapter uses a full 7-day window (guards bullet format drift).
        for day in range(9, 16):
            name = f"2025-03-{day:02d}.md"
            (mem / name).write_text(
                "## Token Usage Report\n"
                f"- estimated_total_tokens: ~{1000 + day}\n"
                "- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        env = {**os.environ, "ZEROCLAW_WORKSPACE": str(zc)}

        proc = subprocess.run(
            [
                sys.executable,
                str(RUN_WRAPPER),
                "weekly-token-trends",
                "--dry-run",
                "--verbose",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        stderr = proc.stderr or ""
        assert "Traceback" not in stderr
        assert "ERROR" not in stderr
        assert "weekly_token_trends:" in stderr
        assert "last7_window=" in stderr

        data = json.loads(proc.stdout)
        assert data.get("status") == "ok"
        assert data.get("wrapper") == "weekly-token-trends"
        body = str(data.get("out") or "")
        assert "## Weekly Token Trends" in body
        # Full week of daily files → no sparse-window note
        assert "calendar days found in window" not in body
        assert "- Days in window: 7 (from memory" in body
        assert "Avg daily:" in body
        assert "Total week:" in body
        assert "Trend:" in body
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        assert any(ln.startswith("- Days in window:") for ln in lines)
        assert any("Avg daily:" in ln for ln in lines)
        assert any("Total week:" in ln for ln in lines)

    def test_weekly_token_trends_sparse_window_emits_missing_days_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify missing-days note when fewer than 7 calendar days have daily files."""
        monkeypatch.chdir(REPO_ROOT)
        zc = tmp_path / "zc"
        mem = zc / "memory"
        mem.mkdir(parents=True)
        for day in (10, 11, 12):
            (mem / f"2025-03-{day:02d}.md").write_text(
                "## Token Usage Report\n"
                f"- estimated_total_tokens: ~{1000 + day}\n"
                "- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        env = {**os.environ, "ZEROCLAW_WORKSPACE": str(zc)}
        proc = subprocess.run(
            [sys.executable, str(RUN_WRAPPER), "weekly-token-trends", "--dry-run"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        body = str(json.loads(proc.stdout).get("out") or "")
        assert "- Note: Only 3 of 7 calendar days found in window (missing daily report files)" in body

    def test_weekly_dry_run_pretty_indents_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Verify --pretty produces readable multi-line JSON while preserving content
        monkeypatch.chdir(REPO_ROOT)
        zc = tmp_path / "zc"
        mem = zc / "memory"
        mem.mkdir(parents=True)
        for day in range(9, 16):
            (mem / f"2025-03-{day:02d}.md").write_text(
                "## Token Usage Report\n- estimated_total_tokens: ~1000\n- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        env = {**os.environ, "ZEROCLAW_WORKSPACE": str(zc)}
        proc = subprocess.run(
            [
                sys.executable,
                str(RUN_WRAPPER),
                "weekly-token-trends",
                "--dry-run",
                "--pretty",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert proc.stdout.count("\n") >= 4
        data = json.loads(proc.stdout)
        assert data.get("status") == "ok"


class TestZeroclawMonthlyTokenSummaryDryRun:
    """Rolling 30-day UTC window using today's calendar dates (stable in CI)."""

    def test_monthly_token_summary_dry_run_with_sample_memory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(REPO_ROOT)
        zc = tmp_path / "zc"
        mem = zc / "memory"
        mem.mkdir(parents=True)
        for i in range(7):
            d = date.today() - timedelta(days=i)
            (mem / f"{d.isoformat()}.md").write_text(
                "## Token Usage Report\n"
                f"- estimated_total_tokens: ~{1100 + i}\n"
                "- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        env = {**os.environ, "ZEROCLAW_WORKSPACE": str(zc)}

        proc = subprocess.run(
            [
                sys.executable,
                str(RUN_WRAPPER),
                "monthly-token-summary",
                "--dry-run",
                "--verbose",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        stderr = proc.stderr or ""
        assert "Traceback" not in stderr
        assert "ERROR" not in stderr
        assert "monthly_token_summary:" in stderr
        assert "window_utc=" in stderr

        data = json.loads(proc.stdout)
        assert data.get("status") == "ok"
        assert data.get("wrapper") == "monthly-token-summary"
        body = str(data.get("out") or "")
        assert "## Monthly Token Summary" in body
        # Verify missing-days note appears when < expected calendar days have daily files
        assert "- Note: Only 7 of 30 calendar days found in window (missing daily report files)" in body
        assert "- Days in window: 7 (from memory" in body
        assert "Avg daily:" in body
        assert "Total month:" in body
        assert "Trend:" in body

    def test_monthly_token_summary_vs_prior_30_days_when_history_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prior UTC window [today-59 .. today-30] must contain token reports to emit vs-prior bullet."""
        monkeypatch.chdir(REPO_ROOT)
        zc = tmp_path / "zc"
        mem = zc / "memory"
        mem.mkdir(parents=True)
        today = date.today()
        # Current rolling month: last 7 days, higher totals
        for i in range(7):
            d = today - timedelta(days=i)
            (mem / f"{d.isoformat()}.md").write_text(
                "## Token Usage Report\n"
                "- estimated_total_tokens: ~2500\n"
                "- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        # Prior 30-day block (31–45 days ago): lower totals so comparison line is deterministic
        for off in range(31, 46):
            d = today - timedelta(days=off)
            (mem / f"{d.isoformat()}.md").write_text(
                "## Token Usage Report\n"
                "- estimated_total_tokens: ~500\n"
                "- budget_used_pct: 1.0%\n",
                encoding="utf-8",
            )
        env = {**os.environ, "ZEROCLAW_WORKSPACE": str(zc)}

        proc = subprocess.run(
            [sys.executable, str(RUN_WRAPPER), "monthly-token-summary", "--dry-run"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        body = str(json.loads(proc.stdout).get("out") or "")
        assert "## Monthly Token Summary" in body
        assert "- vs prior 30 days:" in body
