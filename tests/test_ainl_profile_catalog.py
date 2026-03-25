"""Tests for tooling/ainl_profile_catalog.py and tooling/ainl_profiles.json."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tooling.ainl_profile_catalog import (
    emit_shell_exports,
    format_profile_text,
    get_profile,
    list_profile_ids,
    load_catalog,
)


def test_catalog_version_and_profiles() -> None:
    data = load_catalog()
    assert data.get("version") == 1
    ids = list_profile_ids()
    assert "dev" in ids
    assert "openclaw-default" in ids
    assert "cost-tight" in ids


def test_get_profile_has_env() -> None:
    p = get_profile("openclaw-default")
    assert p["id"] == "openclaw-default"
    assert p["env"].get("AINL_IR_CACHE") == "1"


def test_emit_shell_quoting() -> None:
    out = emit_shell_exports("cost-tight")
    assert "export AINL_BRIDGE_REPORT_MAX_CHARS=" in out
    assert "16384" in out


def test_unknown_profile() -> None:
    with pytest.raises(KeyError):
        get_profile("no-such-profile")


def test_cli_profile_list() -> None:
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-m", "cli.main", "profile", "list"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [x.strip() for x in r.stdout.strip().splitlines() if x.strip()]
    assert "openclaw-default" in lines


def test_cli_profile_show_json() -> None:
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-m", "cli.main", "profile", "show", "dev", "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )
    d = json.loads(r.stdout)
    assert d["id"] == "dev"
    assert "env" in d


def test_format_profile_text() -> None:
    t = format_profile_text("staging")
    assert "staging" in t
    assert "AINL_INTELLIGENCE_ROLLING_CONSERVATIVE_DAILY" in t
