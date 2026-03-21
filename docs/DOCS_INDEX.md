# AI Native Lang (AINL) Documentation Index (Human + Agent)

This file is the detailed reference map for the documentation set.
Use [`docs/README.md`](README.md) as the primary navigation hub, then use this file when you want the exhaustive inventory.

## Start Here

### Primary navigation

- **Primary docs hub:** `docs/README.md` — section-by-section navigation organized by user intent and conceptual layer.
- **Reference map:** `docs/DOCS_INDEX.md` — this file; use it when you need the full inventory.

### Bot onboarding and implementation preflight

- **Bot onboarding:** `docs/BOT_ONBOARDING.md` — where to start, which docs matter first, and that the implementation preflight is required before coding.
- **Implementation preflight:** `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` — required steps and output structure before selecting or implementing work (reduces duplicate work, stale assumptions, and adapter misuse).
- **Machine-readable bootstrap:** `tooling/bot_bootstrap.json` — pointers to onboarding doc, preflight doc, safe-default docs, advanced docs, and required steps.

### Core / safe-default docs

- Project origin and attribution: `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
- Machine-readable project provenance: `tooling/project_provenance.json`
- Provenance and release evidence playbook: `docs/PROVENANCE_AND_RELEASE_EVIDENCE.md`
- Human initiator: Steven Hooley
- Public initiator references: <https://x.com/sbhooley>, <https://stevenhooley.com>, <https://linkedin.com/in/sbhooley>
- Project timeline + release milestones (2024 foundations; 2025-2026 formalization): `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`, `docs/CHANGELOG.md`
- **Consultant reports index**: `CONSULTANT_REPORTS.md` (see also `AI_CONSULTANT_REPORT_APOLLO.md`)
- **Agent field reports (OpenClaw / ops narratives)**: `agent_reports/README.md` (e.g. `ainl-king-openclaw-2026-03-19.md`)
- **Intelligence AINL programs** (`memory`, context injection, summarizer): `docs/INTELLIGENCE_PROGRAMS.md`
- Contributor entrypoint: `CONTRIBUTING.md`
- Audience quickstart: `docs/AUDIENCE_GUIDE.md`
- What is AINL (short primer + v1.2 snapshot): `docs/WHAT_IS_AINL.md` (and `WHAT_IS_AINL.md` at repo root)
- Install and environment setup: `docs/INSTALL.md` (includes `ainl-validate` strict / `--json-diagnostics` / optional **rich**)
- Compiler structured diagnostics module: `compiler_diagnostics.py` (used by `compiler_v2.py`, `langserver.py`, `scripts/validate_ainl.py`; tests in `tests/test_diagnostics.py`)
- GitHub release checklist: `docs/GITHUB_RELEASE_CHECKLIST.md`
- Open core charter: `docs/OPEN_CORE_CHARTER.md`
- Open/commercial boundary map: `docs/OPEN_CORE_BOUNDARY_MAP.md`
- Licensing/repo layout plan: `docs/LICENSING_AND_REPO_LAYOUT_PLAN.md`
- Language specification: `docs/AINL_SPEC.md`
- Canonical public language lane: `docs/AINL_CANONICAL_CORE.md`
- Core language and module structure: `docs/language/AINL_CORE_AND_MODULES.md`
- Extension lanes and OpenClaw-specific surfaces: `docs/language/AINL_EXTENSIONS.md`
- Canonical profile snapshot (v0.9): `docs/reference/AINL_V0_9_PROFILE.md`
- Runtime behavior specification (complement to `SEMANTICS.md`): `docs/ainl_runtime_spec.md`
- Target/runtime support roadmap: `docs/runtime/TARGETS_ROADMAP.md`
- Example support classification: `docs/EXAMPLE_SUPPORT_MATRIX.md`
- Timeout include demo examples: `examples/timeout_demo.ainl`, `examples/timeout_memory_prune_demo.ainl`
- Graph/IR introspection guide: `docs/architecture/GRAPH_INTROSPECTION.md` (includes **Mermaid** CLI: `ainl visualize` / `ainl-visualize`, `scripts/visualize_ainl.py`; image export `--png/--svg` with Playwright; and DOT via `scripts/render_graph.py`)
- State discipline (tiered state model): `docs/architecture/STATE_DISCIPLINE.md`
- Runtime semantics contract: `SEMANTICS.md`
- Runtime/compiler execution contract: `docs/RUNTIME_COMPILER_CONTRACT.md`
- Autonomous ops playbook: `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md`
- Sandbox execution profiles: `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- Capability grant model: `docs/operations/CAPABILITY_GRANT_MODEL.md`
- Structured audit logging: `docs/operations/AUDIT_LOGGING.md`
- Runtime container guide: `docs/operations/RUNTIME_CONTAINER_GUIDE.md`
- External orchestration guide: `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` — includes MCP agent role templates, desktop-safe recipe, end-to-end validator/inspector/runner example, and Claude Code / Cowork / Dispatch guidance
- **MCP host hub (OpenClaw, ZeroClaw, future):** `docs/HOST_MCP_INTEGRATIONS.md` — **`ainl install-mcp --host …`**, skill + CLI pattern, maintainer notes (`tooling/mcp_host_install.py`)
- **AINL → external workers (HTTP bridge contract):** `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` — generic `http.Post` envelope for non-MCP executors; **OpenClaw / NemoClaw / ZeroClaw should prefer `ainl-mcp` first** (see doc); **OpenClaw skill:** `docs/OPENCLAW_INTEGRATION.md` · **ZeroClaw skill:** `docs/ZEROCLAW_INTEGRATION.md`
- Batch repo-automation guide: `docs/operations/BATCH_AUTOMATION_GUIDE.md` — inspect-first, worktree-safe, deterministic, auditable batch flows for Dispatch-style environments
- Integration story (AINL in agent stacks): `docs/INTEGRATION_STORY.md`
- **OpenClaw skill + bootstrap (`ainl install-mcp --host openclaw`, `~/.openclaw/openclaw.json`, `examples/ecosystem/`):** `docs/OPENCLAW_INTEGRATION.md`
- **ZeroClaw skill + bootstrap (`ainl install-mcp --host zeroclaw`, `~/.zeroclaw/mcp.json`, `examples/ecosystem/`):** `docs/ZEROCLAW_INTEGRATION.md`
- Case studies: `docs/case_studies/` — graph-native vs prompt-loop agents, runtime cost advantage, long-context memory
- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md` · **OpenClaw skill + MCP:** `docs/OPENCLAW_INTEGRATION.md`
- Workflow patterns: `docs/PATTERNS.md`
- Safe optimization policy (language vs compiler optimization guardrails): `docs/runtime/SAFE_OPTIMIZATION_POLICY.md`
- Machine-readable support levels: `tooling/support_matrix.json`
- Runtime compatibility shim (`ExecutionEngine` facade): `runtime/compat.py`, `runtime.py`
- Documentation maintenance contract: `docs/DOCS_MAINTENANCE.md`
- Grammar quick reference: `docs/language/grammar.md`
- Pattern cookbook and composition examples: `docs/PATTERNS.md`
- Compiler/IR contracts: `docs/reference/IR_SCHEMA.md`, `docs/reference/GRAPH_SCHEMA.md`
- Conformance status: `docs/CONFORMANCE.md`
- Full conformance command: `make conformance` (snapshot update: `SNAPSHOT_UPDATE=1 make conformance`; artifacts under `tests/snapshots/conformance/`). Matrix includes memory continuity runtime snapshot coverage (`memory_continuity_runtime`) and tokenizer coverage for `demo/session_budget_enforcer.lang`.
- Release readiness checklist: `docs/RELEASE_READINESS.md`
- No-break migration tracker: `docs/NO_BREAK_MIGRATION_PLAN.md`
- Release notes: `docs/RELEASE_NOTES.md`
- Post-release immediate roadmap: `docs/POST_RELEASE_ROADMAP.md`
- Maintainer release operations: `docs/RELEASING.md`
- Reproducible size benchmark report (tiktoken **cl100k_base**, viable vs legacy-inclusive transparency): `BENCHMARK.md`
- Benchmark hub (highlights Mar 2026, metrics glossary, `make benchmark` / `make benchmark-ci`, CI gate, LLM/cloud bench): `docs/benchmarks.md`
- Ecosystem examples (Clawflows / Agency-Agents, weekly auto-sync, OpenClaw / ZeroClaw hooks, MCP pointers): `docs/ECOSYSTEM_OPENCLAW.md` · **OpenClaw:** `docs/OPENCLAW_INTEGRATION.md` · **ZeroClaw:** `docs/ZEROCLAW_INTEGRATION.md`
- Benchmark generator script: `scripts/benchmark_size.py`
- Machine-readable benchmark output: `tooling/benchmark_size.json`
- Runtime benchmark script: `scripts/benchmark_runtime.py`
- Shared bench metrics (tiktoken, pricing helpers): `tooling/bench_metrics.py`
- Benchmark JSON regression checker: `scripts/compare_benchmark_json.py`
- Tracked runtime benchmark JSON (CI regression baseline): `tooling/benchmark_runtime_results.json`
- Compile-once / run-many proof pack: `docs/architecture/COMPILE_ONCE_RUN_MANY.md`
  - Includes `scripts/summarize_runs.py` for aggregating `RuntimeEngine.run(..., trace=True)` JSON payloads into small health summaries.
- Launch copy pack: `docs/launch/SHORT_POST.md`, `docs/launch/TECHNICAL_POST.md`
- Maintainer publish checklist snapshot: `docs/launch/PUBLISH_CHECKLIST.md`
- Post-release issue drafts and migration templates:
  - `docs/issues/README.md`
  - `docs/issues/ISSUE_CREATION_PLAN.md`
  - `docs/issues/01-structured-diagnostics-first-class-contract.md`
  - `docs/issues/02-nonstrict-legacy-artifact-migration-plan.md`
  - `docs/issues/03-compatibility-path-retirement-plan.md`
  - `docs/issues/04-strict-adapter-contract-expansion-policy.md`
  - `docs/issues/05-post-release-docs-onboarding-tightening.md`
- Architecture overview: `docs/architecture/ARCHITECTURE_OVERVIEW.md`
- Glossary: `docs/reference/GLOSSARY.md`

### Advanced / operator-only / experimental docs

These docs describe **advanced, extension/OpenClaw, and coordination** features.
They are intended for operators and advanced users, not as the safe-default
entry point for new users or unsupervised agents.

- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md` · **OpenClaw skill + MCP:** `docs/OPENCLAW_INTEGRATION.md`
- Agent coordination contract (multi-agent envelopes/spec): `docs/advanced/AGENT_COORDINATION_CONTRACT.md`
- Safe use and threat model: `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`
- Adapter inventory and conventions (including extension/OpenClaw adapters): `docs/reference/ADAPTER_REGISTRY.md`, `docs/adapters/OPENCLAW_ADAPTERS.md`
- Sandbox execution profiles: `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- Capability grant model (host handshake): `docs/operations/CAPABILITY_GRANT_MODEL.md`
- Structured audit logging: `docs/operations/AUDIT_LOGGING.md`
- Runtime container guide: `docs/operations/RUNTIME_CONTAINER_GUIDE.md`
- External orchestration guide: `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- **HTTP bridge for generic external executors** (secondary to MCP for OpenClaw / NemoClaw / ZeroClaw): `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`
- MCP server (workflow-level integration for MCP-compatible hosts): `scripts/ainl_mcp_server.py`
- MCP exposure profiles (tool/resource scoping): `tooling/mcp_exposure_profiles.json`
- Autonomous ops monitors index: `docs/operations/AUTONOMOUS_OPS_MONITORS.md`
- **Unified AINL + OpenClaw bridge monitoring** (token budget alert, weekly trends, sentinel, daily memory path): `docs/operations/UNIFIED_MONITORING_GUIDE.md` — **OpenClaw** MCP + skill: `docs/OPENCLAW_INTEGRATION.md` · **ZeroClaw** uses `docs/ZEROCLAW_INTEGRATION.md` (`~/.zeroclaw/`, not `~/.openclaw/` memory)
- OpenClaw bridge runner reference: `openclaw/bridge/README.md`
- Token budget wrapper (bridge): `docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`
- AINL ↔ OpenClaw integration (wrappers, env): `docs/ainl_openclaw_unified_integration.md` — **OpenClaw skill + MCP:** `docs/OPENCLAW_INTEGRATION.md` · **ZeroClaw:** `docs/ZEROCLAW_INTEGRATION.md`
- Cron orchestration / drift: `docs/CRON_ORCHESTRATION.md`
- Standardized health envelope (monitor payloads): `docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md`
- Memory contract and v1 adapter: `docs/adapters/MEMORY_CONTRACT.md`
  - v1.1 additive RFC (deterministic metadata/filtering only): `docs/adapters/MEMORY_CONTRACT_V1_1_RFC.md`
  - Memory v1 bridge and CLI tools (JSON/JSONL): `tooling/memory_bridge.py`, `scripts/export_memory_records.py`, `scripts/import_memory_records.py`
  - One-way markdown daily-log export (human-facing): `tooling/memory_markdown_bridge.py`, `scripts/export_memory_daily_log_markdown.py`
  - Curated markdown import (long-term facts/preferences): `tooling/memory_markdown_import.py`, `scripts/import_memory_markdown.py`
  - Legacy markdown migration helper (MEMORY.md, memory/YYYY-MM-DD.md): `tooling/memory_migrate.py`, `scripts/migrate_memory_legacy.py`

