# AI Native Lang (AINL)

<p align="center">
  <img src="docs/assets/ainl_logo.png" alt="AINL logo" width="220" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <a href="https://github.com/sbhooley/ainativelang/tags">
    <img src="https://img.shields.io/github/v/tag/sbhooley/ainativelang?label=release" alt="Latest tag" />
  </a>
  <a href="tests/snapshots/conformance/summary.md">
    <img src="tests/snapshots/conformance/conformance_badge.svg" alt="Conformance status" />
  </a>
  <a href="https://github.com/sbhooley/ainativelang/actions/workflows/sync-ecosystem.yml">
    <img src="https://github.com/sbhooley/ainativelang/actions/workflows/sync-ecosystem.yml/badge.svg" alt="Auto-sync OpenClaw/NemoClaw/Clawflows/Agency-Agents" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache-2.0" />
  </a>
  <img src="https://img.shields.io/badge/MCP-v1%20server-blueviolet" alt="MCP v1" />
  <a href="https://github.com/sbhooley/ainativelang/tree/main/skills/ainl">
    <img src="https://img.shields.io/badge/ZeroClaw%20Skill-AINL-blue" alt="ZeroClaw Skill: AINL" />
  </a>
  <a href="https://github.com/sbhooley/ainativelang/tree/main/skills/openclaw">
    <img src="https://img.shields.io/badge/OpenClaw%20Skill-AINL-blue" alt="OpenClaw Skill: AINL" />
  </a>
  <a href="https://github.com/NousResearch/hermes-agent">
    <img src="https://img.shields.io/badge/Hermes%20Agent-AINL-blue" alt="Hermes Agent: AINL" />
  </a>
  <img src="https://img.shields.io/badge/graph--first-deterministic%20IR-orange" alt="Graph-first deterministic IR" />
  <img src="https://img.shields.io/badge/AI%20workflow-language-brightgreen" alt="AI workflow language" />
</p>

> AI-led co-development project, human-initiated by Steven Hooley (`x.com/sbhooley`, `stevenhooley.com`, `linkedin.com/in/sbhooley`). Attribution details: `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md` and `tooling/project_provenance.json`.

