"""AINL_GRAPH_MEMORY_ARMARAOS_EXPORT: merge Rust AgentGraphSnapshot into GraphStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_rust_snapshot_schema_version_one_passes_guard_and_merges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rust ainl-memory uses SNAPSHOT_SCHEMA_VERSION = \"1\"; Python must accept it (not only \"1.0\")."""
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType, _looks_like_armaraos_snapshot

    assert _looks_like_armaraos_snapshot({"schema_version": "1"}) is True

    snap_path = tmp_path / "rust_export_v1.json"
    snap = {
        "agent_id": "agent-rust-1",
        "schema_version": "1",
        "exported_at": "2026-04-01T00:00:00Z",
        "nodes": [
            {
                "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "memory_category": "semantic",
                "importance_score": 0.7,
                "agent_id": "agent-rust-1",
                "node_type": {
                    "type": "semantic",
                    "fact": "from rust",
                    "confidence": 0.9,
                    "source_turn_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "source_episode_id": "",
                    "tags": [],
                },
                "edges": [],
            }
        ],
        "edges": [],
    }
    snap_path.write_text(json.dumps(snap), encoding="utf-8")
    json_path = tmp_path / "overlay.json"
    json_path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    monkeypatch.setenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", str(snap_path))
    store = GraphStore(path=json_path)
    node = store.get_node("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert node is not None
    assert node.node_type == NodeType.SEMANTIC.value
    assert node.payload.get("rust_snapshot", {}).get("node_type", {}).get("fact") == "from rust"


def test_graph_store_merges_armaraos_export_then_overlays_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType

    snap_path = tmp_path / "rust_export.json"
    snap = {
        "agent_id": "agent-1",
        "schema_version": "1.0",
        "exported_at": "2026-01-01T00:00:00Z",
        "nodes": [
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "memory_category": "episodic",
                "importance_score": 0.5,
                "agent_id": "agent-1",
                "node_type": {
                    "type": "episode",
                    "turn_id": "00000000-0000-4000-8000-000000000001",
                    "timestamp": 1700000000,
                    "tool_calls": ["shell_exec"],
                    "trace_event": {"agent_id": "agent-1", "trace_id": "trace-xyz"},
                },
                "edges": [],
            }
        ],
        "edges": [
            {
                "source_id": "00000000-0000-4000-8000-000000000001",
                "target_id": "00000000-0000-4000-8000-000000000002",
                "edge_type": "follows",
                "weight": 1.0,
            }
        ],
    }
    snap_path.write_text(json.dumps(snap), encoding="utf-8")

    json_path = tmp_path / "overlay.json"
    json_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "local-1",
                        "node_type": "semantic",
                        "agent_id": "agent-1",
                        "label": "overlay",
                        "payload": {},
                        "tags": [],
                        "created_at": 1700000100.0,
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", str(snap_path))
    store = GraphStore(path=json_path)
    ids = {n.id for n in store.all_nodes()}
    assert "00000000-0000-4000-8000-000000000001" in ids
    assert "local-1" in ids
    ep = store.get_node("00000000-0000-4000-8000-000000000001")
    assert ep is not None
    assert ep.node_type == NodeType.EPISODIC.value
    assert ep.payload.get("rust_snapshot", {}).get("node_type", {}).get("trace_event", {}).get("trace_id") == "trace-xyz"
    assert len(store.all_edges()) >= 1


