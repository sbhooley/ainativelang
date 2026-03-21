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
_VALID_NAMESPACES: Set[str] = {"session", "long_term", "daily_log", "workflow", "ops"}


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
    - list(namespace, record_kind?, record_id_prefix?, updated_since?)
    - delete(namespace, record_kind, record_id)
    - prune(namespace?)

    This adapter is local/SQLite-backed, explicit, and non-magical; it does not
    implement vector search, policy semantics, or implicit recall.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        valid_namespaces: Optional[Set[str]] = None,
        default_ttl_by_namespace: Optional[Dict[str, Optional[int]]] = None,
        prune_strategy_by_namespace: Optional[Dict[str, str]] = None,
    ):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.valid_namespaces: Set[str] = set(valid_namespaces or _VALID_NAMESPACES)
        self.default_ttl_by_namespace: Dict[str, Optional[int]] = dict(default_ttl_by_namespace or {})
        self.prune_strategy_by_namespace: Dict[str, str] = dict(prune_strategy_by_namespace or {})
        self._op_counts: Dict[str, int] = {
            "operations": 0,
            "reads": 0,
            "writes": 0,
            "pruned": 0,
        }
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
                payload_json TEXT NOT NULL,
                metadata_json TEXT NULL
            )
            """
        )
        # Backward-compatible migration for existing databases.
        existing_cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(memory_records)").fetchall()
        }
        if "metadata_json" not in existing_cols:
            self._conn.execute("ALTER TABLE memory_records ADD COLUMN metadata_json TEXT NULL")
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

    def _normalize_ttl(self, namespace: str, ttl_seconds: Optional[int]) -> Optional[int]:
        if ttl_seconds is not None:
            return ttl_seconds
        if namespace in self.default_ttl_by_namespace:
            default_ttl = self.default_ttl_by_namespace[namespace]
            return self._validate_ttl(default_ttl)
        return None

    def _validate_metadata(self, metadata: Any) -> Optional[Dict[str, Any]]:
        if metadata is None:
            return None
        if not isinstance(metadata, dict):
            raise AdapterError("memory metadata must be a JSON object when provided")

        out: Dict[str, Any] = {}
        if "source" in metadata:
            source = metadata["source"]
            if source is not None and (not isinstance(source, str) or not source):
                raise AdapterError("memory metadata.source must be a non-empty string or null")
            out["source"] = source
        if "confidence" in metadata:
            confidence = metadata["confidence"]
            if confidence is not None:
                if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                    raise AdapterError("memory metadata.confidence must be a number or null")
                if confidence < 0.0 or confidence > 1.0:
                    raise AdapterError("memory metadata.confidence must be in range [0.0, 1.0]")
            out["confidence"] = confidence
        if "tags" in metadata:
            tags = metadata["tags"]
            if tags is None:
                out["tags"] = None
            else:
                if not isinstance(tags, list) or any((not isinstance(t, str) or not t) for t in tags):
                    raise AdapterError("memory metadata.tags must be a list of non-empty strings or null")
                out["tags"] = tags
        if "valid_at" in metadata:
            valid_at = metadata["valid_at"]
            if valid_at is not None and (not isinstance(valid_at, str) or not valid_at):
                raise AdapterError("memory metadata.valid_at must be a non-empty RFC3339 string or null")
            out["valid_at"] = valid_at
        if "last_accessed" in metadata:
            last_accessed = metadata["last_accessed"]
            if last_accessed is not None and (not isinstance(last_accessed, str) or not last_accessed):
                raise AdapterError(
                    "memory metadata.last_accessed must be a non-empty RFC3339 string or null"
                )
            out["last_accessed"] = last_accessed
        if "access_count" in metadata:
            access_count = metadata["access_count"]
            if access_count is not None:
                if isinstance(access_count, bool) or not isinstance(access_count, int) or access_count < 0:
                    raise AdapterError(
                        "memory metadata.access_count must be a non-negative integer or null"
                    )
            out["access_count"] = access_count

        # Preserve any future optional keys as additive metadata.
        for k, v in metadata.items():
            if k not in out:
                out[k] = v
        return out

    def _response(self, body: Dict[str, Any], *, read: int = 0, write: int = 0, pruned: int = 0) -> Dict[str, Any]:
        self._op_counts["operations"] += 1
        self._op_counts["reads"] += read
        self._op_counts["writes"] += write
        self._op_counts["pruned"] += pruned
        enriched = dict(body)
        enriched["stats"] = dict(self._op_counts)
        return enriched

    def _put_record(
        self,
        namespace: str,
        record_kind: str,
        record_id: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int],
        metadata: Optional[Dict[str, Any]],
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
                    (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace,
                    record_kind,
                    record_id,
                    now,
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    json.dumps(metadata, separators=(",", ":")) if metadata is not None else None,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE memory_records
                SET updated_at = ?, ttl_seconds = ?, payload_json = ?, metadata_json = ?
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    json.dumps(metadata, separators=(",", ":")) if metadata is not None else None,
                    namespace,
                    record_kind,
                    record_id,
                ),
            )
        self._conn.commit()
        return self._response({"ok": True, "created": created, "updated_at": now}, write=1)

    def _row_to_record(self, row: sqlite3.Row) -> Dict[str, Any]:
        payload = json.loads(row["payload_json"])
        metadata_raw = row["metadata_json"] if "metadata_json" in row.keys() else None
        metadata = json.loads(metadata_raw) if metadata_raw else None
        return {
            "namespace": row["namespace"],
            "record_kind": row["record_kind"],
            "record_id": row["record_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "ttl_seconds": row["ttl_seconds"],
            "payload": payload,
            "metadata": metadata,
        }

    def _get_record(self, namespace: str, record_kind: str, record_id: str) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json, metadata_json
            FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (namespace, record_kind, record_id),
        )
        row = cur.fetchone()
        if row is None:
            return self._response({"found": False, "record": None}, read=1)
        # TTL is advisory; if implemented on read, treat expired as not found.
        ttl_seconds = row["ttl_seconds"]
        if ttl_seconds is not None:
            try:
                created = datetime.fromisoformat(row["created_at"])
                age = (datetime.now(timezone.utc) - created).total_seconds()
                if age > ttl_seconds:
                    return self._response({"found": False, "record": None}, read=1)
            except Exception:
                # If timestamp parsing fails, fall back to returning the record.
                pass
        return self._response({"found": True, "record": self._row_to_record(row)}, read=1)

    def _append_record(
        self,
        namespace: str,
        record_kind: str,
        record_id: str,
        entry: Dict[str, Any],
        ttl_seconds: Optional[int],
        metadata: Optional[Dict[str, Any]],
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
                    (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace,
                    record_kind,
                    record_id,
                    created_at,
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    json.dumps(metadata, separators=(",", ":")) if metadata is not None else None,
                ),
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
                SET updated_at = ?, ttl_seconds = ?, payload_json = ?, metadata_json = COALESCE(?, metadata_json)
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (
                    now,
                    ttl_seconds,
                    json.dumps(payload, separators=(",", ":")),
                    json.dumps(metadata, separators=(",", ":")) if metadata is not None else None,
                    namespace,
                    record_kind,
                    record_id,
                ),
            )
        self._conn.commit()
        return self._response({"ok": True, "updated_at": now}, write=1)

    def _delete_record(
        self,
        namespace: str,
        record_kind: str,
        record_id: str,
    ) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute(
            """
            DELETE FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (namespace, record_kind, record_id),
        )
        deleted = cur.rowcount > 0
        self._conn.commit()
        return self._response({"ok": True, "deleted": deleted}, write=1 if deleted else 0)

    def _prune(self, namespace: Optional[str]) -> Dict[str, Any]:
        """
        Remove expired records based on TTL and created_at, optionally scoped
        to a single namespace.
        """
        cur = self._conn.cursor()
        sql = """
        SELECT namespace, record_kind, record_id, created_at, ttl_seconds
        FROM memory_records
        WHERE ttl_seconds IS NOT NULL
        """
        params: List[Any] = []
        if namespace:
            sql += " AND namespace = ?"
            params.append(namespace)

        cur.execute(sql, params)
        rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        keys_to_delete: List[tuple[str, str, str]] = []

        for row in rows:
            strategy = self.prune_strategy_by_namespace.get(row["namespace"], "ttl_only")
            if strategy == "none":
                continue
            ttl = row["ttl_seconds"]
            if ttl is None:
                continue
            try:
                created = datetime.fromisoformat(row["created_at"])
            except Exception:
                # If timestamp parsing fails, skip pruning this record.
                continue
            age = (now - created).total_seconds()
            if age > ttl:
                keys_to_delete.append(
                    (row["namespace"], row["record_kind"], row["record_id"])
                )

        pruned = 0
        for ns, rk, rid in keys_to_delete:
            cur.execute(
                """
                DELETE FROM memory_records
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (ns, rk, rid),
            )
            pruned += cur.rowcount

        self._conn.commit()
        return self._response({"ok": True, "pruned": pruned}, write=pruned, pruned=pruned)

    def _list_records(
        self,
        namespace: str,
        record_kind: Optional[str],
        record_id_prefix: Optional[str],
        updated_since: Optional[str],
        filters: Optional[Dict[str, Any]],
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

        if filters:
            created_after = filters.get("created_after")
            if created_after:
                sql.append("AND created_at >= ?")
                params.append(created_after)
            created_before = filters.get("created_before")
            if created_before:
                sql.append("AND created_at <= ?")
                params.append(created_before)
            updated_after = filters.get("updated_after")
            if updated_after:
                sql.append("AND updated_at >= ?")
                params.append(updated_after)
            updated_before = filters.get("updated_before")
            if updated_before:
                sql.append("AND updated_at <= ?")
                params.append(updated_before)
            source = filters.get("source")
            if source:
                sql.append("AND json_extract(metadata_json, '$.source') = ?")
                params.append(source)
            valid_at_after = filters.get("valid_at_after")
            if valid_at_after:
                sql.append("AND json_extract(metadata_json, '$.valid_at') >= ?")
                params.append(valid_at_after)
            valid_at_before = filters.get("valid_at_before")
            if valid_at_before:
                sql.append("AND json_extract(metadata_json, '$.valid_at') <= ?")
                params.append(valid_at_before)
            since_last_accessed = filters.get("since_last_accessed")
            if since_last_accessed:
                sql.append("AND json_extract(metadata_json, '$.last_accessed') >= ?")
                params.append(since_last_accessed)
            tags_any = filters.get("tags_any")
            if tags_any:
                placeholders = ",".join(["?"] * len(tags_any))
                sql.append(
                    "AND EXISTS (SELECT 1 FROM json_each(COALESCE(json_extract(metadata_json, '$.tags'), '[]')) WHERE value IN ("
                    + placeholders
                    + "))"
                )
                params.extend(tags_any)
            tags_all = filters.get("tags_all")
            if tags_all:
                for tag in tags_all:
                    sql.append(
                        "AND EXISTS (SELECT 1 FROM json_each(COALESCE(json_extract(metadata_json, '$.tags'), '[]')) WHERE value = ?)"
                    )
                    params.append(tag)

        # Deterministic ordering: by record_kind then record_id.
        sql.append("ORDER BY record_kind ASC, record_id ASC")

        limit = None
        offset = None
        if filters:
            limit = filters.get("limit")
            offset = filters.get("offset")
        if limit is not None:
            sql.append("LIMIT ?")
            params.append(limit)
            if offset is not None:
                sql.append("OFFSET ?")
                params.append(offset)
        elif offset is not None:
            # SQLite requires LIMIT when OFFSET is present.
            sql.append("LIMIT -1 OFFSET ?")
            params.append(offset)
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
        return self._response({"items": items}, read=len(items))

    def _validate_list_filters(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise AdapterError("memory.list filters must be an object when provided")
        allowed = {
            "tags_any",
            "tags_all",
            "created_after",
            "created_before",
            "updated_after",
            "updated_before",
            "valid_at_after",
            "valid_at_before",
            "since_last_accessed",
            "source",
            "limit",
            "offset",
        }
        unknown = [k for k in value.keys() if k not in allowed]
        if unknown:
            raise AdapterError(f"memory.list filters contain unsupported keys: {', '.join(unknown)}")

        out: Dict[str, Any] = {}
        for k in (
            "created_after",
            "created_before",
            "updated_after",
            "updated_before",
            "valid_at_after",
            "valid_at_before",
            "since_last_accessed",
            "source",
        ):
            if k in value and value[k] is not None:
                if not isinstance(value[k], str) or not value[k]:
                    raise AdapterError(f"memory.list filter '{k}' must be a non-empty string")
                out[k] = value[k]
        for k in ("tags_any", "tags_all"):
            if k in value and value[k] is not None:
                v = value[k]
                if not isinstance(v, list) or any((not isinstance(t, str) or not t) for t in v):
                    raise AdapterError(f"memory.list filter '{k}' must be a list of non-empty strings")
                out[k] = v
        for k in ("limit", "offset"):
            if k in value and value[k] is not None:
                v = value[k]
                if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                    raise AdapterError(f"memory.list filter '{k}' must be a non-negative integer")
                out[k] = v
        return out

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().lower()
        if verb not in {"put", "get", "append", "list", "delete", "prune"}:
            raise AdapterError(f"memory adapter unsupported verb: {target}")

        if verb == "list":
            if len(args) < 1:
                raise AdapterError("memory.list requires at least namespace argument")
            namespace = self._validate_namespace(args[0])
            record_kind = args[1] if len(args) > 1 else None
            record_id_prefix = args[2] if len(args) > 2 else None
            updated_since = args[3] if len(args) > 3 else None
            filters = self._validate_list_filters(args[4]) if len(args) > 4 else {}
            if record_kind is not None and (not isinstance(record_kind, str) or not record_kind):
                raise AdapterError("memory.list record_kind, when provided, must be a non-empty string")
            if record_id_prefix is not None and (not isinstance(record_id_prefix, str) or not record_id_prefix):
                raise AdapterError("memory.list record_id_prefix, when provided, must be a non-empty string")
            if updated_since is not None and (not isinstance(updated_since, str) or not updated_since):
                raise AdapterError("memory.list updated_since, when provided, must be a non-empty ISO timestamp string")
            return self._list_records(namespace, record_kind, record_id_prefix, updated_since, filters)

        if verb == "prune":
            ns_filter: Optional[str]
            if len(args) >= 1 and args[0] is not None:
                ns_filter = self._validate_namespace(args[0])
            else:
                ns_filter = None
            return self._prune(ns_filter)

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
            metadata = self._validate_metadata(args[5]) if len(args) > 5 else self._validate_metadata(payload.get("_metadata"))
            normalized_ttl = self._normalize_ttl(namespace, ttl)
            return self._put_record(namespace, record_kind, record_id, payload, normalized_ttl, metadata)

        if verb == "get":
            return self._get_record(namespace, record_kind, record_id)

        if verb == "delete":
            return self._delete_record(namespace, record_kind, record_id)

        # append
        if len(args) < 4:
            raise AdapterError("memory.append requires entry argument")
        entry = self._validate_payload_object(args[3])
        ttl = self._validate_ttl(args[4]) if len(args) > 4 else None
        metadata = self._validate_metadata(args[5]) if len(args) > 5 else None
        normalized_ttl = self._normalize_ttl(namespace, ttl)
        return self._append_record(namespace, record_kind, record_id, entry, normalized_ttl, metadata)
