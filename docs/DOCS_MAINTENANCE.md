# Documentation Maintenance Contract

This document keeps docs updates consistent across humans and AI agents.
Use it whenever runtime/compiler/grammar semantics change.

## Source-Of-Truth Priority

When conflicts exist, update in this order:

1. `AINL_SPEC.md` (normative language + execution model)
2. `RUNTIME_COMPILER_CONTRACT.md` (runtime/compiler ownership and behavior contract)
3. `CONFORMANCE.md` (what is shipped now)
4. `CHANGELOG.md` (what changed and why)

Then update supporting docs (`README.md`, schemas, profiles, guides).

## Required Update Set (Behavioral Changes)

For any semantic/runtime/compiler behavior change, update all applicable:

- `RUNTIME_COMPILER_CONTRACT.md`
- `CONFORMANCE.md`
- `CHANGELOG.md`
- `README.md` (entrypoint summary)

If IR/graph shapes change, also update:

- `reference/IR_SCHEMA.md`
- `reference/GRAPH_SCHEMA.md`
- `AINL_SPEC.md` (if normative language changes)

If new runtime ops dispatch a named adapter (for example IR **`MemoryRecall`/`MemorySearch`** → **`ainl_graph_memory`**), also align **`tooling/effect_analysis.py`** (**`ADAPTER_EFFECT`** + node effect helpers), **`tooling/adapter_manifest.json`**, and the operator catalog in **`docs/reference/ADAPTER_REGISTRY.md`** (plus **`ADAPTER_REGISTRY.json`** when that JSON is maintained for the release).

If strict-mode behavior changes, also update:

- `AINL_SPEC.md` strict guarantees
- `language/grammar.md` quick-reference rules
- profile docs (`reference/AINL_V0_9_PROFILE.md`) when affected

## Deep-Linking Standard

Prefer deep links for cross-doc navigation:

- Use section anchors when pointing to specific policy/contract clauses.
- Keep anchor text stable (avoid frequent heading rename churn).
- Ensure links are relative within `docs/` (no `docs/...` prefix from docs-internal links).

## Compatibility Wording Standard

Use consistent terms:

- **Canonical runtime:** `RuntimeEngine` in `runtime/engine.py`
- **Compatibility API:** `ExecutionEngine` in `runtime/compat.py` (re-exported by `runtime.py`)
- **Canonical semantics:** graph nodes/edges
- **Compatibility serialization:** `legacy.steps`

Avoid stale transitional phrasing when behavior is already shipped.

## AI-Agent Handoff Checklist

Before ending a docs-heavy session:

1. Agent implementation entrypoints: `BOT_ONBOARDING.md`, `OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`, `tooling/bot_bootstrap.json` — ensure any new agent-facing doc links these where applicable.
2. Verify cross-links from `DOCS_INDEX.md`, `README.md`, and contract docs.
3. Confirm strict-mode wording is consistent across spec/contract/conformance.
4. Add changelog entry for meaningful behavior/contract changes.
5. Run lints/diagnostics for touched docs.

Automation commands:

- Full docs contract check (local/CI parity): `ainl-check-docs`
- Python entrypoint equivalent: `python scripts/check_docs_contracts.py --scope all`
- PR diff-aware mode (CI): `python scripts/check_docs_contracts.py --scope changed --base-ref origin/main`
- Local pre-commit install: `pre-commit install` (runs docs contract checks before commit)

## Scope Discipline

Not every code change needs every doc changed. Use this heuristic:

- **Semantics changed?** Update contract + conformance + changelog.
- **Only implementation/internal refactor?** Update changelog, and contract only if externally observable behavior/policy changed.
- **No user-visible impact?** Changelog optional unless release tracking requires it.
