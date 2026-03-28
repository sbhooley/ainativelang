from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


def _truthy_env(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


from intelligence.monitor.collector import collector as _collector

class RuntimeObservability:
    """
    Lightweight runtime metrics collector.

    Metrics are emitted as JSON lines to stderr when enabled.
    """

    def __init__(self, *, enabled: bool = False, jsonl_path: Optional[str] = None):
        self.enabled = bool(enabled)
        self._ack_total = 0
        self._ack_ok = 0
        self._last_seq_by_key: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._warned_jsonl_open = False
        self._jsonl_path = str(jsonl_path or "").strip() or None
        self._jsonl_fh: Optional[TextIO] = None
        if self.enabled and self._jsonl_path:
            self._open_jsonl_sink()

    @classmethod
    def from_env_or_flag(cls, explicit: bool = False, jsonl_path: Optional[str] = None) -> "RuntimeObservability":
        path = str(jsonl_path or "").strip() or os.environ.get("AINL_OBSERVABILITY_JSONL") or None
        return cls(enabled=bool(explicit or _truthy_env("AINL_OBSERVABILITY")), jsonl_path=path)

    def _open_jsonl_sink(self) -> None:
        if not self._jsonl_path:
            return
        try:
            p = Path(self._jsonl_path).expanduser()
            if p.parent and not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            self._jsonl_fh = p.open("a", encoding="utf-8")
            self._jsonl_path = str(p)
        except Exception as e:
            self._jsonl_fh = None
            if not self._warned_jsonl_open:
                self._warned_jsonl_open = True
                try:
                    print(
                        f"AINL observability: unable to open jsonl sink at {self._jsonl_path!r}; falling back to stderr only ({e})",
                        file=sys.stderr,
                    )
                except Exception:
                    pass

    def emit(self, name: str, value: Any, *, labels: Optional[Dict[str, Any]] = None) -> None:
        # Always update in-memory collector for Prometheus endpoint
        try:
            _collector.set(name, value, labels=dict(labels or {}))
        except Exception:
            pass
        if not self.enabled:
            return
        event = {
            "kind": "ainl.runtime.metric",
            "metric": str(name),
            "value": value,
            "labels": dict(labels or {}),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }
        try:
            print(json.dumps(event, ensure_ascii=False), file=sys.stderr)
        except Exception:
            # Keep observability strictly non-fatal.
            pass
        if self._jsonl_fh is not None:
            try:
                line = json.dumps(event, ensure_ascii=False)
                with self._lock:
                    self._jsonl_fh.write(line + "\n")
                    self._jsonl_fh.flush()
            except Exception:
                # Keep sink failures non-fatal.
                pass

def record_metric(context: Dict[str, Any], name: str, value: Any, *, labels: Optional[Dict[str, Any]] = None) -> None:
    """
    Adapter-side helper: safely emit runtime metrics when observability is enabled.
    """
    if not isinstance(context, dict):
        return
    obs = context.get("_observability")
    if isinstance(obs, RuntimeObservability):
        obs.emit(name, value, labels=labels)


def record_ack(context: Dict[str, Any], ok: bool, *, labels: Optional[Dict[str, Any]] = None) -> None:
    if not isinstance(context, dict):
        return
    obs = context.get("_observability")
    if isinstance(obs, RuntimeObservability):
        obs.on_ack(bool(ok), labels=labels)


def now_unix_s() -> float:
    return time.time()

