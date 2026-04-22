# Retry with Exponential Backoff Pattern

> **ℹ️ TWO SYNTAX STYLES**: This document shows two AINL syntax styles:
> 1. **Compact syntax** (works now) — Python-like, recommended for new code.
>    See `examples/compact/` and `AGENTS.md` for the full reference.
> 2. **Graph block syntax** (`graph { node ... }`) — **DESIGN PREVIEW**, does
>    NOT compile. These blocks are labeled "Design Preview" below.
>
> Use compact syntax for real projects: `ainl validate <file> --strict`


Handle transient failures in external API calls with intelligent retry logic.

---

## 🎯 Use Case

You're calling an external API (HTTP, database, LLM) that occasionally fails due to:
- Network blips
- Rate limiting (429)
- Temporary service unavailability (5xx)

You want to:
- Retry automatically instead of failing the whole graph
- Wait longer between retries (backoff)
- Give up after reasonable attempts
- Log each retry attempt for observability

---

## 📐 Pattern Structure

```mermaid
graph TD
    A[Call API] --> B{Success?};
    B -->|Yes| C[Return result];
    B -->|No| D{Retryable?};
    D -->|Yes| E[Wait (backoff)];
    E --> A;
    D -->|No| F[Fail graph];
```

---

## 🏗️ Implementation

### Real AINL Syntax (v1.7.1 — this compiles)

```ainl
# retry_api.ainl — Retry HTTP call with backoff
# ainl validate retry_api.ainl --strict

S app core noop

L_call:
  R core.GET ctx "url" ->url
  R http.POST url {} ->resp
  R core.GET resp "status" ->status
  If (core.eq status 200) ->L_ok ->L_retry

L_retry:
  # Check attempt count
  R core.GET ctx "attempt" ->attempt
  X max_attempts 3
  If (core.gt attempt max_attempts) ->L_fail ->L_wait

L_wait:
  # Exponential backoff: sleep 1s * 2^attempt
  R core.mul 1000 (core.pow 2 attempt) ->delay_ms
  R core.sleep delay_ms ->_
  Set attempt (core.add attempt 1)
  Call L_call

L_ok:
  J resp

L_fail:
  Err "Max retries exceeded"
```

### Design Preview Syntax (AINL 2.0 — does NOT compile yet)

```ainl
graph RetryApiCall {
  input: Request = { url: string, payload: object }
  
  node call: HTTP("external-api") {
    method: POST
    url: input.url
    body: input.payload
    timeout: 10s
    # Note: retry logic is in wrapper below
  }
  
  node with_retry: retry(call) {
    max_attempts: 3
    backoff: "exponential"  # 1s, 2s, 4s
    retryable_codes: [429, 500, 502, 503]  # HTTP status codes
    on_retry: log_retry
  }
  
  node log_retry: WriteFile("retry-log") {
    path: "./logs/retries.jsonl"
    content: '{"attempt":{{retry.attempt}},"error":"{{retry.error}}","ts":"{{now}}"}'
    mode: append
  }
  
  output: with_retry.result
}
```

**Key elements**:
- `with_retry` wrapper node (built-in AINL construct)
- `max_attempts`: total tries = 1 initial + 2 retries = 3
- `backoff`: exponential means wait 1s, then 2s, then 4s
- `retryable_codes`: only retry on these HTTP status codes
- `on_retry`: optional action before each retry (here: log)

---

## 🔧 Retry Policies

### Backoff Strategies

| Strategy | Formula | Example (3 retries) |
|----------|---------|---------------------|
| Fixed | `wait = base_delay` | 1s, 1s, 1s |
| Exponential | `wait = base_delay * 2^attempt` | 1s, 2s, 4s |
| Linear | `wait = base_delay * attempt` | 1s, 2s, 3s |

**Recommendation**: Exponential with jitter to avoid thundering herd.

```ainl
node with_retry: retry(call) {
  backoff: "exponential"
  base_delay: 1s
  jitter: "random"  # ±25% randomness
}
```

---

## 🧪 Testing Retry Logic

