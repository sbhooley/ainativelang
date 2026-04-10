# MCP host integrations (OpenClaw, ZeroClaw, Hermes Agent, …)

Single entry point for wiring **AINL** into agent stacks that consume **stdio `ainl-mcp`**: upgrade **`ainl[mcp]`** from PyPI, merge **`mcp.servers.ainl`** (or YAML **`mcp_servers.ainl`** on Hermes), install **`ainl-run`** under the host’s config tree, and suggest shell **`PATH`** updates.

**Current PyPI release:** `ainativelang` **v1.5.0**.

## Two-step pattern (every host)

1. **Install and onboard the agent runtime** using that product’s official docs (e.g. OpenClaw → [openclaw.ai](https://openclaw.ai/) · Hermes Agent → [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)).
2. **Add AINL** using either:
   - **Skill folder:** copy **`skills/<host>/`** from this repo, then **`chmod +x install.sh && ./install.sh`**, or  
   - **CLI:** **`pip install 'ainativelang[mcp]'`** then **`ainl install-mcp --host openclaw`**, **`zeroclaw`**, or **`hermes`** (see **`ainl install-mcp --list-hosts`**).

Legacy per-host commands remain aliases:

| Host | Unified CLI | Legacy alias |
|------|-------------|----------------|
| OpenClaw | `ainl install-mcp --host openclaw` | `ainl install-openclaw` |
| ZeroClaw | `ainl install-mcp --host zeroclaw` | `ainl install-zeroclaw` |
| Hermes Agent | `ainl install-mcp --host hermes` | `ainl hermes-install` |
| ArmaraOS | `ainl install-mcp --host armaraos` | `ainl install-armaraos` |

List supported ids: **`ainl install-mcp --list-hosts`**.

**Optional `ainl run` adapters (e.g. `code_context`):** MCP install wires **`ainl-mcp`** and **`ainl-run`**; it does **not** enable optional adapters. Workflows that call **`R code_context.*`** (tiered repo index, dependencies, impact, **`COMPRESS_CONTEXT`**) must pass **`--enable-adapter code_context`** to **`ainl run`** or the host **`ainl-run`** shim (args forward). Guide: **`docs/adapters/CODE_CONTEXT.md`**.

Older **`ainl`** wheels may only expose **`install-openclaw`** / **`install-zeroclaw`**; those are equivalent—upgrade PyPI when you want **`install-mcp`**.

## Adding a new host (maintainers)

1. Add a **`McpHostProfile`** entry in **[`tooling/mcp_host_install.py`](../../tooling/mcp_host_install.py)** (`PROFILES`): dot-directory, JSON config filename, **`PATH`** line, success tip.
2. If the host needs extra files (like ZeroClaw’s repo bridge), branch on **`host_id`** in **`run_install_mcp_host`** or call a small helper module (see **[`tooling/zeroclaw_bridge.py`](../../tooling/zeroclaw_bridge.py)**).
3. Add **`skills/<host>/`** mirroring **`skills/openclaw/`** ( **`SKILL.md`**, **`README.md`**, **`install.sh`** ) and a doc **`docs/<HOST>_INTEGRATION.md`**.
4. Register a thin **`install-<host>`** subcommand in **`cli/main.py`** if you want a stable alias without typing **`--host`**.

## Deep dives

- **OpenClaw:** [`OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) — **`~/.openclaw/openclaw.json`**, **`~/.openclaw/bin/ainl-run`**. Cron/bridge (non-MCP): [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md). **Unified bridge & workspace automation:** [`../ainl_openclaw_unified_integration.md`](../ainl_openclaw_unified_integration.md) (**token tracker adapter**, **`content-engine`** model override + budget guards, **`OPENCLAW_BIN`** / **`TOKEN_TRACKER_*`**).
- **ZeroClaw:** [`ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md) — **`~/.zeroclaw/mcp.json`**, optional **`[ainl_bridge]`** when run from a git checkout.
- **Hermes Agent:** [`HERMES_INTEGRATION.md`](../HERMES_INTEGRATION.md) — upstream **[github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)** · **`~/.hermes/config.yaml`** (`mcp_servers.ainl`), **`~/.hermes/bin/ainl-run`**, and **`--emit hermes-skill`** bundles under **`~/.hermes/skills/ainl-imports/`**.
- **ArmaraOS:** [`ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md) — MCP bootstrap + status + cron helper + emit-to-hand package.
- **Operators / MCP templates:** [`operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md).
