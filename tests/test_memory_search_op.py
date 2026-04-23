"""
Runtime coverage for ``MemorySearch`` against a real ``GraphStore`` / bridge.

``GraphStore.search`` ranks by substring match over label+payload+tags in
internal iteration order (insertion order among matches). ``count`` reflects
the number of returned rows after the ``limit`` cap.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge, GraphStore, MemoryNode
from runtime.adapters.base import AdapterRegistry
from runtime.engine import AinlRuntimeError, RuntimeEngine

pytestmark = pytest.mark.usefixtures("offline_llm_provider_config")


def _capabilities() -> dict:
    return {"allow": ["core", "ainl_graph_memory"]}


def _node(
    nid: str,
    *,
    label: str,
    node_type: str = "semantic",
    agent_id: str = "agent_test",
    payload: Dict[str, Any] | None = None,
    tags: List[str] | None = None,
) -> MemoryNode:
    return MemoryNode(
        id=nid,
        node_type=node_type,
        agent_id=agent_id,
        label=label,
        payload=payload or {},
        tags=tags or [],
        created_at=time.time(),
        ttl=None,
    )


def _registry(store: GraphStore) -> AdapterRegistry:
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", AINLGraphMemoryBridge(store))
    return reg


def _run_search_ir(store: GraphStore, *, query: str, node_type: str | None, limit: int) -> Any:
    ir: Dict[str, Any] = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemorySearch",
                            "query": query,
                            "node_type": node_type,
                            "limit": limit,
                            "out": "hits",
                        },
                        {"op": "J", "var": "hits"},
                    ],
                },
            },
        },
        "source": {"lines": []},
        "cst": {"lines": []},
        "capabilities": _capabilities(),
    }
    eng = RuntimeEngine(
        ir=ir,
        adapters=_registry(store),
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
    )
    return eng.run_label("0", {})


def test_memory_search_matches_ranked_insertion_order(tmp_path: Path):
    path = tmp_path / "graph.json"
    store = GraphStore(path)
    store.add_node(_node("m1", label="alpha ranktoken z"))
    store.add_node(_node("m2", label="beta ranktoken y"))
    store.add_node(_node("m3", label="gamma ranktoken x"))
    out = _run_search_ir(store, query="ranktoken", node_type=None, limit=10)
    assert isinstance(out, dict)
    assert out["count"] == 3
    ids = [r["id"] for r in out["results"]]
    assert ids == ["m1", "m2", "m3"]


def test_memory_search_no_matches_empty_envelope(tmp_path: Path):
    store = GraphStore(tmp_path / "g.json")
    out = _run_search_ir(store, query="nomatch_xyz", node_type=None, limit=10)
    assert out == {"results": [], "count": 0}


def test_memory_search_special_characters_in_query(tmp_path: Path):
    store = GraphStore(tmp_path / "g.json")
    needle = '''"quotes":/slashes\\path'''
    store.add_node(_node("sp1", label=f"doc {needle} tail", payload={"k": 1}))
    out = _run_search_ir(store, query=needle, node_type=None, limit=5)
    assert out["count"] == 1
    assert out["results"][0]["id"] == "sp1"


def test_memory_search_missing_adapter_raises_descriptive(tmp_path: Path):
    ir: Dict[str, Any] = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemorySearch",
                            "query": "q",
                            "node_type": None,
                            "limit": 3,
                            "out": "hits",
                        },
                    ],
                },
            },
        },
        "source": {"lines": []},
        "cst": {"lines": []},
        "capabilities": _capabilities(),
    }
    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    eng = RuntimeEngine(
        ir=ir,
        adapters=reg,
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
        host_adapter_denylist=["ainl_graph_memory"],
    )
    with pytest.raises(AinlRuntimeError) as ei:
        eng.run_label("0", {})
    low = str(ei.value).lower()
    assert "adapter" in low or "not registered" in low or "blocked" in low
    env = ei.value.to_dict()
    assert env.get("op") == "MemorySearch"
    assert "ainl_graph_memory" in str(env.get("message", "")).lower()


@pytest.mark.parametrize("limit,expected_len", [(1, 1), (3, 3)])
def test_memory_search_topk_cap(tmp_path: Path, limit: int, expected_len: int):
    store = GraphStore(tmp_path / "g.json")
    for i in range(5):
        store.add_node(_node(f"b{i}", label=f"bulk token {i}"))
    out = _run_search_ir(store, query="bulk", node_type=None, limit=limit)
    assert out["count"] == expected_len
    assert len(out["results"]) == expected_len


def test_memory_search_relevance_substring_order(tmp_path: Path):
    """Earlier inserted nodes that still match the query appear first."""
    store = GraphStore(tmp_path / "g.json")
    store.add_node(_node("r1", label="weak matchtoken", payload={"score": 0.1}))
    store.add_node(_node("r2", label="strong matchtoken extra", payload={"score": 0.9}))
    store.add_node(_node("r3", label="mid matchtoken", payload={"score": 0.5}))
    out = _run_search_ir(store, query="matchtoken", node_type=None, limit=10)
    assert [r["id"] for r in out["results"]] == ["r1", "r2", "r3"]
