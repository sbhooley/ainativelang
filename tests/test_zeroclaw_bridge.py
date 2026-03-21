"""Tests for zeroclaw/bridge (mocked zeroclaw CLI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_zeroclaw_cron_list_json_mocked() -> None:
    from zeroclaw.bridge.zeroclaw_cron_adapter import list_cron_jobs_json

    fake_out = json.dumps({"jobs": [{"name": "j1", "payload": {"message": "run_wrapper_ainl"}}]})
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = fake_out
    proc.stderr = ""
    with patch("zeroclaw.bridge.zeroclaw_cron_adapter.subprocess.run", return_value=proc):
        jobs, err = list_cron_jobs_json()
    assert err is None
    assert jobs is not None
    assert jobs[0]["name"] == "j1"


def test_zeroclaw_memory_append_today_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEROCLAW_WORKSPACE", str(tmp_path / "zc"))
    from zeroclaw.bridge.zeroclaw_memory_adapter import ZeroclawMemoryAdapter

    ad = ZeroclawMemoryAdapter()
    n = ad.call("append_today", ["hello"], {"dry_run": True})
    assert n == 1
    mem = tmp_path / "zc" / "memory"
    assert not mem.exists() or not any(mem.glob("*.md"))


def test_zeroclaw_queue_put_dry_run() -> None:
    from zeroclaw.bridge.zeroclaw_queue_adapter import ZeroclawQueueAdapter

    ad = ZeroclawQueueAdapter()
    r = ad.call("Put", ["notify", "ping"], {"dry_run": True})
    assert r == "dry_run"


def test_zeroclaw_queue_notify_target_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ZEROCLAW_NOTIFY_TARGET wins over ZEROCLAW_TARGET for live sends."""
    from zeroclaw.bridge.zeroclaw_queue_adapter import ZeroclawQueueAdapter

    monkeypatch.setenv("ZEROCLAW_TARGET", "wrong")
    monkeypatch.setenv("ZEROCLAW_NOTIFY_TARGET", "staging-channel")
    monkeypatch.setenv("ZEROCLAW_NOTIFY_CHANNEL", "telegram")

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        return proc

    with patch("zeroclaw.bridge.zeroclaw_queue_adapter.subprocess.run", side_effect=fake_run):
        ad = ZeroclawQueueAdapter()
        ad.call("Put", ["notify", "hello"], {})

    cmd = captured.get("cmd")
    assert isinstance(cmd, list)
    ti = cmd.index("--target")
    assert cmd[ti + 1] == "staging-channel"


def test_zeroclaw_queue_notify_target_none_skips_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEROCLAW_NOTIFY_TARGET", "none")

    called: list[str] = []

    def boom(*_a, **_k):  # type: ignore[no-untyped-def]
        called.append("run")
        raise AssertionError("subprocess should not run when TARGET=none")

    with patch("zeroclaw.bridge.zeroclaw_queue_adapter.subprocess.run", side_effect=boom):
        from zeroclaw.bridge.zeroclaw_queue_adapter import ZeroclawQueueAdapter

        ad = ZeroclawQueueAdapter()
        r = ad.call("Put", ["notify", "hello"], {})
    assert r == "skipped"
    assert not called


def test_zeroclaw_queue_notify_target_telegram_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEROCLAW_NOTIFY_TARGET", "telegram:-1001234567890")
    monkeypatch.delenv("ZEROCLAW_NOTIFY_CHANNEL", raising=False)

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        return proc

    with patch("zeroclaw.bridge.zeroclaw_queue_adapter.subprocess.run", side_effect=fake_run):
        from zeroclaw.bridge.zeroclaw_queue_adapter import ZeroclawQueueAdapter

        ZeroclawQueueAdapter().call("Put", ["notify", "ping"], {})

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--channel") + 1] == "telegram"
    assert cmd[cmd.index("--target") + 1] == "-1001234567890"


def test_zeroclaw_queue_notify_target_slack_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEROCLAW_NOTIFY_TARGET", "slack:zero-claw-alerts")

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        return proc

    with patch("zeroclaw.bridge.zeroclaw_queue_adapter.subprocess.run", side_effect=fake_run):
        from zeroclaw.bridge.zeroclaw_queue_adapter import ZeroclawQueueAdapter

        ZeroclawQueueAdapter().call("Put", ["notify", "x"], {})

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--channel") + 1] == "slack"
    assert cmd[cmd.index("--target") + 1] == "zero-claw-alerts"


def test_zeroclaw_bridge_main_help_exits_zero() -> None:
    bridge_main = REPO_ROOT / "zeroclaw" / "bridge" / "zeroclaw_bridge_main.py"
    with patch.object(sys, "argv", [str(bridge_main), "--help"]):
        with pytest.raises(SystemExit) as ei:
            import runpy

            runpy.run_path(str(bridge_main), run_name="__main__")
        assert ei.value.code == 0


def test_cron_drift_report_json_mocked_zeroclaw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    reg_path = tmp_path / "cron_registry.json"
    reg_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "meta": {"untracked_payload_substrings": []},
                "jobs": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CRON_REGISTRY_PATH", str(reg_path))

    jobs = [{"name": "x", "payload": {"message": "nope"}}]
    with patch(
        "zeroclaw.bridge.cron_drift_check.list_cron_jobs_json",
        return_value=(jobs, None),
    ):
        from zeroclaw.bridge.cron_drift_check import run_report

        report = run_report()

    assert report.get("zeroclaw_bin")
    assert report.get("ok") is True


def test_zeroclaw_bridge_token_report_parse_block() -> None:
    # Verifies that bridge verb, weekly/monthly aggregators, and AINL helpers all converge on the same parsed structure
    from zeroclaw.bridge.token_budget_adapter import ZeroclawBridgeTokenBudgetAdapter

    ad = ZeroclawBridgeTokenBudgetAdapter()
    md = "## Token Usage Report\n- estimated_total_tokens: ~999\n- budget_used_pct: 2.5%\n"
    raw = ad.call("token_report_parse_block", [md], {})
    d = json.loads(raw)
    assert d["has_token_usage_section"] is True
    assert d["estimated_total_tokens"] == 999
    assert d["budget_used_pct"] == 2.5


def test_zeroclaw_bridge_token_report_list_daily_md(tmp_path: Path) -> None:
    from zeroclaw.bridge.token_budget_adapter import ZeroclawBridgeTokenBudgetAdapter

    mem = tmp_path / "memory"
    mem.mkdir(parents=True)
    (mem / "2025-01-05.md").write_text("x", encoding="utf-8")
    (mem / "nope.txt").write_text("x", encoding="utf-8")
    (mem / "2025-01-01.md").write_text("x", encoding="utf-8")

    ad = ZeroclawBridgeTokenBudgetAdapter()
    raw = ad.call("token_report_list_daily_md", [str(mem)], {})
    names = json.loads(raw)
    assert names == ["2025-01-01.md", "2025-01-05.md"]
