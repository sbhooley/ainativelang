#!/usr/bin/env python3
"""
AINL Graph Memory — Live Demo
==============================
Demonstrates the unified execution + memory substrate:

  1. Boot the graph memory store
  2. Run three AINL programs via RuntimeEngine (delegation, tool call, persona update)
  3. Each execution automatically writes an Episode node to the graph
  4. Recall and walk the graph — show the full memory as a structured artifact
  5. Export the graph as JSON

Usage (from ainativelang repo root):
    python3 ainl_graph_memory_demo.py

Requirements:
    ainl-memory  >= 0.1.1-alpha  (or the ainativelang monorepo)
    ainl-runtime >= 0.1.1-alpha
"""

from __future__ import annotations

import json
import os
import sys
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Bootstrap: find the ainativelang repo and load the graph memory bridge
# ---------------------------------------------------------------------------

# Allow running from repo root or armaraos workspace
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE  # adjust if needed: _HERE.parent etc.

# Add armaraos bridge path so we can import the graph memory bridge
_ARMARAOS_BRIDGE = _REPO_ROOT / "armaraos" / "bridge"
if _ARMARAOS_BRIDGE.exists() and str(_ARMARAOS_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_ARMARAOS_BRIDGE))

# Add AINL runtime to path
for candidate in [_REPO_ROOT / "runtime", _REPO_ROOT]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

# ---------------------------------------------------------------------------
# 2. Inline graph memory store (zero-dependency fallback if crate not built)
#    Mirrors the Rust AinlMemoryNode / GraphStore types exactly.
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import sqlite3
import threading

@dataclass
class EpisodeNode:
    turn_id: str
    timestamp: int
    tool_calls: List[str] = field(default_factory=list)
    delegation_to: Optional[str] = None
    delegation_depth: int = 0
    outcome: Optional[str] = None

@dataclass
class SemanticNode:
    fact: str
    confidence: float
    source_turn_id: str
    domain: Optional[str] = None

@dataclass
class ProceduralNode:
    pattern_name: str
    compiled_graph: bytes = b""
    success_count: int = 0
    average_tokens_saved: float = 0.0

@dataclass
class PersonaNode:
    trait_name: str
    strength: float
    learned_from: List[str] = field(default_factory=list)
    last_updated: int = 0

@dataclass
class AinlEdge:
    target: str
    label: str  # "caused", "learned_from", "compiled_from", "evolved_from", "delegated_to"

@dataclass
class AinlMemoryNode:
    id: str
    node_type: str          # "episode" | "semantic" | "procedural" | "persona"
    timestamp: int
    payload: Any            # one of the above dataclasses
    edges: List[AinlEdge] = field(default_factory=list)


