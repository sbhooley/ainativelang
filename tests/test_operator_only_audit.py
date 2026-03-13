"""Tests for the operator-only adapter audit script (read-only)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.operator_only_adapter_audit import (
    load_operator_only_capabilities,
    find_references,
    run_audit,
    format_plain,
    CAPABILITIES_PATH,
    ROOT,
)


def test_load_operator_only_capabilities():
    """Collect operator_only capabilities from current metadata."""
    caps = load_operator_only_capabilities(CAPABILITIES_PATH)
    assert len(caps) >= 1, "registry should define at least one operator_only capability"
    ids = [c["id"] for c in caps]
    assert "adapter.memory.put" in ids or "adapter.memory.prune" in ids or "adapter.svc.caddy" in ids
    for c in caps:
        assert "operator_only" in (c.get("safety_tags") or [])
        assert c.get("kind") in ("adapter_verb", "module_skill")


def test_operator_only_audit_detects_known_refs():
    """Detect expected operator_only references in known files."""
    caps = load_operator_only_capabilities(CAPABILITIES_PATH)
    refs = find_references(ROOT, caps)

    # memory.prune is used in demo/memory_prune.lang and examples/autonomous_ops/memory_prune.lang
    prune_id = "adapter.memory.prune"
    if prune_id in refs:
        paths = [p for p, _ in refs[prune_id]]
        assert any("memory_prune" in p for p in paths), "expected memory_prune.lang to reference memory.prune"

    # memory.put is used in many monitors
    put_id = "adapter.memory.put"
    if put_id in refs:
        assert len(refs[put_id]) >= 1, "expected at least one reference to memory.put"

    # svc caddy or extras file_exists in monitor_system
    caddy_id = "adapter.svc.caddy"
    file_exists_id = "adapter.extras.file_exists"
    monitor_paths = [p for p, _ in refs.get(caddy_id, [])] + [p for p, _ in refs.get(file_exists_id, [])]
    assert any("monitor_system" in p for p in monitor_paths), "expected monitor_system to reference svc.caddy or extras.file_exists"


def test_operator_only_audit_json_shape():
    """JSON output has expected shape."""
    result = run_audit(ROOT, CAPABILITIES_PATH)
    assert "summary" in result
    s = result["summary"]
    assert "total_operator_only_in_registry" in s
    assert "total_operator_only_referenced" in s
    assert "total_files_referencing_operator_only" in s
    assert isinstance(s["total_operator_only_in_registry"], int)
    assert isinstance(s["total_operator_only_referenced"], int)
    assert isinstance(s["total_files_referencing_operator_only"], int)

    assert "report" in result
    assert isinstance(result["report"], list)
    for entry in result["report"]:
        assert "capability_id" in entry
        assert "kind" in entry
        assert "files" in entry
        assert isinstance(entry["files"], list)
        for f in entry["files"]:
            assert "path" in f
            assert "category" in f

    assert "unused_capability_ids" in result
    assert isinstance(result["unused_capability_ids"], list)


def test_operator_only_audit_no_crash_when_no_matches():
    """Audit does not crash when run; empty refs are valid."""
    result = run_audit(ROOT, CAPABILITIES_PATH)
    # Some capabilities may have zero refs (unused); report should still be well-formed
    assert result["summary"]["total_operator_only_in_registry"] >= 0
    assert result["summary"]["total_operator_only_referenced"] >= 0
    assert result["summary"]["total_files_referencing_operator_only"] >= 0


def test_operator_only_audit_plain_format():
    """Plain text output includes summary and at least one capability line."""
    result = run_audit(ROOT, CAPABILITIES_PATH)
    text = format_plain(result)
    assert "Operator-only" in text or "operator_only" in text
    assert "Total" in text or "total" in text
    assert "adapter." in text or "module." in text


def test_operator_only_audit_only_used_filter():
    """--only-used restricts report to referenced capabilities."""
    result_full = run_audit(ROOT, CAPABILITIES_PATH)
    result_used = run_audit(ROOT, CAPABILITIES_PATH, only_used=True)
    assert len(result_used["report"]) <= len(result_full["report"])
    for entry in result_used["report"]:
        assert len(entry["files"]) >= 1


def test_operator_only_audit_only_unused_filter():
    """--only-unused restricts report to unreferenced capabilities."""
    result = run_audit(ROOT, CAPABILITIES_PATH, only_unused=True)
    for entry in result["report"]:
        assert len(entry["files"]) == 0
