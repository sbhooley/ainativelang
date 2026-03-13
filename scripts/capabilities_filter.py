#!/usr/bin/env python3
"""
Capability filtering helper (Option B).

Reads the Tool API v2 projection and returns filtered subsets of tools based on
kind, lane, support_tier, adapter, safety_tags, and effects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parent.parent


def _load_tools() -> List[Dict[str, Any]]:
  tools_doc = json.loads((ROOT / "tooling" / "tool_api_v2.tools.json").read_text(encoding="utf-8"))
  return tools_doc.get("tools", [])


SUPPORTED_LIST_FIELDS = {
  "domain",
  "common_pattern",
  "safety_tags",
  "effects",
  "lane",
  "support_tier",
  "usage_model",
  "kind",
  "adapter",
}


def list_values(field: str) -> List[str]:
  """Return sorted distinct values for a given metadata field.

  For list-valued fields (effects, safety_tags) this flattens across tools.
  """
  if field not in SUPPORTED_LIST_FIELDS:
    raise ValueError(
      f"Unsupported field '{field}' for --list-values. "
      f"Supported fields: {', '.join(sorted(SUPPORTED_LIST_FIELDS))}"
    )

  tools = _load_tools()
  values = set()

  for t in tools:
    v = t.get(field)
    if v is None:
      continue
    if isinstance(v, list):
      for item in v:
        if item is not None:
          values.add(str(item))
    else:
      values.add(str(v))

  return sorted(values)

def filter_tools(
  *,
  kind: str | None = None,
  lane: str | None = None,
  support_tier: str | None = None,
  adapter: str | None = None,
  has_safety_tags: Iterable[str] | None = None,
  has_effects: Iterable[str] | None = None,
  domain: str | None = None,
  usage_model: str | None = None,
  common_pattern: str | None = None,
) -> List[Dict[str, Any]]:
  tools = _load_tools()

  def _match(t: Dict[str, Any]) -> bool:
    if kind and (t.get("kind") or "") != kind:
      return False
    if lane and (t.get("lane") or "") != lane:
      return False
    if support_tier and (t.get("support_tier") or "") != support_tier:
      return False
    if adapter and (t.get("adapter") or "") != adapter:
      return False

    if domain and (t.get("domain") or "") != domain:
      return False

    if usage_model and (t.get("usage_model") or "") != usage_model:
      return False

    if common_pattern and (t.get("common_pattern") or "") != common_pattern:
      return False

    stags = set(t.get("safety_tags") or [])
    if has_safety_tags:
      required = set(has_safety_tags)
      if not required.issubset(stags):
        return False

    eff = set(t.get("effects") or [])
    if has_effects:
      required_eff = set(has_effects)
      if not required_eff.issubset(eff):
        return False

    return True

  return [t for t in tools if _match(t)]


def main() -> None:
  ap = argparse.ArgumentParser(description="Capability filtering helper (metadata-only).")
  ap.add_argument("--kind", choices=["adapter_verb", "module_skill"], help="Filter by tool kind.")
  ap.add_argument("--lane", help="Filter by lane (e.g. canonical, noncanonical).")
  ap.add_argument("--support-tier", dest="support_tier", help="Filter by support tier (e.g. core, extension_openclaw).")
  ap.add_argument("--adapter", help="Filter adapter_verb tools by adapter id.")
  ap.add_argument("--domain", help="Filter by domain (e.g. http, memory, queue).")
  ap.add_argument("--usage-model", dest="usage_model", choices=["primitive", "composite"], help="Filter by usage model.")
  ap.add_argument("--common-pattern", dest="common_pattern", help="Filter by exact common_pattern value.")
  ap.add_argument(
    "--list-values",
    dest="list_field",
    help="List distinct values for a metadata field (e.g. domain, safety_tags).",
  )
  ap.add_argument(
    "--has-safety-tag",
    action="append",
    dest="safety_tags",
    help="Require a safety tag (can be passed multiple times).",
  )
  ap.add_argument(
    "--has-effect",
    action="append",
    dest="effects",
    help="Require an effect (can be passed multiple times).",
  )
  ap.add_argument(
    "--json",
    action="store_true",
    help="Emit full JSON tool entries instead of plain text ids.",
  )
  args = ap.parse_args()

  # List-values mode: emit distinct values for a single field and exit.
  if args.list_field:
    try:
      vals = list_values(args.list_field)
    except ValueError as e:
      # Print a clear error and exit non-zero.
      print(str(e))
      raise SystemExit(1)

    if args.json:
      print(json.dumps(vals, indent=2))
    else:
      for v in vals:
        print(v)
    return

  tools = filter_tools(
    kind=args.kind,
    lane=args.lane,
    support_tier=args.support_tier,
    adapter=args.adapter,
    has_safety_tags=args.safety_tags,
    has_effects=args.effects,
    domain=getattr(args, "domain", None),
    usage_model=getattr(args, "usage_model", None),
    common_pattern=getattr(args, "common_pattern", None),
  )

  if args.json:
    print(json.dumps(tools, indent=2))
  else:
    for t in tools:
      tool_id = t.get("id")
      name = t.get("name")
      print(f"{tool_id} ({name})")


if __name__ == "__main__":
  main()

