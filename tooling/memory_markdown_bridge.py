import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DB_PATH = os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")


def _open_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)


def _ensure_daily_log_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)


def _render_daily_log_markdown(record: Dict[str, Any]) -> str:
    """
    Render a single daily_log.note record to markdown.

    record is the object returned by the memory adapter: it must contain
    namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload.
    """
    ns = record.get("namespace")
    rk = record.get("record_kind")
    rid = record.get("record_id")
    payload = record.get("payload") or {}
    entries: List[Dict[str, Any]] = []

    # Preferred log shape: payload["entries"] is a list of objects
    raw_entries = payload.get("entries")
    if isinstance(raw_entries, list):
        for e in raw_entries:
            if isinstance(e, dict):
                entries.append(e)
    else:
        # Fallback: single note-style payload with ts/text
        if isinstance(payload, dict) and ("ts" in payload or "text" in payload):
            entries.append(payload)

    # Sort entries by ts when present
    def _ts_key(e: Dict[str, Any]) -> str:
        ts = e.get("ts")
        return str(ts) if ts is not None else ""

    entries.sort(key=_ts_key)

    lines: List[str] = []
    lines.append("---")
    lines.append(f"ainl_namespace: {ns}")
    lines.append(f"ainl_record_kind: {rk}")
    lines.append(f"ainl_record_id: {rid}")
    lines.append(f"exported_from: ainl.memory")
    lines.append("---")
    lines.append("")
    lines.append(f"# Daily Log – {rid}")
    lines.append("")

    if not entries:
        lines.append("_No entries recorded in memory for this day._")
    else:
        for e in entries:
            ts = e.get("ts", "")
            text = e.get("text", "")
            # Simple, deterministic bullet format
            if ts:
                lines.append(f"- [{ts}] {text}")
            else:
                lines.append(f"- {text}")

    return "\n".join(lines) + "\n"


def export_daily_log_markdown(
    db_path: str,
    output_root: Path,
    *,
    overwrite: bool = False,
) -> List[Path]:
    """
    Export daily_log.note records from the SQLite memory store to markdown files.

    Each record with (namespace='daily_log', record_kind='daily_log.note', record_id='<YYYY-MM-DD>')
    is rendered to:

        output_root/<YYYY>/<YYYY-MM-DD>.md

    Returns the list of paths written.
    """
    conn = _open_conn(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT namespace, record_kind, record_id, created_at, updated_at, ttl_seconds, payload_json
        FROM memory_records
        WHERE namespace = 'daily_log' AND record_kind = 'daily_log.note'
        """
    )
    rows = cur.fetchall()

    written: List[Path] = []

    for row in rows:
        record_id = row["record_id"]
        # Expect record_id of form YYYY-MM-DD; use first 4 chars as year fallback.
        year = str(record_id)[:4] or "unknown"
        day_dir = output_root / year
        _ensure_daily_log_dir(day_dir)
        path = day_dir / f"{record_id}.md"
        if path.exists() and not overwrite:
            continue

        import json as _json

        record = {
            "namespace": row["namespace"],
            "record_kind": row["record_kind"],
            "record_id": record_id,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "ttl_seconds": row["ttl_seconds"],
            "payload": _json.loads(row["payload_json"]),
        }
        content = _render_daily_log_markdown(record)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    return written

