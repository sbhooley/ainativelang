#!/usr/bin/env python3
"""
Generate Tool API v2 tools descriptor from the unified capability registry.

This is metadata-only:
- reads `tooling/capabilities.json`
- writes `tooling/tool_api_v2.tools.json`
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
  caps_path = ROOT / "tooling" / "capabilities.json"
  out_path = ROOT / "tooling" / "tool_api_v2.tools.json"

  caps = json.loads(caps_path.read_text(encoding="utf-8"))
  adapters = caps.get("adapters", {})

  tools = []

  # Adapter verbs -> adapter_verb tools
  for av in caps.get("adapter_verbs", []):
    tools.append(
      {
        "id": av["id"],
        "kind": "adapter_verb",
        "name": av["name"],
        "description": av["description"],
        "adapter": av["adapter"],
        "verb": av["verb"],
        "inputs": av.get("inputs", []),
        "outputs": av.get("outputs", []),
        "effects": av.get("effects", []),
        "domain": av.get("domain") or adapters.get(av["adapter"], {}).get("domain"),
        "lane": av.get("lane"),
        "support_tier": av.get("support_tier"),
        "usage_model": av.get("usage_model"),
        "common_pattern": av.get("common_pattern"),
        "adapter_dependencies": av.get("adapter_dependencies", []),
        "safety_tags": av.get("safety_tags", []),
      }
    )

  # Module skills -> module_skill tools
  for ms in caps.get("module_skills", []):
    tools.append(
      {
        "id": ms["id"],
        "kind": "module_skill",
        "name": ms["name"],
        "description": ms["description"],
        "source": ms["source"],
        "inputs": ms.get("inputs", []),
        "outputs": ms.get("outputs", []),
        "effects": ms.get("effects", []),
        "domain": ms.get("domain"),
        "lane": ms.get("lane"),
        "support_tier": ms.get("support_tier"),
        "usage_model": ms.get("usage_model"),
        "adapter_dependencies": ms.get("adapter_dependencies", []),
        "safety_tags": ms.get("safety_tags", []),
      }
    )

  out = {"schema_version": "2.0", "tools": tools}
  out_path.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
  main()

