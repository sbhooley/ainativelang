# Releasing `ainl-lang`

This document describes how to cut a **PyPI-ready** release of the **`ainl-lang`** package defined in **[`pyproject.toml`](../pyproject.toml)**.

**Latest version in this tree:** **1.2.6** (see **`pyproject.toml`**, **`runtime/engine.py`** **`RUNTIME_VERSION`**, **`CITATION.cff`**). Older versions remain documented in **`docs/CHANGELOG.md`** and **`docs/RELEASE_NOTES.md`**.

## Public API surface (for downstream apps)

Downstream code should depend on stable **behavior**, not private scripts:

| Area | Intended use |
|------|----------------|
| **Compiler** | `compiler_v2.AICodeCompiler` — compile `.ainl` / fragments to IR. |
| **Runtime** | `runtime.engine.RuntimeEngine` — execute IR. |
| **Hybrid wrappers** | `runtime.wrappers.langgraph_wrapper.run_ainl_graph`, `runtime.wrappers.temporal_wrapper.execute_ainl_activity`. |
| **Emitters (optional)** | `scripts.emit_langgraph`, `scripts.emit_temporal` when used as libraries from a checkout. |

CLI entry points are listed under **`[project.scripts]`** in `pyproject.toml` (`ainl`, `ainl-validate`, …).

**Generated file templates** (LangGraph / Temporal output) may evolve between minors; consumers should **re-emit from source** when upgrading.

## Version bump

1. Update **`version`** in **`pyproject.toml`** (semantic versioning).  
2. Update **`docs/CHANGELOG.md`** (or root changelog policy) with user-facing notes.  
3. Ensure **`make conformance`** and **`pytest`** pass on **Python 3.10** (minimum supported).  
4. Optional: run **`make benchmark PYTHON=./.venv-py310/bin/python`** and commit refreshed **`BENCHMARK.md`** / **`tooling/benchmark_size.json`** / **`tooling/benchmark_runtime_results.json`** if you track **full** baselines on `main`.
5. For **CI regression parity**, run **`make benchmark-ci PYTHON=./.venv-py310/bin/python`** and commit **`tooling/benchmark_size_ci.json`** and **`tooling/benchmark_runtime_ci.json`** when they drift. GitHub Actions **`benchmark-regression`** **prefers** those `*_ci.json` files on the baseline commit when present (see **`BENCHMARK.md`** § *CI regression baselines*).
6. Confirm install hardening gates are green (including non-root container smoke + `constraints/py313-mcp.txt` health workflow status).

## Build and upload

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
twine upload dist/*
```

Use **TestPyPI** first if desired: `twine upload --repository testpypi dist/*`.

## Required release gates (automation)

Before tagging/uploading, ensure **`Release Gates`** GitHub workflow passes:

- wheel build + `twine check`
- wheel install smoke (`import runtime.compat, adapters, cli.main`)
- `ainl --help` and `ainl-mcp --help`
- `python -m pip check`
- `ainl install-mcp --host openclaw --dry-run`
- `ainl install-mcp --host zeroclaw --dry-run`
- install sections in release notes explicitly mention install-regression status (pass/fail and any known host-lane caveats)

For Python 3.13 sandbox compatibility, use:

```bash
python -m pip install --constraint constraints/py313-mcp.txt "ainl-lang[mcp]"
```

## Git tag

After upload:

```bash
git tag -a vX.Y.Z -m "ainl-lang X.Y.Z"
git push origin vX.Y.Z
```

Tags should match **`pyproject.toml`** `version` (with or without `v` prefix — pick one convention and stick to it).

## Optional extras (document for users)

- **`[dev]`** — tests, linters.  
- **`[benchmark]`** — size/runtime benches + handwritten baselines + **`temporalio`**.  
- **`[interop]`** — **`langgraph`**, **`temporalio`**, **`aiohttp`** for hybrid local runs.

See **[`docs/PACKAGING_AND_INTEROP.md`](PACKAGING_AND_INTEROP.md)**.
