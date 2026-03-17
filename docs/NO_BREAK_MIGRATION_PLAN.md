# AINL No-Break Migration Plan

This document is the operator-grade execution plan for evolving AINL without
causing widespread breakage across current programs, examples, corpora, emitters,
runtime behavior, or user trust.

It assumes the current reality of the repository:

- the graph-first compiler/runtime/tooling core is the strongest part of AINL,
- the public surface is mixed across canonical, compatible, and legacy forms,
- some targets and examples are substantially more mature than others,
- the next phase should be convergence, not uncontrolled expansion.

## Mission

Stabilize the present, define the canonical future, and migrate toward it
deliberately under compatibility protection.

## Non-Negotiable Rules

1. No silent semantic changes.
- If meaning changes, it must be gated by strict mode, canonical mode, feature flags,
  migration tooling, or explicit deprecation policy.

2. Canonical future is additive before subtractive.
- First create a strong canonical lane.
- Only later tighten defaults or retire compatibility behavior.

3. Freeze surface expansion during stabilization.
- No new syntax families, adapter namespaces, or broad target additions unless they
  are critical bug fixes or directly support convergence.

4. Measure before refactoring.
- No major internal extraction without compile/runtime/emitter snapshots.

## Operating Model

AINL should be managed as three support lanes:

- `canonical`: the future public truth and recommended path
- `compatible`: supported for continuity, but not recommended for new work
- `deprecated`: still accepted, but on a retirement path with warnings and migration

These lanes should apply to:

- syntax forms
- ops
- adapters
- examples
- emitters
- training assets

## Workstreams

### Workstream A — Compatibility Envelope

Purpose:
- Create clarity without breaking existing behavior.

Primary outputs:
- `tooling/support_matrix.json`
- `docs/AINL_CANONICAL_CORE.md`
- `docs/EXAMPLE_SUPPORT_MATRIX.md`

Scope:
- classify current syntax/forms/features
- classify examples and emitters
- define canonical vs compatible vs deprecated

Breakage risk:
- Low

Definition of done:
- public docs clearly distinguish canonical and compatibility surfaces
- major examples are classified
- major emitters are classified
- there is one declared canonical lane for new users, docs, and training

### Workstream B — Regression Safety Net

Purpose:
- make internal cleanup safe

Primary outputs:
- snapshot tests for compile outputs
- snapshot tests for selected emitter outputs
- snapshot tests for selected runtime paths
- graph checksum fixtures for canonical examples

Priority example set:
- `examples/hello.ainl`
- `examples/web/basic_web_api.ainl`
- `examples/crud_api.ainl`
- `examples/retry_error_resilience.ainl`
- one compatibility example from `examples/openclaw/`
- one compatibility example from `examples/golden/`

Breakage risk:
- Low

Definition of done:
- canonical examples have locked compile/runtime/emitter expectations
- selected compatibility examples have locked expected behavior
- refactors can be checked for parity rather than guessed

### Workstream C — Truth Source Unification

Purpose:
- stop drift between manifests, docs, strict validation, and runtime expectations

Primary outputs:
- one declared canonical adapter metadata source
- consistency tests for duplicate truth surfaces
- one declared support-level source for examples/features/targets

Priority areas:
- `tooling/adapter_manifest.json`
- `ADAPTER_REGISTRY.json`
- `tooling/effect_analysis.py`
- `docs/reference/ADAPTER_REGISTRY.md`
- `tooling/artifact_profiles.json`

Breakage risk:
- Medium

Definition of done:
- duplicate truth sources are either generated, validated, or explicitly secondary
- adapter/documentation drift becomes test-visible
- support levels are machine-readable and docs-consumable

### Workstream D — Canonical Training and Evaluation Lane

Purpose:
- make AINL’s AI-native claims more credible

Primary outputs:
- canonical-only training lane
- held-out evaluation lane
- repair/edit benchmark lane
- evaluation integrity policy

Priority requirements:
- no prompt leakage between held-out evaluation and supervision
- no benchmark claims from contaminated sets
- canonical syntax only in canonical training assets

Breakage risk:
- Low to Medium

Definition of done:
- canonical training assets are clean
- held-out evaluation is genuinely held out
- at least one benchmark lane measures repair/edit/patchability, not only syntax validity

### Workstream E — Compiler Extraction Under Parity

Purpose:
- reduce risk in `compiler_v2.py` without changing external behavior

Primary outputs:
- internal helper/module extraction plan
- output-parity checks for each extraction

Recommended extraction order:
1. pure helpers
2. emitter helpers
3. validation helpers
4. graph lowering helpers
5. parser/tokenization last

