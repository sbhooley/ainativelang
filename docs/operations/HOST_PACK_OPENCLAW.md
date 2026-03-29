# Host pack: OpenClaw (reference bundle)

This is a **documentation bundle** for a supported OpenClaw stack: **not** a separate installer, but a single checklist so support and operators align.

## Gold standard (install / upgrade)

**Start here:** [`OPENCLAW_AINL_GOLD_STANDARD.md`](OPENCLAW_AINL_GOLD_STANDARD.md) — profiles (`openclaw-default` → `cost-tight`), caps, cron, host bootstrap, verification, and **`budget_hydrate`** checks. **`tooling/bot_bootstrap.json`** → **`openclaw_ainl_gold_standard`**.

**AINL v1.3.3 — host responsibilities (what ships vs what you must wire):** [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md) — **`openclaw_host_ainl_1_2_8`** (bridge probe, rolling hydrate, profiles, explicit OpenClaw obligations).

## Contents

1. **Bootstrap** — [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) (`ainl install-mcp --host openclaw`, `~/.openclaw/openclaw.json`, `ainl-run`).
2. **Profile** — `ainl profile show openclaw-default` + [`AINL_PROFILES.md`](AINL_PROFILES.md).
3. **Agent + AINL model** — [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) (host must load curated bootstrap; default operational loop).
4. **Monitoring** — [`UNIFIED_MONITORING_GUIDE.md`](UNIFIED_MONITORING_GUIDE.md) (bridge `run_wrapper_ainl.py`, daily memory, token budget).
5. **Observability** — [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md).
6. **OpenClaw requests 2–6 mapping (what’s shipped vs proposed):** [`OPENCLAW_REQUESTS_2_6_MAPPING.md`](OPENCLAW_REQUESTS_2_6_MAPPING.md) (summarizer, WASM, embeddings, caps, “sparse attention” honest note).

## Versioning

When behavior or env vars change in a breaking way, bump the **profile catalog** `version` field in `tooling/ainl_profiles.json` and note the release in [`CHANGELOG.md`](../CHANGELOG.md).

## Other hosts

- **ZeroClaw:** [`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md) — different paths; do not reuse OpenClaw daily-memory assumptions.
- **Generic MCP:** [`../getting_started/HOST_MCP_INTEGRATIONS.md`](../getting_started/HOST_MCP_INTEGRATIONS.md).
