# AI Native Lang (AINL) Documentation Index (Human + Agent)

This file is the quickest way to orient a new contributor (human or AI agent).
Use it as the top-level entry point before touching code.

## Start Here

### Core / safe-default docs

- Project origin and attribution: `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
- Machine-readable project provenance: `tooling/project_provenance.json`
- Provenance and release evidence playbook: `docs/PROVENANCE_AND_RELEASE_EVIDENCE.md`
- Human initiator: Steven Hooley
- Public initiator references: <https://x.com/sbhooley>, <https://stevenhooley.com>, <https://linkedin.com/in/sbhooley>
- Project timeline + release milestones (2024 foundations; 2025-2026 formalization): `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`, `docs/CHANGELOG.md`
- **Consultant reports index**: `CONSULTANT_REPORTS.md` (see also `AI_CONSULTANT_REPORT_APOLLO.md`)
- Contributor entrypoint: `CONTRIBUTING.md`
- Audience quickstart: `docs/AUDIENCE_GUIDE.md`
- Install and environment setup: `docs/INSTALL.md`
- GitHub release checklist: `docs/GITHUB_RELEASE_CHECKLIST.md`
- Open core charter: `docs/OPEN_CORE_CHARTER.md`
- Open/commercial boundary map: `docs/OPEN_CORE_BOUNDARY_MAP.md`
- Licensing/repo layout plan: `docs/LICENSING_AND_REPO_LAYOUT_PLAN.md`
- Language specification: `docs/AINL_SPEC.md`
- Canonical public language lane: `docs/AINL_CANONICAL_CORE.md`
- Core language and module structure: `docs/AINL_CORE_AND_MODULES.md`
- Extension lanes and OpenClaw-specific surfaces: `docs/AINL_EXTENSIONS.md`
- Canonical profile snapshot (v0.9): `docs/AINL_V0_9_PROFILE.md`
- Runtime behavior specification (complement to `SEMANTICS.md`): `docs/ainl_runtime_spec.md`
- Target/runtime support roadmap: `docs/TARGETS_ROADMAP.md`
- Example support classification: `docs/EXAMPLE_SUPPORT_MATRIX.md`
- Graph/IR introspection guide: `docs/GRAPH_INTROSPECTION.md`
- Runtime semantics contract: `SEMANTICS.md`
- Runtime/compiler execution contract: `docs/RUNTIME_COMPILER_CONTRACT.md`
- Autonomous ops playbook: `docs/AUTONOMOUS_OPS_PLAYBOOK.md`
- Safe optimization policy (language vs compiler optimization guardrails): `docs/SAFE_OPTIMIZATION_POLICY.md`
- Machine-readable support levels: `tooling/support_matrix.json`
- Runtime compatibility shim (`ExecutionEngine` facade): `runtime/compat.py`, `runtime.py`
- Documentation maintenance contract: `docs/DOCS_MAINTENANCE.md`
- Grammar quick reference: `docs/grammar.md`
- Pattern cookbook and composition examples: `docs/PATTERNS.md`
- Compiler/IR contracts: `docs/IR_SCHEMA.md`, `docs/GRAPH_SCHEMA.md`
- Conformance status: `docs/CONFORMANCE.md`
- Release readiness checklist: `docs/RELEASE_READINESS.md`
- No-break migration tracker: `docs/NO_BREAK_MIGRATION_PLAN.md`
- Release notes draft (GitHub-ready body): `docs/RELEASE_NOTES_DRAFT.md`
- Post-release immediate roadmap: `docs/POST_RELEASE_ROADMAP.md`
- Maintainer release operations: `docs/RELEASING.md`
- Reproducible size benchmark report: `BENCHMARK.md`
- Benchmark generator script: `scripts/benchmark_size.py`
- Machine-readable benchmark output: `tooling/benchmark_size.json`
- Compile-once / run-many proof pack: `docs/COMPILE_ONCE_RUN_MANY.md`
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
- Architecture overview: `docs/ARCHITECTURE_OVERVIEW.md`
- Glossary: `docs/GLOSSARY.md`

### Advanced / operator-only / experimental docs

These docs describe **advanced, extension/OpenClaw, and coordination** features.
They are intended for operators and advanced users, not as the safe-default
entry point for new users or unsupervised agents.

- OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- Agent coordination contract (multi-agent envelopes/spec): `docs/AGENT_COORDINATION_CONTRACT.md`
- Safe use and threat model: `docs/SAFE_USE_AND_THREAT_MODEL.md`
- Adapter inventory and conventions (including extension/OpenClaw adapters): `docs/ADAPTER_REGISTRY.md`, `docs/OPENCLAW_ADAPTERS.md`
- Memory contract and v1 adapter: `docs/MEMORY_CONTRACT.md`
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
- Tool API contract for loop orchestration: `docs/TOOL_API.md`
- Adapter inventory and conventions: `docs/ADAPTER_REGISTRY.md`, `docs/OPENCLAW_ADAPTERS.md`

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
