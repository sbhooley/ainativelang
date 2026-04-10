# AINL Documentation

This is the primary navigation hub for the `docs/` tree.

**Current `ainl` release:** **v1.5.0** — [`CHANGELOG.md`](CHANGELOG.md), [`RELEASE_NOTES.md`](RELEASE_NOTES.md) (PyPI / **`RUNTIME_VERSION`** / citation metadata).

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
- [`competitive/`](competitive/README.md) — comparative framing, LangGraph/Temporal onboarding, benchmark methodology vs other stacks
- [`operations/`](operations/README.md) — autonomous ops, monitors, and deployment-style operational docs
- [`advanced/`](advanced/README.md) — operator-only, OpenClaw / ZeroClaw / Hermes-adjacent ops, and advanced coordination surfaces
- [`reference/`](reference/README.md) — schemas, contracts, indexes, and reference-style maps

## Recommended paths

- New to the project: start with [`overview/`](overview/README.md), then [`getting_started/`](getting_started/README.md). **Strict vs non-strict compile:** [`getting_started/STRICT_AND_NON_STRICT.md`](getting_started/STRICT_AND_NON_STRICT.md) (strict is **opt-in**; default is permissive).
- Trying to understand the category: read [`fundamentals/`](fundamentals/README.md)
- Implementing or extending AINL: read [`language/`](language/README.md), [`architecture/`](architecture/README.md), and [`runtime/`](runtime/README.md)
- Working with integrations, **OpenClaw**, **ZeroClaw**, or **Hermes Agent**: read **[`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)** (**`ainl install-mcp --host …`**, one table for all stacks), then [`adapters/`](adapters/README.md) and [`advanced/`](advanced/README.md); **OpenClaw skill** onboarding is **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)** (**`~/.openclaw/openclaw.json`**); **ZeroClaw skill** onboarding is **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**; **Hermes** onboarding is **[`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md)** · hub **[`integrations/hermes-agent.md`](integrations/hermes-agent.md)** · upstream **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**. Generic external executors via HTTP bridge (multi-backend capable): [`integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](integrations/EXTERNAL_EXECUTOR_BRIDGE.md) — **MCP (`ainl-mcp`) first** for OpenClaw / NemoClaw / ZeroClaw / Hermes.
- **MCP hosts hub:** [`getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host openclaw|zeroclaw|hermes`** (aliases **`install-openclaw`** / **`install-zeroclaw`** / **`hermes-install`**).
- **OpenClaw skill:** [`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md) — ClawHub or manual copy, **`~/.openclaw/`** MCP + **`ainl-run`**; links **[`examples/ecosystem/`](../examples/ecosystem/)** and benchmarks (**viable subset**, **~1.02×** context).
- **ZeroClaw skill:** [`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md) — one-command skill install, **`~/.zeroclaw/`** MCP + **`ainl-run`** shim; links **[`examples/ecosystem/`](../examples/ecosystem/)** and benchmarks (**viable subset**, **~1.02×** context).
- **Hermes Agent:** [`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md) — **`~/.hermes/config.yaml`** MCP + **`--emit hermes-skill`**; skill pack [`skills/hermes/`](../skills/hermes/) · **`ainl compile --emit hermes-skill`**
- Looking for proof and practical examples: read [`case_studies/`](case_studies/README.md) and [`operations/`](operations/README.md)
- **Performance & benchmarks:** reproducible **tiktoken cl100k_base** size tables in **[`BENCHMARK.md`](../BENCHMARK.md)**; narrative hub **[`benchmarks.md`](benchmarks.md)** (highlights, `make benchmark` / `make benchmark-ci`, runtime + LLM eval links)
- **Energy pattern framing:** [`case_studies/DESIGNING_ENERGY_CONSUMPTION_PATTERNS.md`](case_studies/DESIGNING_ENERGY_CONSUMPTION_PATTERNS.md) — mapping AINL to explicit inference/compute budget design
- **Clawflows / Agency-Agents ecosystem & OpenClaw / ZeroClaw hooks:** **[`ECOSYSTEM_OPENCLAW.md`](ECOSYSTEM_OPENCLAW.md)** — `examples/ecosystem/` (weekly auto-sync), CLI, MCP, PR templates; **OpenClaw** path **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)** · **ZeroClaw** path **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)** · **Hermes** path **[`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md)** · **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**

## Operations & monitoring (OpenClaw bridge; see also ZeroClaw; Hermes uses [`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md))

