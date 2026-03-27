# Token budget monitor (handwritten baseline)

## Original AINL

This folder ports the **control-flow and thresholds** of
[`openclaw/bridge/wrappers/token_budget_alert.ainl`](../../../openclaw/bridge/wrappers/token_budget_alert.ainl):

- Daily-style digest pipeline: reset notify state, read **cache MB**, branch on **>10**, **>15**, **>12** MB.
- **Critical** path adds a notify when cache is very large (skipped in **dry_run**).
- **Digest**: warn flag + report text; live runs append report and touch a **“already sent today”** sentinel unless duplicate.
- **Prune** when **>12 MB**: success vs error markdown paths, optional prune notify, then **finalize** (budget notify text when `wb && cache_ok`, consolidated **queue Put**).

Bridge adapters (`bridge.*`, `openclaw_memory`, `queue`) are **not** invoked; they are mocked by `BudgetContext` so runs are deterministic and offline.

## Implementations

| File | Role |
|------|------|
| `pure_async_python.py` | Single coroutine `run_token_budget_monitor()` mirroring the AINL label order. |
| `langgraph_version.py` | Same logic split into nodes (`reset_stat` → `threshold` → `digest` → `prune` → `finalize`) with linear edges. |

## Equivalence

For the same `TokenBudgetInput` and initial `BudgetContext.report_sent_today`, both implementations produce identical `report`, `memory_appends`, `notify_adds`, and `queue_puts`. Run:

```bash
cd benchmarks/handwritten_baselines/token_budget_monitor
python langgraph_version.py   # runs the exhaustive grid check; requires langgraph
```

## Key differences vs AINL

- **Declarative vs explicit graph**: AINL uses labels, `If`, and `Call`; Python uses `if` / functions; LangGraph makes the phase structure explicit.
- **Adapters**: Real program depends on bridge + filesystem + queue; baselines use in-memory async mocks (`asyncio.sleep(0)` I/O stand-ins).
- **No tokenizer edge cases**: The original notes `If (core.gt cache_mb N)` can break the tokenizer; Python compares floats directly.

## Assumptions

- Thresholds **10 / 12 / 15** MB and the **dry_run** / **duplicate report** gating match the linked `.ainl`.
- `token_budget_warn(1)` / `token_budget_report(1)` return fixed mock values (real bridge would vary).
- The intermediate `L_notify_budget` / `L_queue_gate` chain that always reaches `L_done` is collapsed; side effects match the reachable path.

## Dependencies

- **Pure**: stdlib + `asyncio`.
- **LangGraph**: `pip install langgraph` (not a declared dependency of `ainl`; used only for this baseline).
