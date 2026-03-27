"""``ainl status`` weekly budget reads legacy table or workflow memory aggregate."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cli.main import _read_weekly_remaining_rollup


def test_weekly_rollup_legacy_table(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite3"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE weekly_remaining_v1 (week_start TEXT PRIMARY KEY, remaining_budget INTEGER, updated_at TEXT)"
    )
    con.execute(
        "INSERT INTO weekly_remaining_v1 (week_start, remaining_budget, updated_at) VALUES (?,?,?)",
        ("2026-W12", 99000, "x"),
    )
    con.commit()
    con.close()
    rem, ws, err = _read_weekly_remaining_rollup(db)
    assert err is None
    assert rem == 99000
    assert ws == "2026-W12"


def test_weekly_rollup_memory_fallback(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite3"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE weekly_remaining_v1 (week_start TEXT PRIMARY KEY, remaining_budget INTEGER, updated_at TEXT)"
    )
    con.execute(
        """CREATE TABLE memory_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace TEXT NOT NULL,
            record_kind TEXT NOT NULL,
            record_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ttl_seconds INTEGER NULL,
            payload_json TEXT NOT NULL,
            metadata_json TEXT NULL
        )"""
    )
    payload = {
        "weekly_remaining_tokens": 42000,
        "updated_at_utc": "2026-03-27T12:00:00Z",
        "source": "bridge.weekly_token_trends",
    }
    con.execute(
        "INSERT INTO memory_records (namespace, record_kind, record_id, created_at, updated_at, payload_json) VALUES (?,?,?,?,?,?)",
        (
            "workflow",
            "budget.aggregate",
            "weekly_remaining_v1",
            "2026-03-27T00:00:00Z",
            "2026-03-27T12:00:00Z",
            json.dumps(payload),
        ),
    )
    con.commit()
    con.close()
    rem, ws, err = _read_weekly_remaining_rollup(db)
    assert err is None
    assert rem == 42000
    assert "2026-03-27" in ws
