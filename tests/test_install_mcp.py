"""Tests for ainl install-mcp / tooling.mcp_host_install."""

from __future__ import annotations

from pathlib import Path

from tooling.mcp_host_install import (
    MCP_SERVER_KEY,
    _ensure_mcp_registration_toml_mcp_servers_array,
    _merge_mcp_env_pass_through_into_toml_text,
    list_mcp_host_ids,
    run_install_mcp_host,
    run_install_mcp_main,
)

# Same list as ArmaraOS profile in tooling.mcp_host_install.ensure_mcp_registration
ARMARAOS_MCP_ENV = [
    "AINL_MCP_EXPOSURE_PROFILE",
    "AINL_MCP_TOOLS",
    "AINL_MCP_TOOLS_EXCLUDE",
    "AINL_MCP_RESOURCES",
    "AINL_MCP_RESOURCES_EXCLUDE",
]


def test_list_mcp_host_ids_sorted() -> None:
    ids = list_mcp_host_ids()
    assert ids == tuple(sorted(ids))
    assert "openclaw" in ids and "zeroclaw" in ids and "hermes" in ids


def test_run_install_mcp_main_list_hosts(capsys) -> None:
    rc = run_install_mcp_main(["--list-hosts"])
    assert rc == 0
    out = capsys.readouterr().out.strip().split()
    assert set(out) == set(list_mcp_host_ids())


def test_run_install_mcp_unknown_host() -> None:
    rc = run_install_mcp_host("nemo", dry_run=True, verbose=False)
    assert rc == 2


def test_run_install_mcp_openclaw_dry_run_no_writes(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    def fake_pip(verbose: bool) -> int:
        raise AssertionError("pip should not run in dry_run")

    rc = run_install_mcp_host("openclaw", dry_run=True, verbose=False, home=home, run_pip=fake_pip)
    assert rc == 0
    assert not (home / ".openclaw").exists()


def test_run_install_mcp_hermes_dry_run_no_writes(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    def fake_pip(verbose: bool) -> int:
        raise AssertionError("pip should not run in dry_run")

    rc = run_install_mcp_host("hermes", dry_run=True, verbose=False, home=home, run_pip=fake_pip)
    assert rc == 0
    assert not (home / ".hermes").exists()


def test_merge_mcp_env_pass_through_into_existing_block() -> None:
    src = """[[mcp_servers]]
name = "ainl"
timeout_secs = 30
env = []

[mcp_servers.transport]
type = "stdio"
command = "/usr/bin/ainl-mcp"
args = []
"""
    new_t, did = _merge_mcp_env_pass_through_into_toml_text(
        src, "ainl", ARMARAOS_MCP_ENV
    )
    assert did is True
    for name in ARMARAOS_MCP_ENV:
        assert name in new_t
    again, did_again = _merge_mcp_env_pass_through_into_toml_text(
        new_t, "ainl", ARMARAOS_MCP_ENV
    )
    assert did_again is False
    assert again == new_t


def test_merge_mcp_env_inserts_when_env_line_missing() -> None:
    src = """[[mcp_servers]]
name = "ainl"
timeout_secs = 30

[mcp_servers.transport]
type = "stdio"
command = "/usr/bin/ainl-mcp"
args = []
"""
    new_t, did = _merge_mcp_env_pass_through_into_toml_text(
        src, "ainl", ARMARAOS_MCP_ENV
    )
    assert did is True
    assert "env = " in new_t
    assert "AINL_MCP_EXPOSURE_PROFILE" in new_t


def test_ensure_mcp_toml_merges_env_when_ainl_already_registered(
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """[[mcp_servers]]
name = "ainl"
timeout_secs = 30
env = []

[mcp_servers.transport]
type = "stdio"
command = "/x/ainl-mcp"
args = []
"""
    )
    _ensure_mcp_registration_toml_mcp_servers_array(
        cfg,
        server_key=MCP_SERVER_KEY,
        desired={"command": "/x/ainl-mcp", "args": []},
        dry_run=False,
        verbose=False,
        env_pass_through=ARMARAOS_MCP_ENV,
    )
    merged = cfg.read_text()
    for name in ARMARAOS_MCP_ENV:
        assert name in merged


def test_ensure_mcp_toml_dry_run_merge_does_not_write(tmp_path: Path) -> None:
    original = """[[mcp_servers]]
name = "ainl"
env = []
"""
    cfg = tmp_path / "config.toml"
    cfg.write_text(original)
    _ensure_mcp_registration_toml_mcp_servers_array(
        cfg,
        server_key=MCP_SERVER_KEY,
        desired={"command": "/z", "args": []},
        dry_run=True,
        verbose=False,
        env_pass_through=ARMARAOS_MCP_ENV,
    )
    assert cfg.read_text() == original
