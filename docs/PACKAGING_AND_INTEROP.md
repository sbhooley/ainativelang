# Packaging and ecosystem interop

AINL ships as the **`ainl`** distribution ([`pyproject.toml`](../pyproject.toml)). The **compiler and deterministic runtime** have no mandatory third-party dependencies (`dependencies = []` in the project table). Optional stacks are pulled in via **extras** so downstream apps only install what they use.

## Optional extras

| Extra | Purpose |
|--------|---------|
| **`benchmark`** | Size/runtime benchmarks: `tiktoken`, `psutil`, `aiohttp`, `langgraph`, **`temporalio`** (for baseline comparisons and hybrid emit smoke tests). |
| **`interop`** | LangGraph + Temporal + aiohttp for **hybrid examples** and local runs of emitted wrappers without the full benchmark stack. |
| **`dev`** | pytest, hypothesis, pre-commit, etc. |

Install examples:

```bash
pip install -e ".[benchmark]"
pip install -e ".[interop]"
pip install -e ".[dev,benchmark,interop]"
```

For Python 3.13 sandboxed hosts (PEP 668/no-sudo environments), use the tested MCP constraints:

```bash
python -m pip install --constraint constraints/py313-mcp.txt "ainativelang[mcp]"
```

## Consuming emitted hybrid modules

Generated files from `scripts/validate_ainl.py --emit langgraph` / `--emit temporal` expect:

- **Repository layout:** `runtime/engine.py` and `adapters/` discoverable from the emitted file’s search path (the emitters embed repo-root discovery).
- **Packages at runtime:** **`langgraph`** to execute a LangGraph graph; **`temporalio`** on workers for `@activity.defn` (the activities module falls back if `temporalio` is missing, but workers need it).

Versioning: pin **`temporalio`** / **`langgraph`** in *your* app to match your worker and platform; AINL’s extras specify **minimum** versions compatible with the emitted stubs.

## PyPI / library consumers

- **Import paths:** `runtime.wrappers.langgraph_wrapper`, `runtime.wrappers.temporal_wrapper`, `compiler_v2.AICodeCompiler`, `scripts.emit_langgraph`, `scripts.emit_temporal` (when the repo is on `PYTHONPATH` or installed editable).
- **Stable API surface:** treat **IR schema**, **strict validation** behavior, and **wrapper function signatures** (`run_ainl_graph`, `execute_ainl_activity`) as the integration contract; generated file templates may evolve between minor releases—re-emit from source `.ainl` when upgrading.

For hybrid authoring, **`S hybrid`**, and validator flags, see **[`HYBRID_GUIDE.md`](HYBRID_GUIDE.md)** and **[`examples/hybrid/README.md`](../examples/hybrid/README.md)**. Maintainer release steps: **[`RELEASING.md`](RELEASING.md)**. Hybrid deployment runbook: **[`docs/hybrid/OPERATOR_RUNBOOK.md`](hybrid/OPERATOR_RUNBOOK.md)**.
