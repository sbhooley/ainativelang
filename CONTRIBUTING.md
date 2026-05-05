# Contributing to AINL

Thanks for helping improve AI Native Lang.

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

**When to run:** before tagging a release (see **`docs/RELEASING.md`**), or after substantial changes under `compiler_v2.py`, `runtime/`, `cli/`, `adapters/`, `tests/`, or `examples/`. CI runs **`repo-stats`** on pull requests that touch those paths.

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
