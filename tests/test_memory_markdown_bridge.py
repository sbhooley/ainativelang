import json
import sqlite3
from pathlib import Path

from tooling.memory_markdown_bridge import (
    export_daily_log_markdown,
    _render_daily_log_markdown,
)


def _make_db(tmp_path: Path) -> str:
    db_path = tmp_path / "memory.sqlite3"
    conn = sqlite3.connect(str(db_path))
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
    return str(db_path)


def test_render_single_entry_markdown():
    record = {
        "namespace": "daily_log",
        "record_kind": "daily_log.note",
        "record_id": "2026-03-09",
        "created_at": "2026-03-09T00:00:00Z",
        "updated_at": "2026-03-09T01:00:00Z",
        "ttl_seconds": None,
        "payload": {
            "entries": [
                {"ts": "2026-03-09T01:00:00Z", "text": "First note."},
            ]
        },
    }
    md = _render_daily_log_markdown(record)
    assert "ainl_namespace: daily_log" in md
    assert "ainl_record_kind: daily_log.note" in md
    assert "ainl_record_id: 2026-03-09" in md
    assert "# Daily Log – 2026-03-09" in md
    assert "- [2026-03-09T01:00:00Z] First note." in md


def test_export_creates_expected_path_and_content(tmp_path):
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    payload = {
        "entries": [
            {"ts": "2026-03-09T02:00:00Z", "text": "Later note."},
            {"ts": "2026-03-09T01:00:00Z", "text": "Earlier note."},
        ]
    }
    conn.execute(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "daily_log",
            "daily_log.note",
            "2026-03-09",
            "2026-03-09T00:00:00Z",
            "2026-03-09T02:00:00Z",
            None,
            json.dumps(payload),
        ),
    )
    conn.commit()

    out_root = tmp_path / "out"
    paths = export_daily_log_markdown(db_path, out_root, overwrite=True)
    assert len(paths) == 1
    md_path = paths[0]
    # Path mapping: root/<YYYY>/<YYYY-MM-DD>.md
    assert md_path.parent.name == "2026"
    assert md_path.name == "2026-03-09.md"

    content = md_path.read_text(encoding="utf-8")
    # Deterministic ordering by ts
    first_idx = content.index("Earlier note.")
    later_idx = content.index("Later note.")
    assert first_idx < later_idx


def test_export_skips_non_daily_log_records(tmp_path):
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    payload = {"entries": [{"ts": "2026-03-09T01:00:00Z", "text": "Should be ignored."}]}
    conn.execute(
        """
        INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "workflow",
            "workflow.token_cost_state",
            "t1",
            "2026-03-09T00:00:00Z",
            "2026-03-09T00:00:00Z",
            None,
            json.dumps(payload),
        ),
    )
    conn.commit()

    out_root = tmp_path / "out"
    paths = export_daily_log_markdown(db_path, out_root, overwrite=True)
    assert paths == []


def test_render_handles_missing_entries_gracefully():
    record = {
        "namespace": "daily_log",
        "record_kind": "daily_log.note",
        "record_id": "2026-03-10",
        "created_at": "2026-03-10T00:00:00Z",
        "updated_at": "2026-03-10T00:00:00Z",
        "ttl_seconds": None,
        "payload": {},
    }
    md = _render_daily_log_markdown(record)
    assert "_No entries recorded in memory for this day._" in md

