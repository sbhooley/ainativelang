"""Identify deterministic (LLM-free) label subgraphs in AINL IR.

Analysis-only tool for the P5 research spike. Identifies labels and subgraphs
that contain no LLM adapter calls and could theoretically be candidates for
deterministic execution (WASM, native, etc.).

This does NOT emit WASM or native code. It is a prerequisite analysis step.

Usage::

    from tooling.wasm_subgraph_analysis import analyze_deterministic_subgraphs

    report = analyze_deterministic_subgraphs(ir)
    for sg in report["subgraphs"]:
        print(sg["labels"], sg["adapter_families"])
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

_LLM_ADAPTER_NAMES = frozenset({
    "llm", "llm_query", "llm_runtime", "openrouter",
    "anthropic", "ollama", "cohere", "openai",
})

_SIDE_EFFECT_ADAPTERS = frozenset({
    "http", "web", "browser", "solana", "email",
})


def _extract_label_adapters(ir: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Map each label to its set of adapter names."""
    label_adapters: Dict[str, Set[str]] = {}
    labels = ir.get("labels") or {}
    for label_name, label_data in labels.items():
        adapters: Set[str] = set()
        steps = label_data if isinstance(label_data, list) else (
            label_data.get("steps") or label_data.get("nodes") or []
        )
        if isinstance(steps, dict):
            steps = list(steps.values())
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = (step.get("op") or "").upper()
            if op not in ("R", "REQUEST", "CALL"):
                continue
            adapter_raw = step.get("adapter") or ""
            if "." in adapter_raw:
                adapter_name = adapter_raw.split(".")[0]
            else:
                adapter_name = adapter_raw
            if adapter_name:
                adapters.add(adapter_name.lower())
        label_adapters[label_name] = adapters
    return label_adapters


def _extract_call_graph(ir: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Extract label-to-label call edges from IR."""
    labels = ir.get("labels") or {}
    graph: Dict[str, Set[str]] = {name: set() for name in labels}
    for label_name, label_data in labels.items():
        steps = label_data if isinstance(label_data, list) else (
            label_data.get("steps") or label_data.get("nodes") or []
        )
        if isinstance(steps, dict):
            steps = list(steps.values())
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = (step.get("op") or "").upper()
            if op in ("CALL", "J"):
                target = step.get("target") or step.get("label") or ""
                if target and target in labels:
                    graph[label_name].add(target)
            if op == "IF":
                for branch_key in ("then", "else", "then_label", "else_label"):
                    branch = step.get(branch_key) or ""
                    if branch and branch in labels:
                        graph[label_name].add(branch)
    return graph


def _is_deterministic_label(adapters: Set[str]) -> bool:
    """A label is deterministic if it has no LLM or external side-effect adapters."""
    return not adapters.intersection(_LLM_ADAPTER_NAMES) and not adapters.intersection(_SIDE_EFFECT_ADAPTERS)


def _find_connected_components(
    labels: Set[str],
    call_graph: Dict[str, Set[str]],
) -> List[Set[str]]:
    """Find connected components in the undirected version of the call graph."""
    undirected: Dict[str, Set[str]] = {l: set() for l in labels}
    for src in labels:
        for dst in call_graph.get(src, set()):
            if dst in labels:
                undirected[src].add(dst)
                undirected[dst].add(src)

    visited: Set[str] = set()
    components: List[Set[str]] = []
    for start in labels:
        if start in visited:
            continue
        component: Set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in undirected.get(node, set()):
                if neighbor not in visited:
                    stack.append(neighbor)
        if component:
            components.append(component)
    return components


def analyze_deterministic_subgraphs(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze an IR graph for deterministic (LLM-free) subgraphs.

    Returns a report with:
    - ``labels``: per-label analysis (adapters, is_deterministic)
    - ``subgraphs``: connected components of deterministic labels
    - ``summary``: high-level counts
    """
    label_adapters = _extract_label_adapters(ir)
    call_graph = _extract_call_graph(ir)

    per_label: List[Dict[str, Any]] = []
    deterministic_labels: Set[str] = set()
    for label_name, adapters in label_adapters.items():
        is_det = _is_deterministic_label(adapters)
        if is_det:
            deterministic_labels.add(label_name)
        per_label.append({
            "label": label_name,
            "adapters": sorted(adapters),
            "is_deterministic": is_det,
        })

    components = _find_connected_components(deterministic_labels, call_graph)
    subgraphs: List[Dict[str, Any]] = []
    for comp in sorted(components, key=len, reverse=True):
        all_adapters: Set[str] = set()
        for label in comp:
            all_adapters.update(label_adapters.get(label, set()))
        subgraphs.append({
            "labels": sorted(comp),
            "label_count": len(comp),
            "adapter_families": sorted(all_adapters),
        })

    total_labels = len(label_adapters)
    det_count = len(deterministic_labels)
    return {
        "labels": per_label,
        "subgraphs": subgraphs,
        "summary": {
            "total_labels": total_labels,
            "deterministic_labels": det_count,
            "non_deterministic_labels": total_labels - det_count,
            "deterministic_subgraph_count": len(subgraphs),
            "deterministic_ratio": round(det_count / max(total_labels, 1), 3),
        },
    }
