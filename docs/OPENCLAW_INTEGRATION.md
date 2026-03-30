# OpenClaw integration

**Hub (all MCP hosts):** [`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host openclaw`** (same as **`ainl install-openclaw`**).

**PyPI:** `ainativelang` **v1.3.3**.

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw%20Skill-AINL-blue)](https://github.com/sbhooley/ainativelang/tree/main/skills/openclaw)

AINL ships an **OpenClaw skill** under [`skills/openclaw/`](../skills/openclaw/) (deterministic graphs, Markdown importer, **`ainl-mcp`**) and **`ainl install-mcp --host openclaw`** (alias **`ainl install-openclaw`**), a user-side bootstrap that wires PyPI, **`~/.openclaw/openclaw.json`** (`mcp.servers.ainl`), and **`~/.openclaw/bin/ainl-run`** without changing the OpenClaw application itself.

**Standalone skill repo (optional, later):** copy **[`skills/openclaw/`](../skills/openclaw/)** to **[github.com/sbhooley/ainl-openclaw-skill](https://github.com/sbhooley/ainl-openclaw-skill)** as the repository root (`SKILL.md`, `install.sh`, `README.md`) if you want a single-purpose repo for ClawHub or docs links.

**Why this matters:** AINL is **compile-once, run-many**—you pay authoring or import cost once, then execute a validated graph repeatedly. Size economics use **tiktoken cl100k_base**; on the **viable subset** of representative workloads, **minimal_emit** lands near **~1.02×** leverage vs unstructured baselines (see **[`BENCHMARK.md`](../BENCHMARK.md)** and **[`benchmarks.md`](benchmarks.md)** for methodology and legacy-inclusive transparency).

OpenClaw normally uses **`npm install -g openclaw`** (or project-local install) and **`openclaw onboard`**. This skill adds the **Python** **`ainl`** toolchain and merges **stdio `ainl-mcp`** into the host MCP table. OpenClaw does **not** use ZeroClaw’s **`zeroclaw skills install <url>`** — prefer **ClawHub** (when listed) or **manual copy** into **`~/.openclaw/skills`** or **`<workspace>/skills`** (default workspace is often **`~/.openclaw/workspace`**).

**Official OpenClaw source:** use **[openclaw.ai](https://openclaw.ai/)** for the installer and docs (e.g. `curl -fsSL https://openclaw.ai/install.sh | bash`). There is no stable public **`openclaw/openclaw`** GitHub repo advertised as the primary home.

**Cron / bridge alternative:** operator workflows that run AINL from OpenClaw cron (wrappers, token budget alerts, etc.) live under **`openclaw/bridge/`** in this repo — see **`openclaw/bridge/README.md`**. That path is separate from this MCP skill.

**Apollo X promoter (supervised HTTP gateway + `ExecutorBridgeAdapter`):** the graph in **`apollo-x-bot/ainl-x-promoter.ainl`** expects a **long-lived** [`apollo-x-bot/gateway_server.py`](../apollo-x-bot/gateway_server.py) and **`ainl run`** with **`--enable-adapter bridge`** (plus **`memory`**). You must schedule polls separately: **OpenClaw cron** or **OS cron** should call **`apollo-x-bot/openclaw-poll.sh`** (or an equivalent command line). The graph’s `S core cron` line is documentation only and does not register a job. That script sets a **long `--http-timeout-s`** so batched **`llm.classify`** over the bridge does not abort at the default **5s** client limit. Production layout, copy-paste **`openclaw cron add`**, and env files: **[`apollo-x-bot/OPENCLAW_DEPLOY.md`](../apollo-x-bot/OPENCLAW_DEPLOY.md)** · operator notes: **[`apollo-x-bot/README.md`](../apollo-x-bot/README.md)** (scheduling + troubleshooting).

**Memory surfaces:** durable **structured** workflow state uses the SQLite **`memory`** adapter (see [`docs/adapters/MEMORY_CONTRACT.md`](adapters/MEMORY_CONTRACT.md)). OpenClaw **bridge** cron may append **daily markdown** under **`~/.openclaw/workspace/memory/`**, which is **orthogonal** to that adapter. **ZeroClaw** uses the same AINL memory/MCP path—not OpenClaw’s markdown layout. Narrative: [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents).

**CLI:** **`ainl install-mcp --host openclaw`** (same as **`install-openclaw`**) ships in current **`ainl`** releases; upgrade from PyPI if your install reports an unknown command.

## Quickstart

1. **Install the skill** — copy [`skills/openclaw/`](../skills/openclaw/) into your OpenClaw skills directory, or install via **ClawHub** when available, then:

   ```bash
   cd /path/to/skill && chmod +x install.sh && ./install.sh
   ```

   `install.sh` optionally refreshes the OpenClaw CLI via npm, upgrades **`ainl[mcp]`**, and runs **`ainl install-mcp --host openclaw`**. To skip the global npm step: **`OPENCLAW_SKIP_NPM=1 ./install.sh`**.

2. **Or run the bootstrap directly** (Python only):

   ```bash
   pip install 'ainativelang[mcp]'
   ainl install-mcp --host openclaw
   ```

   Equivalent: **`ainl install-openclaw`**. Preview: **`--dry-run`** · noisy logs: **`--verbose`**.

## Chat example

After a successful install, try:

> Import the morning briefing using AINL.

Then use **`ainl import markdown …`**, ecosystem shortcuts (**`ainl import clawflows`** / **`ainl import agency-agents`**), or MCP tools so the agent produces compiling **`.ainl`** source, followed by **`ainl compile`** / **`ainl run`** or **`~/.openclaw/bin/ainl-run my.ainl`**.

**Optional adapter — `code_context`:** graphs that call **`R code_context.*`** (tiered repo index, dependencies, impact, **`COMPRESS_CONTEXT`**) must pass **`--enable-adapter code_context`** to **`ainl run`** or **`~/.openclaw/bin/ainl-run`** (extra args forward to **`ainl run`**). Installing MCP does **not** enable optional adapters. Guide: **`docs/adapters/CODE_CONTEXT.md`** · demo **`examples/code_context_demo.ainl`** · optional env **`AINL_CODE_CONTEXT_STORE`**.

## What gets installed

| Artifact | Purpose |
|----------|---------|
| `pip install --upgrade 'ainativelang[mcp]'` | Latest compiler, importer extras, MCP dependencies |
| `~/.openclaw/openclaw.json` | Merges **`mcp.servers.ainl`** stdio entry pointing at **`ainl-mcp`** (skipped if already present with the same resolved command); other top-level keys preserved |
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

- **OpenClaw + AINL gold standard (install / upgrade):** [`operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md) — profiles, caps, cron, bootstrap, verification (**`tooling/bot_bootstrap.json`** → **`openclaw_ainl_gold_standard`**)
- **AINL v1.3.3 — host briefing (what the repo includes vs what OpenClaw must do; current PyPI):** [`operations/OPENCLAW_HOST_AINL_1_2_8.md`](operations/OPENCLAW_HOST_AINL_1_2_8.md) — **`openclaw_host_ainl_1_2_8`**
- **All MCP hosts:** **[`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)**
- Skill files: **[`skills/openclaw/README.md`](../skills/openclaw/README.md)**
- ZeroClaw parallel: **[`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**
- MCP operator guide: **[`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](operations/EXTERNAL_ORCHESTRATION_GUIDE.md)** (stdio **`ainl-mcp`**, OpenClaw **`openclaw.json`**)
- Integration narrative: **[`docs/INTEGRATION_STORY.md`](INTEGRATION_STORY.md)**
- Unified bridge / workspace notes: **[`docs/ainl_openclaw_unified_integration.md`](ainl_openclaw_unified_integration.md)**
- Cron / bridge code (non-MCP): **[`openclaw/bridge/README.md`](../openclaw/bridge/README.md)**

## LLM Adapter Setup

To enable cloud LLM providers, create an AINL config file following the guide in `docs/LLM_ADAPTER_USAGE.md`. Set your provider API keys via environment variables (e.g., `OPENROUTER_API_KEY`). Then pass the config path using `--config` or set `AINL_CONFIG`.

You can verify cost tracking and retry behavior by running a program and checking the SQLite DB under `intelligence/monitor/`.

