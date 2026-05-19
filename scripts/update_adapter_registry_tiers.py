"""One-time helper for T3.1: stamp `tier: "core" | "extended"` on every adapter
entry in `ADAPTER_REGISTRY.json` and inject a top-level `tier_meanings` block.

This script is idempotent — re-running with the same TIER_MAP leaves the file
unchanged (other than reformatting, which we suppress with a stable indent).

After T3.1 lands, this script is kept as the canonical place to express the
tier mapping; tier changes (promotions / new adapters) edit `TIER_MAP` here
and re-run the script rather than hand-editing the registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "ADAPTER_REGISTRY.json"

TIER_MEANINGS = {
    "core": (
        "Production-grade adapters on the gold path. Have dedicated docs, "
        "test coverage, strict-valid examples in CI, and are the recommended "
        "choice for production deployments. Backed by the maintainer team."
    ),
    "extended": (
        "Supported adapters in the broader catalog. Cover narrower domains "
        "(web3, social, browser, niche interop) or are newer additions still "
        "growing test coverage. Fully supported alongside Core; no deprecation."
    ),
}

# Authoritative tier assignment for every adapter present in the registry.
# Confirmed with project lead on 2026-05-19 (PR #...).
TIER_MAP: Dict[str, str] = {
    # --- Core: language primitives & engine-level adapters -------------------
    "core": "core",
    "http": "core",
    "fs": "core",
    "memory": "core",
    "cache": "core",
    "queue": "core",
    "sqlite": "core",
    "wasm": "core",
    "a2a": "core",
    "tools": "core",
    # --- Core: memory / audit / tool substrate ------------------------------
    "audit_trail": "core",
    "ainl_graph_memory": "core",
    "vector_memory": "core",
    "embedding_memory": "core",
    "tool_registry": "core",
    # --- Core: LLM + general orchestration ----------------------------------
    "llm": "core",
    "bridge": "core",
    "db": "core",
    "api": "core",
    # --- Core: external infra (databases) -----------------------------------
    "postgres": "core",
    "mysql": "core",
    "redis": "core",
    "dynamodb": "core",
    "supabase": "core",
    "airtable": "core",
    # --- Core: repo intelligence --------------------------------------------
    "code_context": "core",
    "ptc_runner": "core",
    # --- Core: system primitives --------------------------------------------
    "svc": "core",
    "txn": "core",
    # --- Extended: web3 / chain-specific ------------------------------------
    "solana": "extended",
    # --- Extended: social / domain ------------------------------------------
    "tiktok": "extended",
    "social": "extended",
    "calendar": "extended",
    "email": "extended",
    "github": "extended",
    "crm": "extended",
    # --- Extended: web / browser interaction --------------------------------
    "web": "extended",
    # --- Extended: interop bridges & helpers --------------------------------
    "langchain_tool": "extended",
    "llm_query": "extended",
    "ext": "extended",
    "fanout": "extended",
    "pggraph": "extended",
    # --- Extended: framework scaffolding ------------------------------------
    # Auth and agent are abstract bases / scaffolding; classified Extended
    # until a concrete production-grade implementation lands.
    "auth": "extended",
    "agent": "extended",
    "extras": "extended",
}


def main() -> None:
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)

    data.setdefault("tier_meanings", {})
    data["tier_meanings"] = TIER_MEANINGS

    adapters = data.get("adapters", {})
    missing_in_map = []
    promoted = 0
    extended = 0

    for name, entry in adapters.items():
        if not isinstance(entry, dict):
            continue
        tier = TIER_MAP.get(name)
        if tier is None:
            missing_in_map.append(name)
            tier = "extended"
        entry["tier"] = tier
        if tier == "core":
            promoted += 1
        else:
            extended += 1

    unknown_in_map = sorted(set(TIER_MAP) - set(adapters))

    out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    REGISTRY_PATH.write_text(out, encoding="utf-8")

    print(f"Updated {REGISTRY_PATH}")
    print(f"  core:     {promoted}")
    print(f"  extended: {extended}")
    if missing_in_map:
        print(f"  WARN: {len(missing_in_map)} adapter(s) in registry not in TIER_MAP "
              f"(defaulted to 'extended'): {missing_in_map}")
    if unknown_in_map:
        print(f"  WARN: {len(unknown_in_map)} adapter(s) in TIER_MAP not in registry: "
              f"{unknown_in_map}")


if __name__ == "__main__":
    main()
