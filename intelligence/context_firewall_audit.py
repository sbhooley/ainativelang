from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set


TARGET_ADAPTERS = {"ptc_runner", "llm_query"}


def _audit_source(path: str) -> Dict[str, Any]:
    src = Path(path)
    if not src.exists():
        return {"ok": False, "error": f"missing source: {src}"}
    lines = src.read_text(encoding="utf-8").splitlines()
    defined_keys: Set[str] = set()
    findings: List[Dict[str, Any]] = []
    set_re = re.compile(r"^\s*Set\s+([A-Za-z_][A-Za-z0-9_]*)\b")
    r_re = re.compile(r"^\s*R\s+([A-Za-z0-9_\.]+)\b")
    for idx, line in enumerate(lines, start=1):
        m = set_re.match(line)
        if m:
            key = m.group(1)
            if not key.startswith("_"):
                defined_keys.add(key)
            continue
        m = r_re.match(line)
        if not m:
            continue
        adapter_ref = m.group(1).split(".", 1)[0].lower()
        if adapter_ref in TARGET_ADAPTERS and defined_keys:
            findings.append(
                {
                    "line": idx,
                    "adapter": adapter_ref,
                    "risk": "non_private_context_keys_present",
                    "keys": sorted(defined_keys),
                    "source": line.strip(),
                }
            )
    return {"ok": True, "mode": "source", "source": str(src), "findings": findings, "count": len(findings)}


def _audit_trajectory(path: str) -> Dict[str, Any]:
    src = Path(path)
    if not src.exists():
        return {"ok": False, "error": f"missing trajectory: {src}"}
    findings: List[Dict[str, Any]] = []
    with src.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("operation") or "") != "R":
                continue
            inputs = row.get("inputs")
            if not isinstance(inputs, dict):
                continue
            step = inputs.get("step")
            adapter = ""
            if isinstance(step, dict):
                adapter = str(step.get("adapter") or step.get("src") or "")
            if not adapter:
                adapter = str(inputs.get("adapter") or "")
            adapter = adapter.split(".", 1)[0].lower()
            if adapter not in TARGET_ADAPTERS:
                continue
            context = inputs.get("context")
            if not isinstance(context, dict):
                continue
            risky = sorted(str(k) for k in context.keys() if not str(k).startswith("_"))
            if risky:
                findings.append(
                    {
                        "step_id": row.get("step_id"),
                        "label": row.get("label"),
                        "adapter": adapter,
                        "risk": "non_private_context_keys_present",
                        "keys": risky,
                    }
                )
    return {"ok": True, "mode": "trajectory", "trajectory": str(src), "findings": findings, "count": len(findings)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit potential context firewall leaks for ptc_runner/llm_query.")
    ap.add_argument("--source", default="", help="Path to .ainl source file to audit")
    ap.add_argument("--trajectory", default="", help="Path to trajectory JSONL to audit")
    ap.add_argument("--json", action="store_true", help="Emit JSON output")
    args = ap.parse_args()

    if not args.source and not args.trajectory:
        print(json.dumps({"ok": False, "error": "provide --source or --trajectory"}, indent=2))
        raise SystemExit(2)

    out: Dict[str, Any]
    if args.source:
        out = _audit_source(args.source)
    else:
        out = _audit_trajectory(args.trajectory)

    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
