from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from adapters.postgres import PostgresAdapter
from runtime.adapters.base import AdapterError, RuntimeAdapter

# Qualified or bare table name for ::regclass (schema defaults to public).
_REGCLASS_RE = re.compile(
    r"^(?:([a-z_][a-z0-9_]*)\.)?([a-z_][a-z0-9_]*)$",
    re.IGNORECASE,
)

_READ_VERBS = frozenset(
    {
        "test_enabled",
        "status",
        "search",
        "traverse",
        "shortest_path",
        "find_related",
    }
)
_ADMIN_VERBS = frozenset({"build", "auto_discover", "reset"})


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def validate_regclass(table: str, *, default_schema: str = "public") -> str:
    """Return canonical schema.table for use with ::regclass."""
    text = str(table or "").strip()
    if not text:
        raise AdapterError("pggraph table argument is required")
    m = _REGCLASS_RE.match(text)
    if not m:
        raise AdapterError(
            f"pggraph invalid table name {table!r} (expected schema.table or table, alphanumeric/underscore)"
        )
    schema = (m.group(1) or default_schema).lower()
    rel = m.group(2).lower()
    return f"{schema}.{rel}"


def _coerce_bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    raise AdapterError(f"pggraph expected boolean, got {val!r}")


def _coerce_int(val: Any, *, name: str, default: int, min_v: int = 0, max_v: Optional[int] = None) -> int:
    if val is None:
        out = default
    else:
        try:
            out = int(val)
        except (TypeError, ValueError) as e:
            raise AdapterError(f"pggraph {name} must be an integer") from e
    if out < min_v:
        raise AdapterError(f"pggraph {name} must be >= {min_v}")
    if max_v is not None and out > max_v:
        raise AdapterError(f"pggraph {name} must be <= {max_v}")
    return out


def _optional_regclass(arg: Any, *, default_schema: str) -> Optional[str]:
    if arg is None or (isinstance(arg, str) and not str(arg).strip()):
        return None
    return validate_regclass(str(arg), default_schema=default_schema)


