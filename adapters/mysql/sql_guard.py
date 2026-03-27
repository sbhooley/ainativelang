from __future__ import annotations

import re
from typing import Iterable, Set

from runtime.adapters.base import AdapterError

# Supports identifiers like users, `users`, "users", schema.users, `schema`.`users`.
_TABLE_RE = re.compile(
    r"\b(?:from|join|into|update|table)\s+((?:[`\"]?[A-Za-z_][A-Za-z0-9_]*[`\"]?\.)?[`\"]?[A-Za-z_][A-Za-z0-9_]*[`\"]?)",
    re.IGNORECASE,
)
_WRITE_PREFIXES = (
    "insert",
    "update",
    "delete",
    "replace",
    "create",
    "alter",
    "drop",
    "truncate",
    "grant",
    "revoke",
    "rename",
)
_LEADING_SQL_COMMENTS_RE = re.compile(r"^(?:\s+|--[^\n]*\n|#[^\n]*\n|/\*.*?\*/)+", re.DOTALL)
_CTE_WRITE_RE = re.compile(r"\b(insert|update|delete|replace)\b", re.IGNORECASE)


def assert_allowed_tables(sql: str, allow_tables: Set[str]) -> None:
    if not allow_tables:
        return
    refs = {_normalize_table_name(m.group(1)) for m in _TABLE_RE.finditer(sql)}
    blocked = [t for t in refs if t and t not in allow_tables]
    if blocked:
        raise AdapterError(f"mysql table blocked by allowlist: {blocked[0]}")


def assert_query_sql(sql: str) -> None:
    stmt = _normalize_sql_prefix(sql)
    if not stmt:
        raise AdapterError("mysql sql must be a non-empty string")
    if stmt.startswith("select") or stmt.startswith("with") or stmt.startswith("explain select") or stmt.startswith("explain analyze select"):
        return
    raise AdapterError("mysql query target requires SELECT/CTE statement")


def assert_execute_sql(sql: str, allow_write: bool) -> None:
    stmt = _normalize_sql_prefix(sql)
    if not stmt:
        raise AdapterError("mysql sql must be a non-empty string")
    if not allow_write:
        raise AdapterError("mysql write blocked: allow_write is false")
    if stmt.startswith("select"):
        raise AdapterError("mysql execute target requires write/ddl statement")
    if stmt.startswith("with"):
        # MySQL supports CTEs for SELECT and DML; write path must include write verb.
        if not _CTE_WRITE_RE.search(stmt):
            raise AdapterError("mysql execute CTE must contain write operation")
        return
    if not stmt.startswith(_WRITE_PREFIXES):
        raise AdapterError("mysql execute target requires write/ddl statement")


def normalize_params(raw: object) -> object:
    if raw is None:
        return ()
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise AdapterError("mysql params must be list/tuple/dict when provided")


def normalize_tables(values: Iterable[str] | None) -> Set[str]:
    return {_normalize_table_name(str(v).strip()) for v in (values or []) if str(v).strip()}


def _normalize_sql_prefix(sql: str) -> str:
    stmt = str(sql or "")
    while True:
        m = _LEADING_SQL_COMMENTS_RE.match(stmt)
        if not m:
            break
        stmt = stmt[m.end() :]
    return stmt.strip().lower()


def _normalize_table_name(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return s
    parts = [p.strip("`\"").strip() for p in s.split(".")]
    return parts[-1] if parts else s.strip("`\"").strip()
