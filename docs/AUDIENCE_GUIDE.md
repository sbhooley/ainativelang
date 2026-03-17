# Audience Guide

This guide helps different contributor types find the best entry point quickly.

Timeline anchor: Foundational AI research and cross-platform experimentation by
the human founder began in **2024**. After partial loss of early artifacts, AINL
workstreams were rebuilt, retested, and formalized in overlapping phases through
**2025-2026**.

## For GitHub Developers

- Start with: `README.md`
- Then read:
  - `docs/architecture/ARCHITECTURE_OVERVIEW.md`
  - `CONTRIBUTING.md`
  - `docs/DOCS_INDEX.md`
- Run baseline checks:
  - `.venv/bin/python scripts/run_test_profiles.py --profile core`

## For Public Readers and First-Time Evaluators

- Start with:
  - `README.md`
  - `docs/DOCS_INDEX.md`
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
  - `docs/RELEASE_READINESS.md`
- If you want the shortest honest picture of the project:
  - treat the compiler/runtime/graph tooling as the core,
  - treat target breadth as uneven in maturity,
  - use `tooling/artifact_profiles.json` to distinguish strict-valid examples from compatibility artifacts.

## For Researchers and Analysts

- Start with:
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
  - `docs/AINL_SPEC.md`
  - `docs/CONFORMANCE.md`
  - `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
- Key artifacts:
  - `corpus/curated/model_eval_report_v5_aligned.json`
  - `corpus/curated/model_eval_trends.json`
  - `corpus/curated/alignment_run_health.json`
- Citation metadata:
  - `CITATION.cff`

## For Data Scientists / ML Engineers

- Start with:
  - `docs/FINETUNE_GUIDE.md`
  - `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
  - `scripts/finetune_ainl.py`
  - `scripts/eval_finetuned_model.py`
- Model-quality focus metrics:
  - `strict_ainl_rate`
  - `runtime_compile_rate`
  - `nonempty_rate`

## For AI Agents (Any Size)

- Start with:
  - `docs/BOT_ONBOARDING.md` (entrypoint; before implementation, complete `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`; see `tooling/bot_bootstrap.json`)
  - `docs/DOCS_INDEX.md`
  - `docs/AI_AGENT_CONTINUITY.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
  - `docs/reference/GLOSSARY.md`
- Minimum handoff payload:
  - files changed
  - behavior deltas
  - verification status
  - next command

## For Product and Program Stakeholders

- Start with:
  - `docs/RELEASE_READINESS.md`
  - `docs/TARGETS_ROADMAP.md`
  - `docs/GITHUB_RELEASE_CHECKLIST.md`
- Track latest status from:
  - `corpus/curated/alignment_run_health.json`

## Fastest Shared Entry Path

If unsure, use this sequence:

1. `README.md`
2. `docs/DOCS_INDEX.md`
3. `docs/architecture/ARCHITECTURE_OVERVIEW.md`
4. `CONTRIBUTING.md`
