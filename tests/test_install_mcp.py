"""Tests for ainl install-mcp / tooling.mcp_host_install."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tooling.mcp_host_install import list_mcp_host_ids, run_install_mcp_host, run_install_mcp_main


def test_list_mcp_host_ids_sorted() -> None:
    ids = list_mcp_host_ids()
    assert ids == tuple(sorted(ids))
    assert "openclaw" in ids and "zeroclaw" in ids


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