## Training and Model Quality

- Fine-tuning quick guide: `docs/FINETUNE_GUIDE.md`
- Alignment cycle runbook (one-command train/sweep/gate): `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
- Canonical training/export packs (few-shot + eval bundles): `docs/CANONICAL_TRAINING_PACKS.md`
- Local model evaluation harness: `docs/OLLAMA_EVAL.md`
- Test profile map: `docs/TEST_PROFILES.md`

## AI-Agent Continuity and Handoff

- Agent handoff protocol and persistence checklist: `docs/AI_AGENT_CONTINUITY.md`
- AI agent contribution guide: `docs/CONTRIBUTING_AI_AGENTS.md`
- Docs update protocol: `docs/DOCS_MAINTENANCE.md`
- Tool API contract for loop orchestration: `docs/reference/TOOL_API.md`
- Adapter inventory and conventions: `docs/reference/ADAPTER_REGISTRY.md`, `docs/adapters/OPENCLAW_ADAPTERS.md`

## Core Implementation Map

- Main compiler: `compiler_v2.py`
- Runtime engine: `runtime/engine.py`
- Formal prefix grammar/state machine: `compiler_grammar.py`
- Decoder priors (non-authoritative): `grammar_priors.py`
- Token constraint compatibility/composition API: `grammar_constraint.py`
- Prefix/runtime conformance tests:
  - `tests/test_grammar_constraint_alignment.py`
  - `tests/test_runtime_compiler_conformance.py`
  - `tests/test_runtime_basic.py`
- Fine-tune entrypoint: `scripts/finetune_ainl.py`
- Evaluation gate: `scripts/eval_finetuned_model.py`
- Checkpoint sweep: `scripts/sweep_checkpoints.py`
- End-to-end cycle: `scripts/run_alignment_cycle.sh`

## Canonical Artifacts Produced by the Alignment Cycle

- Sweep report: `corpus/curated/checkpoint_sweep_report_v5_aligned.json`
- Final eval report: `corpus/curated/model_eval_report_v5_aligned.json`
- Trend report: `corpus/curated/model_eval_trends.json`
- Run health gate output: `corpus/curated/alignment_run_health.json`

## Repository Trust and Community Standards

- Code of conduct: `CODE_OF_CONDUCT.md`
- Security policy: `SECURITY.md`
- Citation metadata: `CITATION.cff`
- Core code license: `LICENSE`
- Docs/content license: `LICENSE.docs`
- Commercial terms overview: `COMMERCIAL.md`
- Commercial offers and sales (first deliverables): offer comparison `docs/OFFER_COMPARISON.md`; offer drafts `docs/OFFER_MANAGED_ALIGNMENT_PIPELINE.md`, `docs/OFFER_SUPPORTED_OPS_MONITOR_PACK.md`, `docs/OFFER_IMPLEMENTATION_REVIEW.md`; proposal template and filled examples `docs/PROPOSAL_TEMPLATE_COMMERCIAL_OFFERS.md`, `docs/EXAMPLE_PROPOSAL_*.md`; services page draft `docs/SERVICES_PAGE_DRAFT.md`; sales deck outline `docs/SALES_DECK_OUTLINE.md`; discovery checklist, intake form, mock workflow `docs/DISCOVERY_CALL_CHECKLIST.md`, `docs/DISCOVERY_INTAKE_FORM.md`, `docs/MOCK_DISCOVERY_WORKFLOW_EXAMPLE.md`.
- Trademark policy: `TRADEMARKS.md`
- Model/data terms: `MODEL_LICENSE.md`
- Notice file: `NOTICE`

## Contributor Path (Suggested)

1. Read `docs/AINL_SPEC.md` and `SEMANTICS.md`.
2. Read `docs/RUNTIME_COMPILER_CONTRACT.md` for canonical runtime ownership and strict literal policy.
3. Run quick checks from `docs/TEST_PROFILES.md`.
4. Make change.
5. Re-run eval gate with `scripts/eval_finetuned_model.py`.
6. Validate trend and run health outputs.
7. Update docs and `docs/CHANGELOG.md` for behavior changes.
