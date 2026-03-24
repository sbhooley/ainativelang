# Reference

> **OpenClaw (MCP skill):** Start at **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** for **`skills/openclaw/`**, **`ainl install-openclaw`**, and **`~/.openclaw/openclaw.json`** — before bridge-only **`openclaw/bridge/`** docs below.
>
> **ZeroClaw:** Start at **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)** for the skill, **`ainl install-zeroclaw`**, and **`ainl-mcp`** — before deep-diving adapter tiers and OpenClaw extension metadata below.

Use this section for schemas, indexes, contracts, maintenance docs, and other reference-style material.

All schema-level docs should live together here to avoid splitting closely related contracts across conceptual folders.

## Key docs

- [`../DOCS_INDEX.md`](../DOCS_INDEX.md) — exhaustive docs reference map
- [`../DOCS_MAINTENANCE.md`](../DOCS_MAINTENANCE.md) — docs maintenance contract
- [`IR_SCHEMA.md`](IR_SCHEMA.md) — canonical IR schema
- [`GRAPH_SCHEMA.md`](GRAPH_SCHEMA.md) — graph schema
- [`TOOL_API.md`](TOOL_API.md) — structured tool API contract
- [`ADAPTER_REGISTRY.md`](ADAPTER_REGISTRY.md) — adapter inventory (includes **`vector_memory`**, **`tool_registry`**, **`memory`**)
- [`../trajectory.md`](../trajectory.md) — CLI trajectory JSONL (`ainl run --log-trajectory`)
- [`CAPABILITY_REGISTRY.md`](CAPABILITY_REGISTRY.md) — capability metadata and Tool API v2 projection
- [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) — OpenClaw skill + **`ainl install-openclaw`** (pair with **`openclaw/bridge/`** + monitoring guide)
- [`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md) — ZeroClaw skill + MCP bootstrap (pair with OpenClaw bridge docs)
- [`GLOSSARY.md`](GLOSSARY.md) — shared terminology
- [`AINL_V0_9_PROFILE.md`](AINL_V0_9_PROFILE.md) — v0.9 small-model profile (beginner subset of the spec)
- **HTTP executor-bridge request (JSON):** [`../../schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json) — JSON Schema for the §3 envelope in [`../integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](../integrations/EXTERNAL_EXECUTOR_BRIDGE.md); Python mirror [`../../schemas/executor_bridge_validate.py`](../../schemas/executor_bridge_validate.py)

## Related sections

- Primary docs navigation: [`../README.md`](../README.md)
- Architecture overview: [`../architecture/README.md`](../architecture/README.md)
- Runtime/compiler contract: [`../RUNTIME_COMPILER_CONTRACT.md`](../RUNTIME_COMPILER_CONTRACT.md)
