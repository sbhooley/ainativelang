from __future__ import annotations

import re
from typing import Iterable, Set

from runtime.adapters.base import AdapterError

_TABLE_RE = re.compile(r"\b(?:from|join|into|update|table)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_WRITE_PREFIXES = ("insert", "update", "delete", "create", "alter", "drop", "truncate", "grant", "revoke")
_LEADING_SQL_COMMENTS_RE = re.compile(r"^(?:\s+|--[^\n]*\n|/\*.*?\*/)+", re.DOTALL)
_CTE_WRITE_RE = re.compile(r"\b(insert|update|delete|merge)\b", re.IGNORECASE)


def assert_allowed_tables(sql: str, allow_tables: Set[str]) -> None:
    if not allow_tables:
        return
    refs = {m.group(1) for m in _TABLE_RE.finditer(sql)}
    blocked = [t for t in refs if t not in allow_tables]
    if blocked:
        raise AdapterError(f"postgres table blocked by allowlist: {blocked[0]}")


def assert_query_sql(sql: str) -> None:
    stmt = _normalize_sql_prefix(sql)
    if not stmt:
        raise AdapterError("postgres sql must be a non-empty string")
    if stmt.startswith("select") or stmt.startswith("with") or stmt.startswith("explain select") or stmt.startswith("explain analyze select"):
        return
    raise AdapterError("postgres query target requires SELECT/CTE statement")


def assert_execute_sql(sql: str, allow_write: bool) -> None:
    stmt = _normalize_sql_prefix(sql)
    if not stmt:
        raise AdapterError("postgres sql must be a non-empty string")
    if not allow_write:
        raise AdapterError("postgres write blocked: allow_write is false")
    if stmt.startswith("select"):
        raise AdapterError("postgres execute target requires write/ddl statement")
    if stmt.startswith("with"):
        # CTE can be read-only or write; enforce explicit write intent by keyword.
        if not _CTE_WRITE_RE.search(stmt):
            raise AdapterError("postgres execute CTE must contain write operation")
        return
    if not stmt.startswith(_WRITE_PREFIXES):
        raise AdapterError("postgres execute target requires write/ddl statement")


def normalize_params(raw: object) -> object:
    if raw is None:
        return ()
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise AdapterError("postgres params must be list/tuple/dict when provided")


def normalize_tables(values: Iterable[str] | None) -> Set[str]:
    return {str(v).strip() for v in (values or []) if str(v).strip()}


def _normalize_sql_prefix(sql: str) -> str:
    stmt = str(sql or "")
    # Strip leading comments/whitespace so classification handles common query wrappers.
    while True:
        m = _LEADING_SQL_COMMENTS_RE.match(stmt)
        if not m:
            break
        stmt = stmt[m.end() :]
    return stmt.strip().lower()
