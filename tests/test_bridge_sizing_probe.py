"""Tests for scripts/bridge_sizing_probe.py and ainl bridge-sizing-probe."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from scripts.bridge_sizing_probe import (
    _embedding_hint,
    _token_usage_section_chars,
    print_plain_report,
    run_probe,
)


def _mk_memory_db(path: Path, rows: list[tuple[str, str, str]]) -> None:
    conn = sqlite3.connect(path)
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
            payload_json TEXT NOT NULL,
            metadata_json TEXT NULL
        )
        """
    )
    for ns, rk, rid in rows:
        conn.execute(
            """
            INSERT INTO memory_records
            (namespace, record_kind, record_id, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, '2020-01-01T00:00:00', '2020-01-01T00:00:00', '{}')
            """,
            (ns, rk, rid),
        )
    conn.commit()
    conn.close()


def test_token_usage_section_chars_basic() -> None:
    text = "## Token Usage Report\n\nhello\n\n## Next\nbody"
    n = _token_usage_section_chars(text)
    assert n == len("hello")


def test_embedding_hint_workflow_beats_intel_by_count() -> None:
    rows = [
        {"namespace": "intel", "count": 2},
        {"namespace": "workflow", "count": 10},
    ]
    assert _embedding_hint(rows) == "workflow"


def test_embedding_hint_intel_when_larger() -> None:
    rows = [
        {"namespace": "workflow", "count": 1},
        {"namespace": "intel", "count": 50},
    ]
    assert _embedding_hint(rows) == "intel"


def test_run_probe_missing_db_and_custom_memory_dir(tmp_path: Path) -> None:
    db = tmp_path / "missing.sqlite3"
    mem = tmp_path / "mem"
    mem.mkdir()
    day = mem / f"{date.today():%Y-%m-%d}.md"
    day.write_text("## Token Usage Report\n\nshort\n\n## Other\n", encoding="utf-8")

    data = run_probe(str(db), days=14, memory_dir=mem)
    assert data["memory_db_exists"] is False
    assert data["retention_error"] is not None
    assert data["by_namespace"] == []
    assert data["token_usage_section_chars_max"] == len("short")
    assert data["suggested_AINL_BRIDGE_REPORT_MAX_CHARS"] == len("short") * 2


def test_run_probe_namespace_hint_and_db(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite3"
    _mk_memory_db(
        db,
        [
            ("workflow", "k", "a"),
            ("workflow", "k", "b"),
            ("intel", "k", "c"),
        ],
    )
    mem = tmp_path / "mem2"
    mem.mkdir()

    data = run_probe(str(db), days=7, memory_dir=mem)
    assert data["memory_db_exists"] is True
    assert data["retention_error"] is None
    assert data["embedding_namespace_hint"] == "workflow"
    assert {r["namespace"]: r["count"] for r in data["by_namespace"]} == {"workflow": 2, "intel": 1}


def test_print_plain_report_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    print_plain_report(
        {
            "memory_db": "/x.sqlite3",
            "memory_db_exists": False,
            "openclaw_memory_dir": "/m",
            "memory_dir_exists": True,
            "retention_error": "Database not found: /x.sqlite3",
            "by_namespace": [],
            "embedding_namespace_hint": None,
            "token_usage_report_sections": [],
            "token_usage_section_chars_max": None,
            "token_usage_section_chars_median": None,
            "suggested_AINL_BRIDGE_REPORT_MAX_CHARS": None,
        }
    )
    out = capsys.readouterr().out
    assert "memory_db:" in out
    assert "Database not found" in out


def test_ainl_cli_bridge_sizing_probe_json(tmp_path: Path) -> None:
    import os

    db = tmp_path / "p.sqlite3"
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "OPENCLAW_MEMORY_DIR": str(tmp_path)}
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.main",
            "bridge-sizing-probe",
            "--json",
            "--db-path",
            str(db),
            "--days",
            "3",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert "by_namespace" in data
    assert data["memory_db"] == str(db)


def test_bridge_sizing_probe_main_module_smoke(tmp_path: Path) -> None:
    from scripts.bridge_sizing_probe import main

    db = tmp_path / "q.sqlite3"
    rc = main(["--json", "--db-path", str(db), "--memory-dir", str(tmp_path), "--days", "1"])
    assert rc == 0
