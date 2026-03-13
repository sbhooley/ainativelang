"""Tests for memory retention report (read-only)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.memory_retention_report import (
    run_report,
    format_plain,
    EXPIRE_SOON_SECONDS,
)


def _make_db(path: Path) -> str:
    db_path = str(path / "memory.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE memory_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            record_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ttl_seconds INTEGER NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


def test_report_on_empty_db(tmp_path):
    """Report on empty DB returns zero counts and does not crash."""
    db_path = _make_db(tmp_path)
    data = run_report(db_path)
    assert "error" not in data
    assert data["summary"]["total_records"] == 0
    assert data["ttl_coverage"]["with_ttl"] == 0
    assert data["ttl_coverage"]["without_ttl"] == 0
    assert data["expired_count"] == 0
    assert data["expiring_soon_count"] == 0
    assert data["by_namespace"] == []
    assert data["by_record_kind"] == []


def test_report_on_missing_db():
    """Report on missing DB returns error structure and does not crash."""
    data = run_report("/nonexistent/path/memory.sqlite3")
    assert "error" in data
    assert data["summary"]["total_records"] == 0
    text = format_plain(data)
    assert "Error:" in text or "not found" in text.lower()


def test_ttl_coverage_counts(tmp_path):
    """TTL vs no-TTL counts are correct."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    now = "2026-03-09T12:00:00Z"
    conn.executemany(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("workflow", "workflow.test", "a", now, now, 3600, "{}"),
            ("workflow", "workflow.test", "b", now, now, 86400, "{}"),
            ("session", "session.context", "c", now, now, None, "{}"),
        ],
    )
    conn.commit()
    conn.close()

    data = run_report(db_path)
    assert data["summary"]["total_records"] == 3
    assert data["ttl_coverage"]["with_ttl"] == 2
    assert data["ttl_coverage"]["without_ttl"] == 1
    assert data["by_namespace"][0]["namespace"] == "workflow"
    assert data["by_namespace"][0]["count"] == 2
    assert data["by_namespace"][1]["namespace"] == "session"
    assert data["by_namespace"][1]["count"] == 1


def test_expired_detection(tmp_path):
    """Records with created_at + ttl_seconds < now are counted as expired."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    # Expired: created 2 days ago, TTL 1 day
    conn.execute(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES ('workflow', 'workflow.test', 'exp1', datetime('now', '-2 days'), datetime('now', '-2 days'), 86400, '{}')
        """
    )
    # Not expired: created now, TTL 1 day
    conn.execute(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES ('workflow', 'workflow.test', 'fresh', datetime('now'), datetime('now'), 86400, '{}')
        """
    )
    conn.commit()
    conn.close()

    data = run_report(db_path)
    assert data["summary"]["total_records"] == 2
    assert data["expired_count"] == 1
    assert len(data["expired_sample"]) == 1
    assert data["expired_sample"][0]["record_id"] == "exp1"


def test_expiring_soon_detection(tmp_path):
    """Records expiring within threshold are counted as expiring_soon."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    # Expires in ~1 hour: created 23h ago, TTL 24h
    conn.execute(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES ('workflow', 'workflow.test', 'soon1', datetime('now', '-23 hours'), datetime('now'), 86400, '{}')
        """
    )
    conn.commit()
    conn.close()

    data = run_report(db_path, expire_soon_seconds=EXPIRE_SOON_SECONDS)
    assert data["summary"]["total_records"] == 1
    assert data["expiring_soon_count"] == 1
    assert len(data["expiring_soon"]) == 1
    assert data["expiring_soon"][0]["record_id"] == "soon1"
    assert "expires_at" in data["expiring_soon"][0]


def test_json_output_shape(tmp_path):
    """JSON output has expected keys and types."""
    db_path = _make_db(tmp_path)
    data = run_report(db_path)
    assert "summary" in data
    assert "total_records" in data["summary"]
    assert "by_namespace" in data
    assert "by_record_kind" in data
    assert "ttl_coverage" in data
    assert "age_distribution" in data
    assert "expired_count" in data
    assert "expiring_soon_count" in data
    assert "expired_sample" in data
    assert "expiring_soon" in data
    # Round-trip
    blob = json.dumps(data)
    back = json.loads(blob)
    assert back["summary"]["total_records"] == data["summary"]["total_records"]


def test_namespace_filter(tmp_path):
    """--namespace filter restricts report."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    now = "2026-03-09T12:00:00Z"
    conn.executemany(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("workflow", "workflow.a", "1", now, now, None, "{}"),
            ("session", "session.b", "2", now, now, None, "{}"),
        ],
    )
    conn.commit()
    conn.close()

    data = run_report(db_path, namespace="workflow")
    assert data["summary"]["total_records"] == 1
    assert all(r["namespace"] == "workflow" for r in data["by_namespace"])


def test_record_kind_filter(tmp_path):
    """--record-kind filter restricts report."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    now = "2026-03-09T12:00:00Z"
    conn.executemany(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("workflow", "workflow.monitor_check", "1", now, now, 604800, "{}"),
            ("workflow", "workflow.token_cost_state", "2", now, now, 604800, "{}"),
        ],
    )
    conn.commit()
    conn.close()

    data = run_report(db_path, record_kind="workflow.monitor_check")
    assert data["summary"]["total_records"] == 1
    assert data["by_record_kind"][0]["record_kind"] == "workflow.monitor_check"
