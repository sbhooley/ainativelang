"""
AINL Compile-Time Token Cost Estimator
=======================================
Analyzes a compiled IR graph and produces a per-node, per-label, and
total projected token cost before any execution occurs.

Usage (programmatic):
    from tooling.cost_estimator import estimate_graph_cost
    report = estimate_graph_cost(ir, model="gpt-4o")
    print(report.format())

Usage (CLI):
    ainl estimate my_graph.ainl [--model gpt-4o] [--format json|table|summary]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Model pricing table (USD per 1M tokens, input/output)
# Source: public pricing as of May 2026. Update as needed.
# ---------------------------------------------------------------------------
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "gpt-4.1":           {"input": 5.00,  "output": 15.00},
    "gpt-4-turbo":       {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":     {"input": 0.50,  "output": 1.50},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80,  "output": 4.00},
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "gemini-1.5-pro":    {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":  {"input": 0.075, "output": 0.30},
}

DEFAULT_MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Node-type token heuristics
# These are conservative estimates per invocation based on typical payloads.
# LLM nodes are the dominant cost; other nodes are near-zero.
# ---------------------------------------------------------------------------
NODE_TOKEN_HEURISTICS: Dict[str, Dict[str, int]] = {
    # LLM / model calls
    "llm":         {"input": 800,  "output": 300},
    "llm.call":    {"input": 800,  "output": 300},
    "llm.classify":{"input": 400,  "output": 50},
    "llm.embed":   {"input": 500,  "output": 0},   # embeddings = input only
    "llm.summarize":{"input": 1200, "output": 400},
    "llm.extract": {"input": 600,  "output": 200},

    # RAG nodes
    "rag.Src":     {"input": 0,    "output": 0},
    "rag.Chunk":   {"input": 0,    "output": 0},
    "rag.Embed":   {"input": 500,  "output": 0},
    "rag.Store":   {"input": 0,    "output": 0},
    "rag.Ret":     {"input": 200,  "output": 0},
    "rag.Aug":     {"input": 300,  "output": 0},
    "rag.Gen":     {"input": 900,  "output": 350},

    # I/O and adapter nodes (no LLM cost)
    "http":        {"input": 0,    "output": 0},
    "http.get":    {"input": 0,    "output": 0},
    "http.post":   {"input": 0,    "output": 0},
    "x.search":    {"input": 0,    "output": 0},
    "x.post":      {"input": 0,    "output": 0},
    "x.reply":     {"input": 0,    "output": 0},
    "fs":          {"input": 0,    "output": 0},
    "sqlite":      {"input": 0,    "output": 0},
    "memory":      {"input": 0,    "output": 0},

    # Logic / control nodes
    "gate":        {"input": 0,    "output": 0},
    "gate_eval":   {"input": 0,    "output": 0},
    "heuristic_scores": {"input": 0, "output": 0},
    "cursor_commit": {"input": 0,  "output": 0},
    "process_tweet": {"input": 0,  "output": 0},
    "map":         {"input": 0,    "output": 0},
    "filter":      {"input": 0,    "output": 0},
    "merge":       {"input": 0,    "output": 0},
    "branch":      {"input": 0,    "output": 0},
    "loop":        {"input": 0,    "output": 0},
}

# Fallback for unknown node types
UNKNOWN_NODE_HEURISTIC = {"input": 100, "output": 50}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NodeCostEstimate:
    node_id: str
    node_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    is_llm_node: bool
    note: str = ""


@dataclass
class LabelCostEstimate:
    label_id: str
    nodes: List[NodeCostEstimate] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(n.input_tokens for n in self.nodes)

    @property
    def total_output_tokens(self) -> int:
        return sum(n.output_tokens for n in self.nodes)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(n.cost_usd for n in self.nodes)

    @property
    def llm_node_count(self) -> int:
        return sum(1 for n in self.nodes if n.is_llm_node)


@dataclass
class GraphCostReport:
    model: str
    labels: List[LabelCostEstimate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(l.total_input_tokens for l in self.labels)

    @property
    def total_output_tokens(self) -> int:
        return sum(l.total_output_tokens for l in self.labels)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(l.total_cost_usd for l in self.labels)

    @property
    def total_llm_nodes(self) -> int:
        return sum(l.llm_node_count for l in self.labels)

    @property
    def total_nodes(self) -> int:
        return sum(len(l.nodes) for l in self.labels)

    def format(self, style: str = "table") -> str:
        if style == "json":
            return self._format_json()
        elif style == "summary":
            return self._format_summary()
        else:
            return self._format_table()

    def _format_summary(self) -> str:
        lines = [
            f"AINL Graph Cost Estimate — model: {self.model}",
            f"{'─' * 48}",
            f"  Total nodes       : {self.total_nodes}",
            f"  LLM nodes         : {self.total_llm_nodes}",
            f"  Input tokens      : {self.total_input_tokens:,}",
            f"  Output tokens     : {self.total_output_tokens:,}",
            f"  Total tokens      : {self.total_tokens:,}",
            f"  Estimated cost    : ${self.total_cost_usd:.6f} per execution",
            f"  Daily (10x/day)   : ${self.total_cost_usd * 10:.4f}",
            f"  Monthly (10x/day) : ${self.total_cost_usd * 10 * 30:.4f}",
        ]
        if self.warnings:
            lines.append(f"\n  ⚠ Warnings:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)

    def _format_table(self) -> str:
        lines = [
            f"AINL Graph Cost Estimate — model: {self.model}",
            f"{'─' * 72}",
            f"{'Label':<16} {'Node':<24} {'Type':<20} {'Tokens':>8} {'Cost':>12}",
            f"{'─' * 72}",
        ]
        for label in self.labels:
            for node in label.nodes:
                marker = "🤖" if node.is_llm_node else "  "
                lines.append(
                    f"{label.label_id:<16} {node.node_id:<24} {marker}{node.node_type:<18} "
                    f"{node.total_tokens:>8,} ${node.cost_usd:>10.6f}"
                )
            lines.append(
                f"{'':16} {'  LABEL TOTAL':<24} {'':20} {label.total_tokens:>8,} ${label.total_cost_usd:>10.6f}"
            )
            lines.append(f"{'─' * 72}")

        lines += [
            f"{'GRAPH TOTAL':<42} {self.total_tokens:>8,} ${self.total_cost_usd:>10.6f}",
            f"",
            f"  Daily  (10 runs/day) : ${self.total_cost_usd * 10:.4f}",
            f"  Monthly(10 runs/day) : ${self.total_cost_usd * 10 * 30:.4f}",
        ]
        if self.warnings:
            lines.append(f"\n  ⚠ Warnings:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)

    def _format_json(self) -> str:
        data = {
            "model": self.model,
            "totals": {
                "nodes": self.total_nodes,
                "llm_nodes": self.total_llm_nodes,
                "input_tokens": self.total_input_tokens,
                "output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd_per_execution": round(self.total_cost_usd, 8),
                "cost_usd_daily_10x": round(self.total_cost_usd * 10, 6),
                "cost_usd_monthly_10x": round(self.total_cost_usd * 10 * 30, 4),
            },
            "labels": [
                {
                    "label_id": label.label_id,
                    "total_tokens": label.total_tokens,
                    "cost_usd": round(label.total_cost_usd, 8),
                    "nodes": [
                        {
                            "node_id": n.node_id,
                            "node_type": n.node_type,
                            "input_tokens": n.input_tokens,
                            "output_tokens": n.output_tokens,
                            "total_tokens": n.total_tokens,
                            "cost_usd": round(n.cost_usd, 8),
                            "is_llm_node": n.is_llm_node,
                        }
                        for n in label.nodes
                    ],
                }
                for label in self.labels
            ],
            "warnings": self.warnings,
        }
        return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Core estimation logic
# ---------------------------------------------------------------------------

def _is_llm_node(node_type: str) -> bool:
    t = node_type.lower()
    return t.startswith("llm") or t.startswith("rag.gen") or t.startswith("rag.aug")


def _get_heuristic(node_type: str) -> Dict[str, int]:
    """Return token heuristic for a node type, falling back gracefully."""
    # Exact match
    if node_type in NODE_TOKEN_HEURISTICS:
        return NODE_TOKEN_HEURISTICS[node_type]
    # Prefix match (e.g. "llm.custom" → llm)
    prefix = node_type.split(".")[0].lower()
    if prefix in NODE_TOKEN_HEURISTICS:
        return NODE_TOKEN_HEURISTICS[prefix]
    return UNKNOWN_NODE_HEURISTIC


def _compute_cost(input_tokens: int, output_tokens: int, pricing: Dict[str, float]) -> float:
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _extract_nodes_from_label(label_ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract node list from a label's IR, handling multiple IR shapes."""
    # Shape 1: label_ir["nodes"] is a list
    if isinstance(label_ir.get("nodes"), list):
        return label_ir["nodes"]
    # Shape 2: label_ir["nodes"] is a dict keyed by node_id
    if isinstance(label_ir.get("nodes"), dict):
        return [{"id": k, **v} for k, v in label_ir["nodes"].items()]
    # Shape 3: steps array (legacy)
    if isinstance(label_ir.get("steps"), list):
        return [{"id": f"step_{i}", "op": s.get("op", "unknown"), **s}
                for i, s in enumerate(label_ir["steps"])]
    return []


