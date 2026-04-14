"""JSON-backed graph memory for ArmaraOS ↔ AINL bridge (episodic / semantic / procedural / persona)."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from runtime.adapters.base import AdapterError, RuntimeAdapter

from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter

logger = logging.getLogger("ainl.graph_memory")


class NodeType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONA = "persona"
    PATCH = "patch"


class EdgeType(str, Enum):
    CAUSED_BY = "caused_by"
    PART_OF = "part_of"
    REFERENCES = "references"
    FOLLOWS = "follows"
    DERIVED_FROM = "derived_from"
    INHERITED_BY = "inherited_by"
    KNOWS = "knows"
    BELIEVES = "believes"
    LEARNED_FROM = "learned_from"
    CONTRADICTS = "contradicts"
    CAUSED_PATCH = "caused_patch"
    STRENGTHENS = "strengthens"


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
    contradicted_by: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MemoryNode:
        cb = d.get("contradicted_by") or []
        if not isinstance(cb, list):
            cb = [str(cb)]
        return cls(
            id=str(d["id"]),
            node_type=str(d["node_type"]),
            agent_id=str(d["agent_id"]),
            label=str(d.get("label", "")),
            payload=dict(d.get("payload") or {}),
            tags=[str(x) for x in (d.get("tags") or [])],
            created_at=float(d["created_at"]),
            ttl=float(d["ttl"]) if d.get("ttl") is not None else None,
            contradicted_by=[str(x) for x in cb],
        )


# ``AINLBundleBuilder._snapshot_memory`` stores ``MemoryNode.to_dict()`` rows (GraphStore JSON shape).
# Persona rows are omitted there; boot also ignores ``node_type == persona`` in ``bundle.memory`` so
# ``bundle.persona`` stays the only persona pre-seed path.
_BUNDLE_PRESEED_MEMORY_NODE_TYPES = frozenset(
    {
        NodeType.EPISODIC.value,
        NodeType.SEMANTIC.value,
        NodeType.PROCEDURAL.value,
        NodeType.PATCH.value,
    }
)


def _normalize_bundle_memory_node(raw: Any, default_agent_id: str) -> Optional[MemoryNode]:
    """Map one ``bundle.memory`` row to :class:`MemoryNode` or return ``None`` if unusable."""
    if not isinstance(raw, dict):
        return None
    nt = str(raw.get("node_type") or "").strip().lower()
    if nt == NodeType.PERSONA.value:
        return None
    if nt not in _BUNDLE_PRESEED_MEMORY_NODE_TYPES:
        return None
    nid = str(raw.get("id") or "").strip()
    if not nid:
        return None
    pl = raw.get("payload")
    if pl is not None and not isinstance(pl, dict):
        return None
    tags_raw = raw.get("tags")
    if tags_raw is not None and not isinstance(tags_raw, list):
        return None
    coerced: Dict[str, Any] = {
        "id": nid,
        "node_type": nt,
        "agent_id": str(raw.get("agent_id") or default_agent_id),
        "label": str(raw.get("label", "")),
        "payload": dict(pl or {}),
        "tags": [str(x) for x in (tags_raw or [])],
        "created_at": raw.get("created_at"),
        "ttl": raw.get("ttl"),
        "contradicted_by": raw.get("contradicted_by") or [],
    }
    if coerced["created_at"] is None:
        coerced["created_at"] = time.time()
    try:
        return MemoryNode.from_dict(coerced)
    except (KeyError, TypeError, ValueError):
        return None


@dataclass
class PersonaNode:
    """Typed persona trait stored under MemoryNode.node_type == \"persona\" (payload projection)."""

    trait_name: str
    strength: float  # 0.0–1.0
    learned_from: List[str] = field(default_factory=list)  # episode node IDs
    last_updated: int = 0  # unix seconds
    edge_type: Optional[str] = None  # epistemic link kind (knows, believes, …)

    def to_payload(self) -> Dict[str, Any]:
        out = {
            "trait_name": self.trait_name,
            "strength": float(self.strength),
            "learned_from": list(self.learned_from),
            "last_updated": int(self.last_updated),
        }
        if self.edge_type:
            out["edge_type"] = str(self.edge_type)
        return out

    @classmethod
    def from_payload(cls, d: Dict[str, Any]) -> "PersonaNode":
        lf = d.get("learned_from") or []
        if not isinstance(lf, list):
            lf = [str(lf)]
        et = d.get("edge_type")
        return cls(
            trait_name=str(d.get("trait_name", "")),
            strength=float(d.get("strength", 0.0)),
            learned_from=[str(x) for x in lf],
            last_updated=int(d.get("last_updated", 0)),
            edge_type=str(et) if et is not None else None,
        )


