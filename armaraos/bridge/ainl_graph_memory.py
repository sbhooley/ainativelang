"""JSON-backed graph memory for ArmaraOS ↔ AINL bridge (episodic / semantic / procedural / persona)."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter

logger = logging.getLogger("ainl.graph_memory")


class NodeType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONA = "persona"


class EdgeType(str, Enum):
    CAUSED_BY = "caused_by"
    PART_OF = "part_of"
    REFERENCES = "references"
    DERIVED_FROM = "derived_from"
    INHERITED_BY = "inherited_by"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class MemoryNode:
    id: str
    node_type: str
    agent_id: str
    label: str
    payload: Dict[str, Any]
    tags: List[str]
    created_at: float
    ttl: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MemoryNode:
        return cls(
            id=str(d["id"]),
            node_type=str(d["node_type"]),
            agent_id=str(d["agent_id"]),
            label=str(d.get("label", "")),
            payload=dict(d.get("payload") or {}),
            tags=[str(x) for x in (d.get("tags") or [])],
            created_at=float(d["created_at"]),
            ttl=float(d["ttl"]) if d.get("ttl") is not None else None,
        )


@dataclass
class MemoryEdge:
    id: str
    src: str
    dst: str
    edge_type: str
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MemoryEdge:
        return cls(
            id=str(d["id"]),
            src=str(d["src"]),
            dst=str(d["dst"]),
            edge_type=str(d["edge_type"]),
            label=str(d.get("label", "")),
        )


def _default_graph_path() -> Path:
    override = (os.environ.get("AINL_GRAPH_MEMORY_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".armaraos" / "ainl_graph_memory.json"


def _dry_run(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes", "on"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on")


class GraphStore:
    """JSON file graph: nodes + edges with atomic replace and TTL pruning."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_graph_path()
        self._lock = threading.Lock()
        self._nodes: Dict[str, MemoryNode] = {}
        self._edges: Dict[str, MemoryEdge] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._nodes = {}
            self._edges = {}
            return
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                self._nodes = {}
                self._edges = {}
                return
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("graph memory load failed (%s): %s", self.path, e)
            self._nodes = {}
            self._edges = {}
            return
        if not isinstance(data, dict):
            self._nodes = {}
            self._edges = {}
            return
        self._nodes = {}
        for item in data.get("nodes") or []:
            if isinstance(item, dict) and item.get("id"):
                try:
                    n = MemoryNode.from_dict(item)
                    self._nodes[n.id] = n
                except (KeyError, TypeError, ValueError):
                    continue
        self._edges = {}
        for item in data.get("edges") or []:
            if isinstance(item, dict) and item.get("id"):
                try:
                    e = MemoryEdge.from_dict(item)
                    self._edges[e.id] = e
                except (KeyError, TypeError, ValueError):
                    continue
        self._prune_expired_unlocked()

    def _prune_expired_unlocked(self) -> None:
        now = time.time()
        remove_ids: List[str] = []
        for nid, node in self._nodes.items():
            if node.ttl is not None and now > node.created_at + float(node.ttl):
                remove_ids.append(nid)
        if not remove_ids:
            return
        dead = set(remove_ids)
        for nid in remove_ids:
            self._nodes.pop(nid, None)
        edge_rm = [eid for eid, e in self._edges.items() if e.src in dead or e.dst in dead]
        for eid in edge_rm:
            self._edges.pop(eid, None)
        logger.info("pruned %d expired graph nodes", len(dead))

    def _atomic_save_unlocked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        data = json.dumps(payload, indent=2, default=str)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, self.path)

    def _touch(self, *, persist: bool) -> None:
        self._prune_expired_unlocked()
        if persist:
            self._atomic_save_unlocked()

    def add_node(self, node: MemoryNode, *, persist: bool = True, dry_run: bool = False) -> MemoryNode:
        with self._lock:
            if dry_run:
                logger.info("[dry_run] graph add_node %s — no write", node.id)
                return node
            self._nodes[node.id] = node
            self._touch(persist=persist)
            return node

    def add_edge(self, edge: MemoryEdge, *, persist: bool = True, dry_run: bool = False) -> MemoryEdge:
        with self._lock:
            if dry_run:
                logger.info("[dry_run] graph add_edge %s — no write", edge.id)
                return edge
            self._edges[edge.id] = edge
            self._touch(persist=persist)
            return edge

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        with self._lock:
            self._prune_expired_unlocked()
            return self._nodes.get(node_id)

    def search(
        self,
        query: str,
        node_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryNode]:
        q = (query or "").lower()
        with self._lock:
            self._prune_expired_unlocked()
            out: List[MemoryNode] = []
            for node in self._nodes.values():
                if node_type and node.node_type != node_type:
                    continue
                if agent_id and node.agent_id != agent_id:
                    continue
                if not q:
                    out.append(node)
                else:
                    blob = " ".join(
                        [
                            node.label.lower(),
                            json.dumps(node.payload, default=str).lower(),
                            " ".join(t.lower() for t in node.tags),
                        ]
                    )
                    if q in blob:
                        out.append(node)
                if len(out) >= limit:
                    break
            return out

    def all_nodes(self) -> List[MemoryNode]:
        with self._lock:
            self._prune_expired_unlocked()
            return list(self._nodes.values())

    def all_edges(self) -> List[MemoryEdge]:
        with self._lock:
            self._prune_expired_unlocked()
            return list(self._edges.values())

    def export_graph(self) -> Dict[str, Any]:
        with self._lock:
            self._prune_expired_unlocked()
            return {
                "nodes": [n.to_dict() for n in self._nodes.values()],
                "edges": [e.to_dict() for e in self._edges.values()],
            }

    def flush(self) -> None:
        """Persist current nodes and edges after prior non-persisting mutations."""
        with self._lock:
            self._touch(persist=True)


