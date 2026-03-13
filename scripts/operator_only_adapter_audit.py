#!/usr/bin/env python3
"""
Operator-only adapter audit (read-only).

Inspects the capability registry and scans AINL source files to report where
operator_only capabilities are used. Used to validate that safety/trust-rail
separation is reflected in the codebase.

Read-only: does not modify compiler, runtime, or capability metadata.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
CAPABILITIES_PATH = ROOT / "tooling" / "capabilities.json"

# Glob patterns for AINL source (relative to repo root)
SOURCE_GLOBS = [
    "examples/**/*.lang",
    "examples/**/*.ainl",
    "demo/**/*.lang",
    "demo/**/*.ainl",
    "corpus/**/*.ainl",
    "corpus/**/*.lang",
    "tests/**/*.lang",
    "tests/**/*.ainl",
]

# Adapter verbs: (adapter, verb) -> capability id. We build patterns from these.
# Pattern in source: "R adapter verb" or "R adapter.verb" or "X x (adapter verb)"
def _adapter_verb_pattern(adapter: str, verb: str) -> re.Pattern[str]:
    # Match adapter and verb with optional dot, space, or parens context
    escaped_a, escaped_v = re.escape(adapter), re.escape(verb)
    return re.compile(
        rf"\b{escaped_a}\s*\.?\s*{escaped_v}\b|\(\s*{escaped_a}\s+{escaped_v}\s*\)",
        re.IGNORECASE,
    )


def _file_category(rel_path: str) -> str:
    if rel_path.startswith("examples/autonomous_ops/"):
        return "autonomous_ops"
    if rel_path.startswith("examples/openclaw/"):
        return "openclaw_extension"
    if rel_path.startswith("demo/"):
        return "demo"
    if rel_path.startswith("examples/"):
        return "example"
    if rel_path.startswith("corpus/"):
        return "corpus"
    if rel_path.startswith("tests/"):
        return "tests"
    return "other"


def load_operator_only_capabilities(cap_path: Path) -> List[Dict[str, Any]]:
    """Load capabilities.json and return entries that have operator_only in safety_tags."""
    data = json.loads(cap_path.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for entry in data.get("adapter_verbs", []):
        if "operator_only" in (entry.get("safety_tags") or []):
            out.append({**entry, "kind": "adapter_verb"})
    for entry in data.get("module_skills", []):
        if "operator_only" in (entry.get("safety_tags") or []):
            out.append({**entry, "kind": "module_skill"})
    return out


def collect_source_files(root: Path) -> List[Path]:
    """Collect AINL source files under root from SOURCE_GLOBS."""
    seen: Set[Path] = set()
    for pattern in SOURCE_GLOBS:
        for p in root.glob(pattern):
            if p.is_file() and p.suffix in (".lang", ".ainl"):
                seen.add(p)
    return sorted(seen)


def find_references(
    root: Path,
    capabilities: List[Dict[str, Any]],
) -> Dict[str, List[Tuple[str, str]]]:
    """
    For each operator_only capability, find (file_path, category) of files that reference it.
    Returns dict: capability_id -> [(rel_path, category), ...]
    """
    source_files = collect_source_files(root)
    # Build matchers for adapter_verbs: id -> compiled pattern
    patterns: Dict[str, re.Pattern[str]] = {}
    program_paths: Dict[str, str] = {}  # module_skill id -> program_path
    for cap in capabilities:
        cid = cap.get("id") or ""
        if cap.get("kind") == "adapter_verb":
            adapter = cap.get("adapter") or ""
            verb = cap.get("verb") or ""
            if adapter and verb:
                patterns[cid] = _adapter_verb_pattern(adapter, verb)
        elif cap.get("kind") == "module_skill":
            src = cap.get("source") or {}
            path = src.get("program_path") or ""
            if path:
                program_paths[cid] = path.replace("\\", "/")

    refs: Dict[str, List[Tuple[str, str]]] = {c["id"]: [] for c in capabilities}

    for path in source_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path.relative_to(root))
        category = _file_category(rel)

        for cap_id, pat in patterns.items():
            if pat.search(text):
                refs[cap_id].append((rel, category))

        for cap_id, prog_path in program_paths.items():
            if rel == prog_path or rel.replace("\\", "/") == prog_path:
                refs[cap_id].append((rel, category))

    return refs


def run_audit(
    root: Path,
    cap_path: Path,
    *,
    only_used: bool = False,
    only_unused: bool = False,
) -> Dict[str, Any]:
    """Run full audit and return structured result."""
    capabilities = load_operator_only_capabilities(cap_path)
    refs = find_references(root, capabilities)

    used_ids: Set[str] = {cid for cid, files in refs.items() if files}
    used_caps = [c for c in capabilities if c["id"] in used_ids]
    unused_caps = [c for c in capabilities if c["id"] not in used_ids]

    if only_used:
        report_caps = used_caps
    elif only_unused:
        report_caps = unused_caps
    else:
        report_caps = capabilities

    files_with_refs: Set[str] = set()
    for flist in refs.values():
        for rel, _ in flist:
            files_with_refs.add(rel)

    report: List[Dict[str, Any]] = []
    for cap in report_caps:
        cid = cap.get("id") or ""
        kind = cap.get("kind") or ""
        file_list = refs.get(cid, [])
        # Deduplicate by path, keep category from first occurrence
        by_path: Dict[str, str] = {}
        for rel, cat in file_list:
            if rel not in by_path:
                by_path[rel] = cat
        report.append({
            "capability_id": cid,
            "kind": kind,
            "files": [{"path": p, "category": by_path[p]} for p in sorted(by_path.keys())],
        })

    return {
        "summary": {
            "total_operator_only_in_registry": len(capabilities),
            "total_operator_only_referenced": len(used_ids),
            "total_files_referencing_operator_only": len(files_with_refs),
        },
        "report": report,
        "unused_capability_ids": sorted([c["id"] for c in unused_caps]),
    }


def format_plain(result: Dict[str, Any]) -> str:
    """Format audit result as plain text."""
    lines: List[str] = []
    s = result["summary"]
    lines.append("Operator-only adapter audit (read-only)")
    lines.append("=" * 50)
    lines.append(f"Total operator_only capabilities in registry: {s['total_operator_only_in_registry']}")
    lines.append(f"Total operator_only capabilities referenced:   {s['total_operator_only_referenced']}")
    lines.append(f"Total files referencing operator_only:        {s['total_files_referencing_operator_only']}")
    lines.append("")
    for entry in result["report"]:
        lines.append(f"  {entry['capability_id']} ({entry['kind']})")
        for f in entry["files"]:
            lines.append(f"    - {f['path']} [{f['category']}]")
        if not entry["files"]:
            lines.append("    (no references)")
        lines.append("")
    unused = result.get("unused_capability_ids") or []
    if unused:
        lines.append("Operator_only in registry but not referenced:")
        for u in unused:
            lines.append(f"  - {u}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Operator-only capability audit: where operator_only capabilities are used (read-only).",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repo root (default: script parent parent).",
    )
    ap.add_argument(
        "--capabilities",
        type=Path,
        default=CAPABILITIES_PATH,
        help="Path to capabilities.json.",
    )
    ap.add_argument(
        "--only-used",
        action="store_true",
        help="Report only capabilities that are referenced in source.",
    )
    ap.add_argument(
        "--only-unused",
        action="store_true",
        help="Report only capabilities that are not referenced.",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    args = ap.parse_args()

    if args.only_used and args.only_unused:
        ap.error("Use at most one of --only-used and --only-unused")

    if not args.capabilities.is_file():
        raise SystemExit(f"Capabilities file not found: {args.capabilities}")

    result = run_audit(
        args.root,
        args.capabilities,
        only_used=args.only_used,
        only_unused=args.only_unused,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_plain(result))


if __name__ == "__main__":
    main()