@dataclass
class PatchRecord:
    """Typed patch record stored under MemoryNode.node_type == \"patch\" (payload projection)."""

    node_id: str  # the PatchRegistry MemoryNode id
    label_name: str  # installed IR label name
    pattern_name: str  # source pattern name
    source_pattern_node_id: str  # PROCEDURAL node that was promoted
    source_episode_ids: List[str]  # episodes that motivated the patch
    declared_reads: List[str]  # union of all step reads
    fitness: float  # 0.0–1.0, updated post-execution
    patch_version: int  # increments on re-patch
    patched_at: int  # unix seconds
    parent_patch_id: Optional[str] = None  # prior PatchRecord node_id if re-patch
    retired_at: Optional[int] = None  # unix seconds if retired
    retired_reason: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        out = {
            "node_id": self.node_id,
            "label_name": self.label_name,
            "pattern_name": self.pattern_name,
            "source_pattern_node_id": self.source_pattern_node_id,
            "source_episode_ids": list(self.source_episode_ids),
            "declared_reads": list(self.declared_reads),
            "fitness": float(self.fitness),
            "patch_version": int(self.patch_version),
            "patched_at": int(self.patched_at),
        }
        if self.parent_patch_id is not None:
            out["parent_patch_id"] = str(self.parent_patch_id)
        if self.retired_at is not None:
            out["retired_at"] = int(self.retired_at)
        if self.retired_reason is not None:
            out["retired_reason"] = str(self.retired_reason)
        return out

    @classmethod
    def from_payload(cls, d: Dict[str, Any]) -> "PatchRecord":
        sei = d.get("source_episode_ids") or []
        if not isinstance(sei, list):
            sei = [str(sei)]
        dr = d.get("declared_reads") or []
        if not isinstance(dr, list):
            dr = []
        return cls(
            node_id=str(d.get("node_id", "")),
            label_name=str(d.get("label_name", "")),
            pattern_name=str(d.get("pattern_name", "")),
            source_pattern_node_id=str(d.get("source_pattern_node_id", "")),
            source_episode_ids=[str(x) for x in sei],
            declared_reads=[str(x) for x in dr],
            fitness=float(d.get("fitness", 0.5)),
            patch_version=int(d.get("patch_version", 1)),
            patched_at=int(d.get("patched_at", 0)),
            parent_patch_id=str(d["parent_patch_id"]) if d.get("parent_patch_id") else None,
            retired_at=int(d["retired_at"]) if d.get("retired_at") is not None else None,
            retired_reason=str(d["retired_reason"]) if d.get("retired_reason") else None,
        )


@dataclass
class MemoryEdge:
    id: str
    src: str
    dst: str
    edge_type: str
    label: str = ""
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MemoryEdge:
        conf = d.get("confidence", 1.0)
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            conf_f = 1.0
        meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
        return cls(
            id=str(d["id"]),
            src=str(d["src"]),
            dst=str(d["dst"]),
            edge_type=str(d["edge_type"]),
            label=str(d.get("label", "")),
            confidence=conf_f,
            meta=dict(meta),
        )


