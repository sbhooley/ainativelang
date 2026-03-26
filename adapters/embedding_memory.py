"""Sidecar semantic index: embeddings + memory (namespace, kind, id) refs. Memory adapter remains SoT.

Enable: ``--enable-adapter embedding_memory`` and set ``AINL_EMBEDDING_MEMORY_DB`` (default ``/tmp/ainl_embedding_memory.sqlite3``).

Modes:
  - ``AINL_EMBEDDING_MODE=stub`` (default): deterministic hash vectors (no network; intended for tests and safe-default installs).
  - ``AINL_EMBEDDING_MODE=local``: dependency-free local embeddings (hashing-based; better than ``stub`` for rough top-k, still not model-semantic).
  - ``AINL_EMBEDDING_MODE=openai``: ``text-embedding-3-small`` via OpenAI-compatible API (needs ``OPENAI_API_KEY`` or ``LLM_API_KEY``).

Verbs:
  - ``UPSERT_REF`` namespace kind record_id text
  - ``SEARCH`` query limit -> top-k list of {{memory_namespace, memory_kind, memory_record_id, score}}
  - ``REMOVE_REF`` namespace kind record_id
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from runtime.adapters.base import AdapterError, RuntimeAdapter

_DEFAULT_DB = "/tmp/ainl_embedding_memory.sqlite3"
_DIM_STUB = 32
_DIM_LOCAL = 256


def _stub_embed(text: str, dim: int = _DIM_STUB) -> List[float]:
    """Deterministic pseudo-embedding for tests and zero-dep installs."""
    t = (text or "").strip().lower()
    vec = [0.0] * dim
    for i, tok in enumerate(t.split()):
        h = hashlib.sha256(f"{i}:{tok}".encode("utf-8")).digest()
        for j in range(dim):
            vec[j] += (h[j % len(h)] - 128) / 128.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _local_embed(text: str, dim: int = _DIM_LOCAL) -> List[float]:
    """Dependency-free local embedding (hashed bag-of-words + char n-grams).

    This is not a learned semantic embedding. It exists to support rough top-k selection
    in offline environments without introducing heavy dependencies.
    """
    t = (text or "").strip().lower()
    vec = [0.0] * dim
    if not t:
        return vec

    def _add_hash(feature: str, weight: float) -> None:
        h = hashlib.sha256(feature.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = -1.0 if (h[4] & 1) else 1.0
        vec[idx] += sign * weight

    # word features
    for tok in t.split():
        if not tok:
            continue
        _add_hash(f"w:{tok}", 1.0)

    # character 3-grams (bounded)
    s = f"  {t}  "
    max_ngrams = 2000
    n = 0
    for i in range(len(s) - 2):
        _add_hash(f"c3:{s[i:i+3]}", 0.3)
        n += 1
        if n >= max_ngrams:
            break

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _openai_embed(text: str, dim: int) -> List[float]:
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
    if not key:
        raise AdapterError("embedding_memory openai mode requires OPENAI_API_KEY or LLM_API_KEY")
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("AINL_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    payload = json.dumps({"model": model, "input": text[:8000]}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/embeddings",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise AdapterError(f"embedding_memory openai HTTP {e.code}: {e.read()[:500]!r}") from e
    except Exception as e:
        raise AdapterError(f"embedding_memory openai request failed: {e}") from e
    obj = json.loads(raw)
    data = (obj.get("data") or [{}])[0]
    emb = data.get("embedding")
    if not isinstance(emb, list):
        raise AdapterError("embedding_memory openai: missing embedding array")
    out = [float(x) for x in emb]
    if len(out) > dim:
        out = out[:dim]
    elif len(out) < dim:
        out = out + [0.0] * (dim - len(out))
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


class EmbeddingMemoryAdapter(RuntimeAdapter):
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = str(db_path or os.environ.get("AINL_EMBEDDING_MEMORY_DB") or _DEFAULT_DB)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mem_ns TEXT NOT NULL,
                mem_kind TEXT NOT NULL,
                mem_id TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vec_json TEXT NOT NULL,
                text_preview TEXT NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(mem_ns, mem_kind, mem_id)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emb_ns ON embedding_refs(mem_ns, mem_kind)"
        )
        self._conn.commit()

    def _embed(self, text: str) -> List[float]:
        mode = (os.environ.get("AINL_EMBEDDING_MODE") or "stub").strip().lower()
        dim = _DIM_LOCAL if mode in ("local", "offline") else _DIM_STUB
        if mode in ("openai", "api"):
            return _openai_embed(text, dim)
        if mode in ("local", "offline"):
            return _local_embed(text, dim)
        return _stub_embed(text, dim)

    def _upsert(
        self,
        mem_ns: str,
        mem_kind: str,
        mem_id: str,
        text: str,
    ) -> Dict[str, Any]:
        if not mem_ns or not mem_kind or not mem_id:
            raise AdapterError("embedding_memory.UPSERT_REF requires namespace, kind, record_id")
        vec = self._embed(text)
        now = __import__("time").time()
        blob = json.dumps(vec, separators=(",", ":"))
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO embedding_refs (mem_ns, mem_kind, mem_id, dim, vec_json, text_preview, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mem_ns, mem_kind, mem_id) DO UPDATE SET
                dim = excluded.dim,
                vec_json = excluded.vec_json,
                text_preview = excluded.text_preview,
                updated_at = excluded.updated_at
            """,
            (mem_ns, mem_kind, mem_id, len(vec), blob, (text or "")[:2000], now),
        )
        self._conn.commit()
        return {"ok": True, "dim": len(vec)}

    def _search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        qv = self._embed(query)
        lim = max(1, min(int(limit), 200))
        cur = self._conn.cursor()
        cur.execute("SELECT mem_ns, mem_kind, mem_id, vec_json FROM embedding_refs")
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for row in cur.fetchall():
            mem_ns, mem_kind, mem_id, raw = row[0], row[1], row[2], row[3]
            try:
                dv = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(dv, list):
                continue
            s = _cosine(qv, [float(x) for x in dv])
            ranked.append(
                (
                    s,
                    {
                        "memory_namespace": mem_ns,
                        "memory_kind": mem_kind,
                        "memory_record_id": mem_id,
                        "score": round(s, 6),
                    },
                )
            )
        ranked.sort(key=lambda x: -x[0])
        return [r[1] for r in ranked[:lim]]

    def _remove(self, mem_ns: str, mem_kind: str, mem_id: str) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute(
            "DELETE FROM embedding_refs WHERE mem_ns = ? AND mem_kind = ? AND mem_id = ?",
            (mem_ns, mem_kind, mem_id),
        )
        self._conn.commit()
        return {"ok": True, "deleted": cur.rowcount > 0}

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().upper()
        if verb in {"UPSERT_REF", "INDEX"}:
            if len(args) < 4:
                raise AdapterError("embedding_memory.UPSERT_REF needs namespace, kind, record_id, text")
            return self._upsert(str(args[0]), str(args[1]), str(args[2]), str(args[3]))
        if verb in {"SEARCH", "QUERY"}:
            if not args:
                raise AdapterError("embedding_memory.SEARCH requires query string")
            q = str(args[0])
            limit = int(args[1]) if len(args) > 1 and args[1] is not None else 5
            return self._search(q, limit)
        if verb in {"REMOVE_REF", "DELETE", "REMOVE"}:
            if len(args) < 3:
                raise AdapterError("embedding_memory.REMOVE_REF needs namespace, kind, record_id")
            return self._remove(str(args[0]), str(args[1]), str(args[2]))
        raise AdapterError(f"embedding_memory unsupported verb: {target!r}")


__all__ = ["EmbeddingMemoryAdapter"]
