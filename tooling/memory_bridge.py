import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tooling.memory_validator import ValidationIssue, validate_records_obj


DEFAULT_DB_PATH = os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")


JsonObject = Dict[str, Any]


@dataclass
class ExportOptions:
    db_path: str
    namespaces: Optional[List[str]] = None
    record_kinds: Optional[List[str]] = None


@dataclass
class ImportResult:
    ok: bool
    inserted: int
    updated: int
    errors: List[ValidationIssue]


def _open_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)


def _row_to_envelope(row: sqlite3.Row) -> JsonObject:
    payload = json.loads(row["payload_json"])
    provenance = {
        "source_system": "ainl.memory",
        "origin_uri": None,
        "authored_by": "bot",
        "confidence": None,
    }
    flags = {
        "authoritative": False,
        "ephemeral": False,
        "curated": False,
    }
    return {
        "namespace": row["namespace"],
        "record_kind": row["record_kind"],
        "record_id": row["record_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "ttl_seconds": row["ttl_seconds"],
        "payload": payload,
        "provenance": provenance,
        "flags": flags,
    }


def export_records(options: ExportOptions) -> List[JsonObject]:
    """
    Export memory records from the SQLite backing store into canonical
    JSON envelopes suitable for further tooling / interoperability.
    """
    db_path = options.db_path or DEFAULT_DB_PATH
    conn = _open_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
    SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json
    FROM memory_records
    """
    clauses: List[str] = []
    params: List[Any] = []

    if options.namespaces:
        placeholders = ",".join("?" for _ in options.namespaces)
        clauses.append(f"namespace IN ({placeholders})")
        params.extend(options.namespaces)

    if options.record_kinds:
        placeholders = ",".join("?" for _ in options.record_kinds)
        clauses.append(f"record_kind IN ({placeholders})")
        params.extend(options.record_kinds)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [_row_to_envelope(r) for r in rows]


def import_records(db_path: str, records: Iterable[JsonObject]) -> ImportResult:
    """
    Import canonical envelopes into the memory SQLite backing store.

    This function validates the envelopes against the v1 memory contract and
    then applies put-like semantics for each record. Provenance/flags are
    preserved inside the payload under reserved keys (_provenance, _flags)
    without changing core adapter behavior.
    """
    # Validate first
    issues = validate_records_obj(list(records))
    errors = [i for i in issues if i.kind == "error"]
    if errors:
        return ImportResult(ok=False, inserted=0, updated=0, errors=errors)

    conn = _open_conn(db_path or DEFAULT_DB_PATH)
    conn.execute(
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_ns_kind_id ON memory_records(namespace, record_kind, record_id)"
    )
    cur = conn.cursor()

    inserted = 0
    updated = 0

    for env in records:
        ns = env.get("namespace")
        rk = env.get("record_kind")
        rid = env.get("record_id")
        ttl = env.get("ttl_seconds")
        created_at = env.get("created_at")
        updated_at = env.get("updated_at")
        payload = env.get("payload") or {}

        # Preserve provenance/flags inside payload without altering core adapter semantics.
        prov = env.get("provenance")
        flags = env.get("flags")
        if prov:
            payload.setdefault("_provenance", prov)
        if flags:
            payload.setdefault("_flags", flags)

        # Determine if record exists
        cur.execute(
            """
            SELECT id FROM memory_records
            WHERE namespace = ? AND record_kind = ? AND record_id = ?
            """,
            (ns, rk, rid),
        )
        row = cur.fetchone()
        created = row is None

        if created:
            inserted += 1
            cur.execute(
                """
                INSERT INTO memory_records
                    (namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ns,
                    rk,
                    rid,
                    created_at or updated_at or "",
                    updated_at or created_at or "",
                    ttl,
                    json.dumps(payload, separators=(",", ":")),
                ),
            )
        else:
            updated += 1
            cur.execute(
                """
                UPDATE memory_records
                SET created_at = COALESCE(?, created_at),
                    updated_at = COALESCE(?, updated_at),
                    ttl_seconds = ?,
                    payload_json = ?
                WHERE namespace = ? AND record_kind = ? AND record_id = ?
                """,
                (
                    created_at,
                    updated_at,
                    ttl,
                    json.dumps(payload, separators=(",", ":")),
                    ns,
                    rk,
                    rid,
                ),
            )

    conn.commit()
    return ImportResult(ok=True, inserted=inserted, updated=updated, errors=[])

