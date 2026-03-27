# Hybrid interop operator runbook

Operational steps for **LangGraph**, **Temporal**, and **LangChain-tool** hybrids in production or staging.

## 1. Regenerate emitted Python

From the repo root (or a tree with `compiler_v2`, `runtime/`, `scripts/` on `PYTHONPATH`):

```bash
# LangGraph single-file wrapper (requires langgraph at execute time)
python3 scripts/validate_ainl.py path/to/workflow.ainl --emit langgraph -o ./out/workflow_langgraph.py

# Temporal activities + workflow (requires temporalio on the worker)
python3 scripts/validate_ainl.py path/to/workflow.ainl --emit temporal -o ./out/prefix
# → writes prefix_activities.py and prefix_workflow.py
```

Re-run these commands after **any** `.ainl` change that should ship in the wrapper. Generated files embed IR (base64); they do **not** auto-track source updates.

## 2. Pin third-party versions

In the **deploying** service (not only the AINL repo), pin:

| Stack | Package | Notes |
|--------|---------|--------|
| LangGraph | `langgraph` | Must match APIs used in generated `StateGraph` code. |
| Temporal worker | `temporalio` | Worker SDK version should match your Temporal server compatibility matrix. |
| HTTP baselines / scrapers | `aiohttp` | Used by handwritten benchmark baselines and some examples. |

AINL’s **`[interop]`** and **`[benchmark]`** extras declare **minimum** versions; apps should lock their own constraints. See **[`docs/PACKAGING_AND_INTEROP.md`](../PACKAGING_AND_INTEROP.md)**.

## 3. PYTHONPATH and repo discovery

Emitted modules search upward for a directory containing **`runtime/engine.py`** and **`adapters/`**. Typical layouts:

- Run with **cwd = repo root**, or  
- Set **`PYTHONPATH`** to the AINL checkout root, or  
- Install **`ainl`** editable from that tree.

## 4. Opt-in hybrid targets in IR (`S hybrid`)

To include **langgraph** / **temporal** in compiler **`minimal_emit`** and benchmark minimal planning (for tooling that reads `emit_capabilities`):

```ainl
S hybrid langgraph temporal
L1:
  R core.ADD 1 2 ->x
  J x
```

Allowed tokens: **`langgraph`**, **`temporal`** (repeat lines or one line with both). Unknown tokens are errors in **strict mode**.

This does **not** auto-install packages; it only sets **`needs_langgraph` / `needs_temporal`** for planners and **`required_emit_targets.minimal_emit`**.

## 5. LangGraph worker checklist

- [ ] `pip install langgraph` (version pinned).  
- [ ] Import path resolves **`runtime.wrappers.langgraph_wrapper`**.  
- [ ] Invoke `build_graph()` from emitted module; pass **`ainl_frame`** for initial AINL variables.  
- [ ] Extend graph with LLM nodes **around** `ainl_core`, not inside deterministic AINL unless intentional.

## 6. Temporal worker checklist

- [ ] `pip install temporalio` (pinned).  
- [ ] Worker registers **activities module** and **workflow module** from emit output.  
- [ ] **`PYTHONPATH`** includes AINL root (for `runtime` / `adapters`).  
- [ ] Tune `start_to_close_timeout` and **`RetryPolicy`** in generated workflow for your SLOs.  
- [ ] Local test: call **`run_ainl_core_activity_impl`** with a dict payload (no server) before wiring the worker.

## 7. LangChain tool bridge

- Enable adapter: **`--enable-adapter langchain_tool`** (CLI) or register tools in Python before run.  
- See **`examples/hybrid/langchain_tool_demo.ainl`** and **`docs/reference/ADAPTER_REGISTRY.md`**.

## 8. Failure triage

| Symptom | Check |
|---------|--------|
| `ModuleNotFoundError: runtime` | `PYTHONPATH` / cwd / editable install. |
| `Install langgraph` / `Install temporalio` | Missing optional dep in **that** environment. |
| Activity timeout / retry storm | Workflow timeouts vs graph size; reduce IR or split activities. |
| Stale behavior after edit | Re-run **`validate_ainl.py --emit …`**; redeploy generated files. |

## References

- **[`docs/HYBRID_GUIDE.md`](../HYBRID_GUIDE.md)** — when to choose which pattern.  
- **[`examples/hybrid/README.md`](../../examples/hybrid/README.md)** — example index.  
- **[`docs/PACKAGING_AND_INTEROP.md`](../PACKAGING_AND_INTEROP.md)** — extras and PyPI notes.