class PggraphAdapter(RuntimeAdapter):
    """
    Evokoa pgGraph (https://github.com/Evokoa/pgGraph) — SQL functions in schema ``graph``.

    Requires the pgGraph PostgreSQL extension on the target server
    (``CREATE EXTENSION graph;`` plus ``graph.build()`` / ``graph.auto_discover()``).
    Delegates to :class:`PostgresAdapter` for connections.

    Read verbs: test_enabled, status, search, traverse, shortest_path, find_related.
    Admin verbs (``allow_admin``): build, auto_discover, reset.
    """

    def __init__(
        self,
        postgres: PostgresAdapter,
        *,
        max_depth: Optional[int] = None,
        max_rows: Optional[int] = None,
        default_schema: str = "public",
        allow_admin: bool = False,
    ):
        self._postgres = postgres
        self.max_depth = _coerce_int(
            max_depth if max_depth is not None else _env_int("AINL_PGGRAPH_MAX_DEPTH", 10),
            name="max_depth",
            default=10,
            min_v=1,
            max_v=100,
        )
        self.max_rows = _coerce_int(
            max_rows if max_rows is not None else _env_int("AINL_PGGRAPH_MAX_ROWS", 1000),
            name="max_rows",
            default=1000,
            min_v=1,
            max_v=10_000,
        )
        self.default_schema = (default_schema or "public").strip() or "public"
        self.allow_admin = bool(allow_admin) or _env_bool("AINL_PGGRAPH_ALLOW_ADMIN")

    def _query(self, sql: str, params: Optional[List[Any]] = None, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        ctx = context if context is not None else {}
        rows = self._postgres.call("query", [sql, params or []], ctx)
        if not isinstance(rows, list):
            raise AdapterError("pggraph expected list result from postgres query")
        return rows

    def _require_admin(self, verb: str) -> None:
        if not self.allow_admin:
            raise AdapterError(
                f"pggraph {verb} is admin-only; enable allow_admin "
                "(--pggraph-allow-admin or AINL_PGGRAPH_ALLOW_ADMIN=1)"
            )

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb in _ADMIN_VERBS:
            self._require_admin(verb)
        elif verb not in _READ_VERBS:
            raise AdapterError(f"unsupported pggraph target: {target}")

        if verb == "test_enabled":
            rows = self._query("SELECT graph.test_enabled() AS enabled", [], context)
            if rows:
                return {"enabled": rows[0].get("enabled")}
            return {"enabled": None}

        if verb == "status":
            return self._query("SELECT * FROM graph.status()", [], context)

        if verb == "search":
            if len(args) < 2:
                raise AdapterError("pggraph search requires property_key and property_value")
            key, value = str(args[0]), str(args[1])
            table = _optional_regclass(args[2] if len(args) > 2 else None, default_schema=self.default_schema)
            mode = str(args[3]).strip() if len(args) > 3 and args[3] is not None else "contains"
            max_rows = _coerce_int(
                args[4] if len(args) > 4 else None,
                name="max_rows",
                default=min(100, self.max_rows),
                min_v=1,
                max_v=self.max_rows,
            )
            if table:
                sql = (
                    "SELECT * FROM graph.search("
                    "%s, %s, table_filter := %s::regclass, mode := %s, max_rows := %s"
                    ")"
                )
                params = [key, value, table, mode, max_rows]
            else:
                sql = "SELECT * FROM graph.search(%s, %s, mode := %s, max_rows := %s)"
                params = [key, value, mode, max_rows]
            return self._query(sql, params, context)

        if verb == "traverse":
            if len(args) < 2:
                raise AdapterError("pggraph traverse requires seed_table and seed_id")
            seed_table = validate_regclass(str(args[0]), default_schema=self.default_schema)
            seed_id = str(args[1])
            depth = _coerce_int(
                args[2] if len(args) > 2 else None,
                name="max_depth",
                default=self.max_depth,
                min_v=1,
                max_v=100,
            )
            hydrate = _coerce_bool(args[3] if len(args) > 3 else None, default=False)
            max_rows = _coerce_int(
                args[4] if len(args) > 4 else None,
                name="max_rows",
                default=min(1000, self.max_rows),
                min_v=1,
                max_v=self.max_rows,
            )
            sql = (
                "SELECT * FROM graph.traverse("
                "%s::regclass, %s, max_depth := %s, hydrate := %s, max_rows := %s"
                ")"
            )
            return self._query(sql, [seed_table, seed_id, depth, hydrate, max_rows], context)

        if verb == "shortest_path":
            if len(args) < 4:
                raise AdapterError(
                    "pggraph shortest_path requires source_table, source_id, target_table, target_id"
                )
            src_table = validate_regclass(str(args[0]), default_schema=self.default_schema)
            src_id = str(args[1])
            tgt_table = validate_regclass(str(args[2]), default_schema=self.default_schema)
            tgt_id = str(args[3])
            depth = _coerce_int(
                args[4] if len(args) > 4 else None,
                name="max_depth",
                default=20,
                min_v=1,
                max_v=100,
            )
            hydrate = _coerce_bool(args[5] if len(args) > 5 else None, default=False)
            sql = (
                "SELECT * FROM graph.shortest_path("
                "%s::regclass, %s, %s::regclass, %s, max_depth := %s, hydrate := %s"
                ")"
            )
            return self._query(
                sql,
                [src_table, src_id, tgt_table, tgt_id, depth, hydrate],
                context,
            )

        if verb == "find_related":
            if len(args) < 2:
                raise AdapterError("pggraph find_related requires property_key and property_value")
            key, value = str(args[0]), str(args[1])
            source_table = _optional_regclass(
                args[2] if len(args) > 2 else None,
                default_schema=self.default_schema,
            )
            depth = _coerce_int(
                args[3] if len(args) > 3 else None,
                name="max_depth",
                default=self.max_depth,
                min_v=1,
                max_v=100,
            )
            max_rows = _coerce_int(
                args[4] if len(args) > 4 else None,
                name="max_rows",
                default=min(20, self.max_rows),
                min_v=1,
                max_v=self.max_rows,
            )
            if source_table:
                sql = (
                    "SELECT * FROM graph.find_related("
                    "%s, %s, source_table := %s::regclass, max_depth := %s, max_rows := %s"
                    ")"
                )
                params: List[Any] = [key, value, source_table, depth, max_rows]
            else:
                sql = (
                    "SELECT * FROM graph.find_related("
                    "%s, %s, max_depth := %s, max_rows := %s"
                    ")"
                )
                params = [key, value, depth, max_rows]
            return self._query(sql, params, context)

        if verb == "build":
            return self._query("SELECT * FROM graph.build()", [], context)

        if verb == "auto_discover":
            schema = str(args[0]).strip() if args else self.default_schema
            if not re.match(r"^[a-z_][a-z0-9_]*$", schema, re.IGNORECASE):
                raise AdapterError(f"pggraph invalid schema name {schema!r}")
            return self._query("SELECT * FROM graph.auto_discover(%s)", [schema], context)

        if verb == "reset":
            self._query("SELECT graph.reset()", [], context)
            return {"ok": True}

        raise AdapterError(f"unsupported pggraph target: {target}")
