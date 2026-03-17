# Structured Audit Logging

The AINL runner service emits structured JSON log events for every
execution request and adapter call. These events support observability,
compliance, and debugging without exposing raw payloads.

Audit logging is part of the **runtime/host** layer. AINL provides the
events; the hosting environment decides how to collect, store, and act on
them. AINL does not provide a log aggregation service or alerting system.

## Event types

### `run_start`

Emitted at the start of every `/run` or `/enqueue` execution.

| Field | Type | Description |
|---|---|---|
| `event` | `"run_start"` | Event type |
| `ts` | ISO 8601 | UTC timestamp |
| `trace_id` | UUID | Unique execution trace |
| `replay_artifact_id` | string | Caller-supplied artifact ID |
| `label` | string | Requested entry label |
| `policy_present` | bool | Whether policy rules are active |
| `limits_summary` | object | Effective runtime limits |

### `adapter_call`

Emitted for every adapter invocation during execution.

| Field | Type | Description |
|---|---|---|
| `event` | `"adapter_call"` | Event type |
| `ts` | ISO 8601 | UTC timestamp |
| `trace_id` | UUID | Execution trace |
| `replay_artifact_id` | string | Caller-supplied artifact ID |
| `adapter` | string | Adapter name (e.g. `core`, `http`) |
| `verb` | string | Adapter verb (e.g. `Get`, `ADD`) |
| `duration_ms` | float | Call duration in milliseconds |
| `status` | `"ok"` or `"error"` | Whether the call succeeded |
| `args` | array | Redacted call arguments |
| `result_hash` | string or null | SHA-256 of the JSON-serialised result |
| `error_summary` | string | Redacted error message (only on failure) |

### `run_complete`

Emitted after successful execution.

### `run_failed`

Emitted after execution failure (runtime error, not policy rejection).

### `policy_rejected`

Emitted when a request is rejected by policy validation before execution.
Includes `replay_artifact_id` for traceability.

## Safety properties

- **No raw results in logs**: only `result_hash` (SHA-256) is logged.
- **Args are redacted**: sensitive tokens (authorization, password, etc.)
  are replaced with `[REDACTED]`.
- **Error messages are redacted and truncated** to 200 characters.
- **Timestamps are UTC ISO 8601** for consistent cross-system correlation.

## Usage

Audit logs are emitted via Python's `logging` module under the
`ainl.runner` logger at INFO level. To capture them:

```python
import logging
logging.getLogger("ainl.runner").setLevel(logging.INFO)
```

For production deployments, configure a structured log handler (e.g.
JSON file handler, log aggregation service) on the `ainl.runner` logger.

## Related docs

- [Capability Grant Model](CAPABILITY_GRANT_MODEL.md)
- [External Orchestration Guide](EXTERNAL_ORCHESTRATION_GUIDE.md)
