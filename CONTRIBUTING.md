# Contributing to AINL

Thanks for helping improve AI Native Lang.

## Pre-commit (recommended — auto-refreshes headline stats)

So no one has to remember manual steps before pushing:

```bash
pip install pre-commit
pre-commit install
```

When you commit changes under `compiler_v2.py`, `runtime/`, `cli/`, `adapters/`, `tests/`, `examples/`, `ainl_preprocess.py`, or the stats script itself, the **`refresh-repo-stats`** hook runs **`python scripts/refresh_repo_stats.py`** and updates **`STATUS.yaml`** / **`AGENTS.md`** if needed. If it modifies files, Git will ask you to stage those updates and commit again (normal pre-commit behavior).

Requires **`pip install -e ".[dev]"`** so `pytest --collect-only` works.

**If hooks are not installed**, GitHub Actions still runs **`python scripts/refresh_repo_stats.py --check`** on **every** pull request and push to `main` — the PR will fail until stats match the tree.

## Where things live

| Area | Entry |
|------|--------|
| Compiler | `compiler_v2.py`, `compiler_diagnostics.py` |
| Runtime | `runtime/engine.py`, `runtime/adapters/` |
| CLI | `cli/main.py` |
| Adapters | `adapters/` |
| Tests | `tests/` |
| Honest shipped vs roadmap | **`STATUS.yaml`** (`real_and_working` vs `aspirational_not_built`) |
| Agent onboarding | **`AGENTS.md`** |

## Contributor visibility

Commit attribution on GitHub is the source of truth for who landed changes. See **Insights → Contributors** on [`sbhooley/ainativelang`](https://github.com/sbhooley/ainativelang). Local clones may use different git user names; use your GitHub-linked identity for commits you want counted publicly.

**When your PR merges (or lands with edits):** maintainers leave a closing comment on the PR that points to:

- the **commit SHA** (or squash merge commit) on `main`
- any **docs path** (`docs/…`) if the feature is documented elsewhere
- a short note if the implementation shape changed during review (e.g. consolidated into an existing module)

Examples: [#70](https://github.com/sbhooley/ainativelang/pull/70#issuecomment-4536108337) (feature reworked, full docs linked), [#71](https://github.com/sbhooley/ainativelang/pull/71#issuecomment-4536109925) (direct merge). If you do not see a follow-up comment within a few days of merge/close, ping in the PR thread.

## Headline statistics (STATUS.yaml + AGENTS.md)

Large edits to the compiler, runtime, CLI, adapters, or test tree change line counts and inventory. Keep **`STATUS.yaml`** and the **Repository Layout** block in **`AGENTS.md`** aligned so README-style blurbs stay accurate.

Refresh machine-generated numbers:

```bash
python scripts/refresh_repo_stats.py
```

Check without writing (exit code **2** if drift):

```bash
python scripts/refresh_repo_stats.py --check
```

Requirements: Python environment with dev deps (`pip install -e ".[dev]"`) so `pytest --collect-only` works.

**When to run:** before tagging a release (see **`docs/RELEASING.md`**), after substantial edits under the paths above, or rely on **pre-commit** / **CI** (see above).

## Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -x -q -k "not test_profiles_cover"
```

Optional integrations (ArmaraOS CLI, LangGraph, Temporal) unlock additional tests; skips are normal without those deps.

## Docs contracts

PRs that change docs may need:

```bash
python scripts/check_docs_contracts.py --scope changed --base-ref origin/main
```

See **CI** workflow **`docs-contract`** for the authoritative command.
