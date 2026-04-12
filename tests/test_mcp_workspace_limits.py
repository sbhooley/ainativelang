"""Per-workspace ``ainl_mcp_limits.json`` merged into MCP ``ainl_run`` limits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_MULTI_STEP = """S app core noop
L1:
R core.ADD 1 2 ->a
R core.ADD a 1 ->b
R core.ADD b 1 ->c
J c
"""

# ``core.SLEEP`` argument is milliseconds (see ``CoreBuiltinAdapter``).
_SLEEP_THEN_ADD = """S app core noop
L1:
R core.SLEEP 200 ->_
R core.ADD 1 2 ->x
J x
"""

@pytest.fixture(autouse=True)
def _clear_ainl_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AINL_CONFIG", raising=False)


def _write_limits(ws: Path, payload: object) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "ainl_mcp_limits.json").write_text(
        json.dumps(payload) if not isinstance(payload, str) else payload,
        encoding="utf-8",
    )


def _fs_adapters(ws: Path) -> dict:
    return {"enable": ["fs"], "fs": {"root": str(ws.resolve())}}


def test_max_steps_tight_halts_with_structured_error(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws1"
    _write_limits(ws, {"max_steps": 1})
    r = ainl_run(_MULTI_STEP, strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is False
    assert "error_structured" in r
    assert r["error_structured"].get("code") == "RUNTIME_MAX_STEPS"
    assert "max_steps" in r["error"].lower()


def test_max_steps_permissive_completes(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws2"
    _write_limits(ws, {"max_steps": 100})
    r = ainl_run(_MULTI_STEP, strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is True
    assert r["out"] == 5


def test_max_time_ms_timeout_envelope(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws3"
    _write_limits(ws, {"max_time_ms": 50})
    r = ainl_run(_SLEEP_THEN_ADD, strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is False
    assert "error_structured" in r
    assert r["error_structured"].get("code") == "RUNTIME_MAX_TIME"
    assert "max_time_ms" in r["error"].lower()


def test_max_adapter_calls_zero_blocks_first_adapter_call(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws4"
    _write_limits(ws, {"max_adapter_calls": 0})
    r = ainl_run("S app core noop\nL1:\nR core.ADD 1 2 ->x\nJ x\n", strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is False
    assert r.get("error_structured", {}).get("code") == "RUNTIME_MAX_ADAPTER_CALLS"


def test_no_limits_file_uses_defaults(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws5"
    ws.mkdir()
    r = ainl_run(_MULTI_STEP, strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is True


def test_malformed_limits_json_warns_and_defaults(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "ws6"
    _write_limits(ws, "{ not json")
    r = ainl_run(_MULTI_STEP, strict=True, adapters=_fs_adapters(ws))
    assert r["ok"] is True
    assert "warnings" in r
    assert any("ainl_mcp_limits.json" in w and "JSON" in w for w in r["warnings"])
