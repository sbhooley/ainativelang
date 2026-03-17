"""
Security/privilege introspection over AINL IR.

This module produces a simple privilege map:
- which adapters / verbs a workflow uses
- which privilege tiers are involved
- per-label breakdown
- whole-graph summary

It is tooling-only and does not change compiler or runtime semantics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler_v2 import AICodeCompiler
from tooling.adapter_manifest import ADAPTER_MANIFEST  # type: ignore
from tooling.graph_api import label_nodes


def _adapter_and_verb(node: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    data = node.get("data") or {}
    if data.get("op") != "R":
        return None
    raw = str(data.get("adapter") or data.get("src") or "")
    if not raw:
        return None
    if "." in raw:
        adapter, verb = raw.split(".", 1)
    else:
        adapter, verb = raw, ""
    return adapter, verb


def _privilege_tier_for_adapter(adapter: str) -> str:
    info = (ADAPTER_MANIFEST.get("adapters") or {}).get(adapter) or {}
    tier = info.get("privilege_tier")
    if isinstance(tier, str) and tier:
        return tier
    return "unknown"


def _adapter_metadata(adapter: str) -> Dict[str, Any]:
    """Return extended metadata fields for an adapter."""
    info = (ADAPTER_MANIFEST.get("adapters") or {}).get(adapter) or {}
    return {
        "destructive": bool(info.get("destructive")),
        "network_facing": bool(info.get("network_facing")),
        "sandbox_safe": bool(info.get("sandbox_safe")),
    }


def analyze_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a privilege map for the given IR.

    Returns a JSON-serializable dict with:
      - schema_version
      - labels: {label_id: {adapters: {...}, nodes: [...]}}
      - summary: {adapters: {...}, privilege_tiers: {...}}
    """
    labels = ir.get("labels") or {}
    label_reports: Dict[str, Any] = {}

    global_adapters: Dict[str, Dict[str, Any]] = {}
    seen_tiers: Set[str] = set()

    for lid in sorted(labels.keys(), key=str):
        nodes = label_nodes(ir, lid)
        label_adapters: Dict[str, Dict[str, Any]] = {}
        label_nodes_report: List[Dict[str, Any]] = []

        for nid, node in nodes.items():
            parsed = _adapter_and_verb(node)
            if not parsed:
                continue
            adapter, verb = parsed
            tier = _privilege_tier_for_adapter(adapter)
            seen_tiers.add(tier)

            meta = _adapter_metadata(adapter)

            label_nodes_report.append(
                {
                    "node_id": nid,
                    "adapter": adapter,
                    "verb": verb,
                    "privilege_tier": tier,
                    "effect": node.get("effect"),
                    "effect_tier": node.get("effect_tier"),
                    "destructive": meta["destructive"],
                    "network_facing": meta["network_facing"],
                    "sandbox_safe": meta["sandbox_safe"],
                }
            )

            # Per-label aggregates.
            la = label_adapters.setdefault(
                adapter,
                {"verbs": set(), "privilege_tiers": set()},
            )
            if verb:
                la["verbs"].add(verb)
            la["privilege_tiers"].add(tier)

            # Global aggregates.
            ga = global_adapters.setdefault(
                adapter,
                {"verbs": set(), "privilege_tiers": set()},
            )
            if verb:
                ga["verbs"].add(verb)
            ga["privilege_tiers"].add(tier)

        # Normalize sets to sorted lists.
        norm_label_adapters: Dict[str, Any] = {}
        for name, info in label_adapters.items():
            norm_label_adapters[name] = {
                "verbs": sorted(info["verbs"]),
                "privilege_tiers": sorted(info["privilege_tiers"]),
            }

        label_reports[str(lid)] = {
            "adapters": norm_label_adapters,
            "nodes": label_nodes_report,
        }

    norm_global_adapters: Dict[str, Any] = {}
    for name, info in global_adapters.items():
        norm_global_adapters[name] = {
            "verbs": sorted(info["verbs"]),
            "privilege_tiers": sorted(info["privilege_tiers"]),
        }

    report = {
        "schema_version": "1.0",
        "labels": label_reports,
        "summary": {
            "adapters": norm_global_adapters,
            "privilege_tiers": sorted(seen_tiers),
        },
    }
    return report


def _load_source_or_ir(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        ir = json.loads(text)
        if not isinstance(ir, dict):
            raise SystemExit("IR JSON must be an object")
        return ir
    # Treat as AINL source.
    compiler = AICodeCompiler()
    ir = compiler.compile(text)
    if ir.get("errors"):
        raise SystemExit(f"compile failed: {ir.get('errors')}")
    return ir


def _print_human(report: Dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    adapters = summary.get("adapters") or {}
    tiers = summary.get("privilege_tiers") or []

    print("== AINL Security / Privilege Report ==")
    print()
    print("Privilege tiers in use:", ", ".join(tiers) if tiers else "(none)")
    print()
    print("Adapters by privilege:")
    for name in sorted(adapters.keys()):
        info = adapters[name]
        v = ", ".join(info.get("verbs") or [])
        t = ", ".join(info.get("privilege_tiers") or [])
        print(f"- {name}: verbs=[{v}] tiers=[{t}]")
    print()
    print("Per-label adapter usage:")
    for lid, lrep in sorted((report.get("labels") or {}).items(), key=lambda x: x[0]):
        ladd = lrep.get("adapters") or {}
        if not ladd:
            continue
        print(f"  Label {lid}:")
        for name, info in sorted(ladd.items()):
            v = ", ".join(info.get("verbs") or [])
            t = ", ".join(info.get("privilege_tiers") or [])
            print(f"    - {name}: verbs=[{v}] tiers=[{t}]")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="AINL security / privilege report")
    parser.add_argument("path", help="Path to AINL source (.ainl/.lang) or IR JSON (.json)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"file not found: {path}")

    ir = _load_source_or_ir(path)
    report = analyze_ir(ir)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)


if __name__ == "__main__":
    main()