def estimate_graph_cost(
    ir: Dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> GraphCostReport:
    """
    Analyse a compiled AINL IR dict and return a GraphCostReport.

    Parameters
    ----------
    ir : dict
        Compiled IR as produced by AICodeCompiler (labels dict expected at ir["labels"]).
    model : str
        Model name for pricing lookup (default: gpt-4o).
    """
    pricing = MODEL_PRICING.get(model)
    warnings: List[str] = []

    if pricing is None:
        warnings.append(
            f"Unknown model '{model}' — falling back to gpt-4o pricing. "
            f"Available: {', '.join(MODEL_PRICING.keys())}"
        )
        pricing = MODEL_PRICING[DEFAULT_MODEL]

    report = GraphCostReport(model=model, warnings=warnings)

    labels_ir: Dict[str, Any] = ir.get("labels", {})
    if not labels_ir:
        warnings.append("No labels found in IR — graph may be empty or IR format unexpected.")
        return report

    for label_id, label_ir in labels_ir.items():
        label_est = LabelCostEstimate(label_id=label_id)
        raw_nodes = _extract_nodes_from_label(label_ir)

        if not raw_nodes:
            warnings.append(f"Label '{label_id}' has no nodes — skipping.")

        for raw_node in raw_nodes:
            # Determine node type from various IR fields
            node_type = (
                raw_node.get("op")
                or raw_node.get("type")
                or raw_node.get("kind")
                or "unknown"
            )
            node_id = raw_node.get("id") or raw_node.get("node_id") or node_type

            heuristic = _get_heuristic(node_type)
            inp = heuristic["input"]
            out = heuristic["output"]
            cost = _compute_cost(inp, out, pricing)
            is_llm = _is_llm_node(node_type)

            note = ""
            if node_type == "unknown":
                note = "unknown node type — used fallback heuristic"
                warnings.append(f"Node '{node_id}' in label '{label_id}' has unknown type.")

            label_est.nodes.append(NodeCostEstimate(
                node_id=str(node_id),
                node_type=node_type,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                cost_usd=cost,
                is_llm_node=is_llm,
                note=note,
            ))

        report.labels.append(label_est)

    return report


def estimate_file_cost(
    ainl_path: str,
    model: str = DEFAULT_MODEL,
) -> GraphCostReport:
    """
    Compile an .ainl/.lang file and return cost estimate.
    Requires AINL compiler on PYTHONPATH.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from compiler_v2 import AICodeCompiler
    except ImportError as e:
        raise RuntimeError(f"Could not import AINL compiler: {e}")

    source = open(ainl_path).read()
    compiler = AICodeCompiler()
    ir = compiler.compile(source)
    return estimate_graph_cost(ir, model=model)
