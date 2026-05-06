# Enterprise evidence bundle recipe (self-hosted)

This runbook helps teams assemble a **small, reproducible folder** of artifacts that support **incident review**, **change-management**, and **control-mapping** conversations. It does **not** replace your SOC 2 program or your SIEM.

**Prerequisites:** Read [`../operations/AUDIT_AND_TELEMETRY_MAP.md`](../operations/AUDIT_AND_TELEMETRY_MAP.md) so you pick the correct telemetry surface for your deployment shape.

## 1. Graph and compiler evidence

Store alongside runtime logs:

| Artifact | Command / source |
|----------|-------------------|
| Exact graph source | The `.ainl` file (or pinned Git commit). |
| Strict check output | `ainl check path/to/workflow.ainl --strict` (save stdout / CI log). |
| Optional IR snapshot | `ainl compile path/to/workflow.ainl -o bundle/ir.json` (or your CI artifact). |

## 2. HTTP runner structured audit (`ainl.runner`)

If you use **`scripts/runtime_runner_service.py`** (or equivalent) for `/run` / `/enqueue`:

1. Configure your process supervisor or container runtime to capture the Python logger **`ainl.runner`** at **INFO** to JSON or to stdout (see [`../operations/AUDIT_LOGGING.md`](../operations/AUDIT_LOGGING.md)).
2. Forward those events to your aggregator (Vector, Fluent Bit, CloudWatch Logs, Datadog Agent, Splunk Universal Forwarder, etc.).
3. Retention, immutability (Object Lock / WORM), and access control are **customer-owned** controls.

## 3. CLI trajectory JSONL (per-step execution)

For **`ainl run`** executions:

```bash
# Option A: explicit path
ainl run examples/hello.ainl --trace-jsonl evidence/hello-run.jsonl --json

# Option B: default path next to source
ainl run examples/hello.ainl --log-trajectory --json
# creates examples/hello.trajectory.jsonl
```

Trajectory lines are **not** the same schema as HTTP runner audit events—do not merge them in one SIEM pipeline without a transform.

### Verify `audit_trail` line hashes (optional)

If your JSONL file contains **`audit_trail`** adapter records (each line includes `event_hash`), verify integrity:

```bash
ainl audit verify-jsonl path/to/audit.jsonl
```

Exit code **0** if every `event_hash` line validates; **non-zero** if any line fails or JSON is invalid.

## 4. Optional app-level audit adapter

Enable **`audit_trail`** and a file sink when graphs must emit business-level events (see [`../tutorials/production_with_estimates_and_audit.md`](../tutorials/production_with_estimates_and_audit.md)):

```bash
export AINL_AUDIT_SINK=file:///var/log/ainl/audit.jsonl
ainl run workflow.ainl --enable-adapter audit_trail
```

Then include that file (or redacted export) in your evidence folder.

## 5. Optional observability metrics JSONL

When diagnosing adapter caps or runtime metrics (distinct from audit):

```bash
ainl run workflow.ainl --observability --observability-jsonl evidence/metrics.jsonl
# or set AINL_OBSERVABILITY=1 and AINL_OBSERVABILITY_JSONL
```

See `runtime/observability.py` and the telemetry map.

## 6. Sample log-shipper pointers (documentation only)

These are **patterns**, not supported products of the AINL repo:

- **Vector** / **Fluent Bit**: tail file or journald, parse JSON lines, ship to S3 / Splunk HEC / OpenSearch.
- **systemd journald**: capture stdout from a supervised `ainl-runner-service` unit; forward with your platform agent.

## 7. Procurement cross-links

- **Shared responsibility (canonical):** [`SHARED_RESPONSIBILITY.md`](SHARED_RESPONSIBILITY.md)
- **SOC 2 mapping starter:** [`SOC2_CHECKLIST.md`](SOC2_CHECKLIST.md)
- **Commercial (if applicable):** [`../../COMMERCIAL.md`](../../COMMERCIAL.md)
