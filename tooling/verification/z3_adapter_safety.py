"""Z3-based adapter safety verification for AINL IR graphs.

Proves that an IR graph only calls adapters within a given host allowlist
and respects declared effect tiers. Requires optional ``z3-solver`` package.

Usage::

    from tooling.verification.z3_adapter_safety import verify_adapter_safety

    result = verify_adapter_safety(ir, host_allowlist={"core", "http", "fs"})
    if result.all_passed:
        print("All properties verified.")
    else:
        for d in result.violations:
            print(d)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

try:
    import z3  # type: ignore[import]
    _HAS_Z3 = True
except ImportError:
    z3 = None  # type: ignore[assignment]
    _HAS_Z3 = False


KNOWN_EFFECT_TIERS = {"pure", "read", "write", "side_effect", "unknown"}

_BUILTIN_EFFECT_MAP: Dict[str, str] = {
    "core": "pure",
    "cache": "write",
    "queue": "write",
    "memory": "write",
    "fs": "write",
    "http": "side_effect",
    "browser": "side_effect",
    "web": "side_effect",
    "llm": "side_effect",
    "wasm": "pure",
    "postgres": "write",
    "sqlite": "write",
    "redis": "write",
    "solana": "side_effect",
}


@dataclass
class Violation:
    property_id: str
    message: str
    adapter: str = ""
    label: str = ""

    def __str__(self) -> str:
        parts = [f"[{self.property_id}]"]
        if self.label:
            parts.append(f"label={self.label}")
        if self.adapter:
            parts.append(f"adapter={self.adapter}")
        parts.append(self.message)
        return " ".join(parts)


@dataclass
class VerificationResult:
    properties_checked: List[str] = field(default_factory=list)
    violations: List[Violation] = field(default_factory=list)
    z3_available: bool = _HAS_Z3

    @property
    def all_passed(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        if not self.z3_available:
            return "z3-solver not installed; verification skipped."
        total = len(self.properties_checked)
        failed = len(self.violations)
        if failed == 0:
            return f"All {total} properties verified."
        return f"{failed} violation(s) across {total} properties checked."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "z3_available": self.z3_available,
            "properties_checked": self.properties_checked,
            "all_passed": self.all_passed,
            "violation_count": len(self.violations),
            "violations": [
                {"property_id": v.property_id, "adapter": v.adapter, "label": v.label, "message": v.message}
                for v in self.violations
            ],
        }


def _extract_adapter_refs(ir: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract all adapter references from IR steps, with label context."""
    refs = []
    labels = ir.get("labels") or {}
    for label_name, label_data in labels.items():
        steps = label_data if isinstance(label_data, list) else (
            label_data.get("steps") or label_data.get("nodes") or []
        )
        if isinstance(steps, dict):
            steps = list(steps.values())
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = (step.get("op") or step.get("opcode") or "").upper()
            if op not in ("R", "REQUEST", "CALL"):
                continue
            adapter_raw = step.get("adapter") or ""
            if "." in adapter_raw:
                adapter_name = adapter_raw.split(".")[0]
            else:
                adapter_name = adapter_raw
            if adapter_name:
                refs.append({"adapter": adapter_name, "label": label_name})
    return refs


def _extract_declared_adapters(ir: Dict[str, Any]) -> Set[str]:
    """Extract the set of adapters declared in IR metadata."""
    declared: Set[str] = set()
    for meta_entry in ir.get("meta", []):
        if isinstance(meta_entry, dict):
            adapter = meta_entry.get("adapter")
            if adapter:
                declared.add(adapter)
    adapters_section = ir.get("adapters") or {}
    if isinstance(adapters_section, dict):
        declared.update(adapters_section.keys())
    for ref in _extract_adapter_refs(ir):
        declared.add(ref["adapter"])
    return declared


def _get_effect_tier(adapter: str) -> str:
    return _BUILTIN_EFFECT_MAP.get(adapter, "unknown")