> [!TIP]
> **New to AINL? --> HUMANS: TO GET STARTED --> JUST HAVE YOUR AGENT INSTALL THIS & ASK IT TO USE IT !!** -- For more info visit **[ainativelang.com](https://ainativelang.com)** for the high-level product story, integrations, use cases, and commercial/enterprise paths.
>
> This GitHub repo is the technical source of truth for AINL:
> - compiler, runtime, and canonical graph IR
> - CLI, HTTP runner, and MCP server
> - docs, examples, conformance, and implementation details
>
> **Start here**
> - **Understand AINL first:** [ainativelang.com](https://ainativelang.com)
> - **Run it now (CLI / runner / MCP):** Choose Your Path
> - **Read the docs hub:** [`docs/README.md`](docs/README.md)
> - **See updated benchmarks (tiktoken cl100k_base, viable subset, minimal_emit fallback stub):** [`BENCHMARK.md`](BENCHMARK.md) · [`docs/benchmarks.md`](docs/benchmarks.md) · comparative methodology [`docs/competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](docs/competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)
> - **ZeroClaw skill (one-command install → deterministic graphs):** [`docs/ZEROCLAW_INTEGRATION.md`](docs/ZEROCLAW_INTEGRATION.md) · [`skills/ainl/`](skills/ainl/) · curated trees [`examples/ecosystem/`](examples/ecosystem/)
> - **MCP host hub:** [`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](docs/getting_started/HOST_MCP_INTEGRATIONS.md) · `ainl install-mcp --host openclaw|zeroclaw|hermes`
> - **Agent guide index:** `docs/AGENT_GUIDE_INDEX.md` summarizes docs for OpenClaw, ZeroClaw, Hermes‑Agent, and generic AI agents.
> - **OpenClaw one-command env + crons + status:** [`docs/QUICKSTART_OPENCLAW.md`](docs/QUICKSTART_OPENCLAW.md) · `ainl install openclaw`, `ainl status` (with `--json`, `--json-summary`, `--summary`), `ainl cron add`, `ainl dashboard`, `ainl doctor --ainl` · rolling-budget storage: [`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md) §c (`memory_records` primary, legacy `weekly_remaining_v1` secondary). Agent discovery: `tooling/bot_bootstrap.json` → `openclaw_commands`.
> - **OpenClaw skill + bootstrap:** [`docs/OPENCLAW_INTEGRATION.md`](docs/OPENCLAW_INTEGRATION.md) · [`skills/openclaw/`](skills/openclaw/) · `ainl install-mcp --host openclaw`
> - **OpenClaw + AINL unified integration (v1.3.3+; includes v1.3.0 Hermes + `ainl install openclaw` / `ainl status`, v1.2.8 token optimizations, bridge, cron):** [`docs/ainl_openclaw_unified_integration.md`](docs/ainl_openclaw_unified_integration.md)
> - **Hermes Agent support (official; self-improving agents with deterministic graphs):** [`docs/HERMES_INTEGRATION.md`](docs/HERMES_INTEGRATION.md) · [`skills/hermes/`](skills/hermes/) · `ainl install-mcp --host hermes` · `ainl compile --emit hermes-skill`
> - **PTC-Lisp integration (opt-in):** [`docs/adapters/PTC_RUNNER.md`](docs/adapters/PTC_RUNNER.md) · quick start: `ainl run-hybrid-ptc` · examples:
>   - examples/hybrid_order_processor.ainl — hybrid order processor (parallel batches, signatures, firewall, LangGraph bridge)
>   - examples/price_monitor.ainl — PTC price monitor with parallel/recovery patterns
>   - health + beam_metrics / beam_telemetry passthrough; optional subprocess BEAM mode (AINL_PTC_USE_SUBPROCESS)
>   - _ context firewall + context_firewall_audit + ainl_ptc_audit MCP tool
>   - reliability overlays: ptc_run.ainl (sugar), ptc_parallel.ainl (pcall-style), recovery_loop.ainl (bounded retries)
>   - LangGraph bridge + PTC-compatible trace export; flow diagram
>   - Run ainl run-hybrid-ptc --help for a mock-friendly onramp
> - **Using Claude Code / Cowork / Dispatch-style tools?** See the MCP/integration guidance in docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md and docs/INTEGRATION_STORY.md
> - **AINL → HTTP workers (bridge contract, secondary to MCP):** docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md · JSON Schema schemas/executor_bridge_request.schema.json · include modules/common/executor_bridge_request.ainl
>
> TECHNICALS: AINL is a compact, graph-canonical, AI-native programming system for building deterministic workflows, multi-target applications, and operational agents without relying on ever-growing prompt loops. Positioning (current v1.3.4; monitoring pack since v1.2.10): AINL is the system that lets you author with an LLM once, validate with a compiler (strict mode, reachability, single-exit discipline), and emit production artifacts for LangGraph, Temporal, FastAPI, React, Hyperspace, Prisma, cron, and more — while deterministic execution, policy, and audit (runner service, trajectory JSONL) stay on the AINL side. Write in AINL → emit LangGraph or Temporal when you need their ecosystem today; keep the .ainl source as the single source of truth (docs/HYBRID_GUIDE.md, docs/competitive/README.md). Since v1.2.10, AINL also ships an optional monitoring pack for LLM/tool adapters and OpenClaw-style intelligence programs: unified LLM usage tracking, budget policy, and a small Flask/Prometheus dashboard under intelligence/monitor/ (see docs/MONITORING_OPERATIONS.md and docs/INTELLIGENCE_PROGRAMS_INTEGRATION.md).

## Open-core boundary

| Area | Status | Notes |
|:-----|:------:|:------|
| Core DSL, compiler, runtime, `ainl validate/check/inspect/visualize` | **Open** (Apache-2.0) | Language legitimacy; essential tooling |
| MCP server / bridge (`ainl-mcp`, `scripts/ainl_mcp_server.py`) | **Open & pluggable** | Any MCP host; bring your own compliant LLMs |
| OpenSpace / Lead AI style flows | **Open via BYO-LLM** | Implemented via MCP; operators choose their models |
| Enterprise audit/policy packs, managed ops, deployment kits | **Paid / optional** | Governance, SLA-backed support, monitored hosted runtime |

> Full boundary details: [`docs/OPEN_CORE_DECISION_SHEET.md`](docs/OPEN_CORE_DECISION_SHEET.md)

## New in v1.3.4

- **Enhanced diagnostics** (`--enhanced-diagnostics`): graph context + Mermaid snippets on compile errors
- **Error highlighting** (`ainl visualize --highlight-errors`): error nodes styled in Mermaid output
- **Static cost estimates** (`--estimate` on `check`, `inspect`, `status`): per-node token/USD estimates
- **Audit trail adapter** (`--enable-adapter audit_trail --audit-sink file:///...`): immutable JSONL compliance log (graph must invoke `audit_trail.record`)

> Tutorials: [Debugging with the Visualizer](docs/tutorials/debugging_with_visualizer.md) · [Production: Estimates & Audit](docs/tutorials/production_with_estimates_and_audit.md)

**AINL helps turn AI from "a smart conversation" into "a structured worker."**

> **v1.3.3 — Native Solana + prediction markets:** See [`docs/solana_quickstart.md`](docs/solana_quickstart.md) for strict graphs, env vars, dry-run-first flows, and `--emit solana-client` / `blockchain-client` usage, plus [`examples/prediction_market_demo.ainl`](examples/prediction_market_demo.ainl) for a concrete resolution → conditional payout pattern.

### v1.3.3 — Native Solana Support for Prediction Markets

- **Deterministic Solana agents:** Strict AINL graphs for market creation, Pyth/Hermes resolution monitoring, and on-chain trades/payouts keep behavior explainable and testable.
- **Key verbs:** `DERIVE_PDA` with **single-quoted JSON** seeds, `GET_PYTH_PRICE` (legacy + PriceUpdateV2), `HERMES_FALLBACK`, and `INVOKE` / `TRANSFER_SPL` with explicit priority fees (micro-lamports per CU).
- **Dry-run + emit:** Full dry-run safety (`AINL_DRY_RUN=1`) and emitted standalone clients via `--emit solana-client` so you can rehearse flows before sending real transactions.
- **Start here:** `docs/solana_quickstart.md` and `examples/prediction_market_demo.ainl`.

All Solana additions are additive-only and preserve full Hyperspace compatibility.

### Recommended production stack: AINL graphs + AVM or general agent sandboxes

AINL provides the deterministic, capability-declared graph layer. Pair it with Hyperspace AVM (`avmd`) or general runtimes (Firecracker microVMs, gVisor, Kubernetes Agent Sandbox, E2B-style runtimes, AVM Codes platform) for stronger isolation.

- New metadata: optional `execution_requirements` in compiled IR (`avm_policy_fragment`, isolation/resource hints).
- New CLI: `ainl generate-sandbox-config <file.ainl> [--target avm|firecracker|gvisor|k8s|general]`.
- New unified shim: optional `runtime/sandbox_shim.py` auto-detects AVM/general sandbox endpoints and falls back cleanly.

It is designed for teams building AI workflows that need multiple steps, state and memory, tool use, repeatable execution, validation and control, and lower dependence on long prompt loops.

**Compile-once, run-many:** you author (or import) a graph once; the runtime executes it deterministically without re-spending LLM tokens on orchestration each time. Size economics are tracked with **tiktoken cl100k_base**; the **viable subset** (e.g. **public_mixed**) shows about **~1.02×** leverage for **minimal_emit** vs unstructured baselines—see **[`BENCHMARK.md`](BENCHMARK.md)**, **[`docs/benchmarks.md`](docs/benchmarks.md)**, and **[`docs/architecture/COMPILE_ONCE_RUN_MANY.md`](docs/architecture/COMPILE_ONCE_RUN_MANY.md)**.

**Performance & benchmarks (updated Mar 2026):** Size results use **tiktoken cl100k_base** (billing-aligned for GPT-4o–class models). Reports separate **viable subset** rows from **legacy-inclusive** aggregates; **minimal_emit fallback stub** and **emitter compaction** (e.g. prisma / react_ts stubs) are documented in the transparency blocks. See **[`BENCHMARK.md`](BENCHMARK.md)** for tables; narrative hub **[`docs/benchmarks.md`](docs/benchmarks.md)** (highlights, commands, CI). Runtime economics and optional reliability batches: **`tooling/benchmark_runtime_results.json`** via `make benchmark` / `scripts/benchmark_runtime.py`. For long-lived OpenClaw deployments, pair these static benchmarks with live token-budget observability and cost tracking via **`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`** and the monitoring components documented in **`docs/MONITORING_OPERATIONS.md`**.

### CLI polish (OpenClaw, v1.3.3+)

These commands are implemented in **`cli/main.py`** and documented in **`docs/QUICKSTART_OPENCLAW.md`**. For bots and IDE tools, **`tooling/bot_bootstrap.json`** exposes the same surface under **`openclaw_commands`** (plus **`ai_native_lang_example_yml`**). Project lock example files: **`aiNativeLang.example.yml`** (repo root) and **`tooling/aiNativeLang.example.yml`** (packaged wheels).

| Command | What it does |
|--------|----------------|
| **`ainl install openclaw --workspace PATH`** | Merges **`env.shellEnv`** into **`<workspace>/.openclaw/openclaw.json`**, bootstraps SQLite, registers three gold-standard crons, restarts gateway; use **`--dry-run`** to preview. |
| **`ainl status`** | Unified health: workspace, schema, weekly budget (**`memory_records`** fallback), crons, drift, 7d tokens, estimated cost avoided (7d), caps. **`--json`** (pretty), **`--json-summary`** (one-line JSON), **`--summary`** (one-line text for alerts). |
| **`ainl doctor --ainl`** | Validates OpenClaw + AINL integration (env, schema, cron names, bootstrap flag). |
| **`ainl cron add FILE.ainl`** | Wraps **`openclaw cron add`** with message **`ainl run <path>`**; **`--cron`** or **`--every`**; **`--dry-run`** prints argv only. |
| **`ainl dashboard`** | Runs **`scripts/serve_dashboard.py`** (emitted server under **`tests/emits/server`** — build first with **`scripts/run_tests_and_emit.py`** in a dev checkout); **`--port`**, **`--no-browser`**. |

The CLI **fails fast** if **`tests/emits/server/server.py`** is missing (typical for PyPI-only installs), with the same **`run_tests_and_emit`** hint.

**Shell shortcut:** **`scripts/setup_ainl_integration.sh`** delegates to **`ainl install openclaw`** (supports **`--dry-run`**, **`--workspace`**, **`--verbose`**).

---

## Get Started (3 minutes)

**Requires Python 3.10+.** No git clone needed to try it.

```bash
# 1. Install the CLI
pip install ainativelang

# 2. Create a new project (generates main.ainl + README)
ainl init my-first-worker
cd my-first-worker

# 3. Check the program compiles cleanly (strict graph semantics)
ainl check main.ainl --strict

# 4. Run it
ainl run main.ainl

# 5. Visualise the control-flow graph
ainl visualize main.ainl --output -    # paste into https://mermaid.live
```

That's it. Edit `main.ainl`, add adapter calls (cache, HTTP, LLM, memory), revalidate, run again.

The `ainl init` command creates a clean, well-commented `main.ainl` designed for newcomers. It demonstrates core concepts — graph labels (`L1:` = control-flow node), requests (`R cache get` = read from the cache adapter), joins (`J` = return a value and finish the node), and branching — while remaining production-ready. Open `main.ainl` after scaffolding; the comments tell you exactly what each line does.

### Compact syntax (new in v1.3.3)

AINL now supports a human-friendly **compact syntax** alongside the original opcodes.
Both compile to the same IR. Compact is recommended for new code — 66% fewer tokens.

```ainl
# examples/compact/hello_compact.ainl
adder:
  result = core.ADD 2 3
  out result
```

```ainl
# Branching, inputs, adapter calls, cron — all work
classifier:
  in: level message
  severity = llm.classify level message
  if severity == "CRITICAL":
    http.POST ${SLACK_WEBHOOK} {text: message}
    out "alerted"
  out "logged"
```

See [`examples/compact/`](examples/compact/) for more, and [`AGENTS.md`](AGENTS.md) for the full compact syntax reference.

### write → check → visualize → run loop

1. **Write** — author in compact or opcode syntax, or have an LLM emit a `.ainl` program.
2. **Validate** strict graph semantics:
   `ainl validate your.ainl --strict`
   Or the equivalent: `ainl check your.ainl --strict`
   Failures include structured diagnostics (line, suggestion, optional `llm_repair_hint`).
   Use `--json-diagnostics` for CI/machine-readable output.
3. **Visualize** control flow as Mermaid:  
   `ainl visualize your.ainl --output - > graph.mmd` — paste into [mermaid.live](https://mermaid.live).
4. **Run** locally: `ainl run your.ainl`
5. **Emit** to other platforms: `ainl emit your.ainl --target langgraph -o graph.py`
6. **Serve** as HTTP API: `ainl serve --port 8080` (POST /validate, /compile, /run)
7. **Inspect canonical IR** (for agent/meta-agent loops): `ainl inspect your.ainl --strict`
8. **Emit JSONL execution tape** for grading/evolution: `ainl run your.ainl --trace-jsonl run.trace.jsonl`

<details>
<summary><strong>Advanced: Contributing or Custom Build (clone + editable install + CI bootstrap)</strong></summary>

```bash
# Clone and create an isolated env (match CI: Python 3.10)
git clone https://github.com/sbhooley/ainativelang.git
cd ainativelang

PYTHON_BIN=python3.10 VENV_DIR=.venv-py310 bash scripts/bootstrap.sh
source .venv-py310/bin/activate  # Windows: .venv-py310\Scripts\activate

# Install with dev + web extras
python -m pip install --upgrade pip
python -m pip install -e ".[dev,web]"

# Validate an example
ainl check examples/hello.ainl --strict

# Run the core test suite
python scripts/run_test_profiles.py --profile core

# Environment diagnostics
ainl doctor

# Full conformance matrix
make conformance

# Runner service (for API/orchestrator integration)
python scripts/runtime_runner_service.py
# GET http://localhost:8770/capabilities
# POST http://localhost:8770/run  {"code": "S app api /api\nL1:\nR core.ADD 2 3 ->sum\nJ sum"}
```

See `docs/INSTALL.md` and `CONTRIBUTING.md` for full contributor setup.

</details>

### Research-loop quickstart (meta-agent)

For self-improving loops (generate -> inspect -> mutate -> evaluate), use:

1. **Inspect canonical IR**
   - `ainl inspect candidate.ainl --strict`
2. **Diff two candidates**
   - MCP tool: `ainl_ir_diff(file1, file2, strict=true)`
3. **Score fitness**
   - MCP tool: `ainl_fitness_report(file, runs=5, strict=true)`
4. **Repair invalid outputs**
   - MCP `ainl_validate` diagnostics include `llm_repair_hint`

Contract and stable payload fields: `docs/operations/MCP_RESEARCH_CONTRACT.md`.

For the full conformance matrix in one command (tokenizer, IR canonicalization, strict validation, runtime parity, emitter stability):

`make conformance` (or `SNAPSHOT_UPDATE=1 make conformance` when intentionally updating snapshots).

### Community & Growth (start here too)

- Growth strategy and milestones: [`GROWTH-PLAN.md`](GROWTH-PLAN.md)
- Validation transparency: [`docs/validation-deep-dive.md`](docs/validation-deep-dive.md)
- GitHub Discussions: <https://github.com/sbhooley/ainativelang/discussions>
- Telegram: <https://t.me/AINL_Portal>
- X / Twitter: <https://x.com/ainativelang>

Short primer for stakeholders: **[`docs/WHAT_IS_AINL.md`](docs/WHAT_IS_AINL.md)** (canonical). [`WHAT_IS_AINL.md`](WHAT_IS_AINL.md) at repo root is a **stub** that points to the same content.

### Getting started with includes

Pull in shared subgraphs from `modules/` (paths resolve next to your source file, then CWD, then `./modules/`):

```ainl
include "modules/common/retry.ainl" as retry

L1: Call retry/ENTRY ->out J out
```

See **Includes & modules** below for `timeout.ainl`, strict rules, and the starter table.

**AI agents:** See `AI_AGENT_QUICKSTART_OPENCLAW.md` for a full agent onboarding guide, or `docs/BOT_ONBOARDING.md` for the machine-readable bootstrap path.

**Deeper setup:** See `docs/INSTALL.md` for platform-specific install, Docker, and pre-commit setup.

---

## Ecosystem & agent hosts (OpenClaw, ZeroClaw, Hermes)

Import **Clawflows**-style `WORKFLOW.md` or **Agency-Agents**-style personality Markdown into a **deterministic** `.ainl` graph (cron trigger, sequential `Call` steps or agent gates, optional `memory` / `queue` hooks for OpenClaw-style bridges). If structured parsing cannot extract steps or agent fields, the importer **falls back** to a compiling **minimal_emit fallback stub** (Phase‑1 style) so you still get valid, reviewable graph source.

**Host quick links:** [OpenClaw](https://openclaw.ai/) · [ZeroClaw skill (AINL)](https://github.com/sbhooley/ainativelang/tree/main/skills/ainl) · **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** · **[ArmaraOS](https://ainativelang.com/ArmaraOS)** — AINL wiring for all four is in [`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](docs/getting_started/HOST_MCP_INTEGRATIONS.md) (**`ainl install-mcp --host openclaw|zeroclaw|hermes|armaraos|armaraos`**).

The same path is exposed over MCP as **`ainl_list_ecosystem`**, **`ainl_import_clawflow`**, **`ainl_import_agency_agent`**, and **`ainl_import_markdown`** (stdio **`ainl-mcp`**). **Weekly auto-sync** ( **[`.github/workflows/sync-ecosystem.yml`](.github/workflows/sync-ecosystem.yml)** ) refreshes **[`examples/ecosystem/`](examples/ecosystem/)** from upstream public Markdown; community additions use **[`.github/PULL_REQUEST_TEMPLATE/`](.github/PULL_REQUEST_TEMPLATE/)** (workflow / agent templates).

```bash
ainl import markdown https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/check-calendar/WORKFLOW.md \
  --type workflow -o morning.ainl
ainl compile morning.ainl
```

Agent imports support `--personality "…"` and optional **`--generate-soul`** (writes `SOUL.md` and `IDENTITY.md` next to `-o`). Use **`--no-openclaw-bridge`** to emit `cache` instead of `memory` / `queue`.

Shortcuts (fetch five samples from upstream into `examples/ecosystem/` — requires network):

```bash
ainl import clawflows
ainl import agency-agents
```

### Install AINL as a ZeroClaw skill

```bash
zeroclaw skills install https://github.com/sbhooley/ainativelang/tree/main/skills/ainl
```

This installs the AINL importer, runtime shim, and MCP tools directly into ZeroClaw.

**Bootstrap** (PyPI self-upgrade, **`ainl-mcp`** in **`~/.zeroclaw/mcp.json`**, **`~/.zeroclaw/bin/ainl-run`**, **`PATH`** hint): from the skill directory run **`./install.sh`**, or run **`ainl install-mcp --host zeroclaw`** (use **`--dry-run`** / **`--verbose`** as needed). Alternative skill URL (standalone repo, when published): `https://github.com/sbhooley/ainl-zeroclaw-skill`.

**Try in chat:** *“Import the morning briefing using AINL.”* (Then point the agent at a Clawflows URL, a preset from **`ainl_list_ecosystem`**, or **`ainl import markdown …`**.)

Details: **[`docs/ZEROCLAW_INTEGRATION.md`](docs/ZEROCLAW_INTEGRATION.md)** · skill files: **[`skills/ainl/README.md`](skills/ainl/README.md)**.

### Install AINL as an OpenClaw skill

[OpenClaw](https://openclaw.ai/) uses **npm** + **`openclaw onboard`** for the host CLI. AINL is added as a **skill folder** (not via **`zeroclaw skills install`**): copy **[`skills/openclaw/`](skills/openclaw/)** to **`~/.openclaw/skills/`** or **`<workspace>/skills/`**, or install from **ClawHub** when the skill is listed there.

**Bootstrap** (PyPI self-upgrade, **`mcp.servers.ainl`** in **`~/.openclaw/openclaw.json`**, **`~/.openclaw/bin/ainl-run`**, **`PATH`** hint): from the skill directory run **`./install.sh`**, or run **`ainl install-mcp --host openclaw`** (use **`--dry-run`** / **`--verbose`** as needed). **`install.sh`** may run **`npm install -g openclaw@latest`** when npm is on PATH; set **`OPENCLAW_SKIP_NPM=1`** to skip.

Once bootstrapped, the OpenClaw bridge automatically activates AINL's intelligence layer, including the cap auto-tuner and memory hydration/embedding pilot. This creates a self-managing runtime that continuously adjusts execution caps and prunes caches based on observed token usage — helping sustain 90–95% token savings on high-frequency monitors and digests with zero recurring LLM orchestration cost.

For restricted Python sandboxes (PEP 668 externally-managed environments, common on OpenClaw/Clawbot hosts), no-root install order is: **venv first**, then **`--user`**, then **`--break-system-packages`** only as a last resort. `skills/ainl/install.sh` runs a compatible fallback sequence automatically and continues with MCP setup once `ainl` is available.

**Intelligence layer (after bootstrap):** `install-mcp` / `./install.sh` wires **MCP** and **`ainl-run`**; **bridge cron, env profiles, and `run_intelligence`** still need the one-time operator pass in [`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md). With that wiring, the **OpenClaw bridge + intelligence** path exposes AINL’s **cap auto-tuner**, **rolling budget → monitor hydration**, and optional **embedding pilot**—a **self-managing resource & budget layer** (not self-tuning workflow logic: compiled graphs stay deterministic) that adjusts **caps and cache pressure** from observed usage. See [`docs/INTELLIGENCE_PROGRAMS.md`](docs/INTELLIGENCE_PROGRAMS.md) and [`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md). On **typical high-frequency monitoring and digest** workloads, that stack helps sustain **~90–95%** token savings versus prompt-loop orchestration for the same scheduled work, with **near-zero recurring orchestration cost** after compile—**validate** on your host (`ainl bridge-sizing-probe`, weekly trends).

If you need a clean uninstall in managed sandboxes:

```bash
pip3 uninstall -y ainl mcp aiohttp langgraph temporalio
rm -rf /tmp/ainl-repo /data/.openclaw/workspace/skills/ainl /data/.local/lib/python3.13/site-packages/*ainl*
```

**Try in chat:** *“Import the morning briefing using AINL.”*

Details: **[`docs/OPENCLAW_INTEGRATION.md`](docs/OPENCLAW_INTEGRATION.md)** · skill files: **[`skills/openclaw/README.md`](skills/openclaw/README.md)**.

**Standalone skill repo (optional, later):** publish the contents of **[`skills/openclaw/`](skills/openclaw/)** as the root of **[github.com/sbhooley/ainl-openclaw-skill](https://github.com/sbhooley/ainl-openclaw-skill)** so users can clone or vendor a single-purpose tree (same three files: `SKILL.md`, `install.sh`, `README.md`).

### Install AINL for Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is a skill-native runtime with a closed learning loop. AINL pairs **deterministic compiled graphs** with Hermes via **`ainl-mcp`** (`ainl_run`) and **`--emit hermes-skill`** bundles (agentskills-style `SKILL.md` + `workflow.ainl` + `ir.json`).

**Bootstrap:** **`pip install 'ainativelang[mcp]'`** then **`ainl install-mcp --host hermes`** (alias **`ainl hermes-install`**), or run **`skills/hermes/install.sh`**. Emit skills to **`~/.hermes/skills/ainl-imports/<name>/`**.

Details: **[`docs/HERMES_INTEGRATION.md`](docs/HERMES_INTEGRATION.md)** · hub one-pager: **[`docs/integrations/hermes-agent.md`](docs/integrations/hermes-agent.md)** · skill pack: **[`skills/hermes/README.md`](skills/hermes/README.md)**.

Curated templates with `original.md`, `converted.ainl`, and notes: **[`examples/ecosystem/README.md`](examples/ecosystem/README.md)**.

**Weekly auto-sync:** the repo can refresh those sample trees from upstream on a schedule via GitHub Actions — see **[`.github/workflows/sync-ecosystem.yml`](.github/workflows/sync-ecosystem.yml)** (Monday 04:00 UTC, plus manual **workflow_dispatch**). PRs are opened only when `examples/ecosystem/**` conversions change. That workflow also **creates** the GitHub labels `ecosystem`, `automation`, `workflow`, and `agent` if missing (idempotent), then applies `ecosystem` + `automation` to the sync PR. If your org **disallows `GITHUB_TOKEN` from opening PRs**, set repository secret **`GH_PAT`** (PAT with repo + PR access to this repo only); see **[`docs/ECOSYSTEM_OPENCLAW.md`](docs/ECOSYSTEM_OPENCLAW.md)** — no access to upstream Clawflows/Agency-Agents orgs is required (public raw fetches only).

### Contributing workflows & agents

After you push a branch, **open a pull request** on GitHub and use the **template** dropdown to choose **Submit Workflow (Clawflows-style)** or **Submit Agent (Agency-Agents-style)** (see [`.github/PULL_REQUEST_TEMPLATE/`](.github/PULL_REQUEST_TEMPLATE/)).  
You can also append `?quick_pull=1&template=workflow-submission.md` or `template=agent-submission.md` to your **compare** URL (`main`…`your-branch`).

Templates: [`workflow-submission.md`](.github/PULL_REQUEST_TEMPLATE/workflow-submission.md) · [`agent-submission.md`](.github/PULL_REQUEST_TEMPLATE/agent-submission.md) · default [`pull_request_template.md`](.github/pull_request_template.md).

---

## Includes & modules

Reuse battle-tested patterns without copy-pasting whole graphs. **Compile-time** `include` merges each module’s labels under **`alias/LABEL`** keys (for example `retry/ENTRY`, `retry/EXIT_OK`, `timeout/WORK`).

**Syntax** (paths resolve next to the source file, then the current working directory, then `./modules/`):

```ainl
include "modules/common/retry.ainl" as retry
include modules/common/timeout.ainl as timeout
```

Quotes around the path are optional when unambiguous; **`as alias`** sets the prefix for every label from that file.

**Prelude order:** put every **`include`** line **before** the first top-level **`S`** or **`E`** (service / endpoint). Lines after **`S`** / **`E`** are not part of the include prelude; modules merged too late will not expose **`Call alias/…`** targets. See **`modules/common/README.md`**.

```ainl
include "modules/common/retry.ainl" as retry
include "modules/common/timeout.ainl" as timeout

S app api /api
L1: Call retry/ENTRY ->r J r
L2: Call timeout/ENTRY ->t J t
```

Subgraphs must define **`LENTRY:`** (merged as `alias/ENTRY`) and **at least one `LEXIT_*:`** label in **strict** mode. Do not declare top-level **`E`** / **`S`** inside includes—endpoints and services belong in the main program. Use **quoted** jumps for string payloads (`J "ok"`) so strict dataflow treats them as literals.

Shared modules live in a **`modules/`** directory next to your files (with CWD / `./modules/` fallback—see compiler path resolution).

**Starter modules in this repo**

| Module | What it is |
|--------|------------|
| `modules/common/retry.ainl` | Minimal **ENTRY → EXIT_OK / EXIT_FAIL** pattern with sample `core.ADD` work—copy and extend with your own retry / backoff steps in the parent or module. |
| `modules/common/timeout.ainl` | **Timeout / cancellation shape** (`ENTRY` → `Call WORK`, plus `LTIMEOUT` for the failure branch). The strict build uses `core.SLEEP` / `core.ECHO` stand-ins until real timer adapters are allowlisted—swap the `R` lines when your runtime supports them. |
| `modules/common/token_cost_memory.ainl` | Shared deterministic memory helper for monitor workflows using the `workflow` namespace (`WRITE` + bounded `LIST` with metadata and filters). |
| `modules/common/ops_memory.ainl` | Shared deterministic memory helper for monitor workflows using the `ops` namespace (`WRITE` + bounded `LIST` with metadata and filters). |
| `modules/common/generic_memory.ainl` | Shared namespace-aware deterministic memory helper for workflows that write/list outside `workflow`/`ops` (for example `session`, `long_term`, `intel`). |
| `modules/common/access_aware_memory.ainl` | Opt-in **access metadata** on reads/lists/writes: bumps **`metadata.last_accessed`** and **`metadata.access_count`** via **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, or graph-safe **`LACCESS_LIST_SAFE`** (recommended when using graph-preferred execution for list snapshots). See module header and **`modules/common/README.md`**. |

### Starter Modules (in `modules/common/`)

- `retry.ainl` — exponential backoff + max retries
- `timeout.ainl` — timeout wrapper with placeholder delay (swap to real timer later)

```ainl
include "modules/common/timeout.ainl" as timeout

L1:
  Call timeout/ENTRY ->out
  J out
```

More patterns coming soon (approval gate, circuit breaker, RAG retrieval, etc.). **Contract (strict):** included subgraphs expose **`LENTRY:`** (merged as `alias/ENTRY`) and at least one **`LEXIT_*:`** exit label; call them with **`Call alias/ENTRY ->out`** from the parent. **Agents** benefit from smaller, verified building blocks and stable qualified names (`retry/n1`, …) in the graph IR. Full behavior, path resolution, and tests: `tests/test_includes.py`, `docs/architecture/GRAPH_INTROSPECTION.md`.

**See your includes in a diagram:** `ainl visualize main.ainl -o graph.mmd` — each alias becomes a Mermaid subgraph cluster; synthetic `Call →` edges into `alias/ENTRY` are annotated in the output.

### Reference bots

- **Apollo X promoter** — production-shaped **strict** graph, HTTP **executor gateway**, OpenClaw/cron entrypoints, `executor_request_builder`, `record_decision`, and KV snapshot hooks: **[`apollo-x-bot/README.md`](apollo-x-bot/README.md)**. Optional **Growth Pack (v1.3)** (follow/discovery/like/thread/awareness, env-gated) is documented in the same README under *Optional Apollo-X Growth Pack*.

---

## Choose Your Path

AINL can be used through three integration surfaces. All three run the same
compiler and runtime; they differ in how you connect.

External runtime option (opt-in): AINL can call PTC-Lisp through `ptc_runner`
for reliability overlays and trace interoperability; see `docs/adapters/PTC_RUNNER.md`.

The canonical "hello world" workflow used below:

```
S app api /api
L1:
R core.ADD 2 3 ->x
J x
```

### Path A — CLI only (fastest start)

```bash
# Validate and inspect IR
ainl-validate examples/hello.ainl --strict --emit ir

# Mermaid diagram (paste into mermaid.live)
ainl visualize examples/hello.ainl --output - > hello.mmd

# Run directly
ainl run examples/hello.ainl --json
```

No server needed. Good for local development, scripting, and CI.

### Path B — HTTP runner (orchestrator integration)

```bash
# Start the runner service
ainl-runner-service
# default: http://localhost:8770

# Discover capabilities
curl http://localhost:8770/capabilities

# Execute a workflow
curl -X POST http://localhost:8770/run \
  -H "Content-Type: application/json" \
  -d '{"code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x", "strict": true}'
```

Best for container deployments, sandbox controllers, and external orchestrators.
See `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`.

### Path C — MCP host (AI coding agents)

```bash
# Install with MCP extra
pip install -e ".[mcp]"

# Start the stdio MCP server
ainl-mcp
```

Then configure your MCP-compatible host (Gemini CLI, Claude Code, Codex, etc.)
to use the `ainl-mcp` stdio transport. The host can call `ainl_validate`,
`ainl_compile`, `ainl_capabilities`, `ainl_security_report`, and `ainl_run`.

MCP v1 runs with safe defaults (core-only adapters, conservative limits).
Operators can scope which tools/resources are exposed via named exposure
profiles (`AINL_MCP_EXPOSURE_PROFILE`) or env-var inclusion/exclusion lists.
See section 9 of `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` for the
full quickstart, exposure scoping, and gateway deployment guidance.

**Three layers:** *MCP exposure profile* → what tools/resources the host can
discover. *Security profile / capability grant* → what execution is allowed.
*Policy / limits* → what each run is constrained by.

> **For Claude Code / Cowork / Dispatch users:** Treat AINL as a scoped MCP
> tool provider and deterministic workflow/runtime layer underneath your host.
> Start with `validate_only` or `inspect_only` exposure profiles, and only
> enable `safe_workflow` after operators have reviewed security profiles,
> grants, policies, limits, and adapter exposure. AINL is not the host, not
> Cowork, not a gateway, and not a control plane. For a concrete
> validator → inspector → safe-runner walkthrough, see the
> *End-to-end example* section of
> `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`.

> **Core first, advanced later.** The paths above use the core compiler and
> runtime only. Advanced/operator-only surfaces (agent coordination, memory
> migration, OpenClaw extensions) are documented separately under
> `docs/advanced/` and are not the recommended starting point for new users.

For the full getting-started guide, see `docs/getting_started/README.md`.

---

## Why AINL Exists

Modern AI systems are increasingly powerful at reasoning, but still unreliable and expensive when forced to orchestrate whole workflows through long prompt loops. Long prompt loops create:

- Prompt bloat and rising token cost
- Hidden state and brittle orchestration
- Poor auditability and hard-to-debug tool behavior

AINL addresses this by moving orchestration out of the model and into a deterministic execution substrate:

1. The model describes the workflow once
2. The compiler validates it
3. The runtime executes it deterministically
4. State lives in variables, cache, memory, databases, and adapters — not in prompt history

```mermaid
flowchart LR
A[AINL Source] --> B[Compiler]
B --> C[Canonical Graph IR]
C --> D[Runtime Engine]
D --> E[Adapters / Tools / State]
D --> F[Optional LLM Calls]
```

The graph is the source of truth. The runtime is the orchestrator. The model is a bounded reasoning component inside the system.

---

## What Makes AINL Different

### 1. Graph-first, not prompt-first

AINL programs compile to canonical graph IR. Execution follows graph semantics, not ad hoc conversational state.

### 2. AI-oriented surface syntax

The surface language is intentionally compact and structured for parseability, determinism, and low-entropy generation by models.

### 3. Strict-mode guarantees

AINL's strict mode enforces high-value invariants such as:

- Canonical graph emission
- No undeclared references
- No unknown module operations
- Adapter arity validation
- No unreachable or duplicate nodes
- Canonical node IDs
- Validated call returns
- Controlled exits

Strict validation is paired with **structured diagnostics** (native `Diagnostic` records: lineno, spans, kinds, suggested fixes) surfaced on the CLI with **rich** or plain text, or **JSON** for automation (`ainl-validate`, `ainl visualize`, language server). See `docs/INSTALL.md` and `docs/CONFORMANCE.md`.

### 4. Adapters separate "what" from "how"

AINL describes what should happen. Adapters implement how it happens. This allows the same graph language to drive HTTP, SQLite, filesystem operations, email/calendar/social integrations, service checks, cache/memory, queues, WASM modules, and OpenClaw-specific operational workflows.

PTC-style overlays are additive and opt-in:

- `ptc_runner` for external PTC-Lisp execution (`R ptc_runner run ...`)
- `llm_query` for ad-hoc LLM calls in graph steps
- optional `# signature: ...` metadata with runtime checks via `intelligence/signature_enforcer.py`
- `_`-prefixed context firewall at adapter/export serialization boundaries
- trajectory export to PTC-compatible JSONL via `intelligence/trace_export_ptc_jsonl.py`

### 5. Multi-target leverage

One AINL program can describe a workflow once and emit multiple downstream artifacts (FastAPI, React/TypeScript, Prisma, OpenAPI, Docker/Compose, Kubernetes, cron/queue/scraper outputs), rather than forcing an agent to regenerate parallel implementations.

**Emitters:** `--emit hyperspace` via `python3 scripts/validate_ainl.py …` writes `hyperspace_agent.py` (use `-o path`). It embeds the compiled IR and runs it with `RuntimeEngine`, registers `vector_memory` / `tool_registry`, optional `hyperspace_sdk` import stub, and respects `AINL_LOG_TRAJECTORY` for `SOURCE_STEM.trajectory.jsonl` in the current working directory.

Hyperspace happy path (use `--enable-adapter vector_memory` and `--enable-adapter tool_registry` with `ainl run` when the graph calls those adapters). After emit, run `python3 demo_agent.py` from **repo root** (or any working tree that contains `runtime/engine.py` and `adapters/`) so imports resolve:

```bash
ainl-validate examples/hyperspace_demo.ainl --strict --emit hyperspace -o demo_agent.py
cd /path/to/AI_Native_Lang && AINL_LOG_TRAJECTORY=1 python3 demo_agent.py
# optional: ainl run examples/hyperspace_demo.ainl --enable-adapter vector_memory --enable-adapter tool_registry --log-trajectory --json
```

### 6. Compile-once, run-many

Once a workflow is compiled, it executes repeatedly without needing the model to regenerate orchestration logic. Runtime state is handled by adapters. Recurring workflows avoid repeated prompt-loop costs.

---

## Competitive Landscape

AINL sits at the intersection of graph-native agent orchestration, deterministic workflow execution, and AI-native programming languages.

| System | Focus | Difference vs AINL |
|--------|------|-------------------|
| LangChain / LangGraph | Chain/graph-based agent orchestration | No canonical IR, no compiler, no compile-once/run-many; LangGraph adds graphs but remains prompt-driven |
| CrewAI | Multi-agent role-based orchestration | Role/prompt-driven, no deterministic graph execution or adapter-level effect control |
| Temporal | Durable workflow execution | Not AI-native, no DSL or emitters |
| Restate | Durable agents & services | Runtime-focused, no language layer |
| Microsoft Agent Framework | Typed graph workflows | Framework, not a compiled language |
| AutoGen | Multi-agent coordination | Prompt/event-driven, not deterministic graphs |

For a detailed comparison of graph-native vs prompt-loop architectures with production evidence, see `docs/case_studies/graph_agents_vs_prompt_agents.md`.

AINL uniquely combines:

- graph-first canonical IR
- strict validation & conformance
- adapter-based effect system
- compile-once, run-many execution
- multi-target emission (API, UI, DB, infra)

→ Treating AI systems as **deterministic programs**, not prompt loops.

---

## Who AINL Is For

AINL is best suited for:

- AI engineers and agent builders
- teams building internal AI workers and structured automations
- platform and ops teams that need controlled AI workflows
- enterprises that care about repeatability, auditability, and workflow governance

AINL is less optimized for casual chatbot prototyping, one-off prompt hacks, or no-code-first usage.

### Why businesses care

AINL matters when AI moves beyond demos and starts doing real operational work. It helps reduce the gap between "a clever AI demo" and "a workflow a business can actually run" — repeatable, inspectable, stateful, tool-using, cost-aware, and easier to validate and maintain.

### Why AI agents care

An AINL program gives an agent explicit control flow, explicit side effects, compile-time validation, capability-aware boundaries, externalized memory, and reproducible runtime behavior. The LLM stops being the whole control plane and becomes a reasoning component inside a deterministic system.

---

## Real-World Usage: Apollo + OpenClaw

AINL is not just a speculative language design. It is already used in live OpenClaw-integrated workflows.

The Apollo / OpenClaw stack exercises adapters such as `email`, `calendar`, `social`, `db`, `svc`, `cache`, `queue`, `wasm`, `memory`, `extras`, and `tiktok`.

Production-validated examples include:

- `demo/monitor_system.lang` — recurring multi-module monitor
- Daily digest workflows
- Infrastructure watchdogs
- Lead enrichment
- Token cost tracking
- TikTok SLA monitoring
- Canary probes
- Memory pruning
- Session continuity
- Meta-monitoring of the monitor fleet itself

These programs demonstrate that AINL is effective for recurring monitors, stateful automation, autonomous ops, safety-aware tool orchestration, and long-lived agent systems.

### Where AINL helps most

AINL is most valuable when workflows are recurring, stateful, branching, safety-sensitive, multi-step, multi-target, or shared across teams or agents. For trivial one-off scripts, the gain is smaller. For multi-step agent systems and autonomous operational workflows, the gain can be substantial.

---

## Token Efficiency

AINL's compactness and cost benefits should be described carefully.

- **Compile-once, run-many:** You pay generation cost once; the **deterministic runtime** executes the graph without a prompt loop per invocation. **Runtime benchmarks** (`scripts/benchmark_runtime.py`, `tooling/benchmark_runtime_results.json`) measure post-compile latency, RSS, optional **execution reliability** batches, and **tiktoken**-based cost estimates—see **[`docs/benchmarks.md`](docs/benchmarks.md)**.
- **Token Cost Efficiency:** AINL can save tokens in two ways. First, at authoring time, because the DSL is denser than general-purpose code. Second, at runtime, because compiled AINL programs execute deterministically through adapters and do not require recurring model inference on each execution. In practice, this can significantly reduce prompt and code-generation volume for non-trivial workflows while also eliminating repeated model-generation cost during normal operation. Complex monitors and similar programs that take roughly 30k–70k tokens in AINL (including the program itself and relevant runtime context) are estimated to require 3–5× more tokens, depending on workload, when generated as equivalent Python or TypeScript by an LLM. Those equivalents would also typically lack AINL's strict validation, graph introspection, and multi-target emission. After the initial learning curve, AINL is estimated to reduce per-task token burn by 2–5× for non-trivial automation. For simple tasks, the savings are smaller but still generally positive due to DSL density.

Bottom line: AINL lowers overall token usage while increasing capability, predictability, and reliability.

**What is supported today:**

- **Reproducible size metrics** default to **tiktoken cl100k_base** (see **[`BENCHMARK.md`](BENCHMARK.md)**). Headline ratios use a **viable subset** for mixed profiles so representative workloads are not drowned out by tiny legacy shells; **legacy-inclusive** totals are printed **separately** for honesty.
- AINL is often denser than equivalent generated implementation artifacts *in the benchmark setup we publish*—always profile- and mode-scoped
- **minimal_emit** is the more honest deployment comparison; **full_multitarget** is downstream expansion leverage, not apples-to-apples terseness
- **`--strict-mode`** on `scripts/benchmark_size.py` enables true strict compilation (reachability pruning) for **`canonical_strict_valid`** only—see `BENCHMARK.md` callout when active
- Compile-once / run-many workflows reduce repeated model-generation cost

**What is not supported:**

- Universal compactness claims against all mainstream languages
- Guaranteed tokenizer pricing savings from lexical proxy metrics alone

**Current benchmark framing:**

- **`canonical_strict_valid`** is the primary headline profile (**19/19** viable example programs in `tooling/artifact_profiles.json`).
- Default sizing is **tiktoken cl100k_base** in markdown tables; JSON still records the CLI `--metric` (default `tiktoken`). Legacy `--metric=approx_chunks` is optional and **deprecated** for billing claims.
- **Highlights (from [`BENCHMARK.md`](BENCHMARK.md), Mar 2026):** `make benchmark` uses **`--mode wide`**: strict-valid **~3.2×** `full_multitarget_core` (six compiler emitters) / **~362×** `full_multitarget` (+ hybrid **langgraph**/**temporal** wrappers with embedded IR) / **~0.76×** `minimal_emit` (tk). **`public_mixed` viable** **72/85**; **`compatibility_only` viable** **53/66**. Full detail: **[`docs/benchmarks.md#benchmark-highlights-march-2026`](docs/benchmarks.md#benchmark-highlights-march-2026)**.
- **Transparency:** **`prisma` / `react_ts`** benchmark stubs **compacted Mar 2026** (~50–70% tk reduction on those emit lines); **minimal_emit** may add a small **python_api fallback stub** (~20–30 tk) when no selected target emits code—both are documented in `BENCHMARK.md`.
- In `full_multitarget`, canonical strict examples show strong expansion leverage; runtime traces on the tracked benchmark JSON typically show **100%** success on optional reliability batches for strict-valid workloads with **sub-millisecond** measured latency (machine-dependent).
- In `minimal_emit`, mixed compatibility examples can be smaller or larger depending on artifact class and required targets
- **Evidence pack:** reproducible **size** + **runtime** benchmarks (tiktoken sizing, compile-time column, latency/RSS, cost estimates, reliability batches, handwritten baselines) live in [`BENCHMARK.md`](BENCHMARK.md) with automation in `make benchmark` / `make benchmark-ci` and CI regression gating—see **[`docs/benchmarks.md`](docs/benchmarks.md)** for the full map.

```bash
# Refresh size markdown + JSON and runtime JSON (local).
# Uses `scripts/benchmark_size.py --mode wide` (core + full hybrid + minimal_emit).
make benchmark

# CI-style JSON only (does not rewrite BENCHMARK.md)
make benchmark-ci
```

Hybrid / LangGraph / Temporal optional deps: **`pip install -e ".[interop]"`** or **`".[benchmark]"`** — see **[`docs/PACKAGING_AND_INTEROP.md`](docs/PACKAGING_AND_INTEROP.md)**.

> AINL provides a compact, reproducible, profile-segmented way to express graph workflows and multi-target systems, while often reducing repeated AI generation effort and avoiding repeated orchestration token burn during runtime.

---

## Status

AI Native Lang is an actively developed open-core project. The core compiler/runtime and graph tooling are real and usable; some language surfaces, examples, targets, and evaluation workflows are still being stabilized.

Public release expectations:
- the **graph-first compiler/runtime core** is the most stable part of the project,
- **server/OpenAPI/runtime/tooling** are the strongest current implementation lanes,
- some examples and compatibility artifacts are intentionally classified as non-strict or legacy,
- broad target coverage exists, but not every target is equally mature or equally validated.

For implementation and shipped-capability status, see:

- [docs/CONFORMANCE.md](docs/CONFORMANCE.md)
- [docs/RELEASE_READINESS.md](docs/RELEASE_READINESS.md)
- [docs/runtime/TARGETS_ROADMAP.md](docs/runtime/TARGETS_ROADMAP.md)
- [docs/AINL_CANONICAL_CORE.md](docs/AINL_CANONICAL_CORE.md)
- [docs/EXAMPLE_SUPPORT_MATRIX.md](docs/EXAMPLE_SUPPORT_MATRIX.md)
- [docs/advanced/SAFE_USE_AND_THREAT_MODEL.md](docs/advanced/SAFE_USE_AND_THREAT_MODEL.md)

### Best supported today

- Canonical compile path in `compiler_v2.py`
- Graph-first runtime execution in `runtime/engine.py`
- Formal prefix grammar orchestration in `compiler_grammar.py`
- Graph normalization, diff, patch, and canonicalization tooling in `tooling/`
- Server/OpenAPI emission and runtime-backed execution flow
- Runtime-native adapters with contract tests: `http`, `sqlite`, `postgres`, `mysql`, `redis`, `dynamodb`, `airtable`, `supabase`, `fs`, `tools`
- Runner service with policy-gated `/run`, `/capabilities`, health/metrics: `scripts/runtime_runner_service.py`
- Adapter privilege-tier metadata and security profiles: `tooling/adapter_manifest.json`, `tooling/security_profiles.json`
- Security/privilege introspection tooling: `tooling/security_report.py`

### Use with care

- Compatibility examples are retained intentionally; do not assume all public examples are strict-valid.
- Some emitters are more mature than others; treat `docs/runtime/TARGETS_ROADMAP.md` as a capability map, not a promise that every target is equally production-ready.
- Model-training and benchmark artifacts are included, but they should be read together with `BENCHMARK.md`, `docs/OLLAMA_EVAL.md`, and `docs/TEST_PROFILES.md` rather than as standalone proof of maturity.

---

## Documentation

### Essential reading

- What is AINL? (canonical primer + capabilities): **`docs/WHAT_IS_AINL.md`** · root **`WHAT_IS_AINL.md`** (stub → docs)
- Whitepaper draft (architecture, benchmarks, OpenClaw ops + token economics through **v1.3.3**, async runtime, reactive DB/realtime adapters; native Solana — **`docs/solana_quickstart.md`**): **`WHITEPAPERDRAFT.md`**
- Reactive / event-driven workflows (DynamoDB Streams, Supabase Realtime, Redis Pub/Sub, Airtable webhooks) + examples: `docs/reactive/REACTIVE_EVENTS.md`, `examples/reactive/`
- Advanced durability patterns for multi-node/cross-process checkpoints and cursors using existing adapters only: `docs/reactive/ADVANCED_DURABILITY.md`
- Packaged durability templates (Redis + Postgres checkpoint helpers): `templates/durability/`
- Production starter templates (durability + observability-ready workers): `templates/production/`
- AINL → HTTP workers (bridge envelope, schema, include): `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` · `schemas/executor_bridge_request.schema.json` · `modules/common/executor_bridge_request.ainl`
- Getting started (3 integration paths): `docs/getting_started/README.md`
- Primary docs hub: `docs/README.md`
- Audience guide: `docs/AUDIENCE_GUIDE.md`
- Spec: `docs/AINL_SPEC.md`
- Canonical core: `docs/AINL_CANONICAL_CORE.md`
- Full docs reference map: `docs/DOCS_INDEX.md`
- Benchmarks & evidence (size, runtime, CI, LLM/cloud): `docs/benchmarks.md`

### Architecture and internals

- Graph/IR introspection: `docs/architecture/GRAPH_INTROSPECTION.md`
- State discipline (tiered state model): `docs/architecture/STATE_DISCIPLINE.md`
- Memory adapter contract (v1 + additive v1.1 deterministic metadata/filtering): `docs/adapters/MEMORY_CONTRACT.md`, `docs/adapters/MEMORY_CONTRACT_V1_1_RFC.md`

#### Memory & State

Workflow memory is **externalized through adapters** (not the prompt). Production-style programs combine **session or workflow namespaces**, **TTLs**, **bounded list filters**, and **prune** so retention stays predictable under load. For a full OpenClaw-style illustration of cache + memory + budget enforcement (including audit rows and pruning hooks), see **`demo/session_budget_enforcer.lang`**. Optional **access-aware** touches (recency / frequency metadata on **`memory`** records) live in **`modules/common/access_aware_memory.ainl`**; use **`LACCESS_LIST_SAFE`** when you need list-wide touches under **graph-preferred** execution (see module header).
- Runtime semantics: `SEMANTICS.md`
- Runtime/compiler ownership: `docs/RUNTIME_COMPILER_CONTRACT.md`
- Grammar reference: `docs/language/grammar.md`
- Conformance and strict policy: `docs/CONFORMANCE.md`
- Embedding in meta-agent loops: `docs/EMBEDDING_RESEARCH_LOOPS.md`
- MCP research payload contract: `docs/operations/MCP_RESEARCH_CONTRACT.md`

### Operations and deployment

- Sandbox execution profiles: `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- Runtime container guide: `docs/operations/RUNTIME_CONTAINER_GUIDE.md`
- External orchestration guide: `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- Integration story (AINL in agent stacks): `docs/INTEGRATION_STORY.md`
- Autonomous ops playbook: `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md`
- Named security profiles: `tooling/security_profiles.json`
- Security/privilege report: `tooling/security_report.py`
- Safe use and threat model: `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`
- MCP server overview: section **9** of `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- MCP server for AI coding agents: `scripts/ainl_mcp_server.py` (see external orchestration guide, section 9)
- LLM/tool cost & budget observability pack (CostTracker/BudgetPolicy/dashboard): `docs/MONITORING_OPERATIONS.md` and `docs/INTELLIGENCE_PROGRAMS_INTEGRATION.md`

### Examples and case studies

- Example support levels: `docs/EXAMPLE_SUPPORT_MATRIX.md`
- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- Case studies: `docs/case_studies/` — graph-native vs prompt-loop agents, runtime cost advantage
- Workflow patterns: `docs/PATTERNS.md`

### For AI agents and bots

- **Bots / implementation discipline:** `docs/BOT_ONBOARDING.md` — onboarding for agents; **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** is required before implementation work. Machine-readable pointers: `tooling/bot_bootstrap.json`.

### Release and contribution

- **Current PyPI / runtime package version:** **`ainl` 1.3.3** (see `pyproject.toml`, `runtime/engine.py` **`RUNTIME_VERSION`**, `docs/CHANGELOG.md`, `docs/RELEASE_NOTES.md`).
- Release readiness matrix: `docs/RELEASE_READINESS.md`
- No-break migration tracker: `docs/NO_BREAK_MIGRATION_PLAN.md`
- Release notes: `docs/RELEASE_NOTES.md`
- Maintainer release execution guide: `docs/RELEASING.md`
- Hybrid deployment runbook: `docs/hybrid/OPERATOR_RUNBOOK.md`
- Immediate post-release roadmap: `docs/POST_RELEASE_ROADMAP.md`
- Docs maintenance contract: `docs/DOCS_MAINTENANCE.md`
- Contributor guide: `CONTRIBUTING.md`
- Security and support: `SECURITY.md`, `SUPPORT.md`
- Machine-readable support levels: `tooling/support_matrix.json`
- Safe optimization guidance: `docs/runtime/SAFE_OPTIMIZATION_POLICY.md`

---

## Technical Architecture

AI Native Lang (AINL) is a compact language and toolchain for agent-oriented workflows. The compiler emits canonical graph IR and compatibility `legacy.steps`; the runtime executes graph-first semantics through `runtime/engine.py`.

AINL is best understood as a **graph-canonical intermediate programming system** with:
- a compact textual surface for generation and transport,
- a compiler/runtime pair designed around deterministic IR,
- emitters for practical targets,
- and tooling for constrained decoding, diffing, patching, and evaluation.

### Core invariant

> **Canonical IR = nodes + edges; everything else is serialization.**

AINL source is a compact surface language for producing the canonical graph. That graph can then be executed by the runtime, inspected and diffed, validated in strict mode, or emitted into targets such as FastAPI, React/TypeScript, Prisma, OpenAPI, Docker/Compose, cron/queue/scraper/MT5 outputs.

### Surfaces and usage lanes

**Core / safe-default surface:** The canonical compiler/runtime and graph IR (`compiler_v2.py`, `runtime/engine.py`), canonical language scope (`docs/AINL_CANONICAL_CORE.md`, `docs/AINL_SPEC.md`), strict/compatible examples classified in `docs/EXAMPLE_SUPPORT_MATRIX.md`, graph/IR tooling (`docs/architecture/GRAPH_INTROSPECTION.md`), server/OpenAPI emission and basic workflows.

**Sandboxed and operator-controlled deployments:** AINL is architecturally suited to run inside sandboxed, containerized, or operator-controlled execution environments. The runtime's adapter allowlist, resource limits, and policy validation tooling provide the configuration surface that external orchestrators and sandbox controllers need to restrict and govern AINL execution. AINL is the **workflow layer**, not the sandbox or security layer; containment, network policy, and process isolation are the responsibility of the hosting environment.

Current security and operator capabilities:

- **Capability grant model** — each execution surface (runner, MCP server) loads a server-level grant at startup from a named security profile (`AINL_SECURITY_PROFILE` / `AINL_MCP_PROFILE` env vars). Callers can tighten restrictions per-request but never widen beyond what the server allows. See `docs/operations/CAPABILITY_GRANT_MODEL.md`.
- **Adapter capability gating** — explicit allowlists via `AdapterRegistry`; only adapters in the effective grant's allowlist can be called.
- **Policy-gated execution** — the `/run` endpoint validates compiled IR against the effective policy (derived from the grant) before execution. Forbidden adapters, effects, privilege tiers, and destructive adapters trigger HTTP 403 with structured errors.
- **Capability discovery** — `GET /capabilities` exposes available adapters, verbs, effect defaults, privilege tiers, and adapter metadata (`destructive`, `network_facing`, `sandbox_safe`) so orchestrators can make informed decisions before submitting workflows.
- **Named security profiles** — `tooling/security_profiles.json` packages recommended adapter allowlists, privilege-tier restrictions, runtime limits, and orchestrator expectations for common deployment scenarios (`local_minimal`, `sandbox_compute_and_store`, `sandbox_network_restricted`, `operator_full`). Profiles are loaded as capability grants at startup.
- **Mandatory default limits** — runner and MCP execution surfaces apply conservative resource ceilings (`max_steps`, `max_depth`, `max_adapter_calls`, etc.) by default. Callers can tighten limits but not widen them.
- **Privilege-tier metadata** — each adapter carries a `privilege_tier` (`pure`, `local_state`, `network`, `operator_sensitive`) plus `destructive`, `network_facing`, and `sandbox_safe` boolean classification fields in `tooling/adapter_manifest.json`.
- **Structured audit logging** — the runner service emits structured JSON log events (`run_start`, `adapter_call`, `run_complete`, `run_failed`, `policy_rejected`) with UTC timestamps, trace IDs, duration, result hashes (no raw payloads), and redacted arguments. See `docs/operations/AUDIT_LOGGING.md`.
- **Security introspection** — `tooling/security_report.py` generates a per-label, per-graph privilege map showing which adapters, verbs, privilege tiers, and adapter metadata flags a workflow uses.

AINL does **not** provide container isolation, process sandboxing, network policy enforcement, authentication/encryption, or multi-tenant isolation. These remain the responsibility of the hosting environment.

See:
- `docs/INTEGRATION_STORY.md` — how AINL fits inside agent stacks, pain-to-solution map, integration surface
- Generic external executors via HTTP bridge (multi-backend capable): [`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md) — **MCP (`ainl-mcp`) remains primary for OpenClaw/NemoClaw**; HTTP bridge is secondary. **Artifacts:** [`schemas/executor_bridge_request.schema.json`](schemas/executor_bridge_request.schema.json), [`schemas/executor_bridge_validate.py`](schemas/executor_bridge_validate.py), [`modules/common/executor_bridge_request.ainl`](modules/common/executor_bridge_request.ainl).
- `docs/operations/CAPABILITY_GRANT_MODEL.md` — host handshake, restrictive-only merge, env-var profile loading
- `docs/operations/AUDIT_LOGGING.md` — structured runtime event logging
- `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` — capability discovery, policy-gated execution, integration checklist
- `docs/operations/SANDBOX_EXECUTION_PROFILE.md` — adapter profiles, limit profiles, environment guidance, named security profiles
- `docs/operations/RUNTIME_CONTAINER_GUIDE.md` — containerized deployment patterns
- `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` — trust model, safe-use guidance, and privilege-tier explanation

**Advanced / operator-only / experimental surface:** AINL also includes advanced, extension/OpenClaw-oriented features that are not the safe-default entry path and are not a built-in secure orchestration or multi-agent safety layer. These are intended for operators who understand the risks and have added their own safeguards.

Key docs in this lane:

- `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` — safe use, threat model, and advisory vs enforced fields.
- `docs/advanced/AGENT_COORDINATION_CONTRACT.md` — AgentTaskRequest/AgentTaskResult/AgentManifest envelopes and local mailbox contract.
- `docs/EXAMPLE_SUPPORT_MATRIX.md` (OpenClaw compatibility family) — advanced coordination and OpenClaw examples.
- `tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py` — optional mailbox linter for advanced coordination usage.

### Stability boundaries

- **Canonical today:** compiler semantics and strict validation in `compiler_v2.py`, runtime semantics in `runtime/engine.py` (`RuntimeEngine`), formal grammar orchestration in `compiler_grammar.py`
- **Compatibility surfaces:** `runtime/compat.py` and `runtime.py` are compatibility wrappers/re-exports, `grammar_constraint.py` is a compatibility composition layer, `legacy.steps` are compatibility IR fields
- **Artifact profile contract:** strict/non-strict/legacy expectations are defined in `tooling/artifact_profiles.json`
- **Support-level contract:** canonical/compatible/deprecated intent is declared in `tooling/support_matrix.json`; public recommended language scope is described in `docs/AINL_CANONICAL_CORE.md`

### Standardized health envelope

All production monitors use a common message envelope for notifications:

```json
{
  "envelope": {"version":"1.0","generated_at":"<ISO>"},
  "module": "<monitor_name>",
  "status": "ok" | "alert",
  "ts": "<ISO>",
  "metrics": { ... },
  "history_24h": { ... },
  "meta": {}
}
```

See [`docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md`](docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md).

---

## Deployment

### Production deploy (Docker)

From repo root after emitting:

```bash
cd tests/emits/server
docker compose up --build
```

Or build image from repo root: `docker build -f tests/emits/server/Dockerfile .`

The emitted server also includes **openapi.json** for API docs, codegen, and gateways.

### Production: logging, rate limit, K8s

The emitted server includes **structured logging** (request_id, method, path, status, duration_ms) and optional **rate limiting** via env `RATE_LIMIT` (requests per minute per client; 0 = off). **Kubernetes**: emitted `k8s.yaml` (Deployment + Service, health/ready probes); use `compiler.emit_k8s(ir, with_ingress=True)` for Ingress.

### Requirements

See [docs/INSTALL.md](docs/INSTALL.md) for full setup details. At a minimum: Python 3.10+, pip and virtual environment support, Docker for container-based deployment flows. **Match CI:** use a 3.10 venv at `.venv-py310` (`PYTHON_BIN=python3.10 VENV_DIR=.venv-py310 bash scripts/bootstrap.sh`) and run tools as `./.venv-py310/bin/python`.

---

## Hybrid Deployments

> **Validator:** `scripts/validate_ainl.py` supports **`--emit langgraph`** (single `StateGraph` wrapper module) and **`--emit temporal`** (paired `*_activities.py` + `*_workflow.py`). These are additive CLI options; default `IR` / server / hyperspace behavior is unchanged. See **[`docs/HYBRID_GUIDE.md`](docs/HYBRID_GUIDE.md)** and **[`examples/hybrid/README.md`](examples/hybrid/README.md)**. To include hybrid wrappers in benchmark **`minimal_emit`** / planner slices, declare **`S hybrid langgraph`**, **`S hybrid temporal`**, or both (see the guide). Ops checklist: **[`docs/hybrid/OPERATOR_RUNBOOK.md`](docs/hybrid/OPERATOR_RUNBOOK.md)**.

| Mode | When to use | AINL role | Host / extras |
|------|-------------|-----------|----------------|
| **Pure AINL** | You want CLI, MCP, or emitted HTTP worker only | Full program | None required |
| **LangGraph hybrid** | Cyclic LLM/tool graphs, LangGraph checkpoints, ecosystem interop | Deterministic core inside one (or more) nodes | `pip install langgraph` for generated runner |
| **Temporal hybrid** | Durable long-running workflows, retries, Temporal visibility | Same, inside an activity | `pip install temporalio` on worker / workflow import |

**LangGraph:** emit a ready-made `StateGraph` with `python3 scripts/validate_ainl.py your.ainl --emit langgraph -o your_langgraph.py`. The module calls `run_ainl_graph()` from `runtime/wrappers/langgraph_wrapper.py` (`RuntimeEngine`, `{"ok", "result", "error"}`-style payload). Example: [`examples/hybrid/langgraph_outer_ainl_core/`](examples/hybrid/langgraph_outer_ainl_core/) · [`docs/hybrid_langgraph.md`](docs/hybrid_langgraph.md).

**Temporal:** `python3 scripts/validate_ainl.py your.ainl --emit temporal` writes `<stem>_activities.py` and `<stem>_workflow.py` (use `-o` for directory or `.py` prefix; see [`docs/hybrid_temporal.md`](docs/hybrid_temporal.md)). Activities use `execute_ainl_activity()` from `runtime/wrappers/temporal_wrapper.py`. Example: [`examples/hybrid/temporal_durable_ainl/`](examples/hybrid/temporal_durable_ainl/).

**LangChain / CrewAI (tools):** optional **`langchain_tool`** adapter — `python3 -m cli.main run ... --enable-adapter langchain_tool`. Demo: [`examples/hybrid/langchain_tool_demo.ainl`](examples/hybrid/langchain_tool_demo.ainl).

**code_context (optional)** — Tiered, ctxzip-style codebase context for a local tree: index Python and basic JS/TS into JSON (default store: `.ainl_code_context.json`, override with `AINL_CODE_CONTEXT_STORE`). After indexing, `QUERY_CONTEXT` returns Tier 0 (signature list), Tier 1 (TF–IDF–ranked signatures plus doc/summary), or Tier 2 (full source when requested). Also: **`GET_DEPENDENCIES`** / **`GET_IMPACT`** (import graph + transitive importers + PageRank) and **`COMPRESS_CONTEXT`** (TF–IDF order, greedy token-budget packing). Enable with **`--enable-adapter code_context`** on **`ainl run`** (installing MCP alone does not enable optional adapters). Full reference: [`docs/adapters/CODE_CONTEXT.md`](docs/adapters/CODE_CONTEXT.md). Tiered design: [BradyD2003/ctxzip](https://github.com/BradyD2003/ctxzip), **Brady Drexler**. Graph/impact/packing ideas: [chrismicah/forgeindex](https://github.com/chrismicah/forgeindex), **Chris Micah**.

Example usage from an AINL graph (adapter target `code_context`): `INDEX /path/to/repo` builds the store; `QUERY_CONTEXT "user authentication flow" 1` returns Tier 1 (signatures plus summaries for top chunks); `QUERY_CONTEXT "user authentication flow" 2` includes full source for those ranked chunks; `COMPRESS_CONTEXT "…" 8000` packs signatures/summaries under a token budget; `STATS` reports chunk count, indexed root, store path, and last update time.

**Example (requires `--enable-adapter code_context`):** index once, then query in a loop — Tier 1 is usually token-efficient; `STATS` exposes chunk count and store metadata.

```ainl
S app coding_agent /agent

# Index once (setup step or dedicated entrypoint)
L_index:
  R code_context.INDEX "/path/to/your/repo" ->index_result
  J index_result

# Main loop: query repeatedly (Tier 1 = signatures + summaries)
L_query:
  R code_context.QUERY_CONTEXT developer_query 1 50 ->context
  R code_context.COMPRESS_CONTEXT developer_query 8000 ->packed
  R code_context.STATS ->stats
  # ... feed context into an LLM node or tool ...
  J context
```

Bind `developer_query` from a slot, prior step, or input. The JSON store persists, so `INDEX` is typically run once per workspace.

---

## Repo Layout

| Path | Purpose |
|------|--------|
| `docs/AINL_SPEC.md` | AINL 1.0 formal spec: principles, grammar, execution, targets |
| `docs/CONFORMANCE.md` | Implementation conformance vs spec (IR shape, graph emission, P, meta) |
| `docs/runtime/TARGETS_ROADMAP.md` | Expanded targets for production and adoption |
| `docs/language/grammar.md` | Ops/slots reference (v1.0) |
| `compiler_v2.py` | Parser + IR + all emitters (OpenAPI, Docker, K8s, Next/Vue/Svelte, SQL, env) |
| `runtime/engine.py` | `RuntimeEngine` (graph-first execution; step fallback) |
| `runtime/compat.py` | `ExecutionEngine` compatibility shim over canonical runtime |
| `runtime.py` | compatibility re-export for historical imports |
| `adapters/` | Pluggable DB/API/Pay/Scrape (mock + base) |
| `compiler_grammar.py` | Compiler-owned formal prefix grammar/state machine (lexical + structural admissibility) |
| `grammar_priors.py` | Non-authoritative token sampling priors (state/class-driven; no formal rule ownership) |
| `grammar_constraint.py` | Thin compatibility layer that composes formal grammar + priors + pruning APIs |
| `docs/RUNTIME_COMPILER_CONTRACT.md` | Runtime/compiler/decoder ownership + conformance contract |
| `scripts/validate_ainl.py` | CLI validator: compile .lang, print IR or emit artifact |
| `scripts/validate_s_cron_schedules.py` | Guardrail: malformed `S <adapter> cron "…"` lines (also **`ainl-validate-s-cron`**); see `docs/CRON_ORCHESTRATION.md` |
| `scripts/visualize_ainl.py` | Graph visualizer: compile to Mermaid (clusters for `include` aliases); see **Visualize your workflow** below |
| `scripts/validator_app.py` | Web validator (FastAPI): POST .lang → validate, GET / for paste UI |
| `scripts/generate_synthetic_dataset.py` | Generate 10k+ valid .lang programs into `data/synthetic/` |
| `tests/test_conformance.py` | Conformance tests (IR shape + emit outputs); run with `pytest tests/test_conformance.py` |
| `tests/test_*.lang` | Example specs |
| `examples/` | Example programs with explicit strict/non-strict classes (see `tooling/artifact_profiles.json`) |
| `intelligence/` | OpenClaw-oriented monitors (digest, memory consolidation, token-aware bootstrap); see `docs/INTELLIGENCE_PROGRAMS.md` |
| `agent_reports/` | Agent field reports from production OpenClaw runs; index in `agent_reports/README.md` |
| `scripts/run_intelligence.py` | Dev runner for selected `intelligence/*.lang` programs |
| `tests/emits/server/` | Emitted server (logging, rate limit, health/ready), static, ir.json, openapi.json, Dockerfile, docker-compose.yml, k8s.yaml |
| `.github/workflows/ci.yml` | CI: pytest conformance, emit pipeline, example validation |

---

## Tooling Reference

### Visualize your workflow

Compile a `.ainl` file to **Mermaid** for GitHub, [mermaid.live](https://mermaid.live), Obsidian, or any Mermaid-capable viewer. **Include aliases** become subgraph clusters automatically; synthetic `Call →` edges show how the main flow enters an included module.

**Your first diagram** (from repo root):

```bash
python3 -m cli.main visualize examples/hello.ainl --output - > hello.mmd
# After pip install -e .
ainl visualize examples/hello.ainl --output - > hello.mmd
```

1. Open [mermaid.live](https://mermaid.live).
2. Click the left editor pane and paste the **entire** contents of `hello.mmd`.

**What you should see** for `examples/hello.ainl`: a top-down graph (`graph TD` + `direction TB`), one **`main`** cluster (`c_main`), rectangular **R** nodes and circular **J** nodes, and edges between them. **Pink fill** (`classDef labelstyle`) applies to nodes in labels whose id ends with `ENTRY` or `EXIT_*` (this hello program only uses `L1`, so you will not see that styling here—try an `include` module to get `retry/ENTRY`, `retry/EXIT_OK`, etc.).

**Includes** (e.g. a file with `include modules/common/retry.ainl as retry` and a `Call` into `retry/ENTRY`): run `visualize` on that file. You should see a separate **`retry`** cluster, nodes such as `"retry/ENTRY/n1"`, cross-cluster edges **after** the subgraphs, and a `%% Synthetic edges: Call → …` comment before the synthetic `|call|` edge into the included entry.

**Save / share** on mermaid.live: **Export → PNG or SVG**, **Share** (link for X/Reddit), or **Edit → copy** the Mermaid block for README or posts.

```bash
# Write to a file, or stdout
ainl visualize examples/hello.ainl --output diagram.md
ainl-visualize examples/hello.ainl -o diagram.md
```

#### Export as image (PNG/SVG)

```bash
# PNG export
ainl visualize examples/hello.ainl --png diagram.png

# SVG export
ainl visualize examples/hello.ainl --svg diagram.svg

# Optional render size
ainl visualize examples/hello.ainl --png diagram.png --width 1600 --height 1000

# Denser graph: timeout module + workflow memory put/list/prune (strict-safe example)
ainl visualize examples/timeout_memory_prune_demo.ainl --png docs/assets/timeout_memory_prune_flow.png
```

Image export uses Playwright. Install dev deps and Chromium once:

```bash
pip install -e ".[dev]"
playwright install chromium
```

| Flag | Purpose |
|------|---------|
| `--output` / `-o` | Write Mermaid to a file, or `-` for stdout (default). |
| `--no-clusters` | Single flat graph (fully qualified node ids, no subgraphs). |
| `--labels-only` | Minimal node text (mostly `op` names) for dense programs. |
| `--format mermaid` | Default; `dot` reserved (use `scripts/render_graph.py` for Graphviz DOT today). |
| `--diagnostics-format` | On compile failure: `auto`, `plain`, `rich`, or `json` (same family as `ainl-validate`). |
| `--no-color` | Plain diagnostics on stderr. |

Use `--no-clusters` for a flat graph, `--labels-only` for dense programs, and `-o -` for stdout.

#### Example output (paste into https://mermaid.live)

Illustrative **include** layout (ids with `/` are **quoted** so Mermaid parses them). The tool emits the same structure with fully qualified node ids such as `"retry/ENTRY/n1"` instead of shorthand labels:

```mermaid
graph TD
    direction TB

    subgraph c_retry ["retry"]
        "retry/ENTRY"[ENTRY] --> "retry/n1"[EXPONENTIAL 5 200]
        "retry/n1" --> "retry/EXIT_OK"[EXIT_OK]
        "retry/n1" --> "retry/EXIT_FAIL"[EXIT_FAIL]
    end

    %% Synthetic edges: Call → included label entry (not explicit in IR)
    L1[Your Main Logic] -->|"call"| "retry/ENTRY"
```

Real output uses fully qualified IDs like `"retry/ENTRY/n1"` and clusters automatically by include **alias** prefix (`retry/…` → subgraph `retry`).

- **Validator CLI**: `python3 scripts/validate_ainl.py [file.lang] [--emit server|react|openapi|prisma|sql|hyperspace] [-o path]`; stdin supported.
- **Strict diagnostics**: `--strict` uses structured compiler diagnostics; stderr shows a numbered report (3-line source context, carets when spans exist, suggestions). **`--diagnostics-format=auto|plain|json|rich`** controls output (`auto` uses rich when the package is installed, stderr is a TTY, and `--no-color` is off). **`--json-diagnostics`** is a legacy alias for `json`. Install optional `pip install -e ".[dev]"` for **rich**. **`--no-color`** forces plain text instead of rich styling.
- **Validator web**: `uvicorn scripts.validator_app:app --port 8766` then open http://127.0.0.1:8766/ to paste and validate.
- **Installed CLIs**: `ainl-validate`, `ainl-validator-web`, `ainl-generate-dataset`, `ainl-compat-report`, `ainl-tool-api`, `ainl-ollama-eval`, `ainl-ollama-benchmark`, `ainl-validate-examples`, `ainl-check-viability`, `ainl-playbook-retrieve`, `ainl-test-runtime`, `ainl-visualize`, `ainl`.
- **Runtime modes**: `ainl run ... --execution-mode graph-preferred|steps-only|graph-only --unknown-op-policy skip|error`.
- **Strict literal policy**: in strict mode, bare identifier-like tokens in read positions are treated as variable refs; quote string literals explicitly (see `docs/RUNTIME_COMPILER_CONTRACT.md` and `docs/language/grammar.md`).
- **Golden fixtures**: `ainl golden` validates `examples/*.ainl` against `*.expected.json`.
- **Replay tooling**: `ainl run ... --record-adapters calls.json` and `ainl run ... --replay-adapters calls.json` for deterministic adapter replay.
- **Reference adapters**: `http`, `sqlite`, `postgres`, `mysql`, `redis`, `dynamodb`, `airtable`, `supabase`, `fs` (sandboxed), and `tools` bridge with contract tests. Optional network adapters include `ptc_runner` and `llm_query` (explicit enablement required).
- **Runner service**: `ainl-runner-service` (FastAPI) with `/run`, `/enqueue`, `/result/{id}`, `/capabilities`, `/health`, `/ready`, and `/metrics`.
- **MCP server**: `ainl-mcp` (stdio-only) exposes `ainl_validate`, `ainl_compile`, `ainl_run`, `ainl_capabilities`, `ainl_security_report`, `ainl_fitness_report`, and `ainl_ir_diff` as MCP tools for Gemini CLI, Claude Code, Codex, and other MCP-compatible agents. PTC-related tools (`ainl_ptc_signature_check`, `ainl_trace_export`, `ainl_ptc_run`, `ainl_ptc_health_check`, `ainl_ptc_audit`) are also available when your MCP exposure profile includes them. It is a thin workflow-level surface over the existing compiler/runtime, not a replacement for the runner service, and currently runs with safe-default restrictions (core-only adapters, hardcoded conservative limits). Requires `pip install -e ".[mcp]"`.
- **Tool API schema**: `tooling/ainl_tool_api.schema.json` (structured compile/validate/emit loop contract).
- **Synthetic dataset**: `python3 scripts/generate_synthetic_dataset.py --count 10000 --out data/synthetic` — writes only programs that compile.
- **Formal prefix grammar (compiler-owned)**: `compiler_grammar.py` is the source of truth for prefix lexical/syntactic/scope admissibility.
- **Grammar ownership contract**: Grammar law lives in `compiler_v2.py`. Formal orchestration lives in `compiler_grammar.py`. Non-authoritative sampling priors live in `grammar_priors.py`. Compatibility composition APIs live in `grammar_constraint.py`.
- **Decoder helpers**: `next_token_priors(prefix)`, `next_token_mask(prefix, raw_candidates)`, `next_valid_tokens(prefix)`.
- **Compile-once / run-many proof pack**: see `docs/architecture/COMPILE_ONCE_RUN_MANY.md`.
- **Program summary**: `python scripts/inspect_ainl.py examples/hello.ainl`
- **Full canonical IR dump**: `ainl inspect examples/hello.ainl --strict`
- **Run summary**: `python scripts/summarize_runs.py run1.json run2.json`
- **Benchmarks (size + runtime + CI gate):** `make benchmark` (full, updates [`BENCHMARK.md`](BENCHMARK.md)); `make benchmark-ci` (JSON-only CI-style). Narrative + metrics glossary: [`docs/benchmarks.md`](docs/benchmarks.md). Optional: `pip install -e ".[benchmark]"` for `tiktoken`/`psutil`; `pip install -e ".[anthropic]"` for `ainl-ollama-benchmark --cloud-model claude-3-5-sonnet`.
- **Corpus tools**: `python scripts/evaluate_corpus.py --mode dual`, `python scripts/validate_corpus.py --include-negatives`, `pytest tests/test_corpus_layout.py -v`
- **Fine-tune**: `bash scripts/setup_finetune_env.sh`, `.venv-ci-smoke/bin/python scripts/finetune_ainl.py --profile fast --epochs 1 --seed 42`
- **Post-train inference**: `.venv-py310/bin/python scripts/infer_ainl_lora.py --adapter-path models/ainl-phi3-lora --max-new-tokens 120 --device cpu`
- **Docs contract guard**: `ainl-check-docs` for cross-link/staleness/coupling checks.
- **Pre-commit**: `pre-commit install` to run docs/quality hooks locally.
- **Test profiles**: `.venv-py310/bin/python scripts/run_test_profiles.py --profile <name>` — `core` (default), `emits`, `lsp`, `integration`, `full`.

### Async runtime (optional)

AINL keeps sync runtime behavior by default. To run with the native async engine path:

```bash
AINL_RUNTIME_ASYNC=1 ainl run examples/hello.ainl --enable-adapter postgres
# or
ainl run examples/hello.ainl --enable-adapter postgres --runtime-async
```

See `docs/runtime/ASYNC_RUNTIME.md` for adapter coverage and fallback behavior.
Current async-capable adapters include postgres/mysql/supabase, redis (full async verb parity with bounded pub/sub listening), dynamodb streams (bounded async subscribe/unsubscribe batching), and airtable attachment/webhook extension verbs.

### Reactive observability (optional)

AINL can emit lightweight adapter timing + reactive batch metrics (off by default):

```bash
AINL_RUNTIME_ASYNC=1 AINL_OBSERVABILITY=1 \
  ainl run examples/reactive/hybrid_stream_broadcast.ainl \
  --runtime-async --observability --enable-adapter dynamodb --enable-adapter supabase --enable-adapter redis --enable-adapter memory
```

When enabled, runtime writes structured JSON metric lines to stderr (for example `adapter.call.duration_ms`, `reactive.events_per_batch`, `reactive.sequence_gap`, `reactive.ack.success_rate`).

You can also persist metrics to a JSONL sink file:

```bash
AINL_RUNTIME_ASYNC=1 AINL_OBSERVABILITY=1 AINL_OBSERVABILITY_JSONL=/tmp/ainl-reactive-metrics.jsonl \
  ainl run examples/reactive/hybrid_stream_broadcast.ainl \
  --runtime-async --observability --observability-jsonl /tmp/ainl-reactive-metrics.jsonl \
  --enable-adapter dynamodb --enable-adapter supabase --enable-adapter redis --enable-adapter memory
```

This makes it easy to consume metrics with `jq`, `vector`, `promtail`, or simple log tail/aggregation tools. Stderr and JSONL file sink can be used together.

For production multi-node durability (shared checkpoints/cursors), see `docs/reactive/ADVANCED_DURABILITY.md` for Redis-backed, Postgres-backed, and hybrid patterns that require no new adapter code.

## Status: Production Ready for Reactive Workflows

AINL is now production-ready for reactive/event-driven graph workflows with a complete end-to-end stack:

- **Full native async runtime** (`--runtime-async`) with async-capable adapter execution.
- **Comprehensive database adapters** across `sqlite`, `postgres`, `mysql`, `redis`, `dynamodb`, `airtable`, and `supabase`.
- **Reactive primitives** with bounded, practical semantics:
  - DynamoDB Streams with checkpointing and ack flows
  - Supabase Realtime with fan-out, replay, cursor, and ack helpers
  - Redis pub/sub for low-latency internal fan-out
- **Observability support** for reactive workloads, including structured metrics and JSONL sink output (`--observability-jsonl` / `AINL_OBSERVABILITY_JSONL`).
- **Production starter templates** in `templates/production/` for immediate rollout patterns.
- **Durability guidance** in `docs/reactive/ADVANCED_DURABILITY.md` for multi-process and multi-node checkpoint/cursor persistence using existing adapters.

What's next: shared multi-node durability coordination beyond process-local helpers, runtime scheduling optimizations for very high-throughput pipelines, and optional advanced adapter features for specialized deployments.

### PostgreSQL adapter (runtime-native)

Enable `postgres` explicitly and configure credentials via environment variables (preferred) or CLI flags:

```bash
export AINL_POSTGRES_URL='postgresql://user:pass@localhost:5432/appdb'
ainl run examples/hello.ainl --enable-adapter postgres --postgres-allow-table users --postgres-allow-write
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R postgres.query "SELECT id, email FROM users WHERE id = %s" [42] ->rows
  J rows
```

Supported verbs: `query`, `execute`, and `transaction` (`R postgres.transaction [{verb, sql, params}] ->out`). For production, keep `allow_write` off unless needed, use parameterized SQL, and scope table access with `--postgres-allow-table`.
Full contract and security guidance: `docs/adapters/POSTGRES.md`.

### MySQL adapter (runtime-native)

Enable `mysql` explicitly and configure credentials via environment variables (preferred) or CLI flags:

```bash
export AINL_MYSQL_URL='mysql://user:pass@localhost:3306/appdb'
ainl run examples/hello.ainl --enable-adapter mysql --mysql-allow-table users --mysql-allow-write
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R mysql.query "SELECT id, email FROM users WHERE id = %s" [42] ->rows
  J rows
```

Supported verbs: `query`, `execute`, and `transaction` (`R mysql.transaction [{verb, sql, params}] ->out`). For production, keep `allow_write` off unless needed, use parameterized SQL, and scope table access with `--mysql-allow-table`.
Full contract and security guidance: `docs/adapters/MYSQL.md`.

### Redis adapter (runtime-native)

Enable `redis` explicitly and configure via environment variables (preferred) or CLI flags:

```bash
export AINL_REDIS_URL='redis://localhost:6379/0'
ainl run examples/hello.ainl --enable-adapter redis --redis-allow-write --redis-allow-prefix session:
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R redis.set "session:42" "{\"state\":\"active\"}" 300 ->ok
  R redis.get "session:42" ->value
  J value
```

Supported verbs include key/value (`get/set/delete/incr/decr`), hashes (`hget/hset/hdel/hmget`), lists (`lpush/rpush/lpop/rpop/llen`), pub/sub (`publish/subscribe`), health (`ping/info`), and `transaction`.
Full contract and security guidance: `docs/adapters/REDIS.md`.

### DynamoDB adapter (runtime-native)

Enable `dynamodb` explicitly and configure endpoint/region via environment variables (preferred) or CLI flags:

```bash
export AINL_DYNAMODB_URL='http://127.0.0.1:8000'
export AWS_ACCESS_KEY_ID='dummy'
export AWS_SECRET_ACCESS_KEY='dummy'
export AWS_DEFAULT_REGION='us-east-1'
ainl run examples/hello.ainl --enable-adapter dynamodb --dynamodb-allow-table users --dynamodb-allow-write
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R dynamodb.get "users" {"pk":"u#42","sk":"profile"} ->out
  J out
```

Supported verbs include single-item (`get/put/update/delete`), collection (`query/scan`), batch/transaction (`batch_get/batch_write/transact_get/transact_write`), health (`describe_table/list_tables`), and bounded streams (`streams.subscribe/streams.unsubscribe`).
Full contract and security guidance: `docs/adapters/DYNAMODB.md`.

### Airtable adapter (runtime-native)

Enable `airtable` explicitly with scoped API key + base id:

```bash
export AINL_AIRTABLE_API_KEY='pat_xxx'
export AINL_AIRTABLE_BASE_ID='app_xxx'
ainl run examples/hello.ainl --enable-adapter airtable --airtable-allow-table users --airtable-allow-write
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R airtable.list "users" {"maxRecords": 20, "pageSize": 20} ->rows
  J rows
```

Supported verbs include `list/find/create/update/delete`, discovery (`get_table/list_tables/list_bases`), `upsert`, plus scoped attachment and webhook helpers (`attachment.upload/attachment.download`, `webhook.create/webhook.list/webhook.delete`).
Full contract and security guidance: `docs/adapters/AIRTABLE.md`.

### Supabase adapter (runtime-native wrapper)

Enable `supabase` explicitly with Supabase DB + project credentials:

```bash
export AINL_SUPABASE_DB_URL='postgresql://user:pass@localhost:5432/appdb'
export AINL_SUPABASE_URL='https://your-project.supabase.co'
export AINL_SUPABASE_SERVICE_ROLE_KEY='ey...'
ainl run examples/hello.ainl --enable-adapter supabase --supabase-allow-table users --supabase-allow-write
```

AINL graph syntax:

```ainl
S app core noop
L1:
  R supabase.select "users" {"id": 42} ["id","email"] ->out
  J out
```

Supported verbs include DB wrapper operations (`from/select/query/insert/update/upsert/delete/rpc`) plus auth (`auth.*`), storage (`storage.*`), and advanced realtime helpers (`realtime.subscribe/unsubscribe/broadcast/replay/get_cursor/ack`) for lightweight fan-out/replay/checkpoint flows.
Full contract and security guidance: `docs/adapters/SUPABASE.md`.

---

## Project Origin

AI Native Lang began from a human-initiated idea and has been developed in explicit human+AI co-development from the start. AI systems have been active contributors in naming, architecture, and implementation iteration; notably, the name **"AI Native Lang"** was proposed by an AI model and adopted by the project.

The human initiator of AINL is **Steven Hooley**.

- X: <https://x.com/sbhooley>
- Website: <https://stevenhooley.com>
- LinkedIn: <https://linkedin.com/in/sbhooley>

Timeline anchor: Foundational AI research and cross-platform experimentation by the human founder began in **2024**. After partial loss of early artifacts, AINL workstreams were rebuilt, retested, and formalized in overlapping phases through **2025-2026**.

For full attribution context, see [docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md](docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md), [tooling/project_provenance.json](tooling/project_provenance.json), and [docs/CHANGELOG.md](docs/CHANGELOG.md).

---

## Community and Support

- Contribution workflow: `CONTRIBUTING.md`
- Contributor behavior policy: `CODE_OF_CONDUCT.md`
- Security reporting: `SECURITY.md`
- Support expectations and channels: `SUPPORT.md`
- Commercial/licensing inquiries: `COMMERCIAL.md`

---

## Community & Growth

Join the conversation:
- [GitHub Discussions](https://github.com/sbhooley/ainativelang/discussions) (enable if not already)
- [Telegram](https://t.me/AINL_Portal)
- [X / Twitter](https://x.com/ainativelang)

See [GROWTH-PLAN.md](GROWTH-PLAN.md) for how we're scaling sustainably.

---

## Licensing

AI Native Lang uses an open-core licensing model.

- **Open Core:** Designated core code is licensed under the Apache License 2.0. See `LICENSE`.
- **Documentation and Content:** Non-code docs/content are licensed under `LICENSE.docs`, unless noted otherwise.
- **Models, Weights, and Data Assets:** Model/checkpoint/data-style artifacts may be governed by separate terms. See `MODEL_LICENSE.md`.
- **Commercial Offerings:** Some hosted/enterprise/premium capabilities are available under separate commercial terms. See `COMMERCIAL.md`.
- **Trademarks:** `AINL` and `AI Native Lang` branding rights are governed separately from code licenses. See `TRADEMARKS.md`.

---

## OpenClaw integration

All agent orchestration, cron unification, memory bridging, and OpenClaw-specific supervision glue lives in **`openclaw/bridge/`** (with backward-compatible **`scripts/`** shims). See **[`openclaw/bridge/README.md`](openclaw/bridge/README.md)** for runners, drift checks, `AINL_WORKSPACE` cron patterns, and the `ainl_bridge_main.py` entrypoint.

---


## ArmaraOS Integration

AINL integrates seamlessly with [OpenFang](https://github.com/RightNow-AI/openfang), the open-source Agent Operating System.

### Quick Start

```bash
# Install AINL for OpenFang
ainl install armaraos

# Emit a hand package
ainl emit --target armaraos -o my_hand/ workflow.ainl

# Run with OpenFang
armaraos hand run my_hand --input '{}'

# Check status
ainl status --host armaraos
```

### Features

- **WASM Sandbox**: All hands run in a secure WASM sandbox with configurable memory/instruction limits
- **Merkle Audit Trail**: Token usage is recorded with cryptographic proofs for accountability
- **Taint Tracking**: Data lineage tracking for sensitive information
- **MCP Native**: OpenFang uses AINL as a first-class MCP server
- **Tauri Sidecar**: Desktop apps can embed AINL via OpenFang sidecar

### Configuration

After `ainl install armaraos`, your `~/.armaraos/config.toml` will contain:

```toml
[[mcp_servers]]
name = "ainl"
command = "ainl-mcp"
args = []
```

Refer to [armaraos/docs/](armaraos/docs/) for detailed documentation.

---


## Production monitoring

OpenClaw-scheduled **bridge wrappers** report token usage, enforce budget awareness, and write operator-facing markdown under **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** (override with `OPENCLAW_MEMORY_DIR` / `OPENCLAW_DAILY_MEMORY_DIR`).

| Piece | What it does |
|-------|----------------|
| **`token-budget-alert`** | Daily (`0 23 * * *` UTC): `## Token Usage Report` append, monitor-cache **stat** / optional **prune** when cache is large, **one consolidated** notify (`Daily AINL Status - … UTC`) when lines are queued (Telegram/OpenClaw queue). |
| **Sentinel duplicate guard** | Live runs use `token_report_today_sent` / `token_report_today_touch` (default file `/tmp/token_report_today_sent`; override **`AINL_TOKEN_REPORT_SENTINEL`**) so the **main** report is not appended twice the same UTC day. **`--dry-run`** skips sentinel and main append. |
| **`weekly-token-trends`** | Weekly Sunday 09:00 UTC (`0 9 * * 0`): scans recent daily `*.md` files, parses `## Token Usage Report`, appends **`## Weekly Token Trends`**. |
| **Docs & ops** | Operator hub: **[`docs/operations/UNIFIED_MONITORING_GUIDE.md`](docs/operations/UNIFIED_MONITORING_GUIDE.md)** · Wrapper detail: **[`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md)** · Cron drift & registry: **[`docs/CRON_ORCHESTRATION.md`](docs/CRON_ORCHESTRATION.md)** |

**Quick validate (no writes):**

```bash
python3 openclaw/bridge/run_wrapper_ainl.py token-budget-alert --dry-run
python3 openclaw/bridge/run_wrapper_ainl.py weekly-token-trends --dry-run
```

Wrappers live under **`openclaw/bridge/wrappers/`** (`token_budget_alert.ainl`, `weekly_token_trends.ainl`); adapter logic in **`openclaw/bridge/bridge_token_budget_adapter.py`**.

---

## KEYWORDS
- AI-native programming language
- agent workflow language
- deterministic agent workflows
- graph-based agent orchestration
- LLM orchestration
- AI agent workflow engine
- workflow language for AI agents
- deterministic AI workflows
- production AI agents
- reliable AI agent workflows
- auditable AI workflows
- deterministic workflow engine for AI
- compile-once run-many AI workflows
- long-running AI agents
- stateful AI agents
- autonomous ops workflows
- LangChain alternative
- LangGraph alternative
- CrewAI alternative
- Temporal for AI agents
- sandboxed agent deployment

---

---

## ArmaraOS

> ArmaraOS is an independent open-source project and is not affiliated with any entities using similar names (e.g., Amaros AI or other).
> It is a customized fork and extension of OpenFang by RightNow-AI (https://github.com/RightNow-AI/openfang), licensed under Apache-2.0 OR MIT.
> It includes and integrates AINativeLang (https://github.com/sbhooley/ainativelang) for deterministic AI workflows.
> Modifications Copyright (c) 2026 sbhooley. Original OpenFang and AINativeLang works retain their respective licenses.

**ArmaraOS — The regenerative Agent OS.**

Powered by AINativeLang’s deterministic workflows.
Like a starfish, it adapts, regrows reliable processes, and thrives with multiple arms (tools, channels, memory, and autonomous Hands) — never breaking, always regenerating.

**Quickstart**
```bash
ainl init my-worker --target armaraos && ainl install armaraos
```

Downloads & full docs: https://ainativelang.com/ArmaraOS

