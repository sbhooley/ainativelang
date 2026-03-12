from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from runtime.adapters.base import AdapterError, RuntimeAdapter


DEFAULT_DB_PATH = os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")

# v1 namespace whitelist
_VALID_NAMESPACES: Set[str] = {"session", "long_term", "daily_log", "workflow"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryAdapter(RuntimeAdapter):
    """
    Extension-level memory adapter.

    Records are keyed by (namespace, record_kind, record_id) and store a JSON
    object payload plus basic timestamps and optional ttl_seconds.

    Verbs (v1):
    - put(namespace, record_kind, record_id, payload, ttl_seconds?)
    - get(namespace, record_kind, record_id)
    - append(namespace, record_kind, record_id, entry, ttl_seconds?)
    - list(namespace, record_kind?, record_id_prefix?)

    This adapter is local/SQLite-backed, explicit, and non-magical; it does not
    implement vector search, policy semantics, or implicit recall.
    """

    def __init__(self, db_path: Optional[str] = None, *, valid_namespaces: Optional[Set[str]] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.valid_namespaces: Set[str] = set(valid_namespaces or _VALID_NAMESPACES)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_ns_kind_id ON memory_records(namespace, record_kind, record_id)"
        )
        self._conn.commit()

    def _validate_namespace(self, namespace: Any) -> str:
        if not isinstance(namespace, str) or not namespace:
            raise AdapterError("memory namespace must be a non-empty string")
        if namespace not in self.valid_namespaces:
            raise AdapterError(f"memory namespace '{namespace}' is not allowed in v1")
        return namespace

    def _validate_key(self, namespace: Any, record_kind: Any, record_id: Any) -> None:
        # Namespace validation is shared with list; record_kind/record_id are required here.
        self._validate_namespace(namespace)
        if not isinstance(record_kind, str) or not record_kind:
            raise AdapterError("memory record_kind must be a non-empty string")
        if not isinstance(record_id, str) or not record_id:
            raise AdapterError("memory record_id must be a non-empty string")

    def _validate_payload_object(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdapterError("memory payload must be a JSON object")
        return payload

    def _validate_ttl(self, ttl_seconds: Any) -> Optional[int]:
        if ttl_seconds is None:
            return None
        if isinstance(ttl_seconds, bool):
            # bool is a subclass of int; treat as invalid here
            raise AdapterError("memory ttl_seconds must be an integer or null")
        if not isinstance(ttl_seconds, int):
            raise AdapterError("memory ttl_seconds must be an integer or null")
        return ttl_seconds

    def _put_record(
        self,
        namespace: str,
        record_kind: str,
        record_id: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int],
    ) -> Dict[str, Any]:
        now = _utc_now_iso()
        cur = self._conn.cursor()
        self._conn.row_factory = sqlite3.Row
        cur.execute(
            """
            SELECT id FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (namespace, record_kind, record_id),
        )
        row = cur.fetchone()
        created = row is None
        if created:
            cur.execute(
                """
                INSERT INTO memory_records
                    (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (namespace, record_kind, record_id, now, now, ttl_seconds, json.dumps(payload, separators=(",", ":"))),
            )
        else:
            cur.execute(
                """
                UPDATE memory_records
                SET updated_at = ?, ttl_seconds = ?, payload_json = ?
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    namespace,
                    record_kind,
                    record_id,
                ),
            )
        self._conn.commit()
        return {"ok": True, "created": created, "updated_at": now}

    def _row_to_record(self, row: sqlite3.Row) -> Dict[str, Any]:
        payload = json.loads(row["payload_json"])
        return {
            "namespace": row["namespace"],
            "record_kind": row["record_kind"],
            "record_id": row["record_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "ttl_seconds": row["ttl_seconds"],
            "payload": payload,
        }

    def _get_record(self, namespace: str, record_kind: str, record_id: str) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json
            FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (namespace, record_kind, record_id),
        )
        row = cur.fetchone()
        if row is None:
            return {"found": False, "record": None}
        # TTL is advisory; if implemented on read, treat expired as not found.
        ttl_seconds = row["ttl_seconds"]
        if ttl_seconds is not None:
            try:
                created = datetime.fromisoformat(row["created_at"])
                age = (datetime.now(timezone.utc) - created).total_seconds()
                if age > ttl_seconds:
                    return {"found": False, "record": None}
            except Exception:
                # If timestamp parsing fails, fall back to returning the record.
                pass
        return {"found": True, "record": self._row_to_record(row)}

    def _append_record(
        self,
        namespace: str,
        record_kind: str,
        record_id: str,
        entry: Dict[str, Any],
        ttl_seconds: Optional[int],
    ) -> Dict[str, Any]:
        now = _utc_now_iso()
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT payload_json FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (namespace, record_kind, record_id),
        )
        row = cur.fetchone()
        if row is None:
            # Create new log-shaped payload.
            payload = {"entries": [entry]}
            created_at = now
            cur.execute(
                """
                INSERT INTO memory_records
                    (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (namespace, record_kind, record_id, created_at, now, ttl_seconds, json.dumps(payload, separators=(",", ":"))),
            )
        else:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError as e:
                raise AdapterError(f"memory.append failed to parse existing payload JSON: {e}") from e
            entries = payload.get("entries")
            if not isinstance(entries, list):
                raise AdapterError("memory.append requires existing payload with 'entries' list")
            entries.append(entry)
            cur.execute(
                """
                UPDATE memory_records
                SET updated_at = ?, ttl_seconds = ?, payload_json = ?
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    namespace,
                    record_kind,
                    record_id,
                ),
            )
        self._conn.commit()
        return {"ok": True, "updated_at": now}

    def _list_records(
        self,
        namespace: str,
        record_kind: Optional[str],
        record_id_prefix: Optional[str],
        updated_since: Optional[str],
    ) -> Dict[str, Any]:
        cur = self._conn.cursor()
        sql = [
            """
            SELECT record_kind, record_id, created_at, updated_at, ttl_seconds
            FROM memory_records
            WHERE namespace = ?
            """
        ]
        params: List[Any] = [namespace]

        if record_kind:
            sql.append("AND record_kind = ?")
            params.append(record_kind)

        if record_id_prefix:
            sql.append("AND record_id LIKE ?")
            params.append(f"{record_id_prefix}%")

        if updated_since:
            sql.append("AND updated_at >= ?")
            params.append(updated_since)

        # Deterministic ordering: by record_kind then record_id.
        sql.append("ORDER BY record_kind ASC, record_id ASC")
        cur.execute(" ".join(sql), params)
        rows = cur.fetchall()
        items = []
        for row in rows:
            items.append(
                {
                    "record_kind": row["record_kind"],
                    "record_id": row["record_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "ttl_seconds": row["ttl_seconds"],
                }
            )
        return {"items": items}

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().lower()
        if verb not in {"put", "get", "append", "list"}:
            raise AdapterError(f"memory adapter unsupported verb: {target}")

        if verb == "list":
            if len(args) < 1:
                raise AdapterError("memory.list requires at least namespace argument")
            namespace = self._validate_namespace(args[0])
            record_kind = args[1] if len(args) > 1 else None
            record_id_prefix = args[2] if len(args) > 2 else None
            updated_since = args[3] if len(args) > 3 else None
            if record_kind is not None and (not isinstance(record_kind, str) or not record_kind):
                raise AdapterError("memory.list record_kind, when provided, must be a non-empty string")
            if record_id_prefix is not None and (not isinstance(record_id_prefix, str) or not record_id_prefix):
                raise AdapterError("memory.list record_id_prefix, when provided, must be a non-empty string")
            if updated_since is not None and (not isinstance(updated_since, str) or not updated_since):
                raise AdapterError("memory.list updated_since, when provided, must be a non-empty ISO timestamp string")
            return self._list_records(namespace, record_kind, record_id_prefix, updated_since)

        if len(args) < 3:
            raise AdapterError("memory adapter requires at least namespace, record_kind, record_id arguments")

        namespace = args[0]
        record_kind = args[1]
        record_id = args[2]
        self._validate_key(namespace, record_kind, record_id)

        if verb == "put":
            if len(args) < 4:
                raise AdapterError("memory.put requires payload argument")
            payload = self._validate_payload_object(args[3])
            ttl = self._validate_ttl(args[4]) if len(args) > 4 else None
            return self._put_record(namespace, record_kind, record_id, payload, ttl)

        if verb == "get":
            return self._get_record(namespace, record_kind, record_id)

        # append
        if len(args) < 4:
            raise AdapterError("memory.append requires entry argument")
        entry = self._validate_payload_object(args[3])
        ttl = self._validate_ttl(args[4]) if len(args) > 4 else None
        return self._append_record(namespace, record_kind, record_id, entry, ttl)

