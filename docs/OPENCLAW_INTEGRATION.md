# OpenClaw integration

**Hub (all MCP hosts):** [`HOST_MCP_INTEGRATIONS.md`](HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host openclaw`** (same as **`ainl install-openclaw`**).

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw%20Skill-AINL-blue)](https://github.com/sbhooley/ainativelang/tree/main/skills/openclaw)

AINL ships an **OpenClaw skill** under [`skills/openclaw/`](../skills/openclaw/) (deterministic graphs, Markdown importer, **`ainl-mcp`**) and **`ainl install-mcp --host openclaw`** (alias **`ainl install-openclaw`**), a user-side bootstrap that wires PyPI, **`~/.openclaw/openclaw.json`** (`mcpServers.ainl`), and **`~/.openclaw/bin/ainl-run`** without changing the OpenClaw application itself.

**Standalone skill repo (optional, later):** copy **[`skills/openclaw/`](../skills/openclaw/)** to **[github.com/sbhooley/ainl-openclaw-skill](https://github.com/sbhooley/ainl-openclaw-skill)** as the repository root (`SKILL.md`, `install.sh`, `README.md`) if you want a single-purpose repo for ClawHub or docs links.

**Why this matters:** AINL is **compile-once, run-many**—you pay authoring or import cost once, then execute a validated graph repeatedly. Size economics use **tiktoken cl100k_base**; on the **viable subset** of representative workloads, **minimal_emit** lands near **~1.02×** leverage vs unstructured baselines (see **[`BENCHMARK.md`](../BENCHMARK.md)** and **[`benchmarks.md`](benchmarks.md)** for methodology and legacy-inclusive transparency).

OpenClaw normally uses **`npm install -g openclaw`** (or project-local install) and **`openclaw onboard`**. This skill adds the **Python** **`ainl-lang`** toolchain and merges **stdio `ainl-mcp`** into the host MCP table. OpenClaw does **not** use ZeroClaw’s **`zeroclaw skills install <url>`** — prefer **ClawHub** (when listed) or **manual copy** into **`~/.openclaw/skills`** or **`<workspace>/skills`** (default workspace is often **`~/.openclaw/workspace`**).

**Official OpenClaw source:** use **[openclaw.ai](https://openclaw.ai/)** for the installer and docs (e.g. `curl -fsSL https://openclaw.ai/install.sh | bash`). There is no stable public **`openclaw/openclaw`** GitHub repo advertised as the primary home.

**Cron / bridge alternative:** operator workflows that run AINL from OpenClaw cron (wrappers, token budget alerts, etc.) live under **`openclaw/bridge/`** in this repo — see **`openclaw/bridge/README.md`**. That path is separate from this MCP skill.

**CLI:** **`ainl install-mcp --host openclaw`** (same as **`install-openclaw`**) ships in current **`ainl-lang`** releases; upgrade from PyPI if your install reports an unknown command.

## Quickstart

1. **Install the skill** — copy [`skills/openclaw/`](../skills/openclaw/) into your OpenClaw skills directory, or install via **ClawHub** when available, then:

   ```bash
   cd /path/to/skill && chmod +x install.sh && ./install.sh
   ```

   `install.sh` optionally refreshes the OpenClaw CLI via npm, upgrades **`ainl-lang[mcp]`**, and runs **`ainl install-mcp --host openclaw`**. To skip the global npm step: **`OPENCLAW_SKIP_NPM=1 ./install.sh`**.

2. **Or run the bootstrap directly** (Python only):

   ```bash
   pip install 'ainl-lang[mcp]'
   ainl install-mcp --host openclaw
   ```

   Equivalent: **`ainl install-openclaw`**. Preview: **`--dry-run`** · noisy logs: **`--verbose`**.

## Chat example

After a successful install, try:

> Import the morning briefing using AINL.

Then use **`ainl import markdown …`**, ecosystem shortcuts (**`ainl import clawflows`** / **`ainl import agency-agents`**), or MCP tools so the agent produces compiling **`.ainl`** source, followed by **`ainl compile`** / **`ainl run`** or **`~/.openclaw/bin/ainl-run my.ainl`**.

## What gets installed

| Artifact | Purpose |
|----------|---------|
| `pip install --upgrade 'ainl-lang[mcp]'` | Latest compiler, importer extras, MCP dependencies |
| `~/.openclaw/openclaw.json` | Merges **`mcpServers.ainl`** stdio entry pointing at **`ainl-mcp`** (skipped if already present with the same resolved command); other top-level keys preserved |
| `~/.openclaw/bin/ainl-run` | Shell wrapper: compile then **`exec ainl run`** with extra args forwarded |
| `~/.bashrc` / `~/.zshrc` | Appends **`export PATH="$HOME/.openclaw/bin:$PATH"`** when those files exist and do not already mention **`~/.openclaw/bin`** |

If no shell rc file is updated, the command prints a one-line **`PATH`** tip you can paste manually.

## Benefits (summary)

| Benefit | Notes |
|---------|--------|
| Deterministic graphs | Compile-time validation; explicit cron, steps, and branches vs prose-only prompts |
| OpenClaw-native paths | **`openclaw.json`** + **`~/.openclaw/bin`** align with OpenClaw’s config layout |
| MCP parity | Same import semantics as CLI; exposure profiles in **`tooling/mcp_exposure_profiles.json`** |
| ~1.02× viable leverage | On tokenizer-aligned viable subset; see benchmarks for honest caveats |

## See also

- **All MCP hosts:** **[`HOST_MCP_INTEGRATIONS.md`](HOST_MCP_INTEGRATIONS.md)**
- Skill files: **[`skills/openclaw/README.md`](../skills/openclaw/README.md)**
- ZeroClaw parallel: **[`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**
- MCP operator guide: **[`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](operations/EXTERNAL_ORCHESTRATION_GUIDE.md)** (stdio **`ainl-mcp`**, OpenClaw **`openclaw.json`**)
- Integration narrative: **[`docs/INTEGRATION_STORY.md`](INTEGRATION_STORY.md)**
- Unified bridge / workspace notes: **[`docs/ainl_openclaw_unified_integration.md`](ainl_openclaw_unified_integration.md)**
- Cron / bridge code (non-MCP): **[`openclaw/bridge/README.md`](../openclaw/bridge/README.md)**