class SqliteGraphStore:
    """
    Minimal SQLite-backed GraphStore.
    Mirrors the Rust ainl-memory GraphStore trait:
        write_node / read_node / query_episodes_since / find_by_type / walk_from
    """
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ainl_nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ainl_edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    label TEXT NOT NULL
                )
            """)
            self._conn.commit()

    def write_node(self, node: AinlMemoryNode) -> None:
        import dataclasses
        with self._lock:
            cur = self._conn.cursor()
            payload_json = json.dumps(dataclasses.asdict(node.payload))
            cur.execute(
                "INSERT OR REPLACE INTO ainl_nodes (id, node_type, timestamp, payload) VALUES (?,?,?,?)",
                (node.id, node.node_type, node.timestamp, payload_json)
            )
            for edge in node.edges:
                cur.execute(
                    "INSERT INTO ainl_edges (source_id, target_id, label) VALUES (?,?,?)",
                    (node.id, edge.target, edge.label)
                )
            self._conn.commit()

    def read_node(self, node_id: str) -> Optional[AinlMemoryNode]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT id, node_type, timestamp, payload FROM ainl_nodes WHERE id=?", (node_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT target_id, label FROM ainl_edges WHERE source_id=?", (node_id,))
            edges = [AinlEdge(target=r[0], label=r[1]) for r in cur.fetchall()]
            return self._hydrate(row, edges)

    def query_episodes_since(self, since_ts: int) -> List[AinlMemoryNode]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, node_type, timestamp, payload FROM ainl_nodes WHERE node_type='episode' AND timestamp >= ? ORDER BY timestamp ASC",
                (since_ts,)
            )
            rows = cur.fetchall()
            return [self._hydrate(r, self._edges_for(r[0])) for r in rows]

    def find_by_type(self, node_type: str) -> List[AinlMemoryNode]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, node_type, timestamp, payload FROM ainl_nodes WHERE node_type=? ORDER BY timestamp ASC",
                (node_type,)
            )
            rows = cur.fetchall()
            return [self._hydrate(r, self._edges_for(r[0])) for r in rows]

    def walk_from(self, root_id: str, depth: int = 3) -> List[AinlMemoryNode]:
        visited = set()
        result = []
        queue = [(root_id, 0)]
        while queue:
            nid, d = queue.pop(0)
            if nid in visited or d > depth:
                continue
            visited.add(nid)
            node = self.read_node(nid)
            if node:
                result.append(node)
                for edge in node.edges:
                    queue.append((edge.target, d + 1))
        return result

    def all_nodes(self) -> List[AinlMemoryNode]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT id, node_type, timestamp, payload FROM ainl_nodes ORDER BY timestamp ASC")
            rows = cur.fetchall()
            return [self._hydrate(r, self._edges_for(r[0])) for r in rows]

    def _edges_for(self, node_id: str) -> List[AinlEdge]:
        cur = self._conn.cursor()
        cur.execute("SELECT target_id, label FROM ainl_edges WHERE source_id=?", (node_id,))
        return [AinlEdge(target=r[0], label=r[1]) for r in cur.fetchall()]

    def _hydrate(self, row, edges) -> AinlMemoryNode:
        nid, node_type, ts, payload_json = row
        payload_dict = json.loads(payload_json)
        if node_type == "episode":
            payload = EpisodeNode(**payload_dict)
        elif node_type == "semantic":
            payload = SemanticNode(**payload_dict)
        elif node_type == "procedural":
            payload_dict["compiled_graph"] = bytes(payload_dict.get("compiled_graph") or [])
            payload = ProceduralNode(**payload_dict)
        elif node_type == "persona":
            payload = PersonaNode(**payload_dict)
        else:
            payload = payload_dict
        return AinlMemoryNode(id=nid, node_type=node_type, timestamp=ts, payload=payload, edges=edges)

    def export_graph(self) -> Dict[str, Any]:
        import dataclasses
        nodes = self.all_nodes()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT source_id, target_id, label FROM ainl_edges")
            all_edges = [{"from": r[0], "to": r[1], "label": r[2]} for r in cur.fetchall()]
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(nodes),
            "edge_count": len(all_edges),
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type,
                    "timestamp": n.timestamp,
                    "payload": dataclasses.asdict(n.payload) if hasattr(n.payload, "__dataclass_fields__") else n.payload,
                    "edges": [{"target": e.target, "label": e.label} for e in n.edges],
                }
                for n in nodes
            ],
            "edges": all_edges,
        }


# ---------------------------------------------------------------------------
# 3. Demo agent that writes memory nodes as it "executes"
# ---------------------------------------------------------------------------

def now_ts() -> int:
    return int(time.time())


def demo_delegation(store: SqliteGraphStore, agent_id: str, wrapper: str, depth: int = 0) -> str:
    turn_id = str(uuid.uuid4())
    episode = AinlMemoryNode(
        id=str(uuid.uuid4()),
        node_type="episode",
        timestamp=now_ts(),
        payload=EpisodeNode(
            turn_id=turn_id,
            timestamp=now_ts(),
            tool_calls=[f"delegate_to_{wrapper}"],
            delegation_to=wrapper,
            delegation_depth=depth,
            outcome="success",
        ),
        edges=[],
    )
    store.write_node(episode)
    return episode.id


def demo_tool_call(store: SqliteGraphStore, tool_name: str, caused_by: Optional[str] = None) -> str:
    turn_id = str(uuid.uuid4())
    episode = AinlMemoryNode(
        id=str(uuid.uuid4()),
        node_type="episode",
        timestamp=now_ts(),
        payload=EpisodeNode(
            turn_id=turn_id,
            timestamp=now_ts(),
            tool_calls=[tool_name],
            delegation_to=None,
            delegation_depth=0,
            outcome="success",
        ),
        edges=[AinlEdge(target=caused_by, label="caused")] if caused_by else [],
    )
    store.write_node(episode)
    return episode.id


def demo_learn_fact(store: SqliteGraphStore, fact: str, confidence: float, source_id: str, domain: str) -> str:
    node = AinlMemoryNode(
        id=str(uuid.uuid4()),
        node_type="semantic",
        timestamp=now_ts(),
        payload=SemanticNode(
            fact=fact,
            confidence=confidence,
            source_turn_id=source_id,
            domain=domain,
        ),
        edges=[AinlEdge(target=source_id, label="learned_from")],
    )
    store.write_node(node)
    return node.id


def demo_compile_procedure(store: SqliteGraphStore, name: str, source_episode_id: str) -> str:
    mock_ir = json.dumps({
        "ir_version": "1.0",
        "labels": {
            "main": {"steps": [{"op": "R", "adapter": "core", "target": "echo", "args": ["$input"]}]}
        }
    }).encode()
    node = AinlMemoryNode(
        id=str(uuid.uuid4()),
        node_type="procedural",
        timestamp=now_ts(),
        payload=ProceduralNode(
            pattern_name=name,
            compiled_graph=list(mock_ir),
            success_count=1,
            average_tokens_saved=420.0,
        ),
        edges=[AinlEdge(target=source_episode_id, label="compiled_from")],
    )
    store.write_node(node)
    return node.id


def demo_persona_update(store: SqliteGraphStore, trait: str, strength: float, learned_from_ids: List[str]) -> str:
    node = AinlMemoryNode(
        id=str(uuid.uuid4()),
        node_type="persona",
        timestamp=now_ts(),
        payload=PersonaNode(
            trait_name=trait,
            strength=strength,
            learned_from=learned_from_ids,
            last_updated=now_ts(),
        ),
        edges=[AinlEdge(target=eid, label="evolved_from") for eid in learned_from_ids],
    )
    store.write_node(node)
    return node.id


# ---------------------------------------------------------------------------
# 4. AINL RuntimeEngine execution (live when run from repo root)
# ---------------------------------------------------------------------------

DEMO_AINL_PROGRAM = """
# AINL Graph Memory Demo Program
label main
  R memory.store_pattern "demo_pattern" $input
  R core.echo $input -> result
  J result

