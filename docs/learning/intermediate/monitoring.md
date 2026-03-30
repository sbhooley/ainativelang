# Monitoring & Observability

> **ℹ️ TWO SYNTAX STYLES**: This document shows two AINL syntax styles:
> 1. **Compact syntax** (works now) — Python-like, recommended for new code.
>    See `examples/compact/` and `AGENTS.md` for the full reference.
> 2. **Graph block syntax** (`graph { node ... }`) — **DESIGN PREVIEW**, does
>    NOT compile. These blocks are labeled "Design Preview" below.
>
> Use compact syntax for real projects: `ainl validate <file> --strict`


Track running AINL graphs: health, performance, costs, and errors.

---

## 📊 The Three Pillars

1. **Health** – Is the graph alive and processing?
2. **Metrics** – Latency, token usage, success rates
3. **Traces** – Per-execution audit logs for debugging

---

## 1️⃣ Health Checking

AINL graphs can expose a health endpoint for liveness/readiness probes.

### Enable Health Server

```bash
ainl run monitor.ainl --health-port 9090
```

Starts HTTP server:
- `GET /health/live` – Returns 200 if process is alive
- `GET /health/ready` – Returns 200 if graph validated and adapters connected
- `GET /health/metrics` – Prometheus-format metrics (optional)

**Kubernetes example**:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 9090
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 9090
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## 2️⃣ Metrics Collection

AINL reports counters and gauges to Prometheus via `/metrics`.

### Available Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ainl_executions_total` | counter | graph, result | Total graph executions (result=success/failure) |
| `ainl_execution_duration_seconds` | histogram | graph | Execution time distribution |
| `ainl_tokens_used_total` | counter | graph, kind (llm/orchestration) | Token consumption |
| `ainl_cost_usd_total` | counter | graph, adapter | LLM API costs |
| `ainl_nodes_total` | gauge | graph, node, status | Nodes completed/failed |

### Prometheus Config

```yaml
scrape_configs:
  - job_name: 'ainl'
    static_configs:
      - targets: ['localhost:9090']
```

### Grafana Dashboard

Import pre-built dashboard JSON from `docs/monitoring/grafana-dashboard.json` (coming soon).

Key panels:
- Graph success rate (SLA)
- P99 latency per node
- Token spend over time
- Cost per execution

---

## 3️⃣ Execution Traces (Audit Logs)

The **most important** feature for compliance.

### Enable Tracing

```bash
ainl run monitor.ainl \
  --trace-jsonl /var/log/ainl/traces/$(date +%s).jsonl \
  --trace-retention-days 90
```

Each line is a JSON event:

```json
{
  "timestamp": "2025-03-30T14:22:15.123Z",
  "graph": "monitor",
  "execution_id": "abc-123-def",
  "node": "classify",
  "phase": "completed",
  "duration_ms": 1245,
  "tokens_used": 245,
  "cost_usd": 0.000612,
  "input": {"prompt": "Classify: DB timeout..."},
  "output": {"result": "CRITICAL"},
  "error": null,
  "traceparent": "00-...-..."  // OpenTelemetry compatible
}
```

### Trace Schema

See `docs/reference/trace-schema.json` for full spec.

Key fields:
- `execution_id`: UUID linking all events from same run
- `phase`: `started` | `completed` | `failed`
- `parent_id`: For nested calls (when node invokes sub-graph)
- `attributes`: Arbitrary key-value for custom data

---

## 📈 Alerting Strategies

### High Error Rate

```promql
# Alert if >5% of executions fail in last 5 min
rate(ainl_executions_total{result="failure"}[5m]) /
rate(ainl_executions_total[5m]) > 0.05
```

### Cost Spike

```promql
# Alert if hourly spend > $100
sum(rate(ainl_cost_usd_total[1h])) * 3600 > 100
```

### Latency SLA breach

