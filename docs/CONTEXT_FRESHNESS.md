# Context freshness contract

Cross-runtime enum (Rust: `ainl_contracts::ContextFreshness`; JSON in [`tooling/ainl_policy_contract.json`](../tooling/ainl_policy_contract.json)).

| Value | Meaning | Consumer behavior (strict) |
|-------|---------|----------------------------|
| `fresh` | Code/index context is confidently current. | May proceed to execute after normal validation. |
| `stale` | Known mismatch (e.g. index behind `HEAD`). | Prefer `impact` / `ir_diff` before writes; refresh index when possible. |
| `unknown` | Cannot determine from available signals. | Conservative: recommend impact-first chain; do not assume repo-wide safety. |

**Default in AINL MCP:** `unknown` — the Python MCP server does not embed git or external indexers; freshness may be supplied by ArmaraOS or future hooks.

**Without `ainl-inference-server`:** this contract is still valid; inference-server is optional for planner telemetry only.
