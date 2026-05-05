# AI Agent Continuity Guide

This project is intentionally designed for multi-session, multi-agent development.
Use this guide to continue work safely and efficiently across handoffs.

## Primary Goal

Preserve correctness of AINL language/runtime behavior while improving model quality
on strict canonical AINL generation.

## First-Read Checklist (Every New Session)

1. **If you will do implementation work:** Read `docs/BOT_ONBOARDING.md` and complete the steps in `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` before coding (see `tooling/bot_bootstrap.json`).
2. Read `README.md` and `docs/DOCS_INDEX.md`.
3. Read `docs/AINL_SPEC.md` and `SEMANTICS.md`.
4. Read `docs/RUNTIME_COMPILER_CONTRACT.md` (compiler/runtime + grammar ownership contract).
5. Read `docs/TRAINING_ALIGNMENT_RUNBOOK.md` before touching train/eval scripts.
6. Read `docs/DOCS_MAINTENANCE.md` before broad documentation edits.
7. Read latest reports:
   - `corpus/curated/alignment_run_health.json`
   - `corpus/curated/model_eval_trends.json`
8. Inspect current generation quality report:
   - `corpus/curated/model_eval_report_v5_aligned.json` (or latest variant)
9. **If planning an integration or major change**, review consultant reports:
   - `AI_CONSULTANT_REPORT_APOLLO.md` — OpenClaw `ocl` adapter integration strategy
   - `docs/ZEROCLAW_INTEGRATION.md` — ZeroClaw skill + MCP bootstrap (parallel integration path)
10. **Operator / field narratives** (what shipped in live stacks): `agent_reports/README.md` — indexed OpenClaw agent field reports (e.g. Day 2 AINL King, 2026-03-19).
11. **Intelligence monitors** (memory / bootstrap / summarizer AINL): `docs/INTELLIGENCE_PROGRAMS.md` and `scripts/run_intelligence.py`.

## Ground Rules for Safe Progress

- Do not weaken strict AINL validation just to improve score.
- Do not patch runtime to hide compiler-analysis gaps; fix compiler-owned contract logic.
- Prefer additive changes (new flags/diagnostics) over breaking behavior.
- Keep constrained decoding deterministic for eval comparability.
- Preserve machine-readable artifacts in `corpus/curated/`.
- If adding optimization knobs, wire them through:
  - script CLI
  - cycle script
  - output diagnostics
  - docs

## Pipeline Components and Ownership

- `scripts/finetune_ainl.py`: model training.
- `scripts/sweep_checkpoints.py`: objective-aligned checkpoint selection.
- `scripts/eval_finetuned_model.py`: constrained generation + compile/repair + diagnostics.
- `scripts/analyze_eval_trends.py`: cross-run trend and regression gate logic.
- `scripts/run_alignment_cycle.sh`: orchestrates all above and emits final run-health verdict.

## Canonical Quality Metrics

Use these as top-line quality signals:

- `strict_ainl_rate`
- `runtime_compile_rate`
- `nonempty_rate`

Treat `eval_loss` as secondary for model selection in this project.

## Runtime/Compiler Contract Reminder

- Canonical runtime semantics live in `runtime/engine.py` (`RuntimeEngine`).
- `ExecutionEngine` is compatibility-only (`runtime/compat.py`, re-exported via `runtime.py` / `runtime/__init__.py`).
- Runtime normalization/shape helpers are compiler-owned (`compiler_v2.py` runtime helper functions).
- In strict mode, bare identifier-like tokens in read positions are treated as vars; quote string literals explicitly.

## Required Diagnostics to Keep

- Constraint diagnostics (`fallback_used_steps`, `eos_blocked`, strict rejects)
- Failure-family counters
- Timing breakdown (prepare, generate, compile, repair, total)
- Length-bucket breakdown for quality and speed
- Quantization diagnostics when enabled

## Fast Triage Procedure

When quality drops:

1. Check `alignment_run_health.json` status and gate failures.
2. Check `model_eval_trends.json` deltas and worst bucket.
3. Check failure families in final eval report.
4. Inspect constraint alerts for over-pruning symptoms.
5. Decide between:
   - data boost (target failing families)
   - constraint tuning
   - decoding/token budget adjustments

## Handoff Template

When ending a session, leave a concise note with:

- What changed (files + behavior)
- What was validated (commands + pass/fail)
- Current bottleneck
- Recommended next command

This keeps both humans and smaller agents effective with minimal context loss.
