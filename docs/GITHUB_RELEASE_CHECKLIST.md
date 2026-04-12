# GitHub Release Checklist

Use this checklist before publishing publicly or cutting a major release.
For the step-by-step maintainer flow, use `docs/RELEASING.md`.

## 1) Repository Basics

- [ ] `README.md` is current and links key docs.
- [ ] `CONTRIBUTING.md` exists and reflects current workflow.
- [ ] `CODE_OF_CONDUCT.md` exists.
- [ ] `SECURITY.md` exists with vulnerability reporting path.
- [ ] License is set for repository publication.
- [ ] `CITATION.cff` exists for academic referencing.

## 2) Documentation Completeness

- [ ] `docs/DOCS_INDEX.md` is up to date.
- [ ] Language spec and semantics are current (`docs/AINL_SPEC.md`, `SEMANTICS.md`).
- [ ] Training and eval docs match scripts:
  - `docs/FINETUNE_GUIDE.md`
  - `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
- [ ] AI continuity/handoff docs are current:
  - `docs/AI_AGENT_CONTINUITY.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
- [ ] Changelog includes this release (`docs/CHANGELOG.md`).

## 3) Quality and Reproducibility

- [ ] Core tests pass (`.venv/bin/python scripts/run_test_profiles.py --profile core`).
- [ ] Training/eval scripts parse and run in expected environment.
- [ ] Latest run artifacts are present and reviewable:
  - `corpus/curated/model_eval_report_v5_aligned.json`
  - `corpus/curated/model_eval_trends.json`
  - `corpus/curated/alignment_run_health.json`
- [ ] Primary quality metrics are reported:
  - `strict_ainl_rate`
  - `runtime_compile_rate`
  - `nonempty_rate`

## 4) GitHub Community UX

- [ ] Issue templates exist for bug reports and feature requests.
- [ ] PR template exists with test/docs checklist.
- [ ] CI workflow is green and documented.

## 5) AI-Led Attribution Clarity

- [ ] README clearly states human-initiated + AI-led co-development model.
- [ ] `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md` is linked and current.
- [ ] Attribution language is consistent across top-level docs.
- [ ] `tooling/project_provenance.json` matches current initiator/provenance metadata.
- [ ] `docs/PROVENANCE_AND_RELEASE_EVIDENCE.md` has been reviewed for this release.
- [ ] Release post(s) include the same initiator references and release commit/hash.

## 6) Coordination and Advanced Surfaces

- [ ] Coordination protocol lock tests pass (e.g. `tests/test_agent_protocol_surface.py`).
- [ ] Coordination baseline artifacts and docs are in sync
      (see `docs/advanced/AGENT_COORDINATION_CONTRACT.md` baseline section).
- [ ] Coordination mailbox validator has been run on baseline task/result artifacts
      (e.g. `python -m scripts.validate_coordination_mailbox --tasks-jsonl ...`).
- [ ] `README.md` and `docs/DOCS_INDEX.md` still clearly separate
      core/safe-default surfaces from advanced/operator-only/experimental surfaces.
- [ ] Advanced coordination/OpenClaw examples remain labeled as
      extension-only, advanced, and advisory-only in `docs/EXAMPLE_SUPPORT_MATRIX.md`
      and their file headers.

Advanced memory and TTL hygiene:

- [ ] Memory adapter contract and verbs (`put`, `get`, `append`, `list`, `delete`, `prune`) match `docs/adapters/MEMORY_CONTRACT.md`, `tooling/adapter_manifest.json`, and `ADAPTER_REGISTRY.json`.
- [ ] Graph memory (`ainl_graph_memory`, IR **`MemoryRecall`/`MemorySearch`**) is reflected in `docs/adapters/AINL_GRAPH_MEMORY.md`, `tooling/adapter_manifest.json`, `tooling/effect_analysis.py` (**`ADAPTER_EFFECT`**), and (when listed) `ADAPTER_REGISTRY.json` / `docs/reference/ADAPTER_REGISTRY.md`.
- [ ] For deployments that rely on TTLs or long-running memory usage, operators have an explicit plan or runbook entry to invoke `memory.prune` periodically as part of maintenance (no built-in scheduler is provided).

## 7) Final Publish Pass

- [ ] Run a final docs link check (manual or scripted).
- [ ] Verify no private/sensitive data in committed artifacts.
- [ ] `Release Gates` workflow is green (wheel import smoke, `pip check`, MCP dry-run gates).
- [ ] Wheel install check passed for `import runtime.compat, adapters, cli.main`.
- [ ] `ainl install-mcp --host openclaw --dry-run` and `--host zeroclaw --dry-run` both pass.
- [ ] Release notes include a clear install-regression status line (what was validated, and any remaining host-lane caveats).
- [ ] Create release notes summarizing:
  - key technical changes
  - known limitations
  - immediate next milestones
