"""Tests for runtime.ainl_bundle — single-artifact workflow + memory + persona + tools."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from armaraos.bridge.ainl_graph_memory import (
    AINLGraphMemoryBridge,
    GraphStore,
    MemoryNode,
    NodeType,
    PatchRecord,
)
from compiler_v2 import AICodeCompiler
from runtime.ainl_bundle import AINLBundle, AINLBundleBuilder


def test_bundle_round_trip(tmp_path: Path) -> None:
    """AINLBundle saves and loads all four dimensions correctly."""
    src = """
S app bundle_rt
L1:
  R persona.load * ->traits
  R core.echo traits ->out
  J out
"""
    builder = AINLBundleBuilder(agent_id="rt1")
    bundle = builder.build(src, graph_bridge=None, source_file="rt.ainl")
    path = tmp_path / "x.ainlbundle"
    bundle.save(str(path))
    loaded = AINLBundle.load(str(path))
    assert loaded.workflow.get("ok") == bundle.workflow.get("ok")
    assert loaded.tools == bundle.tools
    assert loaded.memory == bundle.memory
    assert loaded.persona == bundle.persona
    assert loaded.agent_id == "rt1"
    assert loaded.bundle_version == bundle.bundle_version


def test_bundle_tools_extracted() -> None:
    """AINLBundleBuilder extracts R-op tool names from compiled IR."""
    src = """
S app bundle_tools
L1:
  R persona.load * ->traits
  R memory.recall * ->episodes
  R core.echo traits ->out
  J out