**OpenClaw + AINL gold standard (install / upgrade):** [`operations/OPENCLAW_AINL_GOLD_STANDARD.md`](operations/OPENCLAW_AINL_GOLD_STANDARD.md) (**`tooling/bot_bootstrap.json`** → **`openclaw_ainl_gold_standard`**). **Host briefing — AINL v1.5.0 (current PyPI):** [`operations/OPENCLAW_HOST_AINL_1_2_8.md`](operations/OPENCLAW_HOST_AINL_1_2_8.md) (**`openclaw_host_ainl_1_2_8`**). **Token / usage observability (evidence-based savings, agent-friendly map):** [`operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](operations/TOKEN_AND_USAGE_OBSERVABILITY.md). **Named env profiles** (scale-out defaults): [`operations/AINL_PROFILES.md`](operations/AINL_PROFILES.md) · **workspace isolation:** [`operations/WORKSPACE_ISOLATION.md`](operations/WORKSPACE_ISOLATION.md) · **agent + AINL operating model:** [`operations/AGENT_AINL_OPERATING_MODEL.md`](operations/AGENT_AINL_OPERATING_MODEL.md).

Production token/budget monitoring, daily memory appends, weekly trends, cron examples, and troubleshooting are documented in one place:

- **[`operations/UNIFIED_MONITORING_GUIDE.md`](operations/UNIFIED_MONITORING_GUIDE.md)** — *Unified AINL + OpenClaw Monitoring Guide* (memory path **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, `token-budget-alert`, `weekly-token-trends`, sentinel guard, env vars). **OpenClaw** MCP + skill bootstrap: **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**. **ZeroClaw** does not use that memory layout; use **[`ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)** for **`~/.zeroclaw/`** MCP + **`ainl install-mcp --host zeroclaw`**. **Hermes** learning loop + Honcho memory: **[`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md)** · **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**.

Supporting detail:

- [`openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`](openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md) — token budget wrapper reference
- [`openclaw/bridge/README.md`](../openclaw/bridge/README.md) — bridge runner, tools table, cron snippets
- [`CRON_ORCHESTRATION.md`](CRON_ORCHESTRATION.md) — drift checks and registry discipline
- [`ainl_openclaw_unified_integration.md`](ainl_openclaw_unified_integration.md) — integration boundaries and env vars

## Notes

- **What is AINL?** **[`WHAT_IS_AINL.md`](WHAT_IS_AINL.md)** — canonical primer (narrative + v1.2+ capabilities). Repository root [`../WHAT_IS_AINL.md`](../WHAT_IS_AINL.md) is a short stub that points here.
- **Long-form architecture / economics:** **[`WHITEPAPERDRAFT.md`](../WHITEPAPERDRAFT.md)** (repo root) — through **v1.5.0** (native Solana + OpenClaw intelligence ops, token caps, Hermes Agent, ArmaraOS host pack, `ainl install openclaw`, `ainl status`).
- **Reactive production workflows:** [`reactive/REACTIVE_EVENTS.md`](reactive/REACTIVE_EVENTS.md) + durability scale guidance [`reactive/ADVANCED_DURABILITY.md`](reactive/ADVANCED_DURABILITY.md) + ready-to-adopt starters in [`../templates/production/`](../templates/production/).
- **Graph diagrams (Mermaid/images):** root `README.md` → *Visualize your workflow*; details in [`architecture/GRAPH_INTROSPECTION.md`](architecture/GRAPH_INTROSPECTION.md) §7 (`ainl visualize`, `ainl-visualize`, `--png`, `--svg`).
- **Starter include demos:** `examples/timeout_demo.ainl` (minimal timeout include) and `examples/timeout_memory_prune_demo.ainl` (timeout + memory put/list/prune, used for PNG export docs).
- **Trajectory logging (`ainl run`):** [`trajectory.md`](trajectory.md) — optional `<stem>.trajectory.jsonl` per step (`--log-trajectory` / `AINL_LOG_TRAJECTORY`); distinct from runner audit logs in [`operations/AUDIT_LOGGING.md`](operations/AUDIT_LOGGING.md).
- **Sandbox/AVM integration helpers:** use `ainl generate-sandbox-config <file.ainl> --target avm|firecracker|gvisor|k8s|general` (plus `ainl generate-avm-policy` for AVM-only fragments), and inspect IR `execution_requirements` for portable runtime hints.
- **Hyperspace emitter:** [`emitters/README.md`](emitters/README.md) — `scripts/validate_ainl.py --strict --emit hyperspace -o agent.py`; pairs with **`vector_memory`** / **`tool_registry`** adapters and root `README.md` happy-path (`examples/hyperspace_demo.ainl`).
- **Tiered code context (optional):** [`adapters/CODE_CONTEXT.md`](adapters/CODE_CONTEXT.md) — **`code_context`** (tiers + deps + impact + **`COMPRESS_CONTEXT`**), demo [`../examples/code_context_demo.ainl`](../examples/code_context_demo.ainl), **`--enable-adapter code_context`** on **`ainl run`** (not Hyperspace-default; MCP install does not enable it). Bootstrap: [`../tooling/bot_bootstrap.json`](../tooling/bot_bootstrap.json) → **`code_context_adapter_doc`**.
- **PTC-Lisp hybrids (opt-in):** [`adapters/PTC_RUNNER.md`](adapters/PTC_RUNNER.md) — full integration guide; hybrid examples:
  - [`../examples/hybrid_order_processor.ainl`](../examples/hybrid_order_processor.ainl) — parallel order batches, signatures, context firewall, trace export, LangGraph bridge
  - [`../examples/price_monitor.ainl`](../examples/price_monitor.ainl) — PTC price monitor with parallel/recovery patterns
  - Quick start: `ainl run-hybrid-ptc` (mock-friendly; see `ainl run-hybrid-ptc --help`)
- **Shared `modules/common/` helpers:** index and include-before-`S` rule in [`../modules/common/README.md`](../modules/common/README.md); optional access-aware memory touches in [`../modules/common/access_aware_memory.ainl`](../modules/common/access_aware_memory.ainl) (`LACCESS_READ` / `LACCESS_WRITE` / `LACCESS_LIST` / graph-safe `LACCESS_LIST_SAFE`). **Guard / session budget / reflect:** [`../modules/common/guard.ainl`](../modules/common/guard.ainl), [`../modules/common/session_budget.ainl`](../modules/common/session_budget.ainl), [`../modules/common/reflect.ainl`](../modules/common/reflect.ainl) (see module README). **HTTP executor-bridge request bodies:** shared include [`../modules/common/executor_bridge_request.ainl`](../modules/common/executor_bridge_request.ainl), JSON Schema [`../schemas/executor_bridge_request.schema.json`](../schemas/executor_bridge_request.schema.json), contract doc [`integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](integrations/EXTERNAL_EXECUTOR_BRIDGE.md) §3.
- **Reusable LLM includes:** [`../modules/llm/README.md`](../modules/llm/README.md) (e.g. JSON-array-only system line for chat completions).
- **App-local strict includes:** bridge JSON shells and deployment-specific graphs live next to your gateway (see [`language/AINL_CORE_AND_MODULES.md`](language/AINL_CORE_AND_MODULES.md) §8); they often compose [`../modules/common/executor_bridge_request.ainl`](../modules/common/executor_bridge_request.ainl).
- **Full conformance matrix:** run `make conformance` from repo root (or `SNAPSHOT_UPDATE=1 make conformance` when intentionally updating snapshots). Outputs are written to `tests/snapshots/conformance/`.
- **Benchmarks (size, runtime, economics, CI regression):** [`benchmarks.md`](benchmarks.md) — links [`BENCHMARK.md`](../BENCHMARK.md), `make benchmark` / `make benchmark-ci`, and LLM bench + optional Claude cloud comparison.
- `DOCS_INDEX.md` remains in place as the detailed reference map.
- Existing paths will be migrated gradually to avoid breaking relative links and old deep links.
- `case_studies/` is the canonical case-study folder name going forward.