### Simulate Failures

```python
from ainl.testing import MockAdapter, FailingMockAdapter

# Make first 2 calls fail, 3rd succeed
failing_mock = FailingMockAdapter(
    failures=2,
    success_response='{"ok": true}',
    failure_exception=RuntimeError("Service temporarily unavailable")
)

graph.get_node("call").adapter = failing_mock

result = graph.run(input_data)
assert result == {"ok": true}  # Eventually succeeds

# Verify retry count
assert failing_mock.call_count == 3
```

### Test Non-Retryable Errors

```python
# 400 Bad Request should not retry
error_mock = MockAdapter(
    status_code=400,
    response='{"error":"bad input"}'
)
graph.get_node("call").adapter = error_mock

with pytest.raises(GraphExecutionError):
    graph.run(input_data)

assert error_mock.call_count == 1  # No retries
```

---

## 📊 Observability

### Metrics to Track

- **Retry count** per node (how often are we retrying?)
- **Failure reasons** (rate limit vs 5xx vs network)
- **Cumulative latency** (including retry waits)
- **Success rate after retries** (eventual success rate)

**Prometheus queries**:

```promql
# Retries per minute
rate(ainl_retry_total[1m])

# Failure breakdown
sum by (error_type) (rate(ainl_node_failures_total[5m]))
```

---

## ⚙️ Production Tips

### 1. Set Reasonable Limits

- **Max attempts**: 3-5 (more = higher latency, more load)
- **Base delay**: 1s for interactive APIs, 5s for batch jobs
- **Total timeout**: Ensure `timeout` on node > sum(backoff delays)

### 2. Different Strategies per Error Type

```ainl
node with_retry: retry(call) {
  backoff: "exponential"
  retry_rules:
    - codes: [429]  # Rate limit
      max_attempts: 5
      base_delay: 2s
    - codes: [500, 502, 503]  # Server errors
      max_attempts: 3
      base_delay: 1s
    - codes: [408, 524]  # Timeouts
      max_attempts: 2
      base_delay: 3s
}
```

### 3. Circuit Breaker Pattern

After N consecutive failures, stop calling for a cool-down period:

```ainl
node call_with_circuit: circuit_breaker(call) {
  failure_threshold: 5
  cool_down: 60s
  on_open: log_circuit_open
}
```

---

## 🔄 Variations

### Parallel Retry (Fan-out)

If you have multiple independent API calls, retry each separately:

```ainl
graph ParallelFetch {
  node fetch_a: retry(HTTP("a")) { max_attempts: 3 }
  node fetch_b: retry(HTTP("b")) { max_attempts: 3 }
  node fetch_c: retry(HTTP("c")) { max_attempts: 3 }
  
  # These run in parallel
  output: { a: fetch_a.result, b: fetch_b.result, c: fetch_c.result }
}
```

---

## 🐛 Common Pitfalls

| Pitfall | Why Bad | Fix |
|---------|---------|-----|
| Infinite retries | Hang forever, no failure notice | Always set `max_attempts` |
| No jitter on backoff | All retries happen at same time → thundering herd | Add `jitter: "random"` |
| Retrying non-idempotent ops | Duplicate creates, double charges | Only idempotent ops should retry |
| Too many retries | High latency, API quota exhaustion | Keep max_attempts ≤ 5 |

---

## 📈 When to Use This Pattern

✅ **Do use**:
- External API calls (weather, payment, email)
- Database connections ( transient network issues)
- LLM API calls (rate limits, occasional 5xx)
- Any operation with known transient failure modes

❌ **Don't use**:
- Permanent failures (validation errors, 400s) – retry won't help
- Non-idempotent operations (create, delete) unless idempotency key
- User-facing interactive requests (retries make latency unpredictable)

---

## 📚 See Also

- [Testing Guide](../testing.md) – Test your retry logic thoroughly
- [Monitoring Guide](../monitoring.md) – Track retry metrics in production
- [Adapters Guide](../adapters/) – Configure adapter-level retries as fallback

---

**Build resilient systems that handle failure gracefully.**