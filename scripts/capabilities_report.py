#!/usr/bin/env python3
"""
Capability report tool (Option A).

Reads the unified capability registry and/or Tool API v2 projection and prints
simple summary statistics. This is strictly metadata-only and read-only.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> Dict[str, Any]:
  return json.loads(path.read_text(encoding="utf-8"))


def build_report() -> Dict[str, Any]:
  """Build a summary report from tool_api_v2.tools.json."""
  tools_doc = _load_json(ROOT / "tooling" / "tool_api_v2.tools.json")
  tools = tools_doc.get("tools", [])

  by_kind = Counter()
  by_lane = Counter()
  by_support_tier = Counter()
  by_domain = Counter()
  by_adapter = Counter()
  by_usage_model = Counter()

  for t in tools:
    kind = t.get("kind") or "unknown"
    by_kind[kind] += 1

    lane = t.get("lane") or "unspecified"
    by_lane[lane] += 1

    tier = t.get("support_tier") or "unspecified"
    by_support_tier[tier] += 1

    if kind == "adapter_verb":
      adapter = t.get("adapter") or "unspecified"
      by_adapter[adapter] += 1

    domain = t.get("domain") or "unspecified"
    by_domain[domain] += 1

    usage = t.get("usage_model") or "unspecified"
    by_usage_model[usage] += 1

  report: Dict[str, Any] = {
    "total_tools": len(tools),
    "by_kind": dict(by_kind),
    "by_lane": dict(by_lane),
    "by_support_tier": dict(by_support_tier),
    "by_domain": dict(by_domain),
    "by_usage_model": dict(by_usage_model),
    "by_adapter": dict(by_adapter),
  }
  return report


def format_text(report: Dict[str, Any]) -> str:
  lines = []
  lines.append(f"Total tools: {report['total_tools']}")
  lines.append("")

  lines.append("By kind:")
  for k, v in sorted(report["by_kind"].items()):
    lines.append(f"  {k}: {v}")
  lines.append("")

  lines.append("By lane:")
  for k, v in sorted(report["by_lane"].items()):
    lines.append(f"  {k}: {v}")
  lines.append("")

  lines.append("By support_tier:")
  for k, v in sorted(report["by_support_tier"].items()):
    lines.append(f"  {k}: {v}")
  lines.append("")

  lines.append("By domain:")
  for k, v in sorted(report["by_domain"].items()):
    lines.append(f"  {k}: {v}")
  lines.append("")

  lines.append("By usage_model:")
  for k, v in sorted(report["by_usage_model"].items()):
    lines.append(f"  {k}: {v}")
  lines.append("")

  if report["by_adapter"]:
    lines.append("Adapter verbs by adapter:")
    for k, v in sorted(report["by_adapter"].items()):
      lines.append(f"  {k}: {v}")

  return "\n".join(lines)


def main() -> None:
  ap = argparse.ArgumentParser(description="Capability report (metadata-only).")
  ap.add_argument(
    "--json",
    action="store_true",
    help="Emit JSON report instead of plain text.",
  )
  args = ap.parse_args()

  report = build_report()
  if args.json:
    print(json.dumps(report, indent=2))
  else:
    print(format_text(report))


if __name__ == "__main__":
  main()

