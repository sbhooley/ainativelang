---
title: MCP host integrations — OpenClaw, ZeroClaw, Hermes
description: Single guide for installing AINL as an MCP-native skill in OpenClaw, ZeroClaw, and Hermes. Per-host install paths, bridges, monitoring, and the Hermes learning loop.
order: 5
---

# MCP host integrations — OpenClaw, ZeroClaw, Hermes

**Hub (all hosts):** [`../getting_started/HOST_MCP_INTEGRATIONS.md`](../getting_started/HOST_MCP_INTEGRATIONS.md) — `ainl install-mcp --host {openclaw|zeroclaw|hermes}`.

**Package:** `ainativelang` **v1.8.0** (this tree; PyPI after publish — [`../RELEASING.md`](../RELEASING.md)).

This doc consolidates the previously per-host install guides ([`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md), [`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md), [`../HERMES_INTEGRATION.md`](../HERMES_INTEGRATION.md) — now stub redirects to here). Shared install + semantics live in one place; per-host specialty (Apollo X for OpenClaw; bridge monitoring wrappers for ZeroClaw; closed learning loop for Hermes) live under their own host sections below.

## Why this matters

AINL is **compile-once, run-many** — pay authoring or import cost once, then execute a validated graph repeatedly. Size economics use **tiktoken cl100k_base**; on the **viable subset** of representative workloads, **minimal_emit** lands near **~1.02×** leverage vs unstructured baselines. See [`../../BENCHMARK.md`](../../BENCHMARK.md) and [`../benchmarks.md`](../benchmarks.md) for methodology and legacy-inclusive transparency.

| Benefit | Notes |
|---------|-------|
| Deterministic graphs | Compile-time validation; explicit cron, steps, branches vs prose-only prompts |
| Host-native paths | `~/.openclaw/`, `~/.zeroclaw/`, `~/.hermes/` MCP entries match each host's config layout |
| MCP parity | Same import semantics across CLI + every host; exposure profiles in [`../../tooling/mcp_exposure_profiles.json`](../../tooling/mcp_exposure_profiles.json) |
| ~1.02× viable leverage | Tokenizer-aligned viable subset; see benchmarks for honest caveats |

## Quick install — one line per host

```bash
pip install 'ainativelang[mcp]'

# pick one:
ainl install-mcp --host openclaw     # alias: ainl install-openclaw
ainl install-mcp --host zeroclaw     # alias: ainl install-zeroclaw
ainl install-mcp --host hermes       # alias: ainl hermes-install
```

| Host | Bootstrap | Skill source | Config touched | Shim |
|------|-----------|--------------|----------------|------|
| OpenClaw | `ainl install-mcp --host openclaw` | [`skills/openclaw/`](../../skills/openclaw/) | `~/.openclaw/openclaw.json` (`mcp.servers.ainl`) | `~/.openclaw/bin/ainl-run` |
| ZeroClaw | `ainl install-mcp --host zeroclaw` | [`skills/ainl/`](../../skills/ainl/) | `~/.zeroclaw/mcp.json` (`ainl` stdio entry) | `~/.zeroclaw/bin/ainl-run` |
| Hermes | `ainl install-mcp --host hermes` | [`skills/hermes/`](../../skills/hermes/) | `~/.hermes/config.yaml` (`mcp_servers.ainl`) | `~/.hermes/bin/ainl-run` |

All three bootstraps also append `export PATH="$HOME/.<host>/bin:$PATH"` to `~/.bashrc` / `~/.zshrc` when those files exist and don't already mention the dir; otherwise they print a one-line PATH tip you can paste manually. Preview with `--dry-run`; verbose with `--verbose`.

After install, try this prompt in any host's chat:

> Import the morning briefing using AINL.

The agent should call `ainl import markdown …`, ecosystem shortcuts (`ainl import clawflows` / `ainl import agency-agents`), or MCP tools (`ainl_list_ecosystem`, `ainl_import_clawflow`, `ainl_import_agency_agent`, `ainl_import_markdown`) and produce compiling `.ainl` source.

---