class AINLGraphMemoryBridge(RuntimeAdapter):
    """AINL adapter + typed hooks for ArmaraOS runtime events."""

    NAME = "ainl_graph_memory"

    def __init__(self, store: Optional[GraphStore] = None) -> None:
        self._store = store or GraphStore()

    def boot(self, agent_id: str = "armaraos") -> str:
        """Record an episodic boot node (call once at ArmaraOS / bridge startup)."""
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        nid = _new_id("boot")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.EPISODIC.value,
            agent_id=agent_id,
            label="bridge_boot",
            payload={"message": "ArmaraOS AINL graph memory bridge initialized"},
            tags=["boot", "armaraos"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=True, dry_run=dry)
        logger.info("graph memory boot node %s (agent_id=%s)", nid, agent_id)
        return nid

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = _dry_run(context)

        if verb == "memory_store_pattern":
            if len(args) < 4:
                raise AdapterError("memory_store_pattern requires label, steps, agent_id, tags")
            label, steps, agent_id, tags = args[0], args[1], args[2], args[3]
            if not isinstance(steps, list):
                raise AdapterError("memory_store_pattern: steps must be a list")
            if not isinstance(tags, list):
                tags = []
            return self.memory_store_pattern(str(label), steps, str(agent_id), [str(t) for t in tags], dry_run=dry)

        if verb == "memory_recall":
            if len(args) < 1:
                raise AdapterError("memory_recall requires node_id")
            return self.memory_recall(str(args[0]))

        if verb == "memory_search":
            query = str(args[0]) if len(args) >= 1 else ""
            nt = args[1] if len(args) >= 2 else None
            aid = args[2] if len(args) >= 3 else None
            lim = int(args[3]) if len(args) >= 4 else 10
            return self.memory_search(query, nt, aid, lim)

        if verb == "export_graph":
            return self.export_graph()

        raise AdapterError(f"ainl_graph_memory: unknown verb {verb!r}")

    def memory_store_pattern(
        self,
        label: str,
        steps: List[Dict[str, Any]],
        agent_id: str,
        tags: List[str],
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        root_id = _new_id("proc")
        root = MemoryNode(
            id=root_id,
            node_type=NodeType.PROCEDURAL.value,
            agent_id=agent_id,
            label=label,
            payload={"kind": "pattern", "step_count": len(steps), "steps": steps},
            tags=list(tags),
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(root, persist=False, dry_run=dry_run)
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                step = {"value": step}
            sid = _new_id("step")
            sn = MemoryNode(
                id=sid,
                node_type=NodeType.PROCEDURAL.value,
                agent_id=agent_id,
                label=f"{label}#step{i}",
                payload={"index": i, "step": step},
                tags=list(tags) + ["pattern_step"],
                created_at=time.time(),
                ttl=None,
            )
            self._store.add_node(sn, persist=False, dry_run=dry_run)
            ed = MemoryEdge(
                id=_new_id("edge"),
                src=sid,
                dst=root_id,
                edge_type=EdgeType.PART_OF.value,
                label=f"step_{i}",
            )
            self._store.add_edge(ed, persist=False, dry_run=dry_run)
        if not dry_run:
            self._store.flush()
        return {"node_id": root_id, "step_count": len(steps)}

    def memory_recall(self, node_id: str) -> Dict[str, Any]:
        n = self._store.get_node(node_id)
        if n is None:
            return {"error": "not found"}
        return n.to_dict()

    def memory_search(
        self,
        query: str,
        node_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        rows = self._store.search(query, node_type, agent_id, limit)
        return {"results": [r.to_dict() for r in rows], "count": len(rows)}

    def export_graph(self) -> Dict[str, Any]:
        return self._store.export_graph()

    def on_delegation(
        self,
        delegator: str,
        delegatee: str,
        task: str,
        payload: Any,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        dry = _dry_run(context or {})
        nid = _new_id("episodic")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.EPISODIC.value,
            agent_id=str(delegator),
            label=f"delegation:{task}",
            payload={
                "delegator": delegator,
                "delegatee": delegatee,
                "task": task,
                "detail": payload,
            },
            tags=["delegation", "episodic"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=True, dry_run=dry)
        return nid

    def on_tool_execution(
        self,
        tool_name: str,
        args: Any,
        result: Any,
        agent_id: str,
        parent_node_id: Optional[str] = None,
    ) -> str:
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        nid = _new_id("tool")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.PROCEDURAL.value,
            agent_id=agent_id,
            label=f"tool:{tool_name}",
            payload={"tool_name": tool_name, "args": args, "result": result},
            tags=["tool_execution"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=False, dry_run=dry)
        if parent_node_id:
            e = MemoryEdge(
                id=_new_id("edge"),
                src=nid,
                dst=str(parent_node_id),
                edge_type=EdgeType.PART_OF.value,
                label="tool_to_parent",
            )
            self._store.add_edge(e, persist=False, dry_run=dry)
        if not dry_run:
            self._store.flush()
        return nid

    def on_prompt_compress(
        self,
        original_tokens: int,
        compressed_tokens: int,
        summary: str,
        agent_id: str,
    ) -> str:
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        nid = _new_id("sem")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.SEMANTIC.value,
            agent_id=agent_id,
            label="prompt_compress",
            payload={
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "summary": summary,
            },
            tags=["compression", "semantic"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=True, dry_run=dry)
        return nid

    def on_swarm_message(self, sender: str, receiver: str, message: str, payload: Any) -> str:
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        nid = _new_id("swarm")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.EPISODIC.value,
            agent_id=str(sender),
            label=f"swarm:{receiver}",
            payload={"sender": sender, "receiver": receiver, "message": message, "extra": payload},
            tags=["swarm", "message"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=True, dry_run=dry)
        return nid

    def on_persona_update(self, agent_id: str, persona_key: str, old_value: Any, new_value: Any) -> str:
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        nid = _new_id("persona")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.PERSONA.value,
            agent_id=agent_id,
            label=f"persona:{persona_key}",
            payload={"persona_key": persona_key, "old_value": old_value, "new_value": new_value},
            tags=["persona", "update"],
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(node, persist=True, dry_run=dry)
        return nid
