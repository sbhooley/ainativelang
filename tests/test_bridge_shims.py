"""Integration checks for scripts/ shims → openclaw/bridge/."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def test_run_wrapper_shim_help_mentions_delegate_path() -> None:
    shim = REPO / "scripts" / "run_wrapper_ainl.py"
    proc = subprocess.run(
        [PY, str(shim), "--help"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "_shim_delegate.py" in out


def test_ainl_bridge_main_help_lists_core_and_auto_discovered() -> None:
    main_py = REPO / "openclaw" / "bridge" / "ainl_bridge_main.py"
    proc = subprocess.run(
        [PY, str(main_py), "--help"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "run-wrapper" in out
    assert "drift-check" in out
    assert "memory-append" in out
    assert "auto-discover" in out.lower()
    assert "trigger-ainl-wrapper" in out or "sync-node-to-ainl-memory" in out
    assert "token-usage" in out


def test_run_wrapper_shim_dry_run_supervisor_exit_zero() -> None:
    shim = REPO / "scripts" / "run_wrapper_ainl.py"
    proc = subprocess.run(
        [PY, str(shim), "supervisor", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    assert '"ok": true' in (proc.stdout or "")


@pytest.mark.integration
def test_ainl_bridge_main_run_wrapper_supervisor_dry_run_e2e() -> None:
    main_py = REPO / "openclaw" / "bridge" / "ainl_bridge_main.py"
    proc = subprocess.run(
        [PY, str(main_py), "run-wrapper", "supervisor", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert '"ok": true' in out


@pytest.mark.integration
def test_ainl_bridge_main_token_usage_dry_run() -> None:
    main_py = REPO / "openclaw" / "bridge" / "ainl_bridge_main.py"
    proc = subprocess.run(
        [PY, str(main_py), "token-usage", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "Token Usage Report" in out


@pytest.mark.integration
def test_ainl_bridge_main_token_usage_json_output() -> None:
    main_py = REPO / "openclaw" / "bridge" / "ainl_bridge_main.py"
    proc = subprocess.run(
        [PY, str(main_py), "token-usage", "--dry-run", "--json-output"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    data = json.loads((proc.stdout or "").strip())
    assert "total_tokens" in data
    assert "budget_percent" in data
    assert "budget_warning" in data
    assert "cache_size_mb" in data
    assert "tokens_by_model" in data


@pytest.mark.integration
def test_run_wrapper_token_budget_alert_dry_run_no_queue() -> None:
    rw = REPO / "openclaw" / "bridge" / "run_wrapper_ainl.py"
    proc = subprocess.run(
        [PY, str(rw), "token-budget-alert", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert '"ok": true' in (proc.stdout or "")
    assert '"wrapper": "token-budget-alert"' in (proc.stdout or "")
    assert "[dry_run]" in blob.lower()
    assert "[Notification]" not in blob
    # Live-only markers: queue send and real prune should not appear on dry-run
    assert "Queue sending" not in blob
    assert "monitor_cache_prune failed" not in blob


@pytest.mark.integration
def test_run_wrapper_token_budget_alert_dry_run_fake_cache_prune_markdown() -> None:
    """Large cache via AINL_BRIDGE_FAKE_CACHE_MB triggers prune path; stdout shows Would prune + markdown."""
    rw = REPO / "openclaw" / "bridge" / "run_wrapper_ainl.py"
    env = {**os.environ, "AINL_BRIDGE_FAKE_CACHE_MB": "16"}
    proc = subprocess.run(
        [PY, str(rw), "token-budget-alert", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert '"ok": true' in out
    assert "Would prune" in out
    assert "## Cache Prune" in out
    assert "- Removed" in out
    assert "- New size:" in out
    assert "[Notification]" not in out


@pytest.mark.integration
def test_run_wrapper_token_budget_alert_dry_run_fake_cache_16_prune_force_error() -> None:
    """FAKE 16 + AINL_BRIDGE_PRUNE_FORCE_ERROR: stdout includes Would prune and Prune failed."""
    rw = REPO / "openclaw" / "bridge" / "run_wrapper_ainl.py"
    env = {
        **os.environ,
        "AINL_BRIDGE_FAKE_CACHE_MB": "16",
        "AINL_BRIDGE_PRUNE_FORCE_ERROR": "1",
    }
    proc = subprocess.run(
        [PY, str(rw), "token-budget-alert", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert '"ok": true' in out
    assert "Would prune" in out
    assert "Prune failed" in out
    assert "[Notification]" not in out


@pytest.mark.integration
def test_run_wrapper_weekly_token_trends_dry_run() -> None:
    rw = REPO / "openclaw" / "bridge" / "run_wrapper_ainl.py"
    proc = subprocess.run(
        [PY, str(rw), "weekly-token-trends", "--dry-run"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert '"ok": true' in out
    assert '"wrapper": "weekly-token-trends"' in out
    assert "Weekly Token Trends" in out
    assert "Avg daily" in out


def _load_openclaw_bridge_token_budget_adapter():
    path = REPO / "openclaw" / "bridge" / "bridge_token_budget_adapter.py"
    spec = importlib.util.spec_from_file_location("openclaw_bridge_token_budget", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_openclaw_bridge_token_report_parse_block() -> None:
    # Verifies that bridge verb, weekly/monthly aggregators, and AINL helpers all converge on the same parsed structure
    mod = _load_openclaw_bridge_token_budget_adapter()
    ad = mod.BridgeTokenBudgetAdapter()
    md = "## Token Usage Report\n- estimated_total_tokens: ~888\n- budget_used_pct: 3.0%\n"
    raw = ad.call("token_report_parse_block", [md], {})
    d = json.loads(raw)
    assert d["has_token_usage_section"] is True
    assert d["estimated_total_tokens"] == 888
    assert d["budget_used_pct"] == 3.0


def test_openclaw_bridge_token_report_list_daily_md(tmp_path: Path) -> None:
    mod = _load_openclaw_bridge_token_budget_adapter()
    mem = tmp_path / "memory"
    mem.mkdir(parents=True)
    (mem / "2025-02-02.md").write_text("x", encoding="utf-8")
    (mem / "2025-02-01.md").write_text("x", encoding="utf-8")
    (mem / "other.md").write_text("x", encoding="utf-8")

    ad = mod.BridgeTokenBudgetAdapter()
    raw = ad.call("token_report_list_daily_md", [str(mem)], {})
    names = json.loads(raw)
    assert names == ["2025-02-01.md", "2025-02-02.md"]
