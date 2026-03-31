# Production runs: static cost estimates and the audit trail adapter

> v1.3.4 feature guide. Covers `--estimate` on `check`/`inspect`/`status` and the `audit_trail` adapter.

## Overview

| Feature | Flag / adapter | Purpose |
|---------|---------------|---------|
| Static cost estimates | `--estimate` | Pre-run USD cost estimate per LLM node (no API calls) |
| Audit trail | `--enable-adapter audit_trail --audit-sink <URI>` | Immutable JSONL compliance log of runtime events |

---

## Part 1 — Static cost estimates (`--estimate`)

The estimate is **purely static** — it reads the compiled IR, identifies LLM nodes, counts tokens from the prompt text (using `tiktoken cl100k_base` when installed; falls back to `len // 4`), and prices them against a per-model rate table. No LLM API calls are made.

### `ainl check --estimate`

```bash
ainl check my_workflow.ainl --strict --estimate
```

The JSON output gains a `cost_estimate` key:

```json
{
  "ok": true,
  "cost_estimate": {
    "per_node": [
      {
        "label_id": "L_classify",
        "node_id": "n2",
        "adapter": "llm_query",
        "model": "gpt-4o-mini",
        "estimated_input_tokens": 312,
        "estimated_output_tokens": 400,
        "estimated_cost_usd": 0.000287,
        "token_method": "tiktoken"
      }
    ],
    "totals": {
      "sum_input_tokens": 312,
      "sum_output_tokens": 400,
      "sum_cost_usd": 0.000287
    },
    "budget_warnings": []
  }
}
```

A human-readable table is also printed to stderr before the JSON:

```
  Cost estimate (static, no LLM calls):
  Node         Label        Adapter         In tok  Out tok    Est USD
  --------------------------------------------------------------------
  n2           L_classify   llm_query          312      400 $0.000287
  --------------------------------------------------------------------
  TOTAL                                        312      400 $0.000287
```

### `ainl inspect --estimate`

Embeds the estimate inside the full IR dump as `ir["_cost_estimate"]`:

```bash
ainl inspect my_workflow.ainl --estimate | python3 -m json.tool | grep -A 20 _cost_estimate
```

### `ainl status --estimate`

Adds a **monthly spend snapshot** (read-only) from the local `CostTracker` database:

```bash
ainl status --json --estimate
```

Output gains:

```json
{
  "cost_estimate": {
    "monthly_spend_usd": 1.2340,
    "monthly_limit_usd": 20.00,
    "usage_pct": 6.2,
    "alert_threshold_pct": 0.8,
    "throttle_threshold_pct": 0.95,
    "policy_status": "ok"
  }
}
```

### Default model for pricing

Set `AINL_DEFAULT_MODEL` to override the default pricing tier (`gpt-4o-mini`):

```bash
AINL_DEFAULT_MODEL=claude-3-5-sonnet ainl check my_workflow.ainl --estimate
```

---

## Part 2 — Audit trail adapter

The `audit_trail` adapter appends an **immutable JSONL record** for each `record` call, containing:

| Field | Description |
|-------|-------------|
| `trace_id` | Run ID from the runtime context |
| `timestamp` | ISO-8601 UTC with milliseconds |
| `label_id` | Current graph label |
| `node_id` | Current node |
| `event` | The audit event name (defaults to the adapter target like `record`, but if the first arg is an object containing `event`, that value is used) |
| `args` | Redacted call arguments |
| `output` | Redacted last output |
| `event_hash` | SHA-256 of the record (tamper evidence) |

Sensitive keys (`api_key`, `token`, `password`, `secret`, `authorization`, etc.) are **always redacted** before the record is written.

Important caveat: **enabling** the adapter does not write anything by itself. Your graph must actually invoke it (for example `R audit_trail.record ...`) for a JSONL line to be appended. This is expected behavior.

### Enable and configure

**Via CLI:**

```bash
ainl run my_workflow.ainl \
  --enable-adapter audit_trail \
  --audit-sink file:///var/log/ainl/audit.jsonl
```

**Via environment variable:**

```bash
export AINL_AUDIT_SINK=file:///var/log/ainl/audit.jsonl
ainl run my_workflow.ainl --enable-adapter audit_trail
```

**Sink options:**

| URI | Description |
|-----|-------------|
| `file:///path/to/audit.jsonl` | Append to a file (parent dirs created automatically) |
| `syslog://` | Write via POSIX syslog (Linux/macOS) |
| `stderr://` | Write to stderr (useful in development) |
| `stdout://` | Write to stdout (useful in tests or piped flows) |

### Call the adapter from a graph

```ainl
# my_workflow.ainl — record an audit event at a key decision point
S app core noop

L_decide:
  in: level
  decision = core.ADD 0 0
  R audit_trail.record {event: "decision_made", level: level} ->audit_ok
  out decision
```

### Example JSONL record

```json
{
  "trace_id": "run-abc123",
  "timestamp": "2026-03-31T14:22:05.123+00:00",
  "label_id": "L_decide",
  "node_id": "n3",
  "event": "decision_made",
  "args": [{"event": "decision_made", "level": "high"}],
  "output": null,
  "event_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

### Verify records are append-only

```bash
# Count records
wc -l /var/log/ainl/audit.jsonl

# Pretty-print last record
tail -1 /var/log/ainl/audit.jsonl | python3 -m json.tool

# Verify a hash matches (re-compute without the event_hash field)
python3 -c "
import json, hashlib, sys
rec = json.loads(sys.stdin.read())
h = rec.pop('event_hash')
blob = json.dumps(rec, ensure_ascii=False, sort_keys=True).encode()
print('OK' if hashlib.sha256(blob).hexdigest() == h else 'MISMATCH')
" < <(tail -1 /var/log/ainl/audit.jsonl)
```

---

## Combining both features

Run with cost estimation (static, before execution) and audit trail (during execution):

```bash
# Pre-flight cost check
ainl check my_workflow.ainl --strict --estimate

# Production run with audit trail
ainl run my_workflow.ainl \
  --enable-adapter audit_trail \
  --audit-sink file:///var/log/ainl/audit.jsonl \
  --trace-jsonl /var/log/ainl/trace.jsonl
```

---

## Related

- [Debugging with the Visualizer](debugging_with_visualizer.md)
- `docs/OPEN_CORE_DECISION_SHEET.md` — open-core boundary details
- `ainl run --help` — all runtime flags
- `ainl status --help` — status and spend snapshot
