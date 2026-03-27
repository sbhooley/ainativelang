from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from runtime.adapters.base import AdapterError, SqliteAdapter


_TABLE_RE = re.compile(r"\b(?:from|join|into|update|table)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


class SimpleSqliteAdapter(SqliteAdapter):
    def __init__(
        self,
        db_path: str,
        *,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        timeout_s: float = 5.0,
    ):
        self.db_path = str(db_path)
        self.allow_write = bool(allow_write)
        self.allow_tables = set(allow_tables or [])
        self.timeout_s = float(timeout_s)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, timeout=self.timeout_s, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def _validate_sql(self, sql: str, write: bool) -> None:
        if not sql or not isinstance(sql, str):
            raise AdapterError("sqlite sql must be a non-empty string")
        stmt = sql.strip().lower()
        if write:
            if not self.allow_write:
                raise AdapterError("sqlite write blocked: allow_write is false")
        else:
            if not stmt.startswith("select"):
                raise AdapterError("sqlite query target requires SELECT statement")
        if self.allow_tables:
            refs = {m.group(1) for m in _TABLE_RE.finditer(sql)}
            blocked = [t for t in refs if t not in self.allow_tables]
            if blocked:
                raise AdapterError(f"sqlite table blocked by allowlist: {blocked[0]}")

    def _params(self, raw: Any) -> Sequence[Any]:
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        raise AdapterError("sqlite params must be list/tuple when provided")

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t = (target or "").strip().lower()
        if t not in {"query", "execute"}:
            raise AdapterError(f"unsupported sqlite target: {target}")
        if not args:
            raise AdapterError("sqlite adapter missing sql argument")
        sql = args[0]
        params = self._params(args[1] if len(args) > 1 else None)
        write = t == "execute"
        self._validate_sql(sql, write=write)
        try:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            if t == "query":
                rows = [dict(r) for r in cur.fetchall()]
                return rows
            self._conn.commit()
            return {"rows_affected": int(cur.rowcount), "lastrowid": cur.lastrowid}
        except sqlite3.Error as e:
            raise AdapterError(f"sqlite error: {e}") from e

    # Async-ready note: sqlite remains sync-first in runtime for deterministic
    # local-state behavior; async wrappers can be added later if needed.
