# Real OpenClaw production savings (template)

This page is a **worksheet** for teams documenting **operational** AI workflows that use **AINL** through **OpenClaw** (or ZeroClaw / NemoClaw) MCP integration. Fill it with **your** anonymized numbers; do not invent statistics in public docs.

## What to measure

| Metric | Why it matters | How to capture |
|--------|----------------|----------------|
| **Tokens to author** (AINL vs hand-written Python/TS orchestration) | LLM generation cost for the workflow definition | Compare tokenizer counts on `.ainl` vs emitted or hand-written baseline; see **`BENCHMARK.md`** |
| **Tokens per recurring run** | Compile-once / run-many economics | Should trend to **zero** LLM tokens for pure graph execution (`ainl run` / runner / MCP execute) |
| **Strict compile success rate** | Reliability of generated programs | CI conformance + local `ainl-validate --strict` |
| **Incidents / fixes per month** | Operational stability | Your incident tracker |
| **Time to patch a monitor** | Maintainability | Wall time from issue → merged `.ainl` change |

## Suggested anonymized case block (copy-paste)

```text
Workload: [e.g. token budget monitor / infra watchdog / daily digest]
Hosts: OpenClaw MCP + [runner / bridge / cron]
Before: [prompt loop or hand-written orchestration — high level]
After: AINL strict-valid program + deterministic runtime
Authoring tokens (approx.): [N] (AINL) vs [M] (baseline)
Recurring runs / week: [R] — LLM tokens per run for orchestration: [0 or describe]
Notable outcome: [one sentence, no customer PII]
```

## Pointers

- **Unified monitoring guide:** [operations guide](../operations/UNIFIED_MONITORING_GUIDE.md)
- **OpenClaw integration:** [OPENCLAW_INTEGRATION](../OPENCLAW_INTEGRATION.md)
- **MCP host hub:** [HOST_MCP_INTEGRATIONS](../getting_started/HOST_MCP_INTEGRATIONS.md)
- **Evidence tables:** [BENCHMARK.md (repo root)](../../BENCHMARK.md), [benchmarks hub](../benchmarks.md)

## Related competitive docs

- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)**
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)**
- **[`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)** — methodology for head-to-head numbers
