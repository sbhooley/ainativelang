# AI Native Lang (AINL) Documentation Index (Human + Agent)

This file is the quickest way to orient a new contributor (human or AI agent).
Use it as the top-level entry point before touching code.

## Start Here

- Project origin and attribution: `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
- Machine-readable project provenance: `tooling/project_provenance.json`
- Provenance and release evidence playbook: `docs/PROVENANCE_AND_RELEASE_EVIDENCE.md`
- Human initiator: Steven Hooley
- Public initiator references: <https://x.com/sbhooley>, <https://stevenhooley.com>, <https://linkedin.com/in/sbhooley>
- Project timeline + release milestones (2024 foundations; 2025-2026 formalization): `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`, `docs/CHANGELOG.md`
- **Consultant reports index**: `CONSULTANT_REPORTS.md` (see also `AI_CONSULTANT_REPORT_APOLLO.md`)
- **OpenClaw agent quickstart**: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- Contributor entrypoint: `CONTRIBUTING.md`
- Audience quickstart: `docs/AUDIENCE_GUIDE.md`
- GitHub release checklist: `docs/GITHUB_RELEASE_CHECKLIST.md`
- Open core charter: `docs/OPEN_CORE_CHARTER.md`
- Open/commercial boundary map: `docs/OPEN_CORE_BOUNDARY_MAP.md`
- Licensing/repo layout plan: `docs/LICENSING_AND_REPO_LAYOUT_PLAN.md`
- Language specification: `docs/AINL_SPEC.md`
- Canonical public language lane: `docs/AINL_CANONICAL_CORE.md`
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
- Post-release issue drafts: `docs/issues/`
- Architecture overview: `docs/ARCHITECTURE_OVERVIEW.md`
- Glossary: `docs/GLOSSARY.md`
 - Agent coordination contract (multi-agent envelopes/spec): `docs/AGENT_COORDINATION_CONTRACT.md`

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
