#!/usr/bin/env python3
"""Idempotent migration for Apollo-X growth pack (v1.3) state.

Creates optional list tables and seeds default KV keys used by monitored_accounts / active_threads
JSON arrays (promoter_kv). Safe to run multiple times on existing promoter_state.sqlite files.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def migrate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS promoter_kv (
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS monitored_accounts (
                user_id TEXT PRIMARY KEY NOT NULL
            );
            CREATE TABLE IF NOT EXISTS active_threads (
                conversation_id TEXT PRIMARY KEY NOT NULL
            );
            """
        )
        for key, default in (("monitored_accounts", "[]"), ("active_threads", "[]")):
            cur.execute("SELECT 1 FROM promoter_kv WHERE k = ?", (key,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO promoter_kv (k, v) VALUES (?, ?)",
                    (key, default),
                )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "sqlite_path",
        nargs="?",
        default="",
        help="Path to promoter_state.sqlite (default: PROMOTER_STATE_PATH or apollo-x-bot/data/promoter_state.sqlite)",
    )
    args = p.parse_args()
    raw = (args.sqlite_path or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        import os

        env = (os.environ.get("PROMOTER_STATE_PATH") or "").strip()
        if env:
            path = Path(env).expanduser()
        else:
            root = Path(__file__).resolve().parents[1]
            path = root / "apollo-x-bot" / "data" / "promoter_state.sqlite"
    migrate(path)
    print(f"apollo_migrate_state: ok {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
