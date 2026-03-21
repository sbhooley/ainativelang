# Retry + timeout wrapper (handwritten baseline)

## Original AINL

Combines two repo patterns:

1. **[`examples/retry_error_resilience.ainl`](../../../examples/retry_error_resilience.ainl)** — `R ext.OP "unstable_task"` with **`Retry @n1 2 0`**: two retries after the first failure (three attempts). On exhaustion, jump to `L_fail` and return **`failed_after_retries`**.
2. **[`modules/common/timeout.ainl`](../../../modules/common/timeout.ainl)** — `LENTRY` runs **`R core.SLEEP 1`** (1 **millisecond** in `core` builtins) before calling into work. The timeout module’s `LTIMEOUT` label is modeled by an **outer** `asyncio.wait_for`: if the deadline elapses, the baseline returns **`timeout`** (parallel to `LEXIT_TIMEOUT`).

## Implementations

| File | Role |
|------|------|
| `pure_async_python.py` | `entry_sleep` → retry loop calling `unstable_task`, wrapped in `wait_for`. |
| `langgraph_version.py` | Nodes: entry sleep → try_op with conditional **retry** via backoff edge; **same** outer `wait_for`. |

## Equivalence

For the same `RetryTimeoutConfig`, both return the same string outcome (`resp…`, `failed_after_retries`, or `timeout`). Run:

```bash
cd benchmarks/handwritten_baselines/retry_timeout_wrapper
python langgraph_version.py
```

## Key differences vs AINL

- **Retry**: AINL attaches retry to a specific step; Python uses an explicit `for` loop / graph cycle.
- **Timeout**: The module’s timer/cancel story is strict-safe with `SLEEP`; we use **asyncio** timeouts around the whole subgraph instead of `R core.cancel_timer`.
- **`ext.OP`**: Replaced by a Python coroutine raising `RuntimeError` until success.

## Assumptions

- `max_retries=2` matches `Retry @n1 2 0` (three total tries: initial + 2 retries).
- Success path return value `"resp"` matches `J resp` (opaque payload).

## Dependencies

- Stdlib only for `pure_async_python.py`.
- `langgraph` for `langgraph_version.py`.