def test_armaraos_export_directory_mode_loads_per_agent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shared export directory + ARMARAOS_AGENT_ID resolves to ``{id}_graph_export.json``."""
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType

    exp_dir = tmp_path / "exports"
    exp_dir.mkdir()
    aid = "cafebabe-cafe-4afe-8afe-cafebabecafe"
    snap_path = exp_dir / f"{aid}_graph_export.json"
    snap = {
        "agent_id": aid,
        "schema_version": "1.0",
        "exported_at": "2026-01-01T00:00:00Z",
        "nodes": [
            {
                "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "memory_category": "semantic",
                "importance_score": 0.7,
                "agent_id": aid,
                "node_type": {
                    "type": "semantic",
                    "fact": "from dir export",
                    "confidence": 0.9,
                    "source_turn_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "source_episode_id": "",
                    "tags": [],
                },
                "edges": [],
            }
        ],
        "edges": [],
    }
    snap_path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", str(exp_dir))
    monkeypatch.setenv("ARMARAOS_AGENT_ID", aid)
    overlay = tmp_path / "overlay.json"
    overlay.write_text("{}", encoding="utf-8")
    store = GraphStore(path=overlay)
    node = store.get_node("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert node is not None
    assert node.node_type == NodeType.SEMANTIC.value
    assert node.payload.get("rust_snapshot", {}).get("node_type", {}).get("fact") == "from dir export"


def test_armaraos_export_auto_path_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No AINL_GRAPH_MEMORY_ARMARAOS_EXPORT: load ``<ARMARAOS_HOME>/agents/<id>/ainl_graph_memory_export.json``."""
    from armaraos.bridge.ainl_graph_memory import GraphStore, NodeType

    monkeypatch.delenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", raising=False)
    home = tmp_path / "arm_home"
    monkeypatch.setenv("ARMARAOS_HOME", str(home))
    aid = "deadbeef-dead-4eef-8eef-deadbeefdead"
    auto = home / "agents" / aid / "ainl_graph_memory_export.json"
    auto.parent.mkdir(parents=True)
    snap = {
        "agent_id": aid,
        "schema_version": "1.0",
        "exported_at": "2026-02-02T00:00:00Z",
        "nodes": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "memory_category": "semantic",
                "importance_score": 0.5,
                "agent_id": aid,
                "node_type": {
                    "type": "semantic",
                    "fact": "auto path",
                    "confidence": 0.5,
                    "source_turn_id": "11111111-1111-4111-8111-111111111111",
                    "source_episode_id": "",
                    "tags": [],
                },
                "edges": [],
            }
        ],
        "edges": [],
    }
    auto.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setenv("ARMARAOS_AGENT_ID", aid)
    overlay = tmp_path / "overlay.json"
    overlay.write_text("{}", encoding="utf-8")
    store = GraphStore(path=overlay)
    n = store.get_node("11111111-1111-4111-8111-111111111111")
    assert n is not None
    assert n.node_type == NodeType.SEMANTIC.value


def test_armaraos_export_shared_directory_distinct_filenames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from armaraos.bridge.ainl_graph_memory import _armaraos_export_snapshot_path

    d = tmp_path / "shared_exports"
    d.mkdir()
    monkeypatch.setenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", str(d))
    monkeypatch.setenv("ARMARAOS_AGENT_ID", "agent-one")
    p1 = _armaraos_export_snapshot_path()
    monkeypatch.setenv("ARMARAOS_AGENT_ID", "agent-two")
    p2 = _armaraos_export_snapshot_path()
    assert p1 != p2
    assert p1 is not None and p2 is not None
    assert p1.name == "agent-one_graph_export.json"
    assert p2.name == "agent-two_graph_export.json"


def test_unknown_rust_edge_maps_to_references_with_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from armaraos.bridge.ainl_graph_memory import EdgeType, GraphStore

    snap_path = tmp_path / "e.json"
    snap_path.write_text(
        json.dumps(
            {
                "agent_id": "a",
                "schema_version": "1.0",
                "exported_at": "2026-01-01T00:00:00Z",
                "nodes": [
                    {
                        "id": "11111111-1111-4111-8111-111111111111",
                        "memory_category": "semantic",
                        "importance_score": 0.5,
                        "agent_id": "a",
                        "node_type": {
                            "type": "semantic",
                            "fact": "x",
                            "confidence": 0.5,
                            "source_turn_id": "11111111-1111-4111-8111-111111111111",
                            "source_episode_id": "",
                            "tags": [],
                        },
                        "edges": [],
                    },
                    {
                        "id": "22222222-2222-4222-8222-222222222222",
                        "memory_category": "semantic",
                        "importance_score": 0.5,
                        "agent_id": "a",
                        "node_type": {
                            "type": "semantic",
                            "fact": "y",
                            "confidence": 0.5,
                            "source_turn_id": "22222222-2222-4222-8222-222222222222",
                            "source_episode_id": "",
                            "tags": [],
                        },
                        "edges": [],
                    },
                ],
                "edges": [
                    {
                        "source_id": "11111111-1111-4111-8111-111111111111",
                        "target_id": "22222222-2222-4222-8222-222222222222",
                        "edge_type": "custom_rel_only_in_sqlite",
                        "weight": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AINL_GRAPH_MEMORY_ARMARAOS_EXPORT", str(snap_path))
    p = tmp_path / "empty.json"
    p.write_text("{}", encoding="utf-8")
    store = GraphStore(path=p)
    edges = store.all_edges()
    assert len(edges) == 1
    assert edges[0].edge_type == EdgeType.REFERENCES.value
    assert edges[0].meta.get("armaraos_edge_type") == "custom_rel_only_in_sqlite"
