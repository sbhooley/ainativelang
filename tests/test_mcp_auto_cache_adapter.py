"""MCP ``ainl_run`` workspace ``cache.json`` path wiring + parse validation.

The :class:`runtime.engine.RuntimeEngine` may also register a default
:class:`adapters.local_cache.LocalFileCacheAdapter` when the IR references
``cache``; these tests isolate ``HOME`` so only the workspace cache file can
satisfy reads, proving the MCP server registered the adapter with the workspace
path when ``output/cache.json`` / ``cache.json`` is present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_CACHE_GET_ONLY = """S app core noop
L1:
R cache.GET "only_ws" ->v
J v
"""

_CACHE_ROUNDTRIP = """S app core noop
L1:
R cache.SET "t_key" 99 ->_
R cache.GET "t_key" ->v
J v
"""


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    h = tmp_path_factory.mktemp("fakehome")
    (h / ".openclaw").mkdir(parents=True, exist_ok=True)
    (h / ".openclaw" / "ainl_cache.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("AINL_CONFIG", raising=False)
    monkeypatch.delenv("AINL_CACHE_JSON", raising=False)
    monkeypatch.delenv("MONITOR_CACHE_JSON", raising=False)


def _fs_only(ws: Path) -> dict:
    return {"enable": ["fs"], "fs": {"root": str(ws.resolve())}}


def test_auto_cache_output_subdir_uses_workspace_file(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "w1"
    out = ws / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cache.json").write_text(json.dumps({"default": {"only_ws": 7}}), encoding="utf-8")
    r = ainl_run(_CACHE_GET_ONLY, strict=True, adapters=_fs_only(ws))
    assert r["ok"] is True
    assert r["out"] == 7


def test_auto_cache_root_file_uses_workspace_file(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "w2"
    ws.mkdir()
    (ws / "cache.json").write_text(json.dumps({"default": {"only_ws": 11}}), encoding="utf-8")
    r = ainl_run(_CACHE_GET_ONLY, strict=True, adapters=_fs_only(ws))
    assert r["ok"] is True
    assert r["out"] == 11


def test_cache_program_round_trip_with_auto_path(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "w3"
    (ws / "output").mkdir(parents=True, exist_ok=True)
    (ws / "output" / "cache.json").write_text("{}", encoding="utf-8")
    r = ainl_run(_CACHE_ROUNDTRIP, strict=True, adapters=_fs_only(ws))
    assert r["ok"] is True
    assert r["out"] == 99
    data = json.loads((ws / "output" / "cache.json").read_text(encoding="utf-8"))
    assert data.get("default", {}).get("t_key") == 99


def test_malformed_cache_json_returns_config_error(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "w5"
    ws.mkdir()
    (ws / "cache.json").write_text("{broken", encoding="utf-8")
    r = ainl_run(_CACHE_ROUNDTRIP, strict=True, adapters=_fs_only(ws))
    assert r["ok"] is False
    assert r.get("error") == "adapter_config_error"
    assert "cache.json" in (r.get("details") or "")


def test_empty_cache_file_round_trip(tmp_path: Path):
    from scripts.ainl_mcp_server import ainl_run

    ws = tmp_path / "w6"
    ws.mkdir()
    (ws / "cache.json").write_bytes(b"")
    r = ainl_run(_CACHE_ROUNDTRIP, strict=True, adapters=_fs_only(ws))
    assert r["ok"] is True
    assert r["out"] == 99
