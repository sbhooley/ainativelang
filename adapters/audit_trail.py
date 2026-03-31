"""Audit trail adapter for AINL — compliance-grade append-only event log.

Additive v1.3.4. Follows the exact pattern of other AINL adapters.
Non-destructive, sandbox-safe, thread-safe.

Supported sink URIs
-------------------
file://path/to/audit.jsonl    — append JSONL records to a file
syslog://                     — write via Python syslog module (POSIX only)
stderr://                     — write to sys.stderr
stdout://                     — write to sys.stdout (useful in tests / piped runs)

Each record is an immutable JSONL object:

    {
        "trace_id":   "<run ID or None>",
        "timestamp":  "<ISO-8601 UTC milliseconds>",
        "label_id":   "<label or None>",
        "node_id":    "<node or None>",
        "event":      "<target string>",
        "args":       [...redacted...],
        "output":     <...redacted...>,
        "event_hash": "<SHA-256 of the record without this field>"
    }

Usage from AINL graph::

    R audit_trail.record {event: "my_event", data: "..."}

Enable via CLI::

    ainl run main.ainl --enable-adapter audit_trail --audit-sink file:///tmp/audit.jsonl

Or environment variable::

    AINL_AUDIT_SINK=file:///tmp/audit.jsonl ainl run main.ainl --enable-adapter audit_trail
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import sys
import threading
from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter

logger = logging.getLogger(__name__)

# Keys whose values are always redacted before logging
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "token",
        "password",
        "passwd",
        "secret",
        "authorization",
        "auth",
        "credential",
        "credentials",
        "private_key",
        "privatekey",
    }
)


def _redact(value: Any, key: str = "") -> Any:
    """Return redacted value if *key* is sensitive, otherwise recurse."""
    if key and key.lower().replace("-", "_").replace(" ", "_") in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class AuditTrailAdapter(RuntimeAdapter):
    """Compliance audit adapter — appends immutable JSONL records to a sink.

    Parameters
    ----------
    sink:
        Sink URI string.  Supported schemes: ``file://``, ``syslog://``,
        ``stderr://``, ``stdout://``.
    """

    def __init__(self, sink: str = "stderr://") -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._syslog_ok = False

        if sink.startswith("syslog://"):
            try:
                import syslog as _syslog  # noqa: F401

                _syslog.openlog(os.path.basename(sys.argv[0]), _syslog.LOG_PID, _syslog.LOG_USER)
                self._syslog_ok = True
            except Exception as exc:
                logger.warning("audit_trail: syslog unavailable (%s); falling back to stderr", exc)

    # ------------------------------------------------------------------
    # RuntimeAdapter interface
    # ------------------------------------------------------------------

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        """Append one audit record.

        *target* becomes the ``event`` field.
        *context* is inspected for ``trace_id``, ``_label_id``, ``_node_id``,
        and ``_last_output`` keys (populated by the runtime engine).
        """
        context = context or {}

        # The runtime calls adapter targets like "record". For human audit logs,
        # prefer an explicit event name when provided in the first arg dict.
        # (Keeps adapter stable while making logs more informative.)
        event = str(target) if target else "record"
        if args and isinstance(args[0], dict) and args[0].get("event"):
            try:
                event = str(args[0].get("event"))
            except Exception:
                pass

        trace_id = (
            context.get("trace_id")
            or context.get("_run_id")
            or context.get("run_id")
        )
        label_id = context.get("_label_id")
        node_id = context.get("_node_id")

        redacted_args = _redact(args)
        redacted_output = _redact(context.get("_last_output"))

        base: Dict[str, Any] = {
            "trace_id": str(trace_id) if trace_id is not None else None,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "label_id": str(label_id) if label_id is not None else None,
            "node_id": str(node_id) if node_id is not None else None,
            "event": event,
            "args": redacted_args,
            "output": redacted_output,
        }

        # SHA-256 hash over a deterministic serialization of the base record
        blob = json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
        base["event_hash"] = hashlib.sha256(blob).hexdigest()

        line = json.dumps(base, ensure_ascii=False)
        self._write(line)
        return {"ok": True, "event": event, "trace_id": base["trace_id"]}

    # ------------------------------------------------------------------
    # Internal write helpers
    # ------------------------------------------------------------------

    def _write(self, line: str) -> None:
        with self._lock:
            try:
                sink = self._sink
                if sink.startswith("file://"):
                    path = sink[len("file://"):]
                    # Ensure parent directory exists
                    parent = os.path.dirname(path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    with open(path, "a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
                elif sink.startswith("syslog://") and self._syslog_ok:
                    import syslog

                    syslog.syslog(line)
                elif sink == "stderr://":
                    sys.stderr.write(line + "\n")
                    sys.stderr.flush()
                elif sink == "stdout://":
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()
                else:
                    # Unsupported / misconfigured sink — log warning, never raise
                    logger.warning("audit_trail: unsupported sink %r; record dropped", sink)
            except Exception as exc:
                # Audit failures must never crash the graph run
                logger.error("audit_trail: failed to write record: %s", exc)
