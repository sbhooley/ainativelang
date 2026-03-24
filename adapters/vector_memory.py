# adapters/vector_memory.py
"""
Local JSON-backed semantic-ish memory: keyword overlap scoring (no extra deps).

Enable: ``--enable-adapter vector_memory`` on the CLI host.

AINL (examples):
  R vector_memory.SEARCH "query" [limit] ->hits
  R vector_memory.LIST_SIMILAR "query" [limit] ->hits
  R vector_memory upsert namespace kind record_id text [payload_json] ->ok

Env:
  AINL_VECTOR_MEMORY_PATH — store file (default: .ainl_vector_memory.json in cwd)

Verbs (target, case-insensitive): SEARCH, LIST_SIMILAR, UPSERT
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from runtime.adapters.base import AdapterError, RuntimeAdapter


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^\w]+", (text or "").lower()) if len(t) > 1]


def _score(query: str, doc: str) -> float:
    q = set(_tokenize(query))
    d = set(_tokenize(doc))
    if not q or not d:
        return 0.0
    inter = len(q & d)
    return float(inter) / (len(q) ** 0.5 * len(d) ** 0.5 + 1e-9)


class VectorMemoryAdapter(RuntimeAdapter):
    def __init__(self, path: Optional[str] = None):
        raw = (path or os.environ.get("AINL_VECTOR_MEMORY_PATH") or "").strip()
        self.path = Path(raw) if raw else Path.cwd() / ".ainl_vector_memory.json"
        self._records: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._records = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("records") if isinstance(data, dict) else None
            self._records = list(items) if isinstance(items, list) else []
        except Exception as e:
            raise AdapterError(f"vector_memory: cannot read store {self.path}: {e}") from e

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "updated_at": time.time(), "records": self._records}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        lim = max(1, min(int(limit), 500))
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for rec in self._records:
            text = str(rec.get("text") or "")
            s = _score(query, text)
            if s > 0:
                ranked.append((s, rec))
        ranked.sort(key=lambda x: -x[0])
        out: List[Dict[str, Any]] = []
        for s, rec in ranked[:lim]:
            row = dict(rec)
            row["score"] = round(s, 6)
            out.append(row)
        return out

    def _upsert(
        self,
        namespace: str,
        kind: str,
        record_id: str,
        text: str,
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not namespace or not kind or not record_id:
            raise AdapterError("vector_memory.UPSERT requires namespace, kind, record_id")
        now = time.time()
        new_rec = {
            "namespace": str(namespace),
            "kind": str(kind),
            "id": str(record_id),
            "text": str(text or ""),
            "payload": payload if isinstance(payload, dict) else {},
            "updated_at": now,
        }
        for i, rec in enumerate(self._records):
            if (
                str(rec.get("namespace")) == new_rec["namespace"]
                and str(rec.get("kind")) == new_rec["kind"]
                and str(rec.get("id")) == new_rec["id"]
            ):
                self._records[i] = new_rec
                self._save()
                return {"ok": True, "updated": True}
        self._records.append(new_rec)
        self._save()
        return {"ok": True, "updated": False}

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().upper()
        if verb in {"SEARCH", "LIST_SIMILAR"}:
            if not args:
                raise AdapterError(f"vector_memory.{verb} requires query string")
            query = str(args[0])
            limit = int(args[1]) if len(args) > 1 and args[1] is not None else 20
            return self._search(query, limit)
        if verb == "UPSERT":
            if len(args) < 4:
                raise AdapterError("vector_memory.UPSERT requires namespace kind record_id text [payload_json]")
            ns, kind, rid, text = (args[0], args[1], args[2], args[3])
            payload: Optional[Dict[str, Any]] = None
            if len(args) >= 5 and args[4] is not None:
                raw = args[4]
                if isinstance(raw, dict):
                    payload = raw
                else:
                    try:
                        payload = json.loads(str(raw))
                    except Exception as e:
                        raise AdapterError(f"vector_memory.UPSERT payload must be JSON object: {e}") from e
            return self._upsert(str(ns), str(kind), str(rid), str(text), payload)
        raise AdapterError(f"vector_memory unsupported verb: {target!r}")
