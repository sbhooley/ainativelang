# Releasing `ainl`

This document describes how to cut a **PyPI-ready** release of the **`ainl`** package defined in **[`pyproject.toml`](../pyproject.toml)**.

**Latest version in this tree:** **1.5.0** (see **`pyproject.toml`**, **`runtime/engine.py`** **`RUNTIME_VERSION`**, **`CITATION.cff`**). Older versions remain documented in **`docs/CHANGELOG.md`** and **`docs/RELEASE_NOTES.md`**.

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

**Preferred (uses project `uv.lock`):**

```bash
rm -rf dist/
uv build
uvx twine check dist/*
```

**Upload to PyPI** (create an API token on [pypi.org](https://pypi.org/manage/account/token/) with scope for **`ainativelang`**):

```bash
UV_PUBLISH_TOKEN=pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx uv publish
```

`uv publish` reads **`UV_PUBLISH_TOKEN`** (or **`--token`**). Do not commit tokens. A local **`.env`** may define **`PYPI_API_KEY`** — export it as **`UV_PUBLISH_TOKEN`** for the same value.

**CI:** See **`.github/workflows/publish-pypi.yml`**.

- **Trusted publishing (OIDC):** Register this repo + workflow on the PyPI project (**Publishing** → GitHub). Then use **Actions → Publish PyPI → Run workflow**, or publish a **GitHub Release** (`release: published`).
- **API token:** Add a repository secret **`PYPI_API_TOKEN`** (PyPI API token scoped to **`ainativelang`**). When this secret is set, the workflow uploads with **`__token__`** + that password; when unset, the action uses OIDC only (same as before).

**Classic tools** (equivalent):

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
twine upload dist/*
```

Use **TestPyPI** first if desired: `twine upload --repository testpypi dist/*` or `uv publish --publish-url https://test.pypi.org/legacy/ --token ...`.

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
python -m pip install --constraint constraints/py313-mcp.txt "ainativelang[mcp]"
```

## Git tag

After upload:

```bash
git tag -a vX.Y.Z -m "ainl X.Y.Z"
git push origin vX.Y.Z
```

Tags should match **`pyproject.toml`** `version` (with or without `v` prefix — pick one convention and stick to it).

### GitHub Release → PyPI (OIDC)

The workflow **`.github/workflows/publish-pypi.yml`** runs on **`release: published`**. After **`main`** is green (especially **`parser-compat`** — wishlist strict + smoke), create a **GitHub Release** for tag **`vX.Y.Z`** and publish it; trusted publishing uploads the wheel/sdist to PyPI. Alternatively use **Actions → Publish PyPI → Run workflow** once the tag exists.

**Pre-flight (local parity with CI wishlist gate):**

```bash
python -m pytest -q tests/test_wishlist_examples_strict.py
python -m cli.main run examples/wishlist/01_cache_and_memory.ainl --json \
  --frame-json '{"session_key":"local","note":"ok"}' 2>/dev/null
python -m cli.main run examples/wishlist/05b_unified_llm_offline_config.ainl --json \
  --config examples/wishlist/fixtures/llm_offline.yaml \
  --frame-json '{"user_query":"local smoke"}' 2>/dev/null
```

(`2>/dev/null` drops the optional sandbox shim line so **`--json`** stdout is clean when piping.)

## Optional extras (document for users)

- **`[dev]`** — tests, linters.  
- **`[benchmark]`** — size/runtime benches + handwritten baselines + **`temporalio`**.  
- **`[interop]`** — **`langgraph`**, **`temporalio`**, **`aiohttp`** for hybrid local runs.

See **[`docs/PACKAGING_AND_INTEROP.md`](PACKAGING_AND_INTEROP.md)**.
