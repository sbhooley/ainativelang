# AINL as compact workflow definition inside Temporal

**Temporal** runs durable workflows (retries, timeouts, visibility). **AINL** stays the **compact, deterministic** definition of policy and adapter logic; the emitted activity executes the whole embedded IR in one `execute_ainl_activity` call.

## Files

- **`monitoring_durable.ainl`** — strict-safe example (metric vs threshold → JSON summary string).
- **`monitoring_durable_activities.py`** — Temporal activity (or call `run_ainl_core_activity_impl` locally without a worker).
- **`monitoring_durable_workflow.py`** — Temporal workflow; **requires** `pip install temporalio` to import.

## Regenerate emitted Python

From the repository root:

```bash
python3 scripts/validate_ainl.py \
  examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl \
  --strict \
  --emit temporal \
  -o examples/hybrid/temporal_durable_ainl/
```

## Local smoke test (no Temporal server)

From this directory, with repo root on `PYTHONPATH`:

```bash
cd examples/hybrid/temporal_durable_ainl
PYTHONPATH=../../.. python3 -c "import monitoring_durable_activities as m; print(m.run_ainl_core_activity_impl({}))"
```

Override frame inputs (match AINL `Set` / `R` variable names):

```bash
PYTHONPATH=../../.. python3 -c \
  "import monitoring_durable_activities as m; print(m.run_ainl_core_activity_impl({'metric_value': 10, 'threshold': 40}))"
```

## Run with Temporal

1. Install `temporalio`, run a Temporal dev service (see [Temporal docs](https://docs.temporal.io/)).
2. Point a **worker** at `monitoring_durable_activities.run_ainl_core_activity` and register **`AinlMonitoringDurableWorkflow`** from `monitoring_durable_workflow.py` (same directory on `PYTHONPATH`).
3. Start workflows with a payload dict; keys become the AINL frame (optional `_label` for entry label).

More detail: [`docs/hybrid_temporal.md`](../../../docs/hybrid_temporal.md).
