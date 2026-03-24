# Hyperagent Pack Signal Quality Report (2026-03-24)

Scope: real-workflow sanity run for `ainl_ir_diff` + `ainl_fitness_report` after v1.2.7 additive changes.

Method:

- Selected 5 existing workflows from `examples/`.
- Created base/mutated copies with deterministic executable mutations.
- Ran:
  - `ainl_ir_diff(base, mut, strict=True)`
  - `ainl_fitness_report(base, runs=5, strict=True)`
  - `ainl_fitness_report(mut, runs=5, strict=True)`

Raw machine output: `/tmp/ainl_real_eval/summary.json`

## Results

| Workflow | IR diff signal | Reliability (base/mut) | Fitness delta (mut-base) | Notes |
|---|---|---|---:|---|
| `retry_error_resilience` | structural add detected (`added_nodes=2`) | 1.0 / 1.0 | `+0.000010` | Mutation inserted extra executable label block. |
| `monitor_escalation` | payload change detected (`changed_nodes=1`) | 1.0 / 1.0 | `-0.000002` | Good payload-level diff quality (`fields=data`). |
| `if_call_workflow` | structural add detected (`added_nodes=2`) | 1.0 / 1.0 | `+0.000013` | Similar to retry shape; tiny fitness movement. |
| `webhook_automation` | structural add detected (`added_nodes=2`) | 0.0 / 0.0 | `0.000000` | Safe profile blocks `http`; reliability gate forces score to 0. |
| `cron/monitor_and_alert` | structural add detected (`added_nodes=2`) | 0.0 / 0.0 | `0.000000` | Safe profile blocks `db`; reliability gate forces score to 0. |

## Assessment

- `ainl_ir_diff` is now useful for both structural and payload-level edits.
- `ainl_fitness_report` reliability gate behaves correctly: non-viable workflows rank at zero.
- For viable pairs, score deltas are currently very small for tiny mutations; ranking is stable but low-sensitivity.

## Recommendation

- Keep current scoring contract stable for v1.2.7.
- If better separation is needed later, tune component scales or add workload-specific signals (for example explicit objective score from assertion labels).
