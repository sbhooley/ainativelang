#!/usr/bin/env python3
"""
Memory retention report (read-only).

Inspects the SQLite memory backing store and produces a summary of record counts,
TTL coverage, age distribution, and records expiring soon or already expired.
Intended for operator hygiene and visibility; does not modify the store or
change runtime/schema.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")

# "Expiring soon" = expiry time (created_at + ttl_seconds) is within this many seconds from now
EXPIRE_SOON_SECONDS = 86400  # 24 hours


def _open_conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=5.0)


def _where_clause(
    namespace: Optional[str],
    record_kind: Optional[str],
) -> tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    if record_kind:
        clauses.append("record_kind = ?")
        params.append(record_kind)
    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def run_report(
    db_path: str,
    namespace: Optional[str] = None,
    record_kind: Optional[str] = None,
    expire_soon_seconds: int = EXPIRE_SOON_SECONDS,
) -> Dict[str, Any]:
    """
    Query the memory store and build the report structure.
    All queries are read-only SELECTs.
    """
    if not Path(db_path).exists():
        return {
            "error": f"Database not found: {db_path}",
            "summary": {"total_records": 0},
            "by_namespace": [],
            "by_record_kind": [],
            "ttl_coverage": {"with_ttl": 0, "without_ttl": 0},
            "age_distribution": {},
            "expiring_soon_count": 0,
            "expiring_soon": [],
            "expired_count": 0,
            "expired_sample": [],
        }

    where_sql, where_params = _where_clause(namespace, record_kind)

    conn = _open_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Total
    cur.execute("SELECT COUNT(*) AS n FROM memory_records" + where_sql, where_params)
    total = cur.fetchone()["n"]

    # By namespace
    cur.execute(
        "SELECT namespace, COUNT(*) AS cnt FROM memory_records"
        + where_sql
        + " GROUP BY namespace ORDER BY cnt DESC",
        where_params,
    )
    by_namespace = [{"namespace": r["namespace"], "count": r["cnt"]} for r in cur.fetchall()]

    # By record_kind
    cur.execute(
        "SELECT record_kind, COUNT(*) AS cnt FROM memory_records"
        + where_sql
        + " GROUP BY record_kind ORDER BY cnt DESC",
        where_params,
    )
    by_record_kind = [{"record_kind": r["record_kind"], "count": r["cnt"]} for r in cur.fetchall()]

    # TTL coverage
    ttl_cond = " AND ttl_seconds IS NOT NULL" if where_sql else " WHERE ttl_seconds IS NOT NULL"
    cur.execute(
        "SELECT COUNT(*) AS n FROM memory_records" + where_sql + ttl_cond,
        where_params,
    )
    with_ttl = cur.fetchone()["n"]
    without_ttl = total - with_ttl

    # Age distribution (based on updated_at; buckets: last 24h, 24h-7d, 7d-30d, 30d+)
    # SQLite: julianday('now') - julianday(updated_at) gives days
    age_sql = """
    SELECT
      CASE
        WHEN julianday('now') - julianday(updated_at) <= 1 THEN 'last_24h'
        WHEN julianday('now') - julianday(updated_at) <= 7 THEN '24h_to_7d'
        WHEN julianday('now') - julianday(updated_at) <= 30 THEN '7d_to_30d'
        ELSE 'older_than_30d'
      END AS bucket,
      COUNT(*) AS cnt
    FROM memory_records
    """ + where_sql + """
    GROUP BY bucket
    ORDER BY cnt DESC
    """
    cur.execute(age_sql, where_params)
    age_distribution = {r["bucket"]: r["cnt"] for r in cur.fetchall()}

    # Expired: created_at + ttl_seconds < now (advisory; matches adapter's read-time check)
    expired_cond = (
        (" AND " if where_sql else " WHERE ")
        + "ttl_seconds IS NOT NULL AND datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') < datetime('now')"
    )
    expired_sql = """
    SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds
    FROM memory_records
    """ + where_sql + expired_cond + """
    ORDER BY created_at ASC
    LIMIT 100
    """
    cur.execute(expired_sql, where_params)
    expired_rows = cur.fetchall()
    cur.execute(
        "SELECT COUNT(*) AS n FROM memory_records" + where_sql + expired_cond,
        where_params,
    )
    expired_count = cur.fetchone()["n"]
    expired_sample = [
        {
            "namespace": r["namespace"],
            "record_kind": r["record_kind"],
            "record_id": r["record_id"],
            "created_at": r["created_at"],
            "ttl_seconds": r["ttl_seconds"],
        }
        for r in expired_rows
    ]

    # Expiring soon: expiry between now and now + expire_soon_seconds
    soon_cond = (
        (" AND " if where_sql else " WHERE ")
        + "ttl_seconds IS NOT NULL "
        + "AND datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') >= datetime('now') "
        + "AND datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') <= datetime('now', '+' || ? || ' seconds')"
    )
    soon_sql = """
    SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds,
           datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') AS expires_at
    FROM memory_records
    """ + where_sql + soon_cond + """
    ORDER BY expires_at ASC
    LIMIT 200
    """
    cur.execute(soon_sql, where_params + [expire_soon_seconds])
    soon_rows = cur.fetchall()
    cur.execute(
        "SELECT COUNT(*) AS n FROM memory_records" + where_sql + soon_cond,
        where_params + [expire_soon_seconds],
    )
    expiring_soon_count = cur.fetchone()["n"]
    expiring_soon = [
        {
            "namespace": r["namespace"],
            "record_kind": r["record_kind"],
            "record_id": r["record_id"],
            "created_at": r["created_at"],
            "ttl_seconds": r["ttl_seconds"],
            "expires_at": r["expires_at"],
        }
        for r in soon_rows
    ]

    conn.close()

    return {
        "db_path": db_path,
        "namespace_filter": namespace,
        "record_kind_filter": record_kind,
        "expire_soon_seconds": expire_soon_seconds,
        "summary": {
            "total_records": total,
            "with_ttl": with_ttl,
            "without_ttl": without_ttl,
            "expired_count": expired_count,
            "expiring_soon_count": expiring_soon_count,
        },
        "by_namespace": by_namespace,
        "by_record_kind": by_record_kind,
        "ttl_coverage": {"with_ttl": with_ttl, "without_ttl": without_ttl},
        "age_distribution": age_distribution,
        "expiring_soon_count": expiring_soon_count,
        "expiring_soon": expiring_soon,
        "expired_count": expired_count,
        "expired_sample": expired_sample,
    }


def format_plain(data: Dict[str, Any]) -> str:
    """Format report as plain text."""
    if "error" in data:
        return f"Error: {data['error']}\n"

    lines: List[str] = []
    lines.append("Memory retention report (read-only)")
    lines.append("=" * 50)
    lines.append(f"DB: {data.get('db_path', '')}")
    if data.get("namespace_filter"):
        lines.append(f"Namespace filter: {data['namespace_filter']}")
    if data.get("record_kind_filter"):
        lines.append(f"Record kind filter: {data['record_kind_filter']}")
    lines.append("")

    s = data.get("summary", {})
    lines.append("Overall totals")
    lines.append("-" * 30)
    lines.append(f"  Total records:     {s.get('total_records', 0)}")
    lines.append(f"  With TTL:           {s.get('with_ttl', 0)}")
    lines.append(f"  Without TTL:        {s.get('without_ttl', 0)}")
    lines.append(f"  Expired (in DB):    {s.get('expired_count', 0)}")
    lines.append(f"  Expiring soon (24h): {s.get('expiring_soon_count', 0)}")
    lines.append("")

    lines.append("By namespace")
    lines.append("-" * 30)
    for row in data.get("by_namespace", []):
        lines.append(f"  {row['namespace']}: {row['count']}")
    if not data.get("by_namespace"):
        lines.append("  (none)")
    lines.append("")

    lines.append("By record kind")
    lines.append("-" * 30)
    for row in data.get("by_record_kind", [])[:20]:
        lines.append(f"  {row['record_kind']}: {row['count']}")
    if len(data.get("by_record_kind", [])) > 20:
        lines.append(f"  ... and {len(data['by_record_kind']) - 20} more kinds")
    if not data.get("by_record_kind"):
        lines.append("  (none)")
    lines.append("")

    lines.append("Age distribution (by updated_at)")
    lines.append("-" * 30)
    for bucket in ["last_24h", "24h_to_7d", "7d_to_30d", "older_than_30d"]:
        cnt = data.get("age_distribution", {}).get(bucket, 0)
        lines.append(f"  {bucket}: {cnt}")
    lines.append("")

    if data.get("expired_count", 0) > 0:
        lines.append("Expired but still present (sample)")
        lines.append("-" * 30)
        for row in data.get("expired_sample", [])[:10]:
            rid = row["record_id"]
            rid_short = rid[:40] + "..." if len(rid) > 40 else rid
            lines.append(f"  {row['namespace']} / {row['record_kind']} / {rid_short}")
        if data["expired_count"] > 10:
            lines.append(f"  ... and {data['expired_count'] - 10} more (run memory.prune to remove)")
        lines.append("")

    if data.get("expiring_soon_count", 0) > 0:
        lines.append("Expiring within 24h (sample)")
        lines.append("-" * 30)
        for row in data.get("expiring_soon", [])[:10]:
            rid = row["record_id"]
            rid_short = rid[:30] + "..." if len(rid) > 30 else rid
            lines.append(f"  {row.get('expires_at')} {row['namespace']}/{row['record_kind']} {rid_short}")
        if data["expiring_soon_count"] > 10:
            lines.append(f"  ... and {data['expiring_soon_count'] - 10} more")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Read-only memory retention report: counts, TTL coverage, age, expiring/expired.",
    )
    ap.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", DEFAULT_DB_PATH),
        help="Path to SQLite memory DB (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    ap.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Filter report to this namespace only.",
    )
    ap.add_argument(
        "--record-kind",
        type=str,
        default=None,
        dest="record_kind",
        help="Filter report to this record_kind only.",
    )
    ap.add_argument(
        "--expire-soon-seconds",
        type=int,
        default=EXPIRE_SOON_SECONDS,
        help=f"Treat records expiring within this many seconds as 'expiring soon' (default: {EXPIRE_SOON_SECONDS}).",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    args = ap.parse_args()

    data = run_report(
        args.db_path,
        namespace=args.namespace,
        record_kind=args.record_kind,
        expire_soon_seconds=args.expire_soon_seconds,
    )

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_plain(data))


if __name__ == "__main__":
    main()
