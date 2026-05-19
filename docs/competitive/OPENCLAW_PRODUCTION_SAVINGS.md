# Real OpenClaw production savings (worksheet + filled examples)

This page is a **worksheet** for teams documenting **operational** AI workflows that use **AINL** through **OpenClaw** (or ZeroClaw / NemoClaw) MCP integration. Fill it with **your** anonymized numbers; do not invent statistics in public docs.

**Committed examples:** **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)** · **[`tooling/production_evidence.json`](../../tooling/production_evidence.json)**

---

## What to measure

| Metric | Why it matters | How to capture |
|--------|----------------|----------------|
| **Tokens to author** (AINL vs hand-written Python/TS orchestration) | LLM generation cost for the workflow definition | Compare tokenizer counts on `.ainl` vs emitted or hand-written baseline; see **`BENCHMARK.md`** |
| **Tokens per recurring run** | Compile-once / run-many economics | Should trend to **zero** LLM tokens for pure graph execution (`ainl run` / runner / MCP execute) |
| **Strict compile success rate** | Reliability of generated programs | CI conformance + local `ainl-validate --strict` |
| **Incidents / fixes per month** | Operational stability | Your incident tracker |
| **Time to patch a monitor** | Maintainability | Wall time from issue → merged `.ainl` change |
| **Your baseline** | Honest savings attribution | See **[`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md)** — hand-optimized runners cap routing wins at ~**1.3–1.5×** |

---

## Filled example — OpenClaw token budget monitor (Case 1)

```text
Workload: Daily token/cache budget digest + optional cache prune
Hosts: OpenClaw bridge cron + bridge adapters (token_budget_*, monitor_cache_*, openclaw_memory, queue)
Source: openclaw/bridge/wrappers/token_budget_alert.ainl
Before: Prompt-loop agent re-invoked daily to decide thresholds, prune policy, digest text, notify queue
After: Compiled AINL graph; ainl run / bridge wrapper executes IR deterministically
Authoring tokens (approx.): see examples/benchmark + bridge wrapper (strict-valid path)
Recurring runs / week: ~7 (daily cron)
LLM orchestration tokens / run (after): 0
LLM content tokens / run (after): 0
Notable outcome: Versioned .ainl with duplicate-run sentinel; no model re-planning on schedule
Evidence: PRODUCTION_EVIDENCE.md Case 1; LangGraph baseline in benchmarks/handwritten_baselines/token_budget_monitor/
```

---

## Filled example — OpenClaw gateway lifetime (Case 2)

```text
Workload: User-facing LLM traffic via OpenClaw gateway (chat, tools, recurring agent tasks)
Hosts: OpenClaw + OpenRouter (free-tier routing) + AINL workflow/monitor orchestration
Before: Equivalent prompt-loop agent architecture on paid Claude Opus (counterfactual)
After: AINL compile-once workflows + free-tier model routing
Measured user-facing tokens (lifetime through 2026-03-27): 10,501,100 total (2.1M in / 8.4M out)
Actual spend: $0.00 (free OpenRouter models)
Counterfactual Claude Opus (OpenRouter rates): ~$220.59
Architectural efficiency multiplier (conservative): ~2.5× vs prompt-loop architecture
Notable outcome: Mixes model-choice savings with architectural efficiency — see agent_reports/2026-03-27-ainl-cost-savings.md
Caveat: Not an isolated A/B of one cron job; read report §1.4 before citing dollar figures
```

---

## Suggested anonymized case block (copy-paste for new rows)

```text
Workload: [e.g. token budget monitor / infra watchdog / daily digest]
Hosts: OpenClaw MCP + [runner / bridge / cron / ArmaraOS Hand]
Baseline: [A prompt-loop | B hand-optimized script | C pure deterministic]
Before: [describe orchestration pattern]
After: AINL strict-valid program + deterministic runtime
Authoring tokens (approx.): [N] (AINL) vs [M] (baseline)
Recurring runs / week: [R] — LLM orchestration tokens per run: [0 or describe]
Notable outcome: [one sentence, no customer PII]
```

---

## Pointers

- **When AINL does not help:** [WHEN_AINL_DOES_NOT_HELP.md](WHEN_AINL_DOES_NOT_HELP.md)
- **ArmaraOS product wedge:** [ARMARAOS_GTM.md](ARMARAOS_GTM.md)
- **Unified monitoring guide:** [operations guide](../operations/UNIFIED_MONITORING_GUIDE.md)
- **OpenClaw integration:** [OPENCLAW_INTEGRATION](../OPENCLAW_INTEGRATION.md)
- **MCP host hub:** [HOST_MCP_INTEGRATIONS](../getting_started/HOST_MCP_INTEGRATIONS.md)
- **Evidence tables:** [BENCHMARK.md (repo root)](../../BENCHMARK.md), [benchmarks hub](../benchmarks.md)

## Related competitive docs

- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)**
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)**
- **[`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)** — methodology for head-to-head numbers
- **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)** — committed case tables
