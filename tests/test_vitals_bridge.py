"""Gap K — CognitiveVitals round-trip through the Python graph bridge.

Tests:
1. test_vitals_round_trip_through_python_graph_store
2. test_armaraos_snapshot_import_maps_vitals
3. test_inbox_write_includes_vitals_when_present
4. test_inbox_write_omits_vitals_when_none
5. test_old_snapshot_without_vitals_imports_cleanly
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_episodic_node(
    *,
    node_id: str | None = None,
    agent_id: str = "test-agent",
    vitals_gate: str | None = None,
    vitals_phase: str | None = None,
    vitals_trust: float | None = None,
) -> "MemoryNode":  # noqa: F821  (imported inside test)
    from armaraos.bridge.ainl_graph_memory import MemoryNode, NodeType

    return MemoryNode(
        id=node_id or str(uuid.uuid4()),
        node_type=NodeType.EPISODIC.value,
        agent_id=agent_id,
        label="test_episode",
        payload={"tool_calls": ["file_read"]},
        tags=["test"],
        created_at=time.time(),
        vitals_gate=vitals_gate,
        vitals_phase=vitals_phase,
        vitals_trust=vitals_trust,
    )


# ---------------------------------------------------------------------------
# Test 1 — vitals survive GraphStore write → read-back
# ---------------------------------------------------------------------------


def test_vitals_round_trip_through_python_graph_store(tmp_path: Path) -> None:
    """MemoryNode with vitals fields persists through GraphStore and can be read back."""
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType

    store_path = tmp_path / "graph.json"
    store = GraphStore(store_path)

    node = _make_episodic_node(
        vitals_gate="pass",
        vitals_phase="reasoning:0.8",
        vitals_trust=0.75,
    )
    store.add_node(node)

    retrieved = store.get_node(node.id)
    assert retrieved is not None
    assert retrieved.vitals_gate == "pass"
    assert retrieved.vitals_phase == "reasoning:0.8"
    assert retrieved.vitals_trust == pytest.approx(0.75, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 2 — Rust snapshot import maps vitals onto Python MemoryNode
# ---------------------------------------------------------------------------


def _rust_episodic_node(
    *,
    node_id: str = "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    agent_id: str = "agent-rust",
    vitals_gate: str | None = "pass",
    vitals_phase: str | None = "reasoning:0.72",
    vitals_trust: float | None = 0.72,
) -> Dict[str, Any]:
    nt: Dict[str, Any] = {
        "type": "episode",
        "turn_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "timestamp": int(time.time()),
        "tool_calls": ["shell_exec"],
        "delegation_to": None,
        "trace_event": None,
        "tags": [],
        "turn_index": 0,
        "user_message_tokens": 10,
        "assistant_response_tokens": 20,
        "persona_signals_emitted": [],
        "flagged": False,
        "conversation_id": "",
        "follows_episode_id": None,
        "user_message": None,
        "assistant_response": None,
        "tools_invoked": [],
    }
    if vitals_gate is not None:
        nt["vitals_gate"] = vitals_gate
    if vitals_phase is not None:
        nt["vitals_phase"] = vitals_phase
    if vitals_trust is not None:
        nt["vitals_trust"] = vitals_trust

    return {
        "id": node_id,
        "agent_id": agent_id,
        "memory_category": "episodic",
        "importance_score": 0.6,
        "node_type": nt,
        "edges": [],
    }


def test_armaraos_snapshot_import_maps_vitals(tmp_path: Path) -> None:
    """Importing a Rust AgentGraphSnapshot episodic node populates vitals on the Python MemoryNode."""
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType, _memory_node_from_rust_export

    rust_node = _rust_episodic_node(
        vitals_gate="pass",
        vitals_phase="reasoning:0.72",
        vitals_trust=0.72,
    )
    py_node = _memory_node_from_rust_export(rust_node)

    assert py_node is not None
    assert py_node.node_type == NodeType.EPISODIC.value
    assert py_node.vitals_gate == "pass"
    assert py_node.vitals_phase == "reasoning:0.72"
    assert py_node.vitals_trust == pytest.approx(0.72, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 3 — inbox write includes vitals when present
# ---------------------------------------------------------------------------


def test_inbox_write_includes_vitals_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a MemoryNode with vitals is pushed to the inbox, vitals keys appear in the JSON."""
    agents_root = tmp_path / "agents"
    agents_root.mkdir(parents=True)
    (agents_root / "agent-vitals").mkdir()

    monkeypatch.setenv("ARMARAOS_AGENT_ID", "agent-vitals")
    monkeypatch.setattr(
        "armaraos.bridge.ainl_memory_sync._armaraos_home_dir",
        lambda: tmp_path,
    )
    from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter

    writer = AinlMemorySyncWriter()
    assert writer.is_available()

    node = _make_episodic_node(
        vitals_gate="warn",
        vitals_phase="hallucination:0.55",
        vitals_trust=0.45,
    )
    result = writer.push_nodes([node])
    assert result.error is None

    inbox_path = agents_root / "agent-vitals" / "ainl_graph_memory_inbox.json"
    data = json.loads(inbox_path.read_text())
    nodes = data["nodes"]
    assert len(nodes) == 1
    n = nodes[0]
    assert n.get("vitals_gate") == "warn"
    assert n.get("vitals_phase") == "hallucination:0.55"
    assert n.get("vitals_trust") == pytest.approx(0.45, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 4 — inbox write omits vitals keys entirely when all None
# ---------------------------------------------------------------------------


def test_inbox_write_omits_vitals_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When vitals are all None, the inbox JSON node must not contain vitals keys at all."""
    agents_root = tmp_path / "agents"
    agents_root.mkdir(parents=True)
    (agents_root / "agent-no-vitals").mkdir()

    monkeypatch.setenv("ARMARAOS_AGENT_ID", "agent-no-vitals")
    monkeypatch.setattr(
        "armaraos.bridge.ainl_memory_sync._armaraos_home_dir",
        lambda: tmp_path,
    )
    from armaraos.bridge.ainl_memory_sync import AinlMemorySyncWriter

    writer = AinlMemorySyncWriter()
    assert writer.is_available()

    node = _make_episodic_node()  # no vitals
    result = writer.push_nodes([node])
    assert result.error is None

    inbox_path = agents_root / "agent-no-vitals" / "ainl_graph_memory_inbox.json"
    data = json.loads(inbox_path.read_text())
    nodes = data["nodes"]
    assert len(nodes) == 1
    n = nodes[0]
    assert "vitals_gate" not in n
    assert "vitals_phase" not in n
    assert "vitals_trust" not in n


# ---------------------------------------------------------------------------
# Test 5 — old snapshot without vitals imports cleanly (no KeyError)
# ---------------------------------------------------------------------------


def test_old_snapshot_without_vitals_imports_cleanly() -> None:
    """Rust snapshot nodes without vitals fields must import cleanly with vitals → None."""
    from armaraos.bridge.ainl_graph_memory import NodeType, _memory_node_from_rust_export

    rust_node = _rust_episodic_node(
        vitals_gate=None,
        vitals_phase=None,
        vitals_trust=None,
    )
    py_node = _memory_node_from_rust_export(rust_node)

    assert py_node is not None
    assert py_node.node_type == NodeType.EPISODIC.value
    assert py_node.vitals_gate is None
    assert py_node.vitals_phase is None
    assert py_node.vitals_trust is None
