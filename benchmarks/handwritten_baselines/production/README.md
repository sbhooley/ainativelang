# Production-grade baseline-B reference implementations

These files are the **production-grade** half of the baseline-B comparison set
used by [`scripts/benchmark_vs_hand_runner.py`](../../../scripts/benchmark_vs_hand_runner.py).
The **competent_python** half lives in [`../authoring_density/`](../authoring_density/).

## Honest disclosures (read before citing externally)

1. **These files are realistic runnable shape, not deployed code.** They were
   written specifically for the benchmark — to make the LOC / token-count /
   audit-checklist measurement defensible against the
   "you only counted skeleton code" critique. They have not been load-tested,
   security-audited, or run continuously in any production environment.

2. **What "production-grade" means here.** Each file ships the structural
   surface a senior engineer would write before shipping: typed retry/backoff
   wrapper, structured logging (`logging` module with JSON-friendly extras),
   metrics counter shim, configuration via environment + dataclass, explicit
   error types, circuit-breaker on the LLM call, request ID propagation, and a
   minimal hash-chained audit JSONL writer.

3. **What "production-grade" does NOT mean here.** No OTEL exporter, no real
   metrics backend (Prometheus / Datadog), no Sentry, no Kubernetes liveness
   probes, no secret rotation, no dead-letter queue. A real production worker
   adds 200–500 additional LOC for those concerns. The benchmark therefore
   *understates* the LOC delta against AINL on the audit / observability axis.

4. **Semantic equivalence to the AINL source is preserved.** All routing
   branches and LLM gates from each `.ainl` file are present. The harness
   verifies branch parity by counting `If`/`if`/`elif`/`else` clauses, but the
   authoritative check is reading the `.ainl` file side-by-side with each `.py`
   file.

## Files

| File                                 | AINL source                                                                   | Approx LOC |
| ------------------------------------ | ------------------------------------------------------------------------------ | ---------- |
| `enterprise_monitor.py`              | `examples/benchmark/enterprise_monitor.ainl`                                   | ~280       |
| `support_ticket_router.py`           | `examples/workflows/support_ticket_router.ainl`                                | ~330       |
| `data_pipeline.py`                   | `examples/workflows/data_pipeline.ainl`                                        | ~400       |

## How they get scored

`scripts/benchmark_vs_hand_runner.py` runs static analysis (regex-based
detection of: `class .*Retry`, `class CircuitBreaker`, `audit_jsonl`,
`hash_chain`, structured logger usage, etc.) and combines that with a manual
declaration block at the top of each file — the
`__benchmark_audit_checklist__` constant — to score the 8-row audit checklist
in [`VS_HAND_WRITTEN_RUNNER.md`](../../../docs/competitive/VS_HAND_WRITTEN_RUNNER.md).

If you remove an audit feature from one of these files, also update its
`__benchmark_audit_checklist__` block — the harness will not catch a lie there
because the JSON checklist is the declared score.
