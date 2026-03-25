# Contributing to AI Native Lang (AINL)

Thank you for your interest in contributing to AINL.

This project supports both human contributors and AI-assisted contribution workflows, with human review and maintainer discretion governing final acceptance. **AI agents** should follow **`docs/BOT_ONBOARDING.md`** and complete **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** before implementation work; see `tooling/bot_bootstrap.json` for pointers.

## Before You Contribute

Please read the relevant project materials before making substantial changes.

Start with:

- `README.md`
- **`docs/CHANGELOG.md`** / **`docs/RELEASE_NOTES.md`** — **current release v1.2.8** (see also **`pyproject.toml`**, **`runtime/engine.py`** **`RUNTIME_VERSION`**)
- `docs/DOCS_INDEX.md`
- `docs/AINL_SPEC.md`
- `SEMANTICS.md`

If you are working on the model, training, or evaluation pipeline, also review:

- `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
- `corpus/curated/alignment_run_health.json`

If the repository includes additional architecture, roadmap, or design documents relevant to your change, review those as well.

## Project Model

AI Native Lang (AINL) is developed using a human-directed, AI-assisted workflow.

The general model is:

- human-initiated project direction
- AI-assisted or AI-led co-development across multiple models and tools
- human review and approval for strategic decisions, publication quality, and final merge decisions
- open-core publication strategy, where applicable

Human maintainers remain responsible for project direction, acceptance criteria, releases, and external publication.

## Contribution Expectations

We welcome contributions such as:

- bug fixes
- documentation improvements
- tests and conformance updates
- tooling improvements
- examples and tutorials
- performance improvements
- language proposals and implementation work
- developer experience improvements

Please prefer changes that are:

- focused and reviewable
- consistent with the project's architecture and quality standards
- backed by tests or diagnostics where appropriate
- accompanied by documentation updates when behavior changes

## Quick Start

A typical contribution flow is:

1. Review the relevant docs and specifications
2. Run the baseline checks
3. Make a focused change
4. Add or update tests, diagnostics, or examples as appropriate
5. Re-run the relevant checks
6. Update documentation and changelog entries where needed
7. Submit a pull request with a clear explanation of the change

Example baseline check:

```bash
.venv/bin/python scripts/run_test_profiles.py --profile core
```

Recommended release-surface checks when touching examples/corpus/docs:

```bash
python scripts/check_all_strict.py
python scripts/check_all_nonstrict.py
pytest tests/test_artifact_profiles.py -q
python scripts/check_docs_contracts.py --scope all
```

## RC Checklist Before Opening a PR

Run this exact sequence from repo root:

```bash
python scripts/run_test_profiles.py --profile core
python scripts/check_all_strict.py
python scripts/check_all_nonstrict.py
python -m pytest -q tests/test_artifact_profiles.py
python scripts/check_docs_contracts.py --scope all
```

This checklist aligns with current public CI/release expectations.
For scope and messaging context, also review `README.md`, `docs/RELEASE_NOTES.md`, and `docs/RELEASE_READINESS.md`.

Maintainers preparing a public release should use `docs/RELEASING.md`.

## Source-of-Truth Architecture (Do Not Drift)

When making semantics-sensitive changes, treat these ownership boundaries as mandatory:

- Compiler semantics and strict validation: `compiler_v2.py`
- Canonical runtime execution: `runtime/engine.py`
- Runtime compatibility wrapper only: `runtime/compat.py` and `runtime.py`
- Formal grammar orchestration: `compiler_grammar.py`
- Grammar compatibility composition: `grammar_constraint.py` (non-authoritative)
- Adapter strict contract allowlist/effects: `tooling/effect_analysis.py`
- Artifact strict/non-strict/legacy classification: `tooling/artifact_profiles.json`
- Safe optimization policy for language-vs-compiler tradeoffs: `docs/runtime/SAFE_OPTIMIZATION_POLICY.md`

If a change alters compiler/runtime/grammar behavior, update:

- `docs/CONFORMANCE.md`
- `docs/RUNTIME_COMPILER_CONTRACT.md`
- `docs/RELEASE_READINESS.md`
- `README.md` (if user-facing behavior changes)

## Strict vs Non-Strict Artifact Expectations

Examples/corpus/fixtures are explicitly profiled:

- `strict-valid`: must compile in strict mode
- `non-strict-only`: must compile non-strict and fail strict mode
- `legacy-compat`: retained for compatibility/training context

Do not silently reclassify artifacts in prose only. Update `tooling/artifact_profiles.json`
and keep `tests/test_artifact_profiles.py` passing.

## Human Contributor Guidance

Human contributors should generally:

- prefer clear, test-backed pull requests with concise rationale
- preserve backward compatibility unless intentionally changing spec or runtime contracts
- add examples when introducing new language patterns or runtime behaviors
- keep unrelated refactors separate from functional changes where practical

## AI-Assisted Contributor Guidance

If you are contributing through an AI-assisted workflow, follow any additional guidance in:

- `docs/CONTRIBUTING_AI_AGENTS.md`

General expectations for AI-assisted contributions include:

- preserve strict AINL correctness
- preserve diagnostics and machine-readable artifacts
- prefer additive feature flags over unnecessary breaking changes
- include verification steps and handoff notes where appropriate
- avoid speculative edits outside the stated scope of the task

AI-assisted contributions are welcome, but they are held to the same review and correctness standards as any other contribution.

## Documentation Requirements

If your change affects behavior, interfaces, workflows, or contributor understanding, update the relevant documentation.

This may include one or more of:

- `README.md`
- `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
- `docs/AI_AGENT_CONTINUITY.md`
- `docs/CHANGELOG.md`

Maintainers may request additional documentation updates when needed for clarity, continuity, or release quality.

## Quality Signals for Model or Evaluation Changes

If you are changing model, alignment, or evaluation behavior, treat the following as primary quality signals:

- `strict_ainl_rate`
- `runtime_compile_rate`
- `nonempty_rate`

Do not optimize for `eval_loss` alone.

## Recommended Commit Scope

Please prefer:

- one cohesive behavior change per commit where practical
- tests, diagnostics, and docs included with the related change whenever possible
- concise commit messages and pull request descriptions that explain intent and impact

## Discuss Major Changes First

For substantial changes, open an issue, design note, or discussion before investing significant implementation effort.

Examples of substantial changes include:

- syntax changes
- semantic changes
- core runtime or compiler architecture changes
- standard library additions with compatibility implications
- public API changes
- major packaging or dependency changes

## Developer Certificate of Origin (DCO)

By contributing to this project, you certify that you have the legal right to submit your contribution under the applicable repository license terms.

All commits should include a `Signed-off-by` line.

Use:

```bash
git commit -s -m "Your message"
```

This appends:

```text
Signed-off-by: Your Name <your.email@example.com>
```

Contributions missing a valid sign-off may be asked to update commits before merge.

## License Scope Reminder

Unless explicitly agreed otherwise:

- core code contributions are accepted under `LICENSE`
- non-code docs and content contributions are accepted under `LICENSE.docs`
- model, checkpoint, dataset, or related ML artifact contributions may be governed by `MODEL_LICENSE.md`

See the relevant license files and notices in the repository for details.

## Review and Acceptance

Submission of a contribution does not guarantee acceptance.

Maintainers may request revisions, redesign, deferral, or rejection of changes in order to preserve project quality, compatibility, maintainability, strategic direction, or publication standards.

## Questions

If you are unsure whether a change is a good fit, open an issue or discussion first.
