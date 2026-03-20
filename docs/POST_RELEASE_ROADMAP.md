# Post-Release Roadmap (Immediate)

This roadmap captures immediate engineering priorities following the first public GitHub release.
It is intentionally narrow and contract-driven.

GitHub-ready issue draft stubs for this roadmap live in `docs/issues/`.
The operator-grade sequencing and breakage-control plan lives in `docs/NO_BREAK_MIGRATION_PLAN.md`.

## 1) Canonical Strict Surface Expansion (Contract-First)

- Expand strict-valid surface only through explicit, compiler-owned contracts.
- Any strict expansion must be reflected in:
  - `tooling/effect_analysis.py` (adapter/effect contract)
  - `tooling/artifact_profiles.json` (artifact expectations)
  - conformance/runtime tests
- No wildcard strict allowances.

## 2) Legacy And Non-Strict Artifact Migration

- Reduce non-strict-only and legacy-compat artifacts over time via intentional migration.
- Promote artifacts to `strict-valid` only after:
  - strict compile pass
  - runtime behavior validation
  - docs/profile updates
- Keep compatibility artifacts explicitly labeled while migration is incomplete.

## 3) Compiler-Structured Diagnostics Expansion

**Status:** In progress — core strict sites done (arity, unknown module, duplicate label, undeclared endpoint/targeted); CLI human view (`ainl-validate` + `rich` when installed); merge-order dedup still TODO (Phase 3).

- Increase structured diagnostic coverage emitted by compiler outputs (`span`, `lineno`, `label_id`, `node_id`, etc.).
- Keep language server diagnostic heuristics strictly as backward-compat fallback.
- Add tests that prevent diagnostic location regressions and fake precision.

## 4) Compatibility-Path Retirement (Incremental)

- Continue reducing compatibility-only execution paths where canonical behavior already exists.
- Maintain backward compatibility wrappers during transition but avoid adding new semantics there.
- Require explicit deprecation notes before removing compatibility paths.

## Guardrails

- No semantic changes without corresponding contract docs and tests.
- Preserve canonical ownership boundaries:
  - compiler semantics: `compiler_v2.py`
  - runtime semantics: `runtime/engine.py`
  - compatibility wrappers: `runtime/compat.py`, `runtime.py`
