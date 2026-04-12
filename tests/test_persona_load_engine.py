"""Integration: ``R persona.load`` fills ``__persona__`` / ``persona_instruction`` via ainl_graph_memory."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge, GraphStore, NodeType, PersonaNode
from compiler_v2 import AICodeCompiler
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine


def test_persona_load_sets_frame_meta_and_returns_traits():
    path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
    try:
        store = GraphStore(path=path)
        bridge = AINLGraphMemoryBridge(store)
        bridge.boot(agent_id="int")
        bridge.call(
            "persona.update",
            {"trait_name": "prefers_brevity", "strength": 0.85, "learned_from": []},
            {},
        )

        reg = AdapterRegistry(allowed=["core", "ainl_graph_memory"])
        reg.register("core", CoreBuiltinAdapter())
        reg.register("ainl_graph_memory", bridge)

        ir = {
            "labels": {
                "1": {
                    "legacy": {
                        "steps": [
                            {
                                "op": "R",
                                "adapter": "persona.load",
                                "target": "*",
                                "args": [],
                                "out": "traits",
                            },
                            {"op": "J", "var": "traits"},
                        ],
                    },
                },
            },
            "capabilities": {"allow": ["core", "ainl_graph_memory"]},
            "source": {"lines": []},
            "cst": {"lines": []},
        }
        eng = RuntimeEngine(
            ir=ir,
            adapters=reg,
            trace=False,
            step_fallback=False,
            execution_mode="steps-only",
            unknown_op_policy="error",
        )
        frame: dict = {"agent_id": "int"}
        out = eng._run_label("1", frame, [], force_steps=True)
        assert isinstance(out, list)
        assert len(out) == 1
        assert out[0]["trait_name"] == "prefers_brevity"
        assert frame["__persona__"] == {"prefers_brevity": 0.85}
        assert "prefers_brevity" in frame["persona_instruction"]
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def test_persona_update_creates_findable_persona_node():
    """persona.update writes a persona node retrievable via find_by_type."""
    path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
    try:
        bridge = AINLGraphMemoryBridge(GraphStore(path=path))
        bridge.boot(agent_id="nid")
        bridge.call(
            "persona.update",
            {"trait_name": "curious", "strength": 0.55, "learned_from": ["ep_1"]},
            {},
        )
        rows = bridge._store.find_by_type(NodeType.PERSONA.value, agent_id="nid")
        assert len(rows) == 1
        assert isinstance(rows[0], PersonaNode)
        assert rows[0].trait_name == "curious"
        assert rows[0].strength == 0.55
        assert rows[0].learned_from == ["ep_1"]
        assert isinstance(rows[0].last_updated, int)
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def test_persona_demo_source_strict_compile_clean():
    """examples/persona_demo.ainl compiles under strict mode with no diagnostics."""
    root = Path(__file__).resolve().parents[1]
    src = (root / "examples" / "persona_demo.ainl").read_text(encoding="utf-8")
    result = AICodeCompiler(strict_mode=True).compile(src)
    assert result.get("ok") is True
    assert result.get("errors") == []
    assert result.get("warnings") == []
