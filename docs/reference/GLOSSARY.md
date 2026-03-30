# AI Native Lang (AINL) Glossary

> **OpenClaw (MCP skill):** **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** — **`skills/openclaw/`**, **`ainl install-openclaw`**, **`~/.openclaw/openclaw.json`** (`mcp.servers.ainl`), stdio **`ainl-mcp`**. (Distinct from **OpenClaw bridge** cron/memory under **`openclaw/bridge/`**.)
>
> **ZeroClaw:** Host integration via **ZeroClaw skill**, **`ainl install-zeroclaw`**, and **`ainl-mcp`** — see **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)** (distinct from **OpenClaw** bridge/cron docs).

## AINL
AI Native Lang. A language designed for AI-first authoring and execution workflows.

## Canonical AINL
The strict, line-oriented AINL form used for validation, training targets, and evaluation.

## IR (Intermediate Representation)
The compiler output graph/step structure used by runtimes and emitters.

## Graph-First Runtime
Execution mode that prioritizes graph semantics and uses step fallback only when needed.

## Adapter
A runtime integration surface for external capabilities (HTTP, DB, files, tools, etc.).

## LoRA
Low-Rank Adaptation fine-tuning strategy used to adapt base models efficiently.

## Strict AINL Rate
Share of prompts where output is non-empty, AINL-like, and passes strict compile checks.

## Runtime Compile Rate
Share of outputs that pass runtime (non-strict) compile validation.

## Nonempty Rate
Share of prompts producing non-empty output.

## Constraint Diagnostics
Telemetry emitted during constrained decoding (allowed/rejected tokens, fallback, EOS gating).

## Failure Family
A normalized category of generation failure (timeout, shape mismatch, compile failure, etc.).

## Prompt-Length Bucket
Grouping prompts by rendered token length to improve shape stability and analysis granularity.

## Checkpoint Sweep
Evaluating checkpoints and ranking them by task metrics instead of raw eval loss.

## Trend Gate
Cross-run quality gate enforcing minimum rates and maximum allowed regressions.

## Run Health Report
Machine-readable pass/fail summary artifact for automation:
`corpus/curated/alignment_run_health.json`.

## Distill Mix
Training-data composition strategy mixing gold examples and repair/check-rewrite supervision.

## Failure Boost Dataset
Targeted dataset generated from failing prompt IDs to improve weak families.

## OpenClaw
An extension and operator-focused surface area built on top of canonical AINL, used for advanced adapters, orchestration, and multi-agent workflows. **MCP skill + bootstrap:** **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** (**`skills/openclaw/`**, **`ainl install-openclaw`**, **`~/.openclaw/openclaw.json`**, **`~/.openclaw/bin/ainl-run`**). **Bridge / cron / daily markdown memory:** **`openclaw/bridge/`** and **[`../operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md)**.

## ZeroClaw
A separate MCP-first onboarding path for AINL: **ZeroClaw skill** in-repo, **`ainl install-zeroclaw`** (`~/.zeroclaw/mcp.json`, **`ainl-run`** shim), and stdio **`ainl-mcp`**. Documented in **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)**; does not replace OpenClaw **`openclaw/bridge/`** cron/memory layouts.

## Adapter Registry
The catalog of available runtime adapters, their identifiers, and supported capabilities as defined in `docs/reference/ADAPTER_REGISTRY.md`.

## Memory Adapter
An adapter responsible for durable memory operations (read, write, list, delete) over structured memory records, specified in `docs/adapters/MEMORY_CONTRACT.md`.

## Memory Record
A structured, schema-validated unit of persisted memory (with fields such as id, kind, timestamps, and content) managed by the memory adapter.

## Conformance Profile
A named set of behavioral and surface-area expectations (e.g., `AINL_V0_9_PROFILE`) that a runtime, compiler, or adapter must meet to be considered compatible.

## Language Lanes and Extensions
The division between canonical AINL and additional extension lanes (including OpenClaw-focused extensions) described in `docs/AINL_CANONICAL_CORE.md` and `docs/language/AINL_EXTENSIONS.md`.

## Runtime Specification
The formal description of how compiled IR and language constructs must behave at runtime, complementing the human-readable semantics; see `docs/ainl_runtime_spec.md` and `SEMANTICS.md`.

## Targets Roadmap
The forward-looking map of officially supported runtimes, adapters, and deployment targets, documented in `docs/runtime/TARGETS_ROADMAP.md`.

## State Discipline
The AINL approach to managing workflow state through explicit, tiered adapters (frame, cache, memory/SQLite/FS, coordination) rather than hiding state in prompt history. Described in `docs/architecture/STATE_DISCIPLINE.md`.

## State Tier
One of four levels of state durability in AINL: Tier 1 (frame, ephemeral), Tier 2 (cache, short-lived), Tier 3 (memory/SQLite/FS, persistent), Tier 4 (queue/agent, cross-workflow coordination).

## Policy Validator
A pre-execution gate (`tooling/policy_validator.py`) that checks compiled IR against a declarative policy (forbidden adapters, effects, effect tiers) and returns structured violations. Can be invoked directly or via the optional `policy` parameter on the runner service `/run` endpoint.

## Capability Discovery
The `GET /capabilities` endpoint on the runner service, which returns available adapters, their verbs, support tiers, default effects, and the runtime version. Used by external orchestrators to inspect what an AINL runtime instance supports before submitting workflows.

## Runner Service
The FastAPI-based execution service (`scripts/runtime_runner_service.py`) exposing `/run`, `/enqueue`, `/result/{id}`, `/capabilities`, `/health`, `/ready`, and `/metrics` endpoints for runtime-facing workflow execution.