```promql
# Alert if P95 latency > 5s
histogram_quantile(0.95, rate(ainl_execution_duration_seconds_bucket[5m])) > 5
```

### Node Failure Pattern

```promql
# Alert if specific node fails >10 times in 2 min
increase(ainl_nodes_total{node="send_slack",status="failed"}[2m]) > 10
```

---

## 🔄 Centralized Logging

Ship traces to a central system (Loki, Datadog, Splunk).

### Fluentd Example

```xml
<source>
  @type tail
  path /var/log/ainl/traces/*.jsonl
  pos_file /var/log/ainl/traces/fluentd.pos
  tag ainl.traces
  <parse>
    @type json
  </parse>
</source>

<match ainl.traces>
  @type elasticsearch
  host localhost
  port 9200
  index_name ainl-traces
  <inject>
    time_key time
    time_type string
    time_format %Y-%m-%dT%H:%M:%S.%NZ
  </inject>
</match>
```

---

## 🧩 Health Envelope (Advanced)

Combine health metrics with traces for full observability.

AINL can emit a **health envelope** every N executions:

```yaml
# ainl.yaml
monitoring:
  health_envelope:
    enabled: true
    every_n_executions: 100
    send_to: "https://monitor.ainativelang.com/health"
    api_key: ${HEALTH_ENVELOPE_KEY}
```

Envelope includes:
- Last N execution summaries
- Token usage statistics
- Error rate
- Custom metrics from nodes (if configured)

Enterprise hosted runtimes provide this out of the box.

---

## 🐛 Debugging with Traces

### Find Slow Node

```bash
# Extract all node completion events
jq 'select(.phase=="completed")' traces.jsonl | \
  jq -r '"\(.node)\t\(.duration_ms)"' | \
  sort -k2 -n -r | head -10
```

### Replay a Failing Execution

```bash
# Find execution ID from logs
grep '"execution_id":"abc-123' traces.jsonl | head -1

# Replay in debugger
ainl replay monitor.ainl --execution-id abc-123 --debug
```

### Correlate with Application Logs

If your app logs a request ID, pass it as an attribute:

```ainl
node classify: LLM("classify") {
  attributes: {
    request_id: "${env.REQUEST_ID}"
  }
}
```

Then trace and app log share `request_id`.

---

## 📊 Dashboard Templates

### Basic Grafana Dashboard (JSON)

Import from `docs/monitoring/grafana-basic.json`:
- Top row: Overall health (executions/sec, error rate)
- Middle row: Cost and token usage
- Bottom row: Top 5 slowest nodes

### Enterprise Dashboard (Coming Soon)

- Multi-tenant views
- SLA compliance tracking
- Cost allocation per team/department
- Automated compliance reports

---

## ✅ Production Checklist

- [ ] Health endpoints exposed (`--health-port`)
- [ ] Traces stored in durable storage (not just local disk)
- [ ] Prometheus scraping metrics endpoint
- [ ] Alerts configured for error rate, cost, latency
- [ ] Grafana dashboards created and shared with team
- [ ] Log retention policy meets compliance needs (usually 90 days minimum)
- [ ] Trace data scrubbed of PII before storage (use `--trace-filter`)

---

## 🎯 Best Practices

1. **Never run without traces** in production (`--trace-jsonl` mandatory)
2. **Rotate logs** – use `logrotate` or cloud storage lifecycle
3. **Filter PII** – configure `trace.fields_to_redact` in config
4. **Aggregate metrics** – send to central Prometheus, not per-host
5. **Set budgets** – Alert on cost thresholds, not just usage

---

## 🔗 Related

- [STRICT_VALIDATION_AND_COMPLIANCE.md](../../docs/validation-deep-dive.md) – Compliance patterns
- [Self-Monitoring Guide](../../intelligence/monitor/README.md) – AINL monitoring itself
- [Trace Schema Reference](../../reference/trace-schema.md) – Full JSON spec

---

**Monitor everything, sleep soundly!** →