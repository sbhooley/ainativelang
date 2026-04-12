"""
TDD for RuntimeEngine MemoryRecall / MemorySearch ops (ainl_graph_memory).

These tests expect ``runtime/engine.py`` to dispatch:

- ``MemoryRecall``: ``adapters.call("ainl_graph_memory", "memory_recall", [node_id], frame)``
  with ``node_id`` resolved from the step; bind result to ``out`` (default ``recalled``).
- ``MemorySearch``: ``adapters.call("ainl_graph_memory", "memory_search", [query, node_type, agent_id, limit], frame)``
  with optional ``agent_id`` defaulting to ``None`` when omitted.

Mirror patterns used for ``CacheGet`` / ``CacheSet`` in ``_exec_step`` (step mode) and
``_run_label_graph`` (graph mode): ``_count_adapter_call``, assign ``frame[out_var]``, then
advance the graph cursor via ``_next_linear_node_edge``.

Until those branches exist, ``pytest tests/test_memory_recall_op.py`` fails (unknown op or
missing frame binding) — that is intentional.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterError, RuntimeAdapter
from runtime.engine import AinlRuntimeError, RuntimeEngine


class MockAinlGraphMemoryAdapter(RuntimeAdapter):
    """Records calls; returns configurable payloads for memory_recall / memory_search."""

    def __init__(
        self,
        *,
        recall_return: dict | None = None,
        search_return: dict | None = None,
    ) -> None:
        self.recall_return = recall_return
        self.search_return = search_return
        self.recall_calls: list[list] = []
        self.search_calls: list[list] = []

    def call(self, target: str, args: list, context: dict):
        t = str(target or "").strip().lower()
        if t == "memory_recall":
            self.recall_calls.append(list(args))
            if self.recall_return is not None:
                return self.recall_return
            return {"error": "not found"}
        if t == "memory_search":
            self.search_calls.append(list(args))
            if self.search_return is not None:
                return self.search_return
            return {"results": [], "count": 0}
        raise AdapterError(f"unexpected target {target!r}")


def _capabilities() -> dict:
    return {"allow": ["core", "ainl_graph_memory"]}


def _make_registry(mock: MockAinlGraphMemoryAdapter) -> "AdapterRegistry":
    from runtime.adapters.base import AdapterRegistry

    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    reg.register("ainl_graph_memory", mock)
    return reg


def test_memory_recall_op_in_step_mode():
    fake_node = {
        "id": "test-node-123",
        "node_type": "procedural",
        "agent_id": "agent_alpha",
        "label": "pat",
        "payload": {"steps": []},
        "tags": [],
        "created_at": 0.0,
        "ttl": None,
    }
    mock = MockAinlGraphMemoryAdapter(recall_return=fake_node)
    ir = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemoryRecall",
                            "node_id": "test-node-123",
                            "out": "recalled",
                        },
                        {"op": "J", "var": "recalled"},
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
        adapters=_make_registry(mock),
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
    )
    out = eng.run_label("0", {})
    assert out == fake_node
    assert mock.recall_calls == [["test-node-123"]]


def test_memory_recall_op_in_graph_mode():
    fake_node = {"id": "nid-graph", "node_type": "episodic", "label": "x"}
    mock = MockAinlGraphMemoryAdapter(recall_return=fake_node)
    ir = {
        "labels": {
            "0": {
                "entry": "n_mr",
                "nodes": [
                    {
                        "id": "n_mr",
                        "op": "MemoryRecall",
                        "data": {
                            "op": "MemoryRecall",
                            "node_id": "test-node-123",
                            "out": "recalled",
                        },
                    },
                    {
                        "id": "n_j",
                        "op": "J",
                        "data": {"op": "J", "var": "recalled"},
                    },
                ],
                "edges": [{"from": "n_mr", "to": "n_j", "to_kind": "node"}],
                "legacy": {"steps": []},
            },
        },
        "source": {"lines": []},
        "cst": {"lines": []},
        "capabilities": _capabilities(),
    }
    eng = RuntimeEngine(
        ir=ir,
        adapters=_make_registry(mock),
        trace=False,
        step_fallback=False,
        execution_mode="graph-only",
        unknown_op_policy="error",
    )
    out = eng.run_label("0", {})
    assert out == fake_node
    assert mock.recall_calls == [["test-node-123"]]


def test_memory_recall_not_found():
    mock = MockAinlGraphMemoryAdapter(recall_return={"error": "not found"})
    ir = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemoryRecall",
                            "node_id": "missing",
                            "out": "recalled",
                        },
                        {"op": "J", "var": "recalled"},
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
        adapters=_make_registry(mock),
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
    )
    out = eng.run_label("0", {})
    assert out == {"error": "not found"}


def test_memory_search_op_in_step_mode():
    search_payload = {
        "results": [{"id": "a", "label": "alpha"}],
        "count": 2,
    }
    mock = MockAinlGraphMemoryAdapter(search_return=search_payload)
    ir = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemorySearch",
                            "query": "transformer",
                            "node_type": "procedural",
                            "limit": 5,
                            "out": "results",
                        },
                        {"op": "J", "var": "results"},
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
        adapters=_make_registry(mock),
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
    )
    out = eng.run_label("0", {})
    assert out == search_payload
    # Bridge signature: memory_search(query, node_type, agent_id, limit)
    assert mock.search_calls == [["transformer", "procedural", None, 5]]


def test_memory_recall_missing_adapter_raises():
    """Without ``ainl_graph_memory`` registered, dispatch must fail.

    Before ``MemoryRecall`` exists in the engine, this is an ``AinlRuntimeError``
    (unknown op). After implementation, expect ``AdapterError`` (adapter not registered).
    """
    ir = {
        "labels": {
            "0": {
                "legacy": {
                    "steps": [
                        {
                            "op": "MemoryRecall",
                            "node_id": "any",
                            "out": "recalled",
                        },
                    ],
                },
            },
        },
        "source": {"lines": []},
        "cst": {"lines": []},
        "capabilities": _capabilities(),
    }
    from runtime.adapters.base import AdapterRegistry

    reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
    # Deliberately omit ainl_graph_memory registration (core still registered by engine).
    eng = RuntimeEngine(
        ir=ir,
        adapters=reg,
        trace=False,
        step_fallback=False,
        execution_mode="steps-only",
        unknown_op_policy="error",
    )
    with pytest.raises((AdapterError, AinlRuntimeError)) as ei:
        eng.run_label("0", {})
    ex = ei.value
    if isinstance(ex, AinlRuntimeError):
        assert "MemoryRecall" in str(ex)
    else:
        low = str(ex).lower()
        assert "adapter" in low or "not registered" in low or "blocked" in low