## OpenClaw

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw%20Skill-AINL-blue)](https://github.com/sbhooley/ainativelang/tree/main/skills/openclaw)

**Bootstrap:** `ainl install-mcp --host openclaw` (alias `ainl install-openclaw`). User-side; does **not** modify the OpenClaw application itself.

OpenClaw normally uses `npm install -g openclaw` (or project-local) and `openclaw onboard`. This skill adds the Python `ainl` toolchain and merges stdio `ainl-mcp` into the host MCP table. OpenClaw does **not** use ZeroClaw's `zeroclaw skills install <url>` — prefer **ClawHub** (when listed) or **manual copy** into `~/.openclaw/skills` or `<workspace>/skills` (default workspace is often `~/.openclaw/workspace`).

**Official OpenClaw source:** [openclaw.ai](https://openclaw.ai/) for the installer and docs (e.g. `curl -fsSL https://openclaw.ai/install.sh | bash`). There is no stable public `openclaw/openclaw` GitHub repo advertised as the primary home.

**Standalone skill repo (optional):** copy [`skills/openclaw/`](../../skills/openclaw/) to [github.com/sbhooley/ainl-openclaw-skill](https://github.com/sbhooley/ainl-openclaw-skill) as the repo root if you want a single-purpose repo for ClawHub or doc links.

### Install

Either run the bootstrap directly:

```bash
pip install 'ainativelang[mcp]'
ainl install-mcp --host openclaw
```

…or copy [`skills/openclaw/`](../../skills/openclaw/) into your OpenClaw skills directory (or install via ClawHub when available) and:

```bash
cd /path/to/skill && chmod +x install.sh && ./install.sh
```

`install.sh` optionally refreshes the OpenClaw CLI via npm, upgrades `ainativelang[mcp]`, and runs `ainl install-mcp --host openclaw`. Skip the global npm step with `OPENCLAW_SKIP_NPM=1 ./install.sh`.

### Apollo X promoter — supervised HTTP gateway + `ExecutorBridgeAdapter`

The graph in [`apollo-x-bot/ainl-x-promoter.ainl`](../../apollo-x-bot/ainl-x-promoter.ainl) expects a **long-lived** [`apollo-x-bot/gateway_server.py`](../../apollo-x-bot/gateway_server.py) and `ainl run` with `--enable-adapter bridge` (plus `memory`). Polls must be scheduled separately: **OpenClaw cron** or **OS cron** should call [`apollo-x-bot/openclaw-poll.sh`](../../apollo-x-bot/openclaw-poll.sh) (or an equivalent command line). The graph's `S core cron` line is documentation only and does not register a job. That script sets a long `--http-timeout-s` so batched `llm.classify` over the bridge does not abort at the default 5s client limit.

Production layout, copy-paste `openclaw cron add`, and env files: [`../../apollo-x-bot/OPENCLAW_DEPLOY.md`](../../apollo-x-bot/OPENCLAW_DEPLOY.md). Operator notes (scheduling + troubleshooting): [`../../apollo-x-bot/README.md`](../../apollo-x-bot/README.md).

### Memory surfaces

Durable structured workflow state uses the SQLite `memory` adapter (see [`../adapters/MEMORY_CONTRACT.md`](../adapters/MEMORY_CONTRACT.md)). OpenClaw **bridge** cron may append daily markdown under `~/.openclaw/workspace/memory/`, which is **orthogonal** to that adapter. ZeroClaw uses the same AINL memory/MCP path — not OpenClaw's markdown layout. Narrative: [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents).

### Cron / bridge alternative (non-MCP)

Operator workflows that run AINL from OpenClaw cron (wrappers, token budget alerts, etc.) live under [`openclaw/bridge/`](../../openclaw/bridge/) — see [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md). That path is separate from this MCP skill.

---

## ZeroClaw

[![ZeroClaw Skill](https://img.shields.io/badge/ZeroClaw%20Skill-AINL-blue)](https://github.com/sbhooley/ainativelang/tree/main/skills/ainl)

**Bootstrap:** `ainl install-mcp --host zeroclaw` (alias `ainl install-zeroclaw`).

### Install

ZeroClaw supports a one-line skill install:

```bash
zeroclaw skills install https://github.com/sbhooley/ainativelang/tree/main/skills/ainl
```

Or run the bootstrap directly:

```bash
pip install 'ainativelang[mcp]'
ainl install-mcp --host zeroclaw
```

Or from a local clone of this monorepo:

```bash
cd skills/ainl && ./install.sh
```

When `ainl install-mcp --host zeroclaw` runs **from a repo checkout** that contains `zeroclaw/bridge/`, it also writes:

| Artifact | Purpose |
|----------|---------|
| `~/.zeroclaw/config.toml` `[ainl_bridge]` `repo_root` | Records the AINL git root for operators and shims |
| `~/.zeroclaw/bin/zeroclaw-ainl-run` | Runs `zeroclaw/bridge/run_wrapper_ainl.py` (wrapper registry with ZeroClaw memory paths) |

### Native bridge vs OpenClaw bridge

| Piece | OpenClaw (`openclaw/bridge/`) | ZeroClaw (`zeroclaw/bridge/`) |
|-------|-------------------------------|-------------------------------|
| Dispatcher CLI | `ainl_bridge_main.py` | `zeroclaw_bridge_main.py` |
| Wrapper runner | `run_wrapper_ainl.py` | `run_wrapper_ainl.py` (registers `ZeroclawMemoryAdapter` as `openclaw_memory` + `zeroclaw_memory`, `ZeroclawQueueAdapter`, `ZeroclawBridgeTokenBudgetAdapter`) |
| Daily markdown | `~/.openclaw/workspace/memory/` | `~/.zeroclaw/workspace/memory/` (overridable via `ZEROCLAW_*`) |
| Cron drift | `openclaw cron list --json` | `zeroclaw cron list --json` |
| Notify | `openclaw message send` | `zeroclaw message send` |
| Token-usage subprocess target | `openclaw/bridge/ainl_bridge_main.py` | `zeroclaw/bridge/zeroclaw_bridge_main.py` |

Detail: [`../../zeroclaw/bridge/README.md`](../../zeroclaw/bridge/README.md).

### Configuration namespaces (AINL vs ZeroClaw)

Bridge wrappers and token tooling reuse `AINL_*` names (`AINL_DRY_RUN`, `AINL_BRIDGE_FAKE_CACHE_MB`, `AINL_TOKEN_PRUNE_DAYS`, `AINL_ADVOCATE_DAILY_TOKEN_BUDGET`, etc.) so behavior matches the OpenClaw bridge and one document set covers both hosts.

ZeroClaw-specific wiring uses `ZEROCLAW_*`: workspace (`ZEROCLAW_WORKSPACE`), memory paths (`ZEROCLAW_MEMORY_DIR`), CLI path (`ZEROCLAW_BIN`), and notify routing (`ZEROCLAW_NOTIFY_CHANNEL`, `ZEROCLAW_TARGET`). `ZEROCLAW_NOTIFY_TARGET` controls `zeroclaw message send` for graphs that use `R queue Put "notify" …` (`token-budget-alert`, `weekly-token-trends`, `monthly-token-summary`). If unset, the queue adapter falls back to `ZEROCLAW_TARGET` / `OPENCLAW_TARGET` and `ZEROCLAW_NOTIFY_CHANNEL` / `OPENCLAW_NOTIFY_CHANNEL`.

We are **not** introducing a separate `ZEROCLAW_AINL_*` prefix: shared bridge semantics stay `AINL_*`; host placement stays `ZEROCLAW_*`.

### Bridge monitoring wrappers

Three wrappers ship in the ZeroClaw bridge for daily/weekly/monthly token usage reports. None of them schedule themselves — the `.ainl` source declares a suggested cron line for documentation only. Your host or ZeroClaw job runner must invoke `zeroclaw-ainl-run <wrapper>` (or `python3 zeroclaw/bridge/run_wrapper_ainl.py <wrapper>`) on the desired schedule.

All wrappers are **timezone-agnostic** (UTC-based date tags + `YYYY-MM-DD.md` filenames); pick a local cron hour for log readability.

#### Daily token budget alert

Wrapper: [`zeroclaw/bridge/wrappers/token_budget_alert.ainl`](../../zeroclaw/bridge/wrappers/token_budget_alert.ainl). Run via `zeroclaw-ainl-run token-budget-alert`. Daily cache/token digest. Env vars and smoke patterns: [`../../zeroclaw/bridge/README.md`](../../zeroclaw/bridge/README.md).

#### Weekly token trends

Wrapper: [`zeroclaw/bridge/wrappers/weekly_token_trends.ainl`](../../zeroclaw/bridge/wrappers/weekly_token_trends.ainl). Suggested cron: `0 9 * * 0` (Sunday 09:00 UTC). Low-impact compared to the daily digest.

| Aspect | Behavior |
|--------|----------|
| **Inputs** | Newest 14 files matching `YYYY-MM-DD.md` under `ZEROCLAW_WORKSPACE/memory/` (or `ZEROCLAW_MEMORY_DIR`), same layout as daily bridge notes. Each file may contain a `## Token Usage Report` section (heuristic parse: `estimated_total_tokens`, `budget_used_pct`, etc.). |
| **Processing** | `ZeroclawBridgeTokenBudgetAdapter` (`R bridge weekly_token_trends_report`) aggregates the last 7 days (or fewer if not enough files), compares halves for a short trend arrow, and optionally compares to the prior 7 days when 14 files exist. |
| **Outputs** | Markdown starting with `## Weekly Token Trends`. With `--dry-run`: report returned in JSON `out` only; `R openclaw_memory append_today` and `R queue Put "notify" …` are skipped. Live: append via `R openclaw_memory append_today`, then short `R queue Put "notify" …` (routing: `ZEROCLAW_NOTIFY_TARGET` / `ZeroclawQueueAdapter`). |
| **Sentinel / de-dupe** | Unlike `token-budget-alert`, this graph has **no** token-report date sentinel. Avoid double appends by not running twice per calendar day, or by scheduling only from cron. |

#### Monthly token summary

Wrapper: [`zeroclaw/bridge/wrappers/monthly_token_summary.ainl`](../../zeroclaw/bridge/wrappers/monthly_token_summary.ainl). Suggested cron: `0 3 1 * *` (1st of month, 03:00 UTC).

| Aspect | Behavior |
|--------|----------|
| **Inputs** | Daily `YYYY-MM-DD.md` under `ZEROCLAW_WORKSPACE/memory/` (or `ZEROCLAW_MEMORY_DIR`) whose stem date falls in the rolling last 30 calendar days (UTC). Same `## Token Usage Report` heuristics as weekly. |
| **Processing** | `ZeroclawBridgeTokenBudgetAdapter` (`R bridge monthly_token_summary_report`) sums token estimates in that window — Avg daily, Trend (split-window), and vs prior 30 days when the prior period has data. |
| **Outputs** | Markdown starting with `## Monthly Token Summary`. Includes optional `vs prior 30 days` line when enough older daily notes exist. `--dry-run`: JSON `out` only; no `append_today`, no queue notify. Live: append via `R openclaw_memory append_today`, then short `R queue Put "notify" …`. |
| **Sentinel / de-dupe** | **No** monthly sentinel — rely on running once per month from cron or manual discipline. |

All three append reports to today's daily note on live runs and trigger a short notification via the queue. Use `--dry-run` for testing without side effects. Live runs can also emit JSON output with `--json`, `--output=json`, and `--pretty` (see [`../../zeroclaw/bridge/run_wrapper_ainl.py`](../../zeroclaw/bridge/run_wrapper_ainl.py)).

<a id="cadence-overview"></a>

#### Monitoring cadence overview

| Wrapper | Cadence | Purpose | Suggested cron (UTC) | Output | Notification | JSON output |
|---------|---------|---------|----------------------|--------|--------------|-------------|
| `token-budget-alert` | Daily | Budget check + prune + alert | `0 23 * * *` | Today's daily note | Yes (`ZEROCLAW_NOTIFY_TARGET`) | Yes (`--json`, `--output=json`, `--pretty`) |
| `weekly-token-trends` | Weekly | 7-day trends & stats | `0 9 * * 0` | Today's daily note | Yes (`ZEROCLAW_NOTIFY_TARGET`) | Yes (`--json`, `--output=json`, `--pretty`) |
| `monthly-token-summary` | Monthly | 30-day overview + prior comparison | `0 3 1 * *` | Today's daily note | Yes (`ZEROCLAW_NOTIFY_TARGET`) | Yes (`--json`, `--output=json`, `--pretty`) |

*Extending the table:* When you add a production monitoring wrapper, register its CLI name in [`../../zeroclaw/bridge/run_wrapper_ainl.py`](../../zeroclaw/bridge/run_wrapper_ainl.py), keep cadence/cron hints in the `.ainl` header, document behavior under a new subsection above, and append a row here. If a new wrapper omits notifications or JSON output, update the corresponding cell (e.g. **No** or **Dry-run only**).

#### Configurable notifications

All three wrappers send a short notification via the queue on live runs (routed by `ZEROCLAW_NOTIFY_TARGET`). The full report is always appended to today's daily note.

Each live run ends with `R queue Put "notify" …` (payload: full daily digest text vs short weekly/monthly summary lines). `ZeroclawQueueAdapter` maps every such put to `zeroclaw message send` using `ZEROCLAW_NOTIFY_TARGET` and related env vars. `--dry-run` skips `append_today` and the queue put for all three.

Set `ZEROCLAW_NOTIFY_TARGET` in the shell or cron (case-insensitive where noted):

| Value | Behavior |
|-------|----------|
| *(unset or empty)* | `--target`: `ZEROCLAW_TARGET` then `OPENCLAW_TARGET`; `--channel`: `ZEROCLAW_NOTIFY_CHANNEL` / `OPENCLAW_NOTIFY_CHANNEL` (default `telegram`) |
| `none` | Skip `zeroclaw message send` entirely (live runs only; `--dry-run` still skips as before) |
| `slack:`*rest* | `--channel slack`, `--target` = *rest* (after first `:`) |
| `email:`*rest* | `--channel email`, `--target` = *rest* |
| `telegram:`*rest* | `--channel telegram`, `--target` = *rest* (numeric chat id, `@username`, etc.) |
| Plain string (no recognized prefix) | `--target` = full string, `--channel` from env (legacy override) |

Examples:

```bash
ZEROCLAW_NOTIFY_TARGET=slack:zero-claw-alerts zeroclaw-ainl-run token-budget-alert
ZEROCLAW_NOTIFY_TARGET=telegram:-1001234567890 zeroclaw-ainl-run weekly-token-trends
ZEROCLAW_NOTIFY_TARGET=none zeroclaw-ainl-run monthly-token-summary
```

The message body is the same payload that would have been sent to the default queue path. Actual delivery depends on your `zeroclaw` CLI supporting each `--channel`.

### Why CLI calls?

ZeroClaw's Rust traits and on-disk layout are **extensible** and may shift between releases. For the native bridge we call `zeroclaw` CLI subcommands (`cron list`, `message send`, `memory search` where available) instead of parsing or writing TOML/DB internals from Python: **CLI is the simplest stable surface and stays version-agnostic for now**. Where no CLI exists (e.g. appending daily markdown), we write the same `YYYY-MM-DD.md` files under `~/.zeroclaw/workspace/memory/` as a deliberate, documented contract.

---

## Hermes

**Bootstrap:** `ainl install-mcp --host hermes` (alias `ainl hermes-install`). Upstream host: [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research).

Hermes brings the learning loop; AINL brings deterministic graph semantics. The result is a **self-improving agent** with a **strictly replayable** execution core. Marketing-facing intro: [`hermes-agent.md`](./hermes-agent.md).

Hermes ships three AINL surfaces:

- **MCP bootstrap:** `ainl install-mcp --host hermes` (merges `ainl-mcp` into `~/.hermes/config.yaml`, installs `~/.hermes/bin/ainl-run`)
- **Skill pack:** [`skills/hermes/`](../../skills/hermes/) (bridge helpers + install script)
- **Emitter:** `ainl compile --emit hermes-skill` (drop-in Hermes skill bundle directory)

Hermes discovers AINL skills automatically through its skills system (e.g. bundles under `~/.hermes/skills/`) and invokes the registered MCP tool `ainl_run` for deterministic execution.

### Architecture (compile → run → learn → validate)

1. **Author/import** a workflow as `.ainl`
2. **Compile** to canonical IR (strict mode): `ainl check --strict` / `ainl compile --strict`
3. **Emit** a Hermes skill bundle: `--emit hermes-skill`
4. **Hermes runs the skill** by calling the MCP tool `ainl_run` with the bundled AINL source
5. **AINL produces audit tapes** (trajectory JSONL) when enabled
6. **Bridge ingests tapes** into Hermes memory (Honcho) so the loop can learn from executions
7. **Hermes evolves** candidate improvements (new prompts, new steps, refined control flow)
8. **Export back to `.ainl`** and re-run `ainl check --strict` before promotion

Key contract:

- **Determinism** lives at the AINL runtime boundary: Hermes calls `ainl_run` rather than re-orchestrating the workflow in prose.
- **Learning** lives above the boundary: Hermes can propose edits, but AINL strict mode is the gate.

### Install Hermes Agent (host)

Follow Hermes' official install docs at [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). Ensure `hermes` is on your `PATH` and that `~/.hermes/` exists after onboarding.

### Install AINL MCP support for Hermes

```bash
pip install 'ainativelang[mcp]'
ainl install-mcp --host hermes        # equivalent: ainl hermes-install
```

What this wires:

- `~/.hermes/config.yaml` → adds a `mcp_servers.ainl` stdio entry pointing to `ainl-mcp`
- `~/.hermes/bin/ainl-run` → shim that compiles then runs a `.ainl` file
- A PATH hint to include `~/.hermes/bin`

### Scaffold a Hermes-targeted worker + emit a skill bundle

```bash
ainl init my-worker --target hermes
cd my-worker
ainl compile main.ainl --strict --emit hermes-skill -o ~/.hermes/skills/ainl-imports/my-worker/
```

The Hermes emitter writes a drop-in skill bundle directory with:

- `SKILL.md` (agentskills-style markdown + `ainl_run` payload)
- `workflow.ainl` (exact source)
- `ir.json` (canonical IR)

Then start Hermes (`hermes chat`) and ask:

> Import the morning briefing using AINL.

…or browse installed skills (depending on your Hermes build) and run the emitted bundle.

### Closed learning loop (audit tapes ↔ Honcho memory ↔ strict validation)

**A) AINL audit tapes → Hermes memory (Honcho).** AINL writes a trajectory JSONL "tape" for each run. With `ainl-run`, enable it via:

```bash
export AINL_LOG_TRAJECTORY=1
```

Then ingest via the bridge helpers in the Hermes skill pack:

- [`skills/hermes/ainl_hermes_bridge.py`](../../skills/hermes/ainl_hermes_bridge.py) (installed into `~/.hermes/skills/ainl/` by `skills/hermes/install.sh`)

**B) Hermes-evolved trajectories → `.ainl` export.** Treat Hermes' proposed changes as **candidates**:

1. Export/edit into `.ainl`
2. Gate with strict mode: `ainl check candidate.ainl --strict`
3. If strict validation passes, re-emit the Hermes bundle and replace the skill directory under `~/.hermes/skills/ainl-imports/`.

### Migration path (OpenClaw → Hermes)

Hermes can migrate some OpenClaw-style workflows using its migration tooling (e.g. `hermes claw migrate`). After migration:

1. Convert the result into compiling `.ainl` (either by hand or with AINL import tools)
2. Validate with `ainl check --strict`
3. Emit a Hermes skill bundle using `--emit hermes-skill`

This layering keeps Hermes' ergonomics while moving orchestration into AINL's deterministic, auditable graph core.

### Troubleshooting

```bash
ainl doctor
```

…should show checks for Hermes MCP config under `~/.hermes/config.yaml` (`mcp_servers.ainl`). If missing, rerun `ainl install-mcp --host hermes`.

Common issues:

- `hermes` not on PATH: install Hermes and add its bin dir to PATH.
- AINL tools not on PATH: ensure your Python user base `bin/` is in PATH (`ainl doctor` prints hints).
- MCP server missing: verify `~/.hermes/config.yaml` contains `mcp_servers:` and `ainl:`.

---

## Shared semantics (every host)

### Memory adapter

Durable structured workflow state uses the SQLite `memory` adapter regardless of host — see [`../adapters/MEMORY_CONTRACT.md`](../adapters/MEMORY_CONTRACT.md). OpenClaw's daily-markdown layout under `~/.openclaw/workspace/memory/` is **bridge-specific**, not part of the cross-host MCP contract; ZeroClaw and Hermes both use the same AINL memory/MCP path.

### Optional adapter — `code_context`

Graphs that call `R code_context.*` (tiered repo index, dependencies, impact, `COMPRESS_CONTEXT`) must pass `--enable-adapter code_context` to `ainl run` or any host's `~/.<host>/bin/ainl-run` shim (extra args forward to `ainl run`). Installing MCP does **not** enable optional adapters. Guide: [`../adapters/CODE_CONTEXT.md`](../adapters/CODE_CONTEXT.md). Demo: [`../../examples/code_context_demo.ainl`](../../examples/code_context_demo.ainl). Optional env: `AINL_CODE_CONTEXT_STORE`.

### LLM adapter setup

To enable cloud LLM providers, create an AINL config file following [`../LLM_ADAPTER_USAGE.md`](../LLM_ADAPTER_USAGE.md). Set provider API keys via environment variables (e.g. `OPENROUTER_API_KEY`). Then pass the config path with `--config` or set `AINL_CONFIG`.

You can verify cost tracking and retry behavior by running a program and checking the SQLite DB under `intelligence/monitor/`.

### Ecosystem transparency

- **Importer:** CLI `ainl import markdown`, `ainl import clawflows`, `ainl import agency-agents` share the same Markdown → graph path as the MCP tools above. When structure cannot be parsed, a **minimal_emit fallback stub** still yields compiling `.ainl` for review.
- **Checked-in samples:** [`../../examples/ecosystem/`](../../examples/ecosystem/) holds `original.md`, `converted.ainl`, and per-folder READMEs; **weekly auto-sync** ([`.github/workflows/sync-ecosystem.yml`](../../.github/workflows/sync-ecosystem.yml)) keeps them aligned with upstream public Markdown — see [`../ECOSYSTEM_OPENCLAW.md`](../ECOSYSTEM_OPENCLAW.md).
- **Contributions:** submit new workflows or agents via [`.github/PULL_REQUEST_TEMPLATE/`](../../.github/PULL_REQUEST_TEMPLATE/) (Clawflows-style workflow or Agency-Agents-style agent templates).

---

## See also

- **All MCP hosts (one-table reference):** [`../getting_started/HOST_MCP_INTEGRATIONS.md`](../getting_started/HOST_MCP_INTEGRATIONS.md)
- **OpenClaw + AINL gold standard (install / upgrade):** [`../operations/OPENCLAW_AINL_GOLD_STANDARD.md`](../operations/OPENCLAW_AINL_GOLD_STANDARD.md) — profiles, caps, cron, bootstrap, verification ([`../../tooling/bot_bootstrap.json`](../../tooling/bot_bootstrap.json) → `openclaw_ainl_gold_standard`)
- **AINL v1.8.0 — host briefing:** [`../operations/OPENCLAW_HOST_AINL_1_2_8.md`](../operations/OPENCLAW_HOST_AINL_1_2_8.md) — `openclaw_host_ainl_1_2_8` — [`../RELEASING.md`](../RELEASING.md)
- **Monitoring (OpenClaw vs ZeroClaw runners):** [`../operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md) and [`../../zeroclaw/bridge/README.md`](../../zeroclaw/bridge/README.md)
- **MCP operator guide:** [`../operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md) (stdio `ainl-mcp`, OpenClaw `openclaw.json`)
- **Integration narrative:** [`../INTEGRATION_STORY.md`](../INTEGRATION_STORY.md)
- **Unified bridge / workspace notes:** [`../ainl_openclaw_unified_integration.md`](../ainl_openclaw_unified_integration.md)
- **Cron / bridge code (non-MCP):** [`../../openclaw/bridge/README.md`](../../openclaw/bridge/README.md)
- **Compile-once framing:** [`../architecture/COMPILE_ONCE_RUN_MANY.md`](../architecture/COMPILE_ONCE_RUN_MANY.md)
- **Skill manifests:** [`../../skills/openclaw/README.md`](../../skills/openclaw/README.md), [`../../skills/ainl/README.md`](../../skills/ainl/README.md), [`../../skills/hermes/README.md`](../../skills/hermes/README.md)
- **Hermes hub (marketing):** [`hermes-agent.md`](./hermes-agent.md)
- **Hermes upstream:** [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **AgentSkills format hub:** [agentskills.io](https://agentskills.io/)
