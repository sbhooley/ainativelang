"""Tests for runtime.ainl_bundle — single-artifact workflow + memory + persona + tools."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from armaraos.bridge.ainl_graph_memory import AINLGraphMemoryBridge, GraphStore
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