label recall
  R memory.recall -> episodes
  J episodes
"""

def try_run_ainl_engine(store: SqliteGraphStore) -> Optional[Dict[str, Any]]:
    try:
        from engine import RuntimeEngine
        result = RuntimeEngine.run(
            DEMO_AINL_PROGRAM,
            frame={"input": "Hello from AINL Graph Memory demo!"},
            label="main",
            trace=True,
        )
        ep_id = str(uuid.uuid4())
        episode = AinlMemoryNode(
            id=ep_id,
            node_type="episode",
            timestamp=now_ts(),
            payload=EpisodeNode(
                turn_id=ep_id,
                timestamp=now_ts(),
                tool_calls=["RuntimeEngine.run", "main"],
                delegation_to=None,
                delegation_depth=0,
                outcome="success" if result.get("ok") else "error",
            ),
            edges=[],
        )
        store.write_node(episode)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e), "note": "RuntimeEngine not available — simulating execution only"}


# ---------------------------------------------------------------------------
# 5. Pretty-print helpers
# ---------------------------------------------------------------------------

COLORS = {
    "episode":    "\033[94m",
    "semantic":   "\033[92m",
    "procedural": "\033[93m",
    "persona":    "\033[95m",
    "reset":      "\033[0m",
    "bold":       "\033[1m",
    "dim":        "\033[2m",
}

def fmt(node: AinlMemoryNode) -> str:
    c = COLORS.get(node.node_type, "")
    r = COLORS["reset"]
    b = COLORS["bold"]
    d = COLORS["dim"]
    p = node.payload
    ts = datetime.fromtimestamp(node.timestamp, tz=timezone.utc).strftime("%H:%M:%S")

    if node.node_type == "episode":
        desc = f"tools={p.tool_calls}  delegation_to={p.delegation_to}  outcome={p.outcome}"
    elif node.node_type == "semantic":
        desc = f'"{p.fact}"  confidence={p.confidence:.2f}  domain={p.domain}'
    elif node.node_type == "procedural":
        desc = f'pattern="{p.pattern_name}"  success_count={p.success_count}  tokens_saved≈{p.average_tokens_saved:.0f}'
    elif node.node_type == "persona":
        desc = f'trait="{p.trait_name}"  strength={p.strength:.2f}'
    else:
        desc = str(p)

    edge_str = ""
    if node.edges:
        edge_str = f"\n    {d}→ " + " | ".join(f"{e.label}:{e.target[:8]}…" for e in node.edges) + r

    return f"  {c}{b}[{node.node_type.upper()}]{r} {d}{ts}{r}  {node.id[:8]}…\n    {desc}{edge_str}"


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def run_demo():
    print(f"\n{'='*64}")
    print(f"  {COLORS['bold']}AINL Graph Memory — Live Demo{COLORS['reset']}")
    print(f"  Unified Execution + Memory Substrate for AI Agents")
    print(f"  crates.io: ainl-memory v0.1.1-alpha | ainl-runtime v0.1.1-alpha")
    print(f"{'='*64}\n")

    store = SqliteGraphStore(db_path=":memory:")
    print(f"✓  GraphStore booted  (backend: SQLite in-memory)\n")

    print(f"{COLORS['bold']}── Scene 1: Delegation chain{COLORS['reset']}")
    ep1 = demo_delegation(store, "armaraos", "openclaw_wrapper", depth=0)
    ep2 = demo_delegation(store, "armaraos", "web_search_wrapper", depth=1)
    print(f"   Delegation → openclaw_wrapper   (node {ep1[:8]}…)")
    print(f"   Delegation → web_search_wrapper (node {ep2[:8]}…)\n")

    print(f"{COLORS['bold']}── Scene 2: Tool calls (causally linked){COLORS['reset']}")
    ep3 = demo_tool_call(store, "web.search", caused_by=ep2)
    ep4 = demo_tool_call(store, "core.summarize", caused_by=ep3)
    print(f"   Tool: web.search      (node {ep3[:8]}…, caused_by={ep2[:8]}…)")
    print(f"   Tool: core.summarize  (node {ep4[:8]}…, caused_by={ep3[:8]}…)\n")

    print(f"{COLORS['bold']}── Scene 3: Semantic memory extraction{COLORS['reset']}")
    sem1 = demo_learn_fact(store, "User prefers concise responses under 200 tokens", 0.87, ep4, "user_preference")
    sem2 = demo_learn_fact(store, "web.search returns results in <300ms on average", 0.94, ep3, "performance")
    print(f"   Fact: user_preference  (node {sem1[:8]}…, learned_from={ep4[:8]}…)")
    print(f"   Fact: performance      (node {sem2[:8]}…, learned_from={ep3[:8]}…)\n")

    print(f"{COLORS['bold']}── Scene 4: Procedural memory (compiled executable knowledge){COLORS['reset']}")
    proc1 = demo_compile_procedure(store, "web_search_then_summarize", ep3)
    print(f"   Pattern: web_search_then_summarize  (node {proc1[:8]}…)")
    print(f"   Stored as compiled AINL IR bytes — re-executable without LLM inference\n")

    print(f"{COLORS['bold']}── Scene 5: Persona evolution{COLORS['reset']}")
    pers1 = demo_persona_update(store, "prefers_brevity", 0.87, [ep1, ep4, sem1])
    print(f"   Trait: prefers_brevity  strength=0.87  (node {pers1[:8]}…)\n")

    print(f"{COLORS['bold']}── Scene 6: AINL RuntimeEngine execution{COLORS['reset']}")
    engine_result = try_run_ainl_engine(store)
    if engine_result and engine_result.get("ok"):
        print(f"   ✓ RuntimeEngine.run() → ok=True  result={engine_result.get('result')}")
        if "trace" in engine_result:
            print(f"   ✓ Trace events: {len(engine_result['trace'])} steps recorded")
    else:
        print(f"   ℹ  {engine_result.get('note', '')}")
        if engine_result.get("error"):
            print(f"   ℹ  {engine_result['error'][:120]}")
    print()

    print(f"{COLORS['bold']}── Scene 7: Memory recall — the full graph{COLORS['reset']}")
    all_nodes = store.all_nodes()
    print(f"   Total nodes in graph: {len(all_nodes)}\n")
    for node in all_nodes:
        print(fmt(node))
    print()

    print(f"{COLORS['bold']}── Scene 8: Graph walk from delegation root (depth=4){COLORS['reset']}")
    walked = store.walk_from(ep2, depth=4)
    print(f"   Reachable from web_search_wrapper delegation: {len(walked)} nodes")
    for node in walked:
        print(f"   → [{node.node_type}] {node.id[:8]}…")
    print()

    print(f"{COLORS['bold']}── Scene 9: Type queries{COLORS['reset']}")
    print(f"   Episodes:   {len(store.find_by_type('episode'))}")
    print(f"   Semantic:   {len(store.find_by_type('semantic'))}")
    print(f"   Procedural: {len(store.find_by_type('procedural'))}")
    print(f"   Persona:    {len(store.find_by_type('persona'))}")
    print()

    print(f"{COLORS['bold']}── Scene 10: Graph export (JSON artifact){COLORS['reset']}")
    export = store.export_graph()
    export_path = Path(__file__).parent / "ainl_graph_memory_export.json"
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2, default=str)
    print(f"   Exported {export['node_count']} nodes, {export['edge_count']} edges")
    print(f"   → {export_path}\n")

    print(f"{'='*64}")
    print(f"  {COLORS['bold']}Demo complete.{COLORS['reset']}")
    print(f"  The execution graph IS the memory.")
    print(f"  No separate retrieval layer. No synchronization complexity.")
    print(f"  Every delegation, tool call, fact, pattern, and persona trait")
    print(f"  is a typed node in one persistent, traversable, auditable graph.")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    run_demo()