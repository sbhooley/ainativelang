"""
AINLBundle — unified single-artifact serialization for AINL agents.

An AINLBundle is a single JSON-serializable dict containing:
  - workflow: the compiled AINL IR (from AICodeCompiler.compile())
  - memory:   snapshot of all MemoryNode / EpisodeNode / SemanticNode objects
  - persona:  snapshot of all PersonaNode objects
  - tools:    list of R-op tool names extracted from the compiled IR

This is the "one file, four dimensions" artifact described in the AINL
whitepaper and arXiv preprint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BUNDLE_VERSION = "1.0"


@dataclass
class AINLBundle:
    # Four dimensions
    workflow: Dict[str, Any]  # compiled IR from AICodeCompiler.compile()
    memory: List[Dict[str, Any]]  # serialized graph nodes (non-persona)
    persona: List[Dict[str, Any]]  # serialized PersonaNode list
    tools: List[str]  # R-op adapter strings from compiled IR (e.g. persona.load)

    # Metadata
    bundle_version: str = BUNDLE_VERSION
    agent_id: str = "default"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "source_file": self.source_file,
            "workflow": self.workflow,
            "memory": self.memory,
            "persona": self.persona,
            "tools": self.tools,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AINLBundle":
        return cls(
            workflow=d["workflow"],
            memory=d.get("memory", []),
            persona=d.get("persona", []),
            tools=d.get("tools", []),
            bundle_version=d.get("bundle_version", BUNDLE_VERSION),
            agent_id=d.get("agent_id", "default"),
            created_at=d.get("created_at", ""),
            source_file=d.get("source_file"),
        )

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "AINLBundle":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _iter_label_step_dicts(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten legacy.steps (or top-level steps) from each label in compiled IR."""
    out: List[Dict[str, Any]] = []
    labels = ir.get("labels") or {}
    if not isinstance(labels, dict):
        return out
    for label_body in labels.values():
        if isinstance(label_body, dict):
            legacy = label_body.get("legacy") or {}
            steps = legacy.get("steps")
            if not isinstance(steps, list):
                steps = label_body.get("steps") or []
        elif isinstance(label_body, list):
            steps = label_body
        else:
            steps = []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    out.append(step)
    return out


class AINLBundleBuilder:
    """
    Assembles an AINLBundle from a .ainl source string + a live graph memory bridge.

    Usage:
        builder = AINLBundleBuilder(agent_id="armaraos")
        bundle = builder.build(ainl_source, graph_bridge)
        bundle.save("my_agent.ainlbundle")

        # Round-trip:
        loaded = AINLBundle.load("my_agent.ainlbundle")
    """

    def __init__(self, agent_id: str = "default") -> None:
        self.agent_id = agent_id

    def build(
        self,
        ainl_source: str,
        graph_bridge: Any = None,
        source_file: Optional[str] = None,
    ) -> AINLBundle:
        from compiler_v2 import AICodeCompiler

        compiler = AICodeCompiler()
        ir = compiler.compile(ainl_source)

        tools = self._extract_tools(ir)
        memory = self._snapshot_memory(graph_bridge)
        persona = self._snapshot_persona(graph_bridge)

        return AINLBundle(
            workflow=ir,
            memory=memory,
            persona=persona,
            tools=tools,
            agent_id=self.agent_id,
            source_file=source_file,
        )

    def _extract_tools(self, ir: Dict[str, Any]) -> List[str]:
        """Walk compiled IR and collect R-op adapter strings (e.g. persona.load, core.echo)."""
        tools: set[str] = set()
        for step in _iter_label_step_dicts(ir):
            if step.get("op") != "R":
                continue
            adapter = str(step.get("adapter") or "").strip()
            if adapter:
                tools.add(adapter)
        return sorted(tools)

    def _snapshot_memory(self, graph_bridge: Any) -> List[Dict[str, Any]]:
        """Non-persona graph nodes from export_graph (episodic, semantic, procedural, …)."""
        if graph_bridge is None:
            return []
        try:
            out = graph_bridge.call("export_graph", [], {})
            if not isinstance(out, dict):
                return []
            nodes = out.get("nodes") or []
            if not isinstance(nodes, list):
                return []
            memory: List[Dict[str, Any]] = []
            for n in nodes:
                if not isinstance(n, dict):
                    continue
                if str(n.get("node_type") or "") == "persona":
                    continue
                memory.append(n)
            return memory
        except Exception:
            return []

    def _snapshot_persona(self, graph_bridge: Any) -> List[Dict[str, Any]]:
        if graph_bridge is None:
            return []
        try:
            result = graph_bridge.call("persona_load", [], {})
            if isinstance(result, dict):
                traits = result.get("traits", [])
                if isinstance(traits, list):
                    return [t for t in traits if isinstance(t, dict)]
            return []
        except Exception:
            return []
