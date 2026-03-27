# External Executor Bridge Integration

The OpenClaw bridge should instrument all tool calls:

- Before calling an external tool, increment `ainl_tool_calls_total{tool_name}` via `MetricsCollector`.
- After call, log success/failure in metrics.
- If the tool uses an LLM internally, also track costs through the same `CostTracker`.

Additionally, the bridge may need to respect global throttling: call `BudgetPolicy().check_and_enforce(run_id)` before expensive operations.

