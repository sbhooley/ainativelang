# AINL Documentation

This is the primary navigation hub for the `docs/` tree.

AINL docs are organized by user intent and conceptual layer rather than by file creation history. Start here if you want the shortest path to the right section. Use [`DOCS_INDEX.md`](DOCS_INDEX.md) as the exhaustive reference map.

## Sections

- [`overview/`](overview/README.md) — what AINL is, who it is for, and top-level orientation
- [`fundamentals/`](fundamentals/README.md) — why AINL exists and the core conceptual problems it addresses
- [`getting_started/`](getting_started/README.md) — first steps, onboarding, and “start here” implementation paths
- [`architecture/`](architecture/README.md) — system design, canonical IR, and compiler/runtime structure
- [`runtime/`](runtime/README.md) — execution semantics, runtime behavior, and safety boundaries
- [`language/`](language/README.md) — language definition, grammar, and canonical scope
- [`adapters/`](adapters/README.md) — adapters, capabilities, and host integration surfaces
- [`emitters/`](emitters/README.md) — multi-target output surfaces and emitter philosophy
- [`examples/`](examples/README.md) — example support levels, walkthroughs, and example-oriented guidance
- [`case_studies/`](case_studies/README.md) — narrative proof, production lessons, and applied explanations
- [`competitive/`](competitive/README.md) — comparative framing and “AINL vs X” materials
- [`operations/`](operations/README.md) — autonomous ops, monitors, and deployment-style operational docs
- [`advanced/`](advanced/README.md) — operator-only, OpenClaw / ZeroClaw-adjacent ops, and advanced coordination surfaces
- [`reference/`](reference/README.md) — schemas, contracts, indexes, and reference-style maps

## Recommended paths

- New to the project: start with [`overview/`](overview/README.md), then [`getting_started/`](getting_started/README.md)
- Trying to understand the category: read [`fundamentals/`](fundamentals/README.md)
- Implementing or extending AINL: read [`language/`](language/README.md), [`architecture/`](architecture/README.md), and [`runtime/`](runtime/README.md)
- Working with integrations, **OpenClaw**, or **ZeroClaw**: read **[`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)** (**`ainl install-mcp --host …`**, one table for all stacks), then [`adapters/`](adapters/README.md) and [`advanced/`](advanced/README.md); **OpenClaw skill** onboarding is **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)** (**`~/.openclaw/openclaw.json`**); **ZeroClaw skill** onboarding is **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**. Generic external executors via HTTP bridge (multi-backend capable): [`integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](integrations/EXTERNAL_EXECUTOR_BRIDGE.md) — **MCP (`ainl-mcp`) first** for OpenClaw / NemoClaw / ZeroClaw.
- **MCP hosts hub:** [`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host openclaw|zeroclaw`** (aliases **`install-openclaw`** / **`install-zeroclaw`**).
- **OpenClaw skill:** [`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md) — ClawHub or manual copy, **`~/.openclaw/`** MCP + **`ainl-run`**; links **[`examples/ecosystem/`](../examples/ecosystem/)** and benchmarks (**viable subset**, **~1.02×** context).
- **ZeroClaw skill:** [`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md) — one-command skill install, **`~/.zeroclaw/`** MCP + **`ainl-run`** shim; links **[`examples/ecosystem/`](../examples/ecosystem/)** and benchmarks (**viable subset**, **~1.02×** context).
- Looking for proof and practical examples: read [`case_studies/`](case_studies/README.md) and [`operations/`](operations/README.md)
- **Performance & benchmarks:** reproducible **tiktoken cl100k_base** size tables in **[`BENCHMARK.md`](../BENCHMARK.md)**; narrative hub **[`benchmarks.md`](benchmarks.md)** (highlights, `make benchmark` / `make benchmark-ci`, runtime + LLM eval links)
- **Clawflows / Agency-Agents ecosystem & OpenClaw / ZeroClaw hooks:** **[`ECOSYSTEM_OPENCLAW.md`](ECOSYSTEM_OPENCLAW.md)** — `examples/ecosystem/` (weekly auto-sync), CLI, MCP, PR templates; **OpenClaw** path **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)** · **ZeroClaw** path **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**

## Operations & monitoring (OpenClaw bridge; see also ZeroClaw)

Production token/budget monitoring, daily memory appends, weekly trends, cron examples, and troubleshooting are documented in one place:

- **[`operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md)** — *Unified AINL + OpenClaw Monitoring Guide* (memory path **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, `token-budget-alert`, `weekly-token-trends`, sentinel guard, env vars). **OpenClaw** MCP + skill bootstrap: **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**. **ZeroClaw** does not use that memory layout; use **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)** for **`~/.zeroclaw/`** MCP + **`ainl install-mcp --host zeroclaw`**.

Supporting detail:

- [`openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md) — token budget wrapper reference
- [`openclaw/bridge/README.md`](../openclaw/bridge/README.md) — bridge runner, tools table, cron snippets
- [`CRON_ORCHESTRATION.md`](CRON_ORCHESTRATION.md) — drift checks and registry discipline
- [`ainl_openclaw_unified_integration.md`](ainl_openclaw_unified_integration.md) — integration boundaries and env vars

## Notes

- **What is AINL?** [`WHAT_IS_AINL.md`](WHAT_IS_AINL.md) (docs hub primer; includes v1.2 capabilities). Root copy: [`../WHAT_IS_AINL.md`](../WHAT_IS_AINL.md).
- **Graph diagrams (Mermaid/images):** root `README.md` → *Visualize your workflow*; details in [`architecture/GRAPH_INTROSPECTION.md`](architecture/GRAPH_INTROSPECTION.md) §7 (`ainl visualize`, `ainl-visualize`, `--png`, `--svg`).
- **Starter include demos:** `examples/timeout_demo.ainl` (minimal timeout include) and `examples/timeout_memory_prune_demo.ainl` (timeout + memory put/list/prune, used for PNG export docs).
- **Shared `modules/common/` helpers:** index and include-before-`S` rule in [`../modules/common/README.md`](../modules/common/README.md); optional access-aware memory touches in [`../modules/common/access_aware_memory.ainl`](../modules/common/access_aware_memory.ainl) (`LACCESS_READ` / `LACCESS_WRITE` / `LACCESS_LIST` / graph-safe `LACCESS_LIST_SAFE`).
- **Full conformance matrix:** run `make conformance` from repo root (or `SNAPSHOT_UPDATE=1 make conformance` when intentionally updating snapshots). Outputs are written to `tests/snapshots/conformance/`.
- **Benchmarks (size, runtime, economics, CI regression):** [`benchmarks.md`](benchmarks.md) — links [`BENCHMARK.md`](../BENCHMARK.md), `make benchmark` / `make benchmark-ci`, and LLM bench + optional Claude cloud comparison.
- `DOCS_INDEX.md` remains in place as the detailed reference map.
- Existing paths will be migrated gradually to avoid breaking relative links and old deep links.
- `case_studies/` is the canonical case-study folder name going forward.
