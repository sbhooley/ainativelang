"""CRM IntelligenceReport SQLite adapter.

Provides verbs:
- F (find/query): SELECT * from IntelligenceReport with optional WHERE, ORDER, LIMIT
- P (put/append): INSERT new record into IntelligenceReport

Uses environment CRM_DB_PATH to locate the database (default: crm/prisma/dev.db).
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter, SqliteAdapter


def _default_workspace() -> Path:
    w = os.getenv("OPENCLAW_WORKSPACE")
    if w:
        return Path(w).expanduser()
    return Path.home() / ".openclaw" / "workspace"


def _resolve_db_path() -> str:
    # Default path relative to workspace
    default = os.getenv("CRM_DB_PATH", "crm/prisma/dev.db")
    p = Path(default).expanduser()
    if not p.is_absolute():
        p = _default_workspace() / p
    return str(p)


class CrmDbAdapter(RuntimeAdapter):
    """Adapter group: crm_db (SQLite for CRM IntelligenceReport)"""

    def __init__(self) -> None:
        self.db_path = _resolve_db_path()
        self._conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Ensure table exists (if not, create a minimal IntelligenceReport table)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS IntelligenceReport (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jobName TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().lower()
        if verb == "f":
            return self._find(args)
        elif verb == "p":
            return self._put(args)
        else:
            raise AdapterError(f"unsupported crm_db verb: {target}")

    def _find(self, args: List[Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("crm_db F requires a WHERE clause JSON or table name")
        # Expected args: [table (optional, defaults to IntelligenceReport), where, order_by (optional), limit (optional)]
        table = "IntelligenceReport"
        where_raw: Optional[str] = None
        where_dict: Dict[str, Any] = {}
        order: Optional[str] = None
        limit: Optional[int] = None

        if args:
            # First arg could be table name or query options
            first = args[0]
            if isinstance(first, str) and not first.startswith("{") and " " not in first:
                table = first
                rest = args[1:]
            else:
                rest = args

            if rest:
                # Second arg: where clause (either dict for simple equality, or raw SQL string)
                where_arg = rest[0]
                if isinstance(where_arg, dict):
                    where_dict = where_arg
                elif isinstance(where_arg, str):
                    where_raw = where_arg
                else:
                    raise AdapterError("crm_db F: where must be dict or string")
                if len(rest) > 1 and isinstance(rest[1], str):
                    order = rest[1]
                if len(rest) > 2 and isinstance(rest[2], (int, float)):
                    limit = int(rest[2])

        # Build SELECT query
        sql = f"SELECT * FROM {table}"
        params: List[Any] = []
        if where_raw:
            # Use raw WHERE clause directly (caller ensures safety)
            sql += " WHERE " + where_raw
        elif where_dict:
            clauses = []
            for k, v in where_dict.items():
                clauses.append(f"{k} = ?")
                params.append(v)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
        if order:
            sql += f" ORDER BY {order}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        try:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            return {"rows": rows, "count": len(rows)}
        except sqlite3.Error as e:
            raise AdapterError(f"sqlite query error: {e}") from e

    def _put(self, args: List[Any]) -> Dict[str, Any]:
        if not args:
            raise AdapterError("crm_db P requires record dict")
        record: Dict[str, Any] = {}
        if isinstance(args[0], dict):
            record = args[0]
        else:
            # Try to parse as JSON string
            try:
                record = json.loads(str(args[0]))
            except Exception:
                raise AdapterError("crm_db P: record must be a dict or JSON string")

        table = record.pop("_table", "IntelligenceReport")
        columns = list(record.keys())
        placeholders = ["?"] * len(columns)
        values = list(record.values())

        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        try:
            cur = self._conn.cursor()
            cur.execute(sql, values)
            self._conn.commit()
            return {"inserted_id": cur.lastrowid}
        except sqlite3.Error as e:
            raise AdapterError(f"sqlite insert error: {e}") from e
