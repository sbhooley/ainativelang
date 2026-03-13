# Contributing (AI Agents)

This guide is for AI contributors operating as implementation agents, reviewers,
or research assistants.

## Contribution Goals

- Improve AINL correctness, reliability, and contributor velocity.
- Improve model generation quality on strict canonical AINL.
- Preserve reproducibility, observability, and compatibility.

## Required Reading Before Changes

1. `docs/BOT_ONBOARDING.md` — bot entrypoint; **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** is required before implementation work (inspect files, confirm not duplicate, verify semantics, emit preflight output).
2. `docs/DOCS_INDEX.md`
3. `docs/AINL_SPEC.md`
4. `SEMANTICS.md`
5. `docs/RUNTIME_COMPILER_CONTRACT.md`
6. `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
7. `docs/AI_AGENT_CONTINUITY.md`
8. `docs/DOCS_MAINTENANCE.md`

Machine-readable bootstrap (pointers to onboarding, preflight, safe vs advanced docs): `tooling/bot_bootstrap.json`.

## Working Protocol

1. **Understand current state**
   - Inspect latest artifacts in `corpus/curated/`:
     - `alignment_run_health.json`
     - `model_eval_trends.json`
     - latest `model_eval_report*.json`
2. **Make minimal, scoped changes**
   - Prefer adding flags/config over hard behavior changes.
3. **Verify**
   - run syntax/lint/tests relevant to changed files
   - run docs contract check when docs or semantics-critical code changes (`ainl-check-docs`)
   - verify pipeline scripts still expose intended CLI flags
4. **Document**
   - update docs + changelog whenever behavior or knobs change

## Preferred Change Pattern

- Add
- Extend
- Refactor
- Replace (last resort)

## Quality Bar for Training/Eval Changes

Any training/eval change should preserve or improve:

- `strict_ainl_rate`
- `runtime_compile_rate`
- `nonempty_rate`

and maintain usable diagnostics for triage.

## Do Not Do

- Do not silently relax strict validation just to raise pass rate.
- Do not move compiler contract issues into runtime workarounds.
- Do not remove machine-readable diagnostics/artifacts without replacement.
- Do not introduce hidden defaults that break reproducibility.

## Runtime/Compiler Ownership Rules

- Canonical executable semantics live in `runtime/engine.py` (`RuntimeEngine`).
- `ExecutionEngine` in `runtime/compat.py` is compatibility-only.
- If strict-mode dataflow fails, fix compiler-owned RW/dataflow modeling in `compiler_v2.py` (and linked tooling), not runtime behavior.
- In strict mode, treat bare identifier-like tokens in read positions as variable references; quote string literals explicitly.

## Recommended Outputs from an AI Contributor

When finishing a session, provide:

- files changed
- behavior change summary
- verification commands run and result
- known risks / follow-ups
- next recommended command

This ensures another agent (or human) can continue work immediately.
