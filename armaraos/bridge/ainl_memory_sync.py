"""Append-only JSON inbox for Python graph-memory mutations → ArmaraOS Rust `ainl_memory.db` ingest.

Uses ``ARMARAOS_AGENT_ID`` + ``ARMARAOS_HOME`` (or default ``~/.armaraos``) to resolve
``<home>/agents/<id>/ainl_graph_memory_inbox.json``. Safe no-ops when unset or offline.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ainl.graph_memory.sync")

INBOX_FILENAME = "ainl_graph_memory_inbox.json"


@dataclass
class SyncResult:
    pushed: int
    skipped: int
    error: Optional[str] = None


def _armaraos_home_dir() -> Path:
    h = (os.environ.get("ARMARAOS_HOME") or os.environ.get("OPENFANG_HOME") or "").strip()
    if h:
        return Path(h).expanduser()
    home = Path.home()
    arm = home / ".armaraos"
    try:
        if arm.is_dir():
            return arm
    except OSError:
        pass
    return home / ".openfang"


class AinlMemorySyncWriter:
    """Atomic append of ``MemoryNode`` rows (GraphStore JSON shape) to the per-agent inbox file."""

    def __init__(self) -> None:
        self._agent_id = (os.environ.get("ARMARAOS_AGENT_ID") or "").strip()
        self._home = _armaraos_home_dir()
        self._lock = threading.Lock()
        self._inbox_path: Optional[Path] = None
        if self._agent_id:
            agents_root = self._home / "agents"
            self._inbox_path = agents_root / self._agent_id / INBOX_FILENAME

    def is_available(self) -> bool:
        if not self._agent_id:
            return False
        agents_root = self._home / "agents"
        try:
            return agents_root.is_dir()
        except OSError:
            return False

    def _unavailable(self) -> SyncResult:
        return SyncResult(pushed=0, skipped=0, error="sync_unavailable")

    def _atomic_write(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        data = json.dumps(payload, indent=2, default=str)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)

    def _read_inbox_unlocked(self, path: Path) -> Dict[str, Any]:
        if not path.is_file():
            return {"nodes": [], "edges": []}
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return {"nodes": [], "edges": []}
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("ainl graph memory inbox read failed (%s): %s", path, e)
            return {"nodes": [], "edges": []}
        if not isinstance(data, dict):
            return {"nodes": [], "edges": []}
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []
        return {"nodes": nodes, "edges": edges}

    def push_nodes(self, nodes: List[Any]) -> SyncResult:
        if not self.is_available() or self._inbox_path is None:
            return self._unavailable()
        if not nodes:
            return SyncResult(pushed=0, skipped=0, error=None)

        rows: List[Dict[str, Any]] = []
        for n in nodes:
            if hasattr(n, "to_dict"):
                rows.append(n.to_dict())  # type: ignore[union-attr]
            elif isinstance(n, dict):
                rows.append(dict(n))

        path = self._inbox_path
        with self._lock:
            try:
                cur = self._read_inbox_unlocked(path)
                cur_nodes = [x for x in cur["nodes"] if isinstance(x, dict)]
                cur_edges = [x for x in cur["edges"] if isinstance(x, dict)]
                cur_nodes.extend(rows)
                self._atomic_write(path, {"nodes": cur_nodes, "edges": cur_edges})
            except OSError as e:
                logger.warning("ainl graph memory inbox write failed (%s): %s", path, e)
                return SyncResult(pushed=0, skipped=0, error=str(e))

        return SyncResult(pushed=len(rows), skipped=0, error=None)

    def push_patch(self, patch: Any, agent_id: str) -> SyncResult:
        # Deferred import: ``ainl_graph_memory`` imports this module at load time.
        from armaraos.bridge.ainl_graph_memory import MemoryNode, NodeType, PatchRecord

        if not isinstance(patch, PatchRecord):
            return SyncResult(pushed=0, skipped=0, error="invalid_patch")
        node = MemoryNode(
            id=patch.node_id,
            node_type=NodeType.PATCH.value,
            agent_id=agent_id,
            label=f"patch:{patch.label_name}",
            payload=patch.to_payload(),
            tags=["patch", patch.pattern_name, f"v{patch.patch_version}"],
            created_at=float(patch.patched_at),
            ttl=None,
        )
        return self.push_nodes([node])
