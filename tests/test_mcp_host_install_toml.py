"""TOML safety for ArmaraOS MCP bootstrap (Windows path escaping)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")

from tooling.mcp_host_install import (  # noqa: E402
    _repair_armaraos_mcp_config_toml_text,
    _repair_windows_backslash_quoted_assignments,
    _toml_safe_quoted_path,
)


def test_toml_safe_quoted_path_normalizes_windows_backslashes():
    raw = r"C:\Users\me\AppData\Roaming\ainl\venv\Scripts\ainl-mcp.EXE"
    assert _toml_safe_quoted_path(raw) == (
        "C:/Users/me/AppData/Roaming/ainl/venv/Scripts/ainl-mcp.EXE"
    )


def test_repair_windows_backslash_command_line():
    broken = (
        'command = "C:\\Users\\me\\AppData\\Roaming\\ai.armaraos.desktop\\ainl\\venv\\Scripts\\ainl-mcp.EXE"\n'
    )
    fixed = _repair_windows_backslash_quoted_assignments(broken)
    tomllib.loads(f"[mcp]\n{fixed}")
    assert "C:/Users/me/AppData" in fixed
    assert "\\" not in fixed.split('"')[1]


def test_repair_armaraos_mcp_config_roundtrip():
    broken = """[[mcp_servers]]
name = "ainl"

[mcp_servers.transport]
type = "stdio"
command = "C:\\Users\\me\\venv\\Scripts\\ainl-mcp.EXE"
args = []
"""
    fixed = _repair_armaraos_mcp_config_toml_text(broken)
    tomllib.loads(fixed)


def test_desired_block_writes_parseable_toml_with_windows_command():
    from tooling.mcp_host_install import _ensure_mcp_registration_toml_mcp_servers_array

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "config.toml"
        win_cmd = r"C:\Users\me\venv\Scripts\ainl-mcp.EXE"
        _ensure_mcp_registration_toml_mcp_servers_array(
            cfg,
            server_key="ainl",
            desired={"command": win_cmd, "args": []},
            dry_run=False,
            verbose=False,
            env_pass_through=["AINL_MCP_TOOLS"],
        )
        raw = cfg.read_text(encoding="utf-8")
        tomllib.loads(raw)
        assert "C:/Users/me/venv/Scripts/ainl-mcp.EXE" in raw