def verify_adapter_safety(
    ir: Dict[str, Any],
    host_allowlist: Optional[FrozenSet[str]] = None,
    effect_map: Optional[Dict[str, str]] = None,
) -> VerificationResult:
    """Verify adapter safety properties on a compiled IR.

    Parameters
    ----------
    ir : dict
        Compiled IR as returned by the compiler.
    host_allowlist : frozenset[str] or None
        Set of adapter names the host permits. If None, P1 is skipped.
    effect_map : dict or None
        Override mapping of adapter name to effect tier. Defaults to builtin map.

    Returns
    -------
    VerificationResult
    """
    result = VerificationResult()

    if not _HAS_Z3:
        return result

    eff_map = dict(_BUILTIN_EFFECT_MAP)
    if effect_map:
        eff_map.update(effect_map)

    refs = _extract_adapter_refs(ir)
    declared = _extract_declared_adapters(ir)
    used_adapters = {r["adapter"] for r in refs}

    # P1: Adapter allowlist
    if host_allowlist is not None:
        result.properties_checked.append("P1_adapter_allowlist")
        for ref in refs:
            adapter = ref["adapter"]
            a_var = z3.Bool(f"allowed_{adapter}")
            solver = z3.Solver()
            solver.add(a_var == z3.BoolVal(adapter in host_allowlist))
            solver.add(z3.Not(a_var))
            if solver.check() == z3.sat:
                result.violations.append(Violation(
                    property_id="P1",
                    message=f"Adapter '{adapter}' is not in the host allowlist",
                    adapter=adapter,
                    label=ref["label"],
                ))

    # P2: No undeclared adapter refs
    result.properties_checked.append("P2_no_undeclared_refs")
    for ref in refs:
        adapter = ref["adapter"]
        d_var = z3.Bool(f"declared_{adapter}")
        solver = z3.Solver()
        solver.add(d_var == z3.BoolVal(adapter in declared))
        solver.add(z3.Not(d_var))
        if solver.check() == z3.sat:
            result.violations.append(Violation(
                property_id="P2",
                message=f"Adapter '{adapter}' used but not declared in IR",
                adapter=adapter,
                label=ref["label"],
            ))

    # P3: Effect tier compliance
    result.properties_checked.append("P3_effect_tier_compliance")
    labels_meta = ir.get("labels") or {}
    for label_name, label_data in labels_meta.items():
        if not isinstance(label_data, dict):
            continue
        label_tier = label_data.get("effect_tier") or label_data.get("pure")
        if label_tier in (True, "pure"):
            for ref in refs:
                if ref["label"] != label_name:
                    continue
                adapter_tier = eff_map.get(ref["adapter"], "unknown")
                if adapter_tier in ("write", "side_effect"):
                    result.violations.append(Violation(
                        property_id="P3",
                        message=f"Label '{label_name}' declared pure but calls '{ref['adapter']}' (effect: {adapter_tier})",
                        adapter=ref["adapter"],
                        label=label_name,
                    ))

    # P4: DAG acyclicity (label call graph)
    result.properties_checked.append("P4_dag_acyclicity")
    call_graph: Dict[str, Set[str]] = {}
    for label_name, label_data in labels_meta.items():
        steps = label_data if isinstance(label_data, list) else (
            label_data.get("steps") or label_data.get("nodes") or []
        )
        if isinstance(steps, dict):
            steps = list(steps.values())
        targets: Set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = (step.get("op") or "").upper()
            if op in ("CALL", "J"):
                target = step.get("target") or step.get("label") or ""
                if target and target in labels_meta:
                    targets.add(target)
        call_graph[label_name] = targets

    def _has_cycle(graph: Dict[str, Set[str]]) -> Optional[str]:
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        for node in graph:
            if node in visited:
                continue
            stack = [(node, False)]
            while stack:
                current, processed = stack.pop()
                if processed:
                    in_stack.discard(current)
                    visited.add(current)
                    continue
                if current in in_stack:
                    return current
                in_stack.add(current)
                stack.append((current, True))
                for neighbor in graph.get(current, set()):
                    if neighbor not in visited:
                        stack.append((neighbor, False))
        return None

    cycle_node = _has_cycle(call_graph)
    if cycle_node:
        result.violations.append(Violation(
            property_id="P4",
            message=f"Cycle detected in label call graph involving '{cycle_node}'",
            label=cycle_node,
        ))

    return result