"""
    ir = AICodeCompiler().compile(src)
    tools = AINLBundleBuilder()._extract_tools(ir)
    assert tools == ["core.echo", "memory.recall", "persona.load"]


def test_bundle_persona_snapshot(tmp_path: Path) -> None:
    """AINLBundleBuilder snapshots persona traits from live graph bridge."""
    gp = tmp_path / "g.json"
    bridge = AINLGraphMemoryBridge(GraphStore(path=gp))
    bridge.boot(agent_id="snap")
    bridge.call(
        "persona.update",
        {"trait_name": "curious", "strength": 0.66, "learned_from": ["e1"]},
        {},
    )
    bundle = AINLBundleBuilder(agent_id="snap").build("S x core noop\nL1:\n  J 1\n", bridge)
    assert len(bundle.persona) == 1
    assert bundle.persona[0].get("trait_name") == "curious"
    assert bundle.persona[0].get("strength") == 0.66


def test_bundle_from_ainl_file() -> None:
    """Build a bundle from examples/persona_demo.ainl, verify ok=True."""
    root = Path(__file__).resolve().parents[1]
    src = (root / "examples" / "persona_demo.ainl").read_text(encoding="utf-8")
    bundle = AINLBundleBuilder().build(src, None, source_file="examples/persona_demo.ainl")
    assert bundle.workflow.get("ok") is True
    assert bundle.workflow.get("errors") == []
    assert "persona.load" in bundle.tools


def _noop_ir() -> dict:
    return AICodeCompiler().compile("S x core noop\nL1:\n  J 1\n")


def test_bundle_boot_preseeds_persona_and_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gp = tmp_path / "graph.json"
    bundle_path = tmp_path / "agent.ainlbundle"
    ts = time.time()
    patch_rec = PatchRecord(
        node_id="patch_seed_1",
        label_name="L_patch",
        pattern_name="pat_a",
        source_pattern_node_id="proc_seed_1",
        source_episode_ids=[],
        declared_reads=["x"],
        fitness=0.5,
        patch_version=1,
        patched_at=int(ts),
    )
    bundle = AINLBundle(
        workflow=_noop_ir(),
        memory=[
            MemoryNode(
                id="sem_seed_1",
                node_type=NodeType.SEMANTIC.value,
                agent_id="boot_ag",
                label="fact",
                payload={"summary": "seed"},
                tags=["t"],
                created_at=ts,
            ).to_dict(),
            MemoryNode(
                id="epi_seed_1",
                node_type=NodeType.EPISODIC.value,
                agent_id="boot_ag",
                label="episode",
                payload={"event": "boot"},
                tags=[],
                created_at=ts,
            ).to_dict(),
            MemoryNode(
                id="proc_seed_1",
                node_type=NodeType.PROCEDURAL.value,
                agent_id="boot_ag",
                label="pat",
                payload={"pattern_name": "pat", "steps": [{"op": "X", "var": "a", "expr": 1}]},
                tags=[],
                created_at=ts,
            ).to_dict(),
            MemoryNode(
                id=patch_rec.node_id,
                node_type=NodeType.PATCH.value,
                agent_id="boot_ag",
                label=f"patch:{patch_rec.label_name}",
                payload=patch_rec.to_payload(),
                tags=["patch"],
                created_at=float(patch_rec.patched_at),
            ).to_dict(),
        ],
        persona=[{"trait_name": "curious", "strength": 0.7, "learned_from": ["epi_seed_1"]}],
        tools=[],
        agent_id="boot_ag",
    )
    bundle.save(str(bundle_path))
    monkeypatch.setenv("AINL_BUNDLE_PATH", str(bundle_path))
    bridge = AINLGraphMemoryBridge(GraphStore(path=gp))
    bridge.boot(agent_id="boot_ag")
    assert bridge._store.get_node("sem_seed_1") is not None
    assert bridge._store.get_node("epi_seed_1") is not None
    assert bridge._store.get_node("proc_seed_1") is not None
    assert bridge._store.get_node("patch_seed_1") is not None
    traits = bridge._store.find_by_type(NodeType.PERSONA.value, agent_id="boot_ag")
    assert len(traits) == 1
    assert traits[0].trait_name == "curious"


def test_bundle_boot_skips_duplicate_memory_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gp = tmp_path / "graph.json"
    bundle_path = tmp_path / "b.ainlbundle"
    ts = time.time()
    live = MemoryNode(
        id="dup_sem",
        node_type=NodeType.SEMANTIC.value,
        agent_id="ag1",
        label="live",
        payload={"summary": "live"},
        tags=[],
        created_at=ts,
    )
    store = GraphStore(path=gp)
    store.write_node(live, persist=True)
    bundle = AINLBundle(
        workflow=_noop_ir(),
        memory=[
            MemoryNode(
                id="dup_sem",
                node_type=NodeType.SEMANTIC.value,
                agent_id="ag1",
                label="bundle",
                payload={"summary": "from_bundle"},
                tags=[],
                created_at=ts + 10,
            ).to_dict(),
        ],
        persona=[],
        tools=[],
    )
    bundle.save(str(bundle_path))
    monkeypatch.setenv("AINL_BUNDLE_PATH", str(bundle_path))
    bridge = AINLGraphMemoryBridge(GraphStore(path=gp))
    bridge.boot(agent_id="ag1")
    n = bridge._store.get_node("dup_sem")
    assert n is not None
    assert n.payload.get("summary") == "live"


def test_bundle_boot_skips_invalid_memory_nodes_nonfatally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gp = tmp_path / "graph.json"
    bundle_path = tmp_path / "bad.ainlbundle"
    ts = time.time()
    bundle = AINLBundle(
        workflow=_noop_ir(),
        memory=[
            "not-a-dict",
            42,
            {"node_type": "unknown_kind", "id": "x1", "agent_id": "a", "label": "", "payload": {}, "tags": [], "created_at": ts},
            {"node_type": "semantic", "id": "", "payload": {}, "tags": [], "created_at": ts},
            {"node_type": "semantic", "id": "ok_sem", "payload": [], "tags": [], "created_at": ts},
            MemoryNode(
                id="ok_sem",
                node_type=NodeType.SEMANTIC.value,
                agent_id="agx",
                label="ok",
                payload={"summary": "good"},
                tags=[],
                created_at=ts,
            ).to_dict(),
        ],
        persona=[],
        tools=[],
    )
    bundle.save(str(bundle_path))
    monkeypatch.setenv("AINL_BUNDLE_PATH", str(bundle_path))
    bridge = AINLGraphMemoryBridge(GraphStore(path=gp))
    bridge.boot(agent_id="agx")
    assert bridge._store.get_node("ok_sem") is not None


def test_bundle_round_trip_preserves_non_persona_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gp1 = tmp_path / "g1.json"
    bundle_path = tmp_path / "round.ainlbundle"
    gp2 = tmp_path / "g2.json"
    ts = time.time()
    bridge_a = AINLGraphMemoryBridge(GraphStore(path=gp1))
    bridge_a.boot(agent_id="rt_ag")
    for nid, nt, label, payload in [
        ("sem_rt", NodeType.SEMANTIC.value, "l1", {"fact": "alpha"}),
        ("epi_rt", NodeType.EPISODIC.value, "l2", {"e": 1}),
        ("proc_rt", NodeType.PROCEDURAL.value, "pat_rt", {"pattern_name": "pat_rt", "steps": []}),
    ]:
        bridge_a._store.write_node(
            MemoryNode(
                id=nid,
                node_type=nt,
                agent_id="rt_ag",
                label=label,
                payload=payload,
                tags=["rt"],
                created_at=ts,
            ),
            persist=True,
        )
    src = "S x core noop\nL1:\n  J 1\n"
    bundle = AINLBundleBuilder(agent_id="rt_ag").build(src, bridge_a)
    bundle.save(str(bundle_path))
    assert any(n.get("id") == "sem_rt" for n in bundle.memory)
    monkeypatch.setenv("AINL_BUNDLE_PATH", str(bundle_path))
    bridge_b = AINLGraphMemoryBridge(GraphStore(path=gp2))
    bridge_b.boot(agent_id="rt_ag")
    for nid in ("sem_rt", "epi_rt", "proc_rt"):
        got = bridge_b._store.get_node(nid)
        assert got is not None, nid
        assert got.agent_id == "rt_ag"
