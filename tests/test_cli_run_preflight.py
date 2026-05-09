"""Tests for ``ainl run`` preflight checks (path_not_found / empty_source).

These are the agent-facing recovery hints the CLI prints before the parser ever
runs. The MCP layer has equivalent ``empty_source`` recovery in ``ainl_run`` /
``ainl_compile``; this preflight covers the CLI invocation path used by
ArmaraOS scheduled ``ainl run`` jobs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.main import (
    _empty_source_path_error,
    _list_sibling_workflows,
    _preflight_workflow_path,
    _pretty_preflight_error,
)


def test_preflight_returns_none_for_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "ok.ainl"
    f.write_text("S app core noop\n\nL_main:\n  R core.NOW ->ts\n  J ts\n", encoding="utf-8")
    assert _preflight_workflow_path(str(f)) is None


def test_preflight_path_not_found_lists_siblings(tmp_path: Path) -> None:
    (tmp_path / "alpha.ainl").write_text("S app core noop\nL: J 1\n", encoding="utf-8")
    (tmp_path / "beta.ainl").write_text("S app core noop\nL: J 2\n", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("nope", encoding="utf-8")
    missing = tmp_path / "social-trend-daily.ainl"
    pre = _preflight_workflow_path(str(missing))
    assert pre is not None
    assert pre["error_kind"] == "path_not_found"
    assert pre["path"] == str(missing)
    assert "alpha.ainl" in pre["sibling_workflows"]
    assert "beta.ainl" in pre["sibling_workflows"]
    assert "ignore.txt" not in pre["sibling_workflows"]
    assert "ainl_get_started" in pre["recommended_next_tools"]


def test_preflight_zero_byte_file_is_empty_source(tmp_path: Path) -> None:
    f = tmp_path / "empty.ainl"
    f.touch()
    assert f.stat().st_size == 0
    pre = _preflight_workflow_path(str(f))
    assert pre is not None
    assert pre["error_kind"] == "empty_source"
    assert "S app core noop" in pre["minimal_strict_valid_example"]
    assert "ainl_get_started" in pre["recommended_next_tools"]


def test_preflight_whitespace_only_file_is_empty_source(tmp_path: Path) -> None:
    f = tmp_path / "blank.ainl"
    f.write_text("   \n\t \n\n", encoding="utf-8")
    pre = _preflight_workflow_path(str(f))
    assert pre is not None
    assert pre["error_kind"] == "empty_source"


def test_preflight_directory_target_is_path_not_a_file(tmp_path: Path) -> None:
    pre = _preflight_workflow_path(str(tmp_path))
    assert pre is not None
    assert pre["error_kind"] == "path_not_a_file"


def test_pretty_preflight_error_includes_path_and_siblings(tmp_path: Path) -> None:
    pre = {
        "error_kind": "path_not_found",
        "path": "/x/y/social-trend-daily.ainl",
        "why_this_matters": "missing",
        "next_step": "ask user",
        "sibling_workflows": ["a.ainl", "b.ainl"],
    }
    rendered = _pretty_preflight_error(pre)
    assert "social-trend-daily.ainl" in rendered
    assert "siblings" in rendered
    assert "a.ainl" in rendered


def test_list_sibling_workflows_handles_missing_dir(tmp_path: Path) -> None:
    nope = tmp_path / "nope"
    assert _list_sibling_workflows(nope) == []


def test_empty_source_path_error_payload_shape(tmp_path: Path) -> None:
    f = tmp_path / "blank.ainl"
    f.touch()
    payload = _empty_source_path_error(f)
    # Must be JSON-serializable for `--json` mode.
    json.dumps(payload)
    assert payload["error"] == "empty_source"
    assert payload["path"] == str(f)
