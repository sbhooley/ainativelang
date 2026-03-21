"""Tests for ainl install-zeroclaw / tooling.zeroclaw_install."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from tooling.zeroclaw_install import (
    _PATH_LINE,
    _SHIM_ZC_AINL,
    _WRAPPER_NAME,
    ensure_ainl_run_wrapper,
    ensure_mcp_registration,
    ensure_path_hint_in_shell_rc,
    run_install_zeroclaw,
)


def test_run_install_zeroclaw_dry_run_no_writes(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    calls: list[bool] = []

    def fake_pip(verbose: bool) -> int:
        calls.append(verbose)
        return 0

    rc = run_install_zeroclaw(dry_run=True, verbose=False, home=home, run_pip=fake_pip)
    assert rc == 0
    assert calls == []
    assert not (home / ".zeroclaw").exists()


def test_run_install_zeroclaw_writes_wrapper_and_mcp(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    def ok_pip(verbose: bool) -> int:
        return 0

    with (
        patch("tooling.mcp_host_install._which_or_fallback") as w,
        patch("tooling.zeroclaw_bridge.detect_ainl_repo_root", return_value=None),
    ):
        w.side_effect = lambda name, fb: f"/fake/{name}" if name in ("ainl", "ainl-mcp") else fb
        rc = run_install_zeroclaw(dry_run=False, verbose=False, home=home, run_pip=ok_pip)
    assert rc == 0

    zc = home / ".zeroclaw"
    wrapper = zc / "bin" / _WRAPPER_NAME
    assert wrapper.is_file()
    assert not wrapper.is_symlink()
    assert wrapper.stat().st_mode & stat.S_IXUSR
    text = wrapper.read_text(encoding="utf-8")
    assert "compile" in text and "run" in text
    assert "/fake/ainl" in text

    mcp = zc / "mcp.json"
    data = json.loads(mcp.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ainl"]["command"] == "/fake/ainl-mcp"


def test_ensure_mcp_skips_when_same_command(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    zc = home / ".zeroclaw"
    zc.mkdir()
    mcp = zc / "mcp.json"
    payload = {"mcpServers": {"ainl": {"command": "/usr/bin/ainl-mcp", "args": []}}}
    mcp.write_text(json.dumps(payload), encoding="utf-8")

    with patch("tooling.mcp_host_install._which_or_fallback", return_value="/usr/bin/ainl-mcp"):
        ensure_mcp_registration(home=home, dry_run=False, verbose=False)

    assert json.loads(mcp.read_text(encoding="utf-8")) == payload


def test_ensure_path_appends_bashrc(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# init\n", encoding="utf-8")

    ensure_path_hint_in_shell_rc(home=home, dry_run=False, verbose=False)
    out = bashrc.read_text(encoding="utf-8")
    assert _PATH_LINE in out


def test_ensure_path_dry_run_no_append(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# only\n", encoding="utf-8")

    ensure_path_hint_in_shell_rc(home=home, dry_run=True, verbose=False)
    assert bashrc.read_text(encoding="utf-8") == "# only\n"


def test_pip_failure_returns_nonzero(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    def bad_pip(verbose: bool) -> int:
        return 1

    rc = run_install_zeroclaw(dry_run=False, verbose=False, home=home, run_pip=bad_pip)
    assert rc == 1
    assert not (home / ".zeroclaw").exists()


def test_install_writes_bridge_shim_and_config_when_repo_detected(tmp_path: Path) -> None:
    repo = tmp_path / "checkout"
    (repo / "zeroclaw" / "bridge").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "ainl"\n', encoding="utf-8")
    (repo / "zeroclaw" / "bridge" / "zeroclaw_bridge_main.py").write_text("# stub\n", encoding="utf-8")
    home = tmp_path / "h"
    home.mkdir()

    def ok_pip(verbose: bool) -> int:
        return 0

    with patch("tooling.mcp_host_install._which_or_fallback") as w:
        w.side_effect = lambda name, fb: f"/fake/{name}" if name in ("ainl", "ainl-mcp") else fb
        with patch("tooling.zeroclaw_bridge.detect_ainl_repo_root", return_value=repo):
            rc = run_install_zeroclaw(dry_run=False, verbose=False, home=home, run_pip=ok_pip)
    assert rc == 0
    shim = home / ".zeroclaw" / "bin" / _SHIM_ZC_AINL
    assert shim.is_file()
    assert "run_wrapper_ainl.py" in shim.read_text(encoding="utf-8")
    cfg = home / ".zeroclaw" / "config.toml"
    assert cfg.is_file()
    assert "[ainl_bridge]" in cfg.read_text(encoding="utf-8")
    assert "repo_root" in cfg.read_text(encoding="utf-8")


@pytest.mark.parametrize("dry", [True, False])
def test_ensure_ainl_run_wrapper_respects_dry_run(tmp_path: Path, dry: bool) -> None:
    home = tmp_path / "h"
    home.mkdir()
    with patch("tooling.mcp_host_install._which_or_fallback", return_value="/x/ainl"):
        ensure_ainl_run_wrapper(home=home, dry_run=dry, verbose=False)
    p = home / ".zeroclaw" / "bin" / _WRAPPER_NAME
    assert p.exists() != dry
