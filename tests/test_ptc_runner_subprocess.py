from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.ptc_runner import PtcRunnerAdapter  # noqa: E402


class _DummyCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_adapter(monkeypatch: pytest.MonkeyPatch, *, proc: Any) -> PtcRunnerAdapter:
    import subprocess  # local import to patch

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: proc)
    monkeypatch.setenv("AINL_ENABLE_PTC", "1")
    monkeypatch.setenv("AINL_PTC_USE_SUBPROCESS", "1")
    monkeypatch.setenv("AINL_PTC_RUNNER_CMD", "ptc_runner_dummy")
    # No URL so we force subprocess path.
    monkeypatch.delenv("AINL_PTC_RUNNER_URL", raising=False)
    return PtcRunnerAdapter(enabled=None)


def test_ptc_runner_subprocess_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "result": {"value": "ok", "beam_metrics": {"heap_bytes": 1024, "reductions": 10}},
        "beam_telemetry": {"supervision": "ok"},
    }
    proc = _DummyCompletedProcess(returncode=0, stdout=json.dumps(body))
    adp = _make_adapter(monkeypatch, proc=proc)

    out = adp.run("(+ 1 2)")
    assert out["ok"] is True
    assert out["runtime"] == "ptc_runner"
    assert out["status_code"] == 0
    assert out["result"]["value"] == "ok"
    assert out["beam_metrics"]["heap_bytes"] == 1024
    assert out["beam_telemetry"]["supervision"] == "ok"


def test_ptc_runner_subprocess_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = _DummyCompletedProcess(returncode=42, stdout="", stderr="boom")
    adp = _make_adapter(monkeypatch, proc=proc)

    out = adp.run("(+ 1 2)")
    assert out["ok"] is False
    assert out["runtime"] == "ptc_runner"
    assert out["status_code"] == 42
    assert "error" in out["result"]
    assert "boom" in out["result"]["error"]


def test_ptc_runner_http_mode_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure that when URL is configured and subprocess flag unset, we use HTTP path.
    calls = []

    class _HttpPtcRunner(PtcRunnerAdapter):
        def _post_http(self, payload):  # type: ignore[override]
            calls.append(payload)
            return {"ok": True, "status_code": 200, "body": {"result": {"value": "http_ok"}}}

    monkeypatch.setenv("AINL_ENABLE_PTC", "1")
    monkeypatch.delenv("AINL_PTC_USE_SUBPROCESS", raising=False)
    monkeypatch.setenv("AINL_PTC_RUNNER_URL", "http://example.com/run")
    adp = _HttpPtcRunner(enabled=None)

    out = adp.run("(+ 1 2)")
    assert out["ok"] is True
    assert out["result"]["value"] == "http_ok"
    # Sanity: HTTP path should have been used exactly once.
    assert len(calls) == 1