def _default_graph_path() -> Path:
    override = (os.environ.get("AINL_GRAPH_MEMORY_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".armaraos" / "ainl_graph_memory.json"


def _armaraos_openfang_home() -> Path:
    """Match `openfang_home_dir()` / per-agent `ainl_memory.db` layout (ARMARAOS_HOME, then OPENFANG_HOME, then ~/.armaraos vs ~/.openfang)."""
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


def _armaraos_export_env_looks_like_directory(expanded: Path) -> bool:
    try:
        if expanded.exists() and expanded.is_dir():
            return True
    except OSError:
        pass
    return not expanded.name.lower().endswith(".json")


def _armaraos_export_snapshot_path() -> Optional[Path]:
    """Optional JSON: `AgentGraphSnapshot` from Rust graph export (per-agent path when env names a directory)."""
    raw = (os.environ.get("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT") or "").strip()
    agent_id = (os.environ.get("ARMARAOS_AGENT_ID") or "").strip()

    if raw:
        p = Path(raw).expanduser()
        if _armaraos_export_env_looks_like_directory(p):
            if not agent_id:
                logger.warning(
                    "AINL_GRAPH_MEMORY_ARMARAOS_EXPORT names a directory (%s) but ARMARAOS_AGENT_ID is unset; "
                    "skipping ArmaraOS snapshot merge",
                    p,
                )
                return None
            return p / f"{agent_id}_graph_export.json"
        return p

    if agent_id:
        return _armaraos_openfang_home() / "agents" / agent_id / "ainl_graph_memory_export.json"

    return None


def _looks_like_armaraos_snapshot(data: Dict[str, Any]) -> bool:
    if data.get("schema_version") in ("1", "1.0"):
        return True
    return bool(
        data.get("exported_at")
        and isinstance(data.get("nodes"), list)
        and "agent_id" in data
    )


def _node_type_from_rust_export(node: Dict[str, Any]) -> str:
    mc = node.get("memory_category")
    if isinstance(mc, str):
        m = mc.lower().strip()
        if m == "episodic":
            return NodeType.EPISODIC.value
        if m == "semantic":
            return NodeType.SEMANTIC.value
        if m == "procedural":
            return NodeType.PROCEDURAL.value
        if m == "persona":
            return NodeType.PERSONA.value
        if m == "runtime_state":
            return NodeType.SEMANTIC.value
    nt = node.get("node_type")
    if isinstance(nt, dict):
        t = str(nt.get("type", "")).lower()
        if t == "episode":
            return NodeType.EPISODIC.value
        if t == "semantic":
            return NodeType.SEMANTIC.value
        if t == "procedural":
            return NodeType.PROCEDURAL.value
        if t == "persona":
            return NodeType.PERSONA.value
        if t == "runtime_state":
            return NodeType.SEMANTIC.value
    return NodeType.SEMANTIC.value


def _label_from_rust_export(node: Dict[str, Any]) -> str:
    nt = node.get("node_type")
    if not isinstance(nt, dict):
        return str(node.get("id", "node"))
    kind = str(nt.get("type", "")).lower()
    if kind == "episode":
        tools = nt.get("tool_calls") or []
        if isinstance(tools, list) and tools:
            return f"episode:{tools[0]}"
        return "episode"
    if kind == "semantic":
        return (str(nt.get("fact", "")) or "fact")[:200]
    if kind == "procedural":
        return str(nt.get("pattern_name", "pattern"))
    if kind == "persona":
        return str(nt.get("trait_name", "persona"))
    if kind == "runtime_state":
        return "runtime_state"
    return str(node.get("id", ""))


def _tags_from_rust_export(node: Dict[str, Any]) -> List[str]:
    out = ["source:armaraos_export", f"rust_id:{node.get('id')}"]
    nt = node.get("node_type")
    if isinstance(nt, dict) and str(nt.get("type", "")).lower() == "semantic":
        for t in nt.get("tags") or []:
            if isinstance(t, str) and t and t not in out:
                out.append(t)
    return out


def _created_at_from_rust_export(node: Dict[str, Any]) -> float:
    nt = node.get("node_type")
    if isinstance(nt, dict) and str(nt.get("type", "")).lower() == "episode":
        ts = nt.get("timestamp")
        if isinstance(ts, (int, float)):
            return float(ts)
    return time.time()


def _memory_node_from_rust_export(node: Dict[str, Any]) -> Optional[MemoryNode]:
    try:
        nid = str(node["id"])
        agent_id = str(node.get("agent_id") or "")
        py_type = _node_type_from_rust_export(node)
        label = _label_from_rust_export(node)
        tags = _tags_from_rust_export(node)
        created = _created_at_from_rust_export(node)
        payload: Dict[str, Any] = {"rust_snapshot": node}
        return MemoryNode(
            id=nid,
            node_type=py_type,
            agent_id=agent_id,
            label=label,
            payload=payload,
            tags=tags,
            created_at=created,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _memory_edges_from_rust_export(edges: Any) -> Dict[str, MemoryEdge]:
    out: Dict[str, MemoryEdge] = {}
    if not isinstance(edges, list):
        return out
    allowed = {e.value for e in EdgeType}
    for raw in edges:
        if not isinstance(raw, dict):
            continue
        try:
            src = str(raw["source_id"])
            dst = str(raw["target_id"])
            et_raw = str(raw.get("edge_type") or "references").strip()
            if et_raw in allowed:
                et = et_raw
                meta: Dict[str, Any] = {}
            else:
                et = EdgeType.REFERENCES.value
                meta = {"armaraos_edge_type": et_raw}
            eid = _new_id("edge")
            out[eid] = MemoryEdge(
                id=eid,
                src=src,
                dst=dst,
                edge_type=et,
                label=et_raw,
                confidence=float(raw.get("weight", 1.0) or 1.0),
                meta=meta,
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _dry_run(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes", "on"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on")


class GraphStore:
    """JSON file graph: nodes + edges with atomic replace and TTL pruning.

    Optional **read-through** from ArmaraOS Rust SQLite: set ``AINL_GRAPH_MEMORY_ARMARAOS_EXPORT``
    to a **directory** (``{dir}/{ARMARAOS_AGENT_ID}_graph_export.json``) or a single **.json** file
    (backward compatible), or leave it unset and set ``ARMARAOS_AGENT_ID`` to load
    ``<openfang_home>/agents/<id>/ainl_graph_memory_export.json`` when that file exists.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_graph_path()
        self._lock = threading.Lock()
        self._nodes: Dict[str, MemoryNode] = {}
        self._edges: Dict[str, MemoryEdge] = {}
        self._load()

    def _load(self) -> None:
        self._nodes = {}
        self._edges = {}
        exp = _armaraos_export_snapshot_path()
        if exp and exp.is_file():
            try:
                snap_raw = exp.read_text(encoding="utf-8").strip()
                if snap_raw:
                    snap = json.loads(snap_raw)
                    if isinstance(snap, dict) and _looks_like_armaraos_snapshot(snap):
                        for n in snap.get("nodes") or []:
                            if isinstance(n, dict):
                                mn = _memory_node_from_rust_export(n)
                                if mn:
                                    self._nodes[mn.id] = mn
                        for eid, me in _memory_edges_from_rust_export(snap.get("edges")).items():
                            self._edges[eid] = me
                        logger.info(
                            "loaded ArmaraOS graph snapshot from %s (%d nodes, %d edges)",
                            exp,
                            len(self._nodes),
                            len(self._edges),
                        )
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning("ArmaraOS graph export load failed (%s): %s", exp, e)

        if not self.path.is_file():
            self._prune_expired_unlocked()
            return
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                self._prune_expired_unlocked()
                return
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("graph memory load failed (%s): %s", self.path, e)
            self._prune_expired_unlocked()
            return
        if not isinstance(data, dict):
            self._prune_expired_unlocked()
            return
        for item in data.get("nodes") or []:
            if isinstance(item, dict) and item.get("id"):
                try:
                    n = MemoryNode.from_dict(item)
                    self._nodes[n.id] = n
                except (KeyError, TypeError, ValueError):
                    continue
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

    def write_node(self, node: MemoryNode, *, persist: bool = True, dry_run: bool = False) -> MemoryNode:
        """Persist any graph node (including ``node_type=\"persona\"``). Same semantics as :meth:`add_node`."""
        return self.add_node(node, persist=persist, dry_run=dry_run)

    def find_by_type(self, node_type: str, agent_id: Optional[str] = None) -> List[Any]:
        """Return nodes of the given type. For ``persona``, returns :class:`PersonaNode` projections."""
        with self._lock:
            self._prune_expired_unlocked()
            out: List[Any] = []
            for node in self._nodes.values():
                if node.node_type != node_type:
                    continue
                if agent_id is not None and node.agent_id != agent_id:
                    continue
                if node_type == NodeType.PERSONA.value:
                    pl = dict(node.payload or {})
                    if not pl.get("trait_name") and node.label.startswith("persona:"):
                        pl.setdefault("trait_name", node.label.split(":", 1)[-1])
                    out.append(PersonaNode.from_payload(pl))
                else:
                    out.append(node)
            return out

    def _allowed_edge_types(self) -> Set[str]:
        return {e.value for e in EdgeType}

    def _node_flag_contradiction(self, nid: str, other_id: str) -> None:
        node = self._nodes.get(nid)
        if node is None:
            return
        pl = dict(node.payload or {})
        meta = pl.setdefault("metadata", {})
        meta["has_contradiction"] = True
        cb = list(node.contradicted_by)
        if other_id not in cb:
            cb.append(other_id)
        self._nodes[nid] = MemoryNode(
            id=node.id,
            node_type=node.node_type,
            agent_id=node.agent_id,
            label=node.label,
            payload=pl,
            tags=list(node.tags),
            created_at=node.created_at,
            ttl=node.ttl,
            contradicted_by=cb,
        )

    def add_edge(self, edge: MemoryEdge, *, persist: bool = True, dry_run: bool = False) -> MemoryEdge:
        with self._lock:
            if dry_run:
                logger.info("[dry_run] graph add_edge %s — no write", edge.id)
                return edge
            et = str(edge.edge_type or "")
            if et and et not in self._allowed_edge_types():
                raise AdapterError(f"graph add_edge: unsupported edge_type {et!r}")
            if et == EdgeType.BELIEVES.value:
                conf = float(edge.meta.get("confidence", edge.confidence))
                edge = MemoryEdge(
                    id=edge.id,
                    src=edge.src,
                    dst=edge.dst,
                    edge_type=edge.edge_type,
                    label=edge.label,
                    confidence=conf,
                    meta=dict(edge.meta),
                )
            self._edges[edge.id] = edge
            if et == EdgeType.CONTRADICTS.value:
                self._node_flag_contradiction(edge.src, edge.dst)
                self._node_flag_contradiction(edge.dst, edge.src)
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

    def add_patch_record(
        self,
        patch: PatchRecord,
        *,
        agent_id: Optional[str] = None,
        persist: bool = True,
        dry_run: bool = False,
    ) -> MemoryNode:
        """Store a PatchRecord as a NodeType.PATCH node."""
        node = MemoryNode(
            id=patch.node_id,
            node_type=NodeType.PATCH.value,
            agent_id=agent_id or "armaraos",  # patches are agent-scoped
            label=f"patch:{patch.label_name}",
            payload=patch.to_payload(),
            tags=["patch", patch.pattern_name, f"v{patch.patch_version}"],
            created_at=float(patch.patched_at),
            ttl=None,
        )
        return self.add_node(node, persist=persist, dry_run=dry_run)

    def get_patch_registry(
        self,
        agent_id: Optional[str] = None,
        include_retired: bool = False,
    ) -> List[PatchRecord]:
        """Return all active PatchRecord nodes for re-installation on boot."""
        with self._lock:
            self._prune_expired_unlocked()
            out: List[PatchRecord] = []
            for node in self._nodes.values():
                if node.node_type != NodeType.PATCH.value:
                    continue
                if agent_id is not None and node.agent_id != agent_id:
                    continue
                try:
                    patch = PatchRecord.from_payload(node.payload or {})
                    if not include_retired and patch.retired_at is not None:
                        continue
                    out.append(patch)
                except (KeyError, TypeError, ValueError):
                    continue
            # Sort by patch_version descending for determinism
            out.sort(key=lambda p: (p.label_name, -p.patch_version))
            return out

    def get_patch_record(self, label_name: str, agent_id: str) -> Optional[PatchRecord]:
        """Return the most recent non-retired PatchRecord for a label."""
        with self._lock:
            self._prune_expired_unlocked()
            candidates: List[PatchRecord] = []
            for node in self._nodes.values():
                if node.node_type != NodeType.PATCH.value:
                    continue
                if node.agent_id != agent_id:
                    continue
                try:
                    patch = PatchRecord.from_payload(node.payload or {})
                    if patch.label_name == label_name and patch.retired_at is None:
                        candidates.append(patch)
                except (KeyError, TypeError, ValueError):
                    continue
            if not candidates:
                return None
            # Return highest patch_version
            candidates.sort(key=lambda p: -p.patch_version)
            return candidates[0]

    def retire_patch(
        self,
        label_name: str,
        agent_id: str,
        reason: str,
        *,
        persist: bool = True,
    ) -> bool:
        """Mark a PatchRecord as retired. Returns True if found."""
        with self._lock:
            self._prune_expired_unlocked()
            for node in self._nodes.values():
                if node.node_type != NodeType.PATCH.value or node.agent_id != agent_id:
                    continue
                try:
                    patch = PatchRecord.from_payload(node.payload or {})
                    if patch.label_name == label_name and patch.retired_at is None:
                        # Update the patch record
                        patch.retired_at = int(time.time())
                        patch.retired_reason = reason
                        # Update the node
                        node.payload = patch.to_payload()
                        node.tags.append("retired")
                        self._nodes[node.id] = node
                        self._touch(persist=persist)
                        return True
                except (KeyError, TypeError, ValueError):
                    continue
            return False

    def update_patch_fitness(
        self,
        label_name: str,
        agent_id: str,
        new_fitness: float,
        *,
        persist: bool = True,
    ) -> bool:
        """Update fitness score on an existing PatchRecord. Returns True if found."""
        with self._lock:
            self._prune_expired_unlocked()
            for node in self._nodes.values():
                if node.node_type != NodeType.PATCH.value or node.agent_id != agent_id:
                    continue
                try:
                    patch = PatchRecord.from_payload(node.payload or {})
                    if patch.label_name == label_name and patch.retired_at is None:
                        # Update fitness
                        patch.fitness = new_fitness
                        # Update the node
                        node.payload = patch.to_payload()
                        self._nodes[node.id] = node
                        self._touch(persist=persist)
                        return True
                except (KeyError, TypeError, ValueError):
                    continue
            return False

    def finalize_patch(
        self,
        node_id: str,
        declared_reads: List[str],
        *,
        persist: bool = True,
    ) -> bool:
        """Update declared_reads on a PatchRecord after normalization. Returns True if found."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None or node.node_type != NodeType.PATCH.value:
                return False
            try:
                patch = PatchRecord.from_payload(node.payload or {})
                patch.declared_reads = list(declared_reads)
                node.payload = patch.to_payload()
                self._nodes[node.id] = node
                self._touch(persist=persist)
                return True
            except (KeyError, TypeError, ValueError):
                return False


# Historical / doc name: persistence is JSON file–backed, not SQLite.
SqliteGraphStore = GraphStore


def _coerce_call_kwargs(args: Any) -> Dict[str, Any]:
    if isinstance(args, dict):
        return dict(args)
    if isinstance(args, (list, tuple)) and args and isinstance(args[0], dict):
        return dict(args[0])
    return {}


class AINLGraphMemoryBridge(RuntimeAdapter):
    """AINL adapter + typed hooks for ArmaraOS runtime events.

    Registered under :attr:`NAME` by ``adapters.armaraos_integration.armaraos_monitor_registry``
    (ArmaraOS bridge / monitor); hosts call :meth:`boot` once per run.
    """

    NAME = "ainl_graph_memory"

    def __init__(self, store: Optional[GraphStore] = None) -> None:
        self._store = store or GraphStore()
        self._agent_id: str = "armaraos"
        self.__dict__["_ainl_graph_memory_sync"] = None  # lazy :class:`AinlMemorySyncWriter`

    @property
    def _sync(self) -> AinlMemorySyncWriter:
        impl = self.__dict__.get("_ainl_graph_memory_sync")
        if impl is None:
            impl = AinlMemorySyncWriter()
            self.__dict__["_ainl_graph_memory_sync"] = impl
        return impl

    def _preseed_memory_nodes_from_bundle(
        self, bundle: Any, *, agent_id: str, dry_run: bool
    ) -> Tuple[int, int, int]:
        """Insert ``bundle.memory`` rows when id not already in store. Returns (inserted, skip_existing, skip_invalid)."""
        inserted = skip_existing = skip_invalid = 0
        rows = getattr(bundle, "memory", None)
        if not isinstance(rows, list):
            return (0, 0, 0)
        for raw in rows:
            node = _normalize_bundle_memory_node(raw, agent_id)
            if node is None:
                skip_invalid += 1
                continue
            if self._store.get_node(node.id) is not None:
                skip_existing += 1
                continue
            try:
                self._store.write_node(node, persist=True, dry_run=dry_run)
                inserted += 1
            except Exception:
                skip_invalid += 1
                logger.debug("bundle memory pre-seed write failed for %s", node.id, exc_info=True)
        return (inserted, skip_existing, skip_invalid)

    def boot(self, agent_id: str = "armaraos") -> str:
        """Record an episodic boot node (call once at ArmaraOS / bridge startup)."""
        self._agent_id = str(agent_id)
        ctx: Dict[str, Any] = {}
        dry = _dry_run(ctx)
        persona_restored = 0
        persona_skipped = 0
        mem_ins = mem_skip_ex = mem_skip_inv = 0
        # Pre-seed from bundle if provided by the host runtime (scheduled `ainl run`).
        bundle_path = (os.environ.get("AINL_BUNDLE_PATH") or "").strip()
        if bundle_path and os.path.exists(bundle_path):
            try:
                from runtime.ainl_bundle import AINLBundle

                bundle = AINLBundle.load(bundle_path)
                for persona_node in bundle.persona or []:
                    if not isinstance(persona_node, dict):
                        persona_skipped += 1
                        continue
                    try:
                        self.call(
                            "persona.update",
                            {
                                "trait_name": persona_node.get("trait_name"),
                                "strength": persona_node.get("strength", 0.0),
                                "learned_from": persona_node.get("learned_from", []),
                            },
                            {},
                        )
                        persona_restored += 1
                    except Exception:
                        persona_skipped += 1
                        logger.debug("bundle persona row skipped", exc_info=True)
                try:
                    mem_ins, mem_skip_ex, mem_skip_inv = self._preseed_memory_nodes_from_bundle(
                        bundle, agent_id=agent_id, dry_run=dry
                    )
                except Exception:
                    logger.debug("bundle memory pre-seed batch failed", exc_info=True)
                logger.info(
                    "graph memory bundle boot: persona_restored=%d persona_skipped=%d memory_restored=%d "
                    "memory_skip_existing=%d memory_skip_invalid=%d",
                    persona_restored,
                    persona_skipped,
                    mem_ins,
                    mem_skip_ex,
                    mem_skip_inv,
                )
            except Exception:
                logger.warning("AINL bundle load or pre-seed failed (%s)", bundle_path, exc_info=True)
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
        if not dry:
            sync_res = self._sync.push_nodes([node])
            logger.info("graph memory inbox sync (boot): %s", sync_res)
        return nid

    def call(self, target: str, args: Any, context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        dry = _dry_run(context)
        arg_list: List[Any] = args if isinstance(args, (list, tuple)) else []

        if verb == "memory_store_pattern":
            if isinstance(args, dict) or (isinstance(args, (list, tuple)) and args and isinstance(args[0], dict)):
                kw = _coerce_call_kwargs(args)
                label = str(kw.get("pattern_name") or kw.get("label") or "").strip()
                steps = kw.get("value")
                if steps is None:
                    steps = kw.get("steps") or []
                if not isinstance(steps, list):
                    steps = [steps]
                agent_id = str(kw.get("agent_id") or context.get("agent_id") or self._agent_id)
                tags = kw.get("tags") if isinstance(kw.get("tags"), list) else []
                tags = [str(t) for t in tags]
                return self.memory_store_pattern(label, steps, agent_id, tags, dry_run=dry)
            if len(arg_list) < 4:
                raise AdapterError("memory_store_pattern requires label, steps, agent_id, tags")
            label, steps, agent_id, tags = arg_list[0], arg_list[1], arg_list[2], arg_list[3]
            if not isinstance(steps, list):
                raise AdapterError("memory_store_pattern: steps must be a list")
            if not isinstance(tags, list):
                tags = []
            return self.memory_store_pattern(str(label), steps, str(agent_id), [str(t) for t in tags], dry_run=dry)

        if verb in ("pattern_recall", "memory_pattern_recall"):
            kw = _coerce_call_kwargs(args) if (isinstance(args, dict) or (isinstance(args, (list, tuple)) and args and isinstance(args[0], dict))) else {}
            pn = kw.get("pattern_name") if kw else None
            if pn is None and arg_list:
                pn = arg_list[0]
            return self.pattern_recall({"pattern_name": pn}, context)

        if verb == "memory_execute":
            raw = None
            if isinstance(args, dict) or (isinstance(args, (list, tuple)) and args and isinstance(args[0], dict)):
                kw_e = _coerce_call_kwargs(args)
                raw = kw_e.get("pattern") if kw_e else None
            if raw is None and arg_list:
                raw = arg_list[0]
            return self.memory_execute(raw, context)

        if verb in ("memory_patch", "graph_patch"):
            kw = _coerce_call_kwargs(args) if (isinstance(args, dict) or (isinstance(args, (list, tuple)) and args and isinstance(args[0], dict))) else {}
            pattern_src = kw.get("pattern") if kw else None
            label_name = kw.get("label_name") if kw else None
            source_episode_ids = kw.get("source_episode_ids") if kw else None

            if pattern_src is None and len(arg_list) >= 1:
                pattern_src = arg_list[0]
            if label_name is None and len(arg_list) >= 2:
                label_name = arg_list[1]
            if source_episode_ids is None and len(arg_list) >= 3:
                source_episode_ids = arg_list[2]

            agent_id = str(context.get("agent_id") or self._agent_id)
            return self.memory_patch(
                pattern_src,
                str(label_name) if label_name else "",
                agent_id=agent_id,
                source_episode_ids=source_episode_ids,
                dry_run=dry,
            )

        if verb == "memory_recall":
            if len(arg_list) < 1:
                raise AdapterError("memory_recall requires node_id")
            return self.memory_recall(str(arg_list[0]))

        if verb == "memory_search":
            query = str(arg_list[0]) if len(arg_list) >= 1 else ""
            nt = arg_list[1] if len(arg_list) >= 2 else None
            aid = arg_list[2] if len(arg_list) >= 3 else None
            lim = int(arg_list[3]) if len(arg_list) >= 4 else 10
            return self.memory_search(query, nt, aid, lim)

        if verb == "export_graph":
            return self.export_graph()

        if verb == "persona_update":
            kw = _coerce_call_kwargs(args)
            agent_id = str(context.get("agent_id") or self._agent_id)
            return self.persona_update(kw, agent_id=agent_id, dry_run=dry)

        if verb == "persona_get":
            kw = _coerce_call_kwargs(args)
            agent_id = str(context.get("agent_id") or self._agent_id)
            return self.persona_get(kw, agent_id=agent_id)

        if verb == "persona_load":
            agent_id = str(context.get("agent_id") or self._agent_id or "")
            traits: List[PersonaNode] = []
            for n in self._store.all_nodes():
                if n.node_type != NodeType.PERSONA.value:
                    continue
                if agent_id and n.agent_id != agent_id:
                    continue
                pl = dict(n.payload or {})
                if not pl.get("trait_name") and str(n.label).startswith("persona:"):
                    pl.setdefault("trait_name", str(n.label).split(":", 1)[-1])
                traits.append(PersonaNode.from_payload(pl))
            traits.sort(key=lambda p: -p.strength)
            trait_dicts = [p.to_payload() for p in traits]
            persona_context = {p.trait_name: float(p.strength) for p in traits if p.strength >= 0.1}
            return {"traits": trait_dicts, "persona_context": persona_context}

        raise AdapterError(f"ainl_graph_memory: unknown verb {verb!r}")

    def persona_update(
        self,
        params: Dict[str, Any],
        *,
        agent_id: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        trait_name = str(params.get("trait_name", "")).strip()
        if not trait_name:
            raise AdapterError("persona_update requires trait_name")
        strength = float(params.get("strength", 0.0))
        lf_in = params.get("learned_from") or []
        if not isinstance(lf_in, list):
            lf_in = [str(lf_in)]
        learned_from = [str(x) for x in lf_in]
        ts = int(time.time())
        edge_type_raw = params.get("edge_type")
        edge_type = str(edge_type_raw).strip() if edge_type_raw is not None else None
        if edge_type == "":
            edge_type = None
        if edge_type is not None and edge_type not in {e.value for e in EdgeType}:
            raise AdapterError(f"persona_update: unsupported edge_type {edge_type!r}")

        existing: Optional[MemoryNode] = None
        for n in self._store.all_nodes():
            if n.node_type != NodeType.PERSONA.value or n.agent_id != agent_id:
                continue
            pl = dict(n.payload or {})
            tname = str(pl.get("trait_name", "")).strip()
            if not tname and str(n.label).startswith("persona:"):
                tname = str(n.label).split(":", 1)[-1].strip()
            if tname == trait_name:
                existing = n
                break

        merged_learned = list(learned_from)
        created = time.time()
        if existing is not None:
            created = float(existing.created_at)
            old_lf = (existing.payload or {}).get("learned_from") or []
            if not isinstance(old_lf, list):
                old_lf = [str(old_lf)]
            merged_learned = sorted({str(x) for x in list(old_lf) + merged_learned})

        persona = PersonaNode(
            trait_name=trait_name,
            strength=strength,
            learned_from=merged_learned,
            last_updated=ts,
            edge_type=edge_type,
        )
        nid = existing.id if existing is not None else _new_id("persona")
        node = MemoryNode(
            id=nid,
            node_type=NodeType.PERSONA.value,
            agent_id=agent_id,
            label=f"persona:{trait_name}",
            payload=persona.to_payload(),
            tags=["persona", "trait"],
            created_at=created,
            ttl=None,
        )
        self._store.write_node(node, persist=True, dry_run=dry_run)
        if not dry_run:
            sync_res = self._sync.push_nodes([node])
            logger.info("graph memory inbox sync (persona): %s", sync_res)
        return {"ok": True, "node_id": nid, **persona.to_payload()}

    def persona_get(self, params: Dict[str, Any], *, agent_id: str) -> Dict[str, Any]:
        trait_name = str(params.get("trait_name", "")).strip()
        if not trait_name:
            raise AdapterError("persona_get requires trait_name")
        for n in self._store.all_nodes():
            if n.node_type != NodeType.PERSONA.value or n.agent_id != agent_id:
                continue
            pl = dict(n.payload or {})
            tname = str(pl.get("trait_name", "")).strip()
            if not tname and str(n.label).startswith("persona:"):
                tname = str(n.label).split(":", 1)[-1].strip()
            if tname == trait_name:
                p = PersonaNode.from_payload(pl)
                return {
                    "trait_name": p.trait_name,
                    "strength": p.strength,
                    "learned_from": list(p.learned_from),
                    "last_updated": p.last_updated,
                }
        raise AdapterError(f"persona_get: no trait {trait_name!r} for agent_id={agent_id!r}")

    def pattern_recall(self, args: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a named procedural pattern node from the graph store."""
        pattern_name: Optional[str] = None
        if isinstance(args, dict):
            pattern_name = args.get("pattern_name")
        if pattern_name is None and isinstance(args, list) and args:
            pattern_name = args[0]
        pattern_name = str(pattern_name or "").strip()
        if not pattern_name:
            return {"ok": False, "error": "pattern_name required"}
        agent_id = str((ctx or {}).get("agent_id") or self._agent_id or "")
        nodes = self._store.find_by_type(
            NodeType.PROCEDURAL.value, agent_id=agent_id if agent_id else None
        )
        for node in nodes:
            if not hasattr(node, "payload"):
                continue
            payload = dict(node.payload or {})
            if payload.get("pattern_name") == pattern_name or str(node.label) == pattern_name:
                steps_hint = list(payload.get("steps_hint") or [])
                return {
                    "ok": True,
                    "pattern_name": pattern_name,
                    "payload": payload,
                    "node_id": node.id,
                    "steps_hint": steps_hint,
                }
        return {"ok": False, "error": f"pattern '{pattern_name}' not found"}

    def memory_execute(self, raw: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve procedural pattern steps for runtime execution (does not run steps)."""
        payload: Optional[Dict[str, Any]] = None
        pattern_name: str = ""
        if isinstance(raw, dict):
            if isinstance(raw.get("steps"), list):
                payload = raw
                pattern_name = str(raw.get("pattern_name") or raw.get("label") or "").strip()
            else:
                inner = raw.get("payload")
                if isinstance(inner, dict) and isinstance(inner.get("steps"), list):
                    payload = inner
                    pattern_name = str(inner.get("pattern_name") or raw.get("pattern_name") or "").strip()
                else:
                    return {"ok": False, "error": "no steps in pattern", "steps": []}
        elif isinstance(raw, str):
            pn = raw.strip()
            if not pn:
                return {"ok": False, "error": "pattern_name required", "steps": []}
            rec = self.pattern_recall({"pattern_name": pn}, ctx)
            if not rec.get("ok"):
                return {**rec, "steps": []}
            inner_pl = rec.get("payload")
            if isinstance(inner_pl, dict) and isinstance(inner_pl.get("steps"), list):
                payload = inner_pl
                pattern_name = str(inner_pl.get("pattern_name") or pn).strip()
            else:
                return {"ok": False, "error": "pattern payload has no steps", "steps": []}
        else:
            return {"ok": False, "error": "invalid pattern source", "steps": []}

        steps = list((payload or {}).get("steps") or [])
        return {
            "ok": True,
            "steps": steps,
            "pattern_name": pattern_name or str((payload or {}).get("pattern_name") or ""),
            "step_count": len(steps),
        }

    def memory_patch(
        self,
        pattern_src: Any,
        label_name: str,
        *,
        agent_id: str,
        source_episode_ids: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        GraphPatch: promote a PROCEDURAL node to a live, first-class IR label.

        Args:
            pattern_src: str (pattern name) or dict (pattern_recall result with steps)
            label_name: target IR label name
            agent_id: agent performing the patch
            source_episode_ids: episodes that motivated this patch
            dry_run: if True, don't persist to disk

        Returns:
            {ok: bool, label_name: str, steps: list, pattern_name: str, step_count: int,
             node_id: str, patch_version: int, parent_patch_id: str|None, error?: str}
        """
        # 1. Resolve pattern_src
        payload: Optional[Dict[str, Any]] = None
        pattern_name: str = ""
        source_node_id: str = ""

        if isinstance(pattern_src, dict):
            # Direct dict with steps or payload.steps
            if isinstance(pattern_src.get("steps"), list):
                payload = pattern_src
                pattern_name = str(pattern_src.get("pattern_name") or pattern_src.get("label") or "").strip()
                source_node_id = str(pattern_src.get("node_id") or pattern_src.get("id") or "").strip()
            else:
                inner = pattern_src.get("payload")
                if isinstance(inner, dict) and isinstance(inner.get("steps"), list):
                    payload = inner
                    pattern_name = str(inner.get("pattern_name") or pattern_src.get("pattern_name") or "").strip()
                    source_node_id = str(pattern_src.get("node_id") or pattern_src.get("id") or "").strip()
                else:
                    return {"ok": False, "error": "unresolvable pattern: no steps in dict"}
        elif isinstance(pattern_src, str):
            # Pattern name - recall it first
            pn = pattern_src.strip()
            if not pn:
                return {"ok": False, "error": "unresolvable pattern: empty name"}
            rec = self.pattern_recall({"pattern_name": pn}, {"agent_id": agent_id})
            if not rec.get("ok"):
                return {"ok": False, "error": f"pattern_recall failed: {rec.get('error', 'unknown')}"}
            inner_pl = rec.get("payload")
            source_node_id = str(rec.get("node_id") or rec.get("id") or "").strip()
            if isinstance(inner_pl, dict) and isinstance(inner_pl.get("steps"), list):
                payload = inner_pl
                pattern_name = str(inner_pl.get("pattern_name") or pn).strip()
            else:
                return {"ok": False, "error": "pattern payload has no steps"}
        else:
            return {"ok": False, "error": "unresolvable pattern: must be str or dict"}

        # 2. Validate steps
        steps = list((payload or {}).get("steps") or [])
        if not steps:
            return {"ok": False, "error": "pattern has no steps"}
        if not all(isinstance(s, dict) for s in steps):
            return {"ok": False, "error": "all steps must be dicts"}

        # 3. Check for existing non-retired PatchRecord
        existing = self._store.get_patch_record(label_name, agent_id)
        patch_version = 1
        parent_patch_id: Optional[str] = None

        if existing:
            # This is a re-patch
            patch_version = existing.patch_version + 1
            parent_patch_id = existing.node_id
            # Retire the old record
            self._store.retire_patch(label_name, agent_id, "superseded", persist=not dry_run)

        # 4. Build PatchRecord
        patch_rec = PatchRecord(
            node_id=_new_id("patch"),
            label_name=label_name,
            pattern_name=pattern_name or "unnamed",
            source_pattern_node_id=source_node_id or "unknown",
            source_episode_ids=list(source_episode_ids or []),
            declared_reads=[],  # engine fills this after normalize
            fitness=0.5,
            patch_version=patch_version,
            patched_at=int(time.time()),
            parent_patch_id=parent_patch_id,
            retired_at=None,
            retired_reason=None,
        )

        # 5. Store patch record
        self._store.add_patch_record(patch_rec, agent_id=agent_id, persist=not dry_run, dry_run=dry_run)

        # 6. Add lineage edges
        if source_node_id and not dry_run:
            # source_pattern --[DERIVED_FROM]--> patch
            edge1 = MemoryEdge(
                id=_new_id("edge"),
                src=source_node_id,
                dst=patch_rec.node_id,
                edge_type=EdgeType.DERIVED_FROM.value,
                label="pattern_to_patch",
                confidence=1.0,
            )
            self._store.add_edge(edge1, persist=False, dry_run=dry_run)

        for ep_id in (source_episode_ids or []):
            if not dry_run:
                # episode --[CAUSED_PATCH]--> patch
                edge2 = MemoryEdge(
                    id=_new_id("edge"),
                    src=ep_id,
                    dst=patch_rec.node_id,
                    edge_type=EdgeType.CAUSED_PATCH.value,
                    label="episode_to_patch",
                    confidence=1.0,
                )
                self._store.add_edge(edge2, persist=False, dry_run=dry_run)

        # Flush to disk
        if not dry_run:
            self._store.flush()
            sync_res = self._sync.push_patch(patch_rec, agent_id)
            logger.info("graph memory inbox sync (patch): %s", sync_res)

        # 7. Return
        return {
            "ok": True,
            "label_name": label_name,
            "steps": steps,
            "pattern_name": pattern_name,
            "step_count": len(steps),
            "node_id": patch_rec.node_id,
            "patch_version": patch_version,
            "parent_patch_id": parent_patch_id,
        }

    def memory_store_pattern(
        self,
        label: str,
        steps: List[Any],
        agent_id: str,
        tags: List[str],
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        norm_steps: List[Dict[str, Any]] = []
        steps_hint: List[str] = []
        for s in steps:
            if isinstance(s, dict):
                norm_steps.append(s)
            else:
                norm_steps.append({"value": s})
                steps_hint.append(str(s))
        if not steps_hint and norm_steps:
            for d in norm_steps:
                v = d.get("value")
                if isinstance(v, str):
                    steps_hint.append(v)
        root_id = _new_id("proc")
        root = MemoryNode(
            id=root_id,
            node_type=NodeType.PROCEDURAL.value,
            agent_id=agent_id,
            label=label,
            payload={
                "kind": "pattern",
                "pattern_name": str(label),
                "step_count": len(norm_steps),
                "steps": norm_steps,
                "steps_hint": steps_hint,
            },
            tags=list(tags),
            created_at=time.time(),
            ttl=None,
        )
        self._store.add_node(root, persist=False, dry_run=dry_run)
        for i, step in enumerate(norm_steps):
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
        return {"node_id": root_id, "step_count": len(norm_steps)}

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
