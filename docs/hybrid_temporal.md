# Hybrid deployments: AINL inside Temporal

## What this is

**Temporal** gives you durable execution: retries, timeouts, visibility, and long-running workflows across process restarts. **AINL** gives you a **small, deterministic program** (graph IR) for policy and adapter logic without encoding that behavior in imperative workflow code.

The **`--emit temporal`** option in `scripts/validate_ainl.py` generates two Python modules:

1. **`*_activities.py`** — defines a Temporal **activity** that calls `execute_ainl_activity()` from `runtime/wrappers/temporal_wrapper.py`, which runs the **embedded IR** via `RuntimeEngine` (same contract as LangGraph hybrid).
2. **`*_workflow.py`** — defines a **workflow** that invokes that activity with `workflow.execute_activity`, including starter `start_to_close_timeout` and `RetryPolicy` you can tune.

## Generate artifacts

From the repository root:

```bash
python3 scripts/validate_ainl.py path/to/workflow.ainl --emit temporal
```

Writes `<stem>_activities.py` and `<stem>_workflow.py` in the current directory (or use `-o` — see below).

### `-o` behavior

- **Omitted:** files go to the current working directory; base name is the source file stem.
- **Path ending in `.py`:** directory is the parent, base name is the stem (e.g. `-o /tmp/job.py` → `/tmp/job_activities.py`).
- **Existing directory:** files are written inside it with the source stem as base.
- **Non-existent path without suffix:** treated as `directory/basename` prefix (e.g. `-o out/monitoring` → `out/monitoring_activities.py` if `out/` exists or is created).

## Dependencies

- **AINL runtime:** repo root on `PYTHONPATH` (the emitted activities module walks up to find `runtime/` and `adapters/`).
- **temporalio:** required on the **worker** that runs activities, and for **importing** the generated workflow module (`pip install temporalio`). The activities file registers `@activity.defn` only when `temporalio` is installed; otherwise `run_ainl_core_activity_impl` remains callable for local smoke tests.

## Input / state contract

The activity accepts a **single dict** payload. Keys are merged into the AINL **frame** for the entry label (e.g. `metric_value`, `threshold`). Reserved optional keys:

- **`_label`** — override entry label id.
- **`_strict`** — reserved for future use (compile path uses `strict=True` in the wrapper for source-based runs; emitted IR does not recompile).

The activity returns **`{"ok", "result", "error"}`** from `execute_ainl_activity`.

## Benefits

- **Compact authoring:** keep branching and `R` adapter steps in AINL instead of growing workflow code.
- **Durability:** Temporal handles retries and timeouts around the whole AINL run as one activity (or split into more activities later).
- **Separation:** LLM / human steps can live in other activities; AINL remains the deterministic core.

## Example

See [`examples/hybrid/temporal_durable_ainl/`](examples/hybrid/temporal_durable_ainl/) for source `.ainl`, emitted `*_activities.py` / `*_workflow.py`, and regen instructions.

## Related

- LangGraph hybrid: [`docs/hybrid_langgraph.md`](hybrid_langgraph.md)
- Runtime contract: [`docs/RUNTIME_COMPILER_CONTRACT.md`](RUNTIME_COMPILER_CONTRACT.md)