Breakage risk:
- Medium

Definition of done:
- `AICodeCompiler` interface remains stable
- snapshots remain green
- module boundaries improve without semantic drift

## Milestone Tracker

| Milestone | Window | Owner | Deliverables | Breakage Risk | Acceptance Criteria |
|-----------|--------|-------|--------------|---------------|---------------------|
| M1 Freeze and classify | T+0 to T+10 days | Maintainer + Docs | support matrix, canonical-core doc, example support matrix | Low | canonical lane defined; examples/emitters classified |
| M2 Snapshot current behavior | T+7 to T+21 days | Compiler + Runtime | compile/runtime/emitter snapshots; graph checksum fixtures | Low | parity guardrails in place for canonical and selected compat examples |
| M3 Warning-only canonical linting | T+14 to T+30 days | Compiler | warning codes, lint/check entrypoint, non-canonical guidance | Low | old forms still work; canonical guidance is machine-visible |
| M4 Adapter/source-of-truth unification | T+21 to T+45 days | Compiler + Runtime + Docs | canonical adapter owner, consistency tests, doc alignment | Medium | duplicate truth surfaces are controlled and validated |
| M5 Compiler extraction pass 1 | T+30 to T+60 days | Compiler | internal helper extraction under parity | Medium | stable public behavior; smaller compiler hotspots |
| M6 Canonical training/eval split | T+30 to T+60 days | ML + Maintainer | clean canonical training lane, held-out eval lane, integrity policy | Low-Medium | improved eval credibility and reduced contamination risk |
| M7 Public canonical convergence | T+60 to T+90 days | Maintainer + Docs | canonical-first onboarding, public example curation, target tier clarity | Low | public repo story matches repo reality |

## Concrete File Plan

### Add Soon

- `tooling/support_matrix.json`
- `docs/AINL_CANONICAL_CORE.md`
- `docs/EXAMPLE_SUPPORT_MATRIX.md`
- `docs/EVALUATION_INTEGRITY.md`
- `tests/test_snapshot_compile_outputs.py`
- `tests/test_snapshot_emitters.py`
- `tests/test_snapshot_runtime_paths.py`
- `tests/fixtures/snapshots/`

### Update Soon

- `README.md`
- `docs/CONFORMANCE.md`
- `docs/runtime/TARGETS_ROADMAP.md`
- `docs/AUDIENCE_GUIDE.md`
- `docs/DOCS_INDEX.md`
- `tooling/artifact_profiles.json`
- `scripts/validate_ainl.py`
- `tooling/adapter_manifest.json`
- `docs/reference/ADAPTER_REGISTRY.md`

## Required Gates Before Tightening Anything

Before any canonical enforcement or compatibility reduction, all of the following
must exist:

- support classification
- snapshot coverage for canonical examples
- snapshot coverage for selected compatibility examples
- warning-only migration path
- docs that clearly explain canonical vs compatible behavior

## PR Decision Checklist

For each migration PR, answer:

1. Does this change accepted syntax?
2. Does this change compiler output?
3. Does this change graph checksum for canonical examples?
4. Does this change runtime behavior?
5. Does this change emitted artifacts for strong targets?
6. If yes, is the change:
   - intentional
   - documented
   - warning-gated or mode-gated
   - covered by tests or snapshots

If not, it should not merge.

## Explicitly Out Of Scope For Now

Do not do these during the stabilization phase:

- full parser rewrite
- removal of `legacy.steps`
- removal of `runtime/compat.py`
- aggressive renaming of core concepts
- deletion of compatibility examples before replacement and classification
- major new target expansion
- stronger public claims about model wins before eval integrity is fixed

## First 30-Day Execution Sequence

### Week 1
- freeze surface expansion
- add support matrix
- add canonical-core doc
- add example support matrix

### Week 2
- add snapshot tests for compile/runtime/emitter behavior
- lock graph checksums for canonical examples
- update onboarding docs to point at the canonical lane

### Week 3
- add warning-only canonical linting
- make canonical examples the public default path
- add migration warnings for accepted-but-non-canonical forms

### Week 4
- declare canonical adapter truth source
- add consistency tests
- begin helper extraction from `compiler_v2.py`

## Repo-Owner Summary

This plan does not try to "fix AINL" through shock therapy.

It treats the repo as something worth preserving:

- protect the working core
- isolate and label the messy middle
- build the canonical future intentionally
- move users, docs, training, and examples toward that future by gravity rather than force

That is the lowest-risk path to making AINL clearer, safer, and stronger without
causing a massive break everywhere.
