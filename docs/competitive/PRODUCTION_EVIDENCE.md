# Production evidence (committed operator worksheets)

Anonymized **field** evidence for public review. This is not a substitute for **`BENCHMARK.md`** analytical scenarios — it documents **what operators actually run** and **what changed**.

**Machine-readable mirror:** [`tooling/production_evidence.json`](../../tooling/production_evidence.json)

**Worksheet template:** [`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md)

---

## Honest scope disclosure (read this first)

We classify every row below using a four-class scheme so reviewers can tell field reports from modeled scenarios at a glance:

| Class | Meaning |
|-------|---------|
| **(a)** | Third-party paying customer deployment with measurable $/token outcome |
| **(b)** | Operator (project author or close collaborator) deployment with real logs / accounting |
| **(c)** | Modeled / analytical scenario authored as a reference case |
| **(d)** | Marketing narrative without a specific deployment |

**Class (a) third-party customer deployments: 0 (none committed yet, as of 2026-05-19).**

The three rows below are honestly labeled with their class. We are actively working to land the first **Class (a)** row — tracked publicly in [`LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md) row **T2.7**. Pilot template and instrumentation kit are tracked under **T2.4–T2.6**.

If you are reading this looking for "show me a customer who saved $X" and the table below does not yet contain a Class (a) row: **we agree that gap matters and we are not pretending it is filled.** Please open a conversation if you want to be the first published deployment — instrumentation cost is small and we will help.

The companion benchmark scenarios in `BENCHMARK.md` and [`tooling/compile_once_run_many_results.json`](../../tooling/compile_once_run_many_results.json) are **Class (c)** modeled work — reproducible on any machine, honest about assumptions ([`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) baseline A/B/C). They are not a substitute for Class (a) and we do not present them as one.

---

## Case 1 — OpenClaw daily token budget monitor (deterministic runtime)

**Classification:** **(b)** Operator deployment — shipped and running, but on the project author's own OpenClaw stack, not an external paying customer.

| Field | Value |
|-------|-------|
| **Workload** | Daily token/cache budget digest + optional cache prune |
| **Source** | [`openclaw/bridge/wrappers/token_budget_alert.ainl`](../../openclaw/bridge/wrappers/token_budget_alert.ainl) |
| **Host** | OpenClaw bridge cron (`0 23 * * *`) + bridge adapters (`token_budget_*`, `monitor_cache_*`, `openclaw_memory`, `queue`) |
| **Before (counterfactual)** | Prompt-loop agent re-invoked daily to decide thresholds, prune policy, digest text, and notify queue |
| **After** | Compiled AINL graph; **`ainl run`** / bridge wrapper executes IR deterministically |
| **LLM orchestration tokens / run** | **0** (bridge + core + cache/queue only) |
| **LLM content tokens / run** | **0** |
| **Recurring runs** | **~30/month** (daily) |
| **Strict compile** | Passes with bridge adapter grant |
| **Notable outcome** | Monitor logic is versioned `.ainl` with duplicate-run sentinel (`token_report_today_sent`); no model re-planning on schedule |
| **Evidence type** | Shipped wrapper in repo + LangGraph equivalence test in [`benchmarks/handwritten_baselines/token_budget_monitor/`](../../benchmarks/handwritten_baselines/token_budget_monitor/) |

**Analytical companion (prompt-loop vs compiled, 2880 runs/mo health-check class):** [`tooling/compile_once_run_many_results.json`](../../tooling/compile_once_run_many_results.json) → `enterprise_monitor` → **96.2%** orchestration-token savings vs modeled prompt-loop baseline (not vs hand-written bash).

---

## Case 2 — OpenClaw gateway lifetime usage (architectural efficiency)

**Classification:** **(b)** Operator deployment — real measured tokens on the project author's OpenClaw gateway, paired with **(c)** counterfactual pricing. **Actual cash spent: $0.00** (free-tier OpenRouter routing). The "$220.59" and "$661.77" figures are *avoided* counterfactual costs at Opus rates, not money that changed hands.

| Field | Value |
|-------|-------|
| **Workload** | User-facing LLM traffic via OpenClaw gateway (chat, tools, recurring agent tasks) |
| **Host** | OpenClaw + OpenRouter (free-tier routing) + AINL for workflow/monitor orchestration |
| **Data period** | Lifetime through **2026-03-27** (see report) |
| **Measured tokens (user-facing)** | **10,501,100** total (2,097,000 in / 8,404,100 out) — internal monitor tokens excluded |
| **Actual spend** | **$0.00** (free OpenRouter models for bulk traffic) |
| **Counterfactual (Claude Opus via OpenRouter)** | **~$220.59** |
| **Counterfactual (Anthropic direct Opus)** | **~$661.77** |
| **Architectural efficiency multiplier (conservative)** | **~2.5×** fewer tokens vs equivalent prompt-loop agent architecture |
| **Implied avoided cost (efficiency only, OpenRouter Opus rates)** | **~$300–$550** band on top of free-model routing |
| **Evidence type** | Field report [`agent_reports/2026-03-27-ainl-cost-savings.md`](../../agent_reports/2026-03-27-ainl-cost-savings.md) — gateway log parsing + OpenRouter pricing snapshot |
| **Caveats** | Mixes **model-choice** savings (free tier) with **architecture** savings; not an isolated A/B of a single cron job; see report §1.4 |

---

## Case 3 — Enterprise HTTP monitor (modeled production scale)

**Classification:** **(c)** Modeled / analytical scenario. Reproducible via `python scripts/benchmark_compile_once_run_many.py`. This row is **not** a deployment — it is a benchmark scenario that demonstrates what *would* happen if a hypothetical operator with the workload below adopted AINL vs a prompt-loop baseline.

| Field | Value |
|-------|-------|
| **Workload** | HTTP health check every 5 minutes with LLM alert only on incident |
| **Source** | [`examples/benchmark/enterprise_monitor.ainl`](../../examples/benchmark/enterprise_monitor.ainl) |
| **Host** | **`ainl run`** / runner / ArmaraOS scheduled Hand (representative deployment pattern) |
| **Before (modeled prompt-loop)** | 2 LLM orchestration calls/run even when healthy |
| **After (compiled AINL)** | **0** LLM tokens on healthy polls (~90% of runs in scenario) |
| **Recurring runs** | **2,880/month** (5-minute cadence) |
| **Modeled orchestration savings** | **96.2%** ([`compile_once_run_many_results.json`](../../tooling/compile_once_run_many_results.json)) |
| **Modeled $/month (GPT-4o blended $0.003/1K, orchestration only)** | AINL **~$0.04** vs prompt-loop **~$0.92** |
| **Evidence type** | **Analytical** — reproducible via `python scripts/benchmark_compile_once_run_many.py` |
| **Not valid vs** | Hand-written `curl && python route.py` runner (baseline B/C) |

---

## How to add a row

1. Copy the table block in [`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md).
2. Append to this file and [`tooling/production_evidence.json`](../../tooling/production_evidence.json) — **include `classification` field (a/b/c/d)**.
3. Update [`COMPARISON_TABLE.md`](COMPARISON_TABLE.md) §G.
4. Link from [`CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) §6.
5. **If the row is Class (a):** bump `external_paying_customer_count` in `tooling/production_evidence.json` and update the disclosure block at the top of this file.

**Do not** commit customer PII, API keys, or raw logs.

---

## Related

- **[`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md)** — baseline A/B/C honest filter
- **[`VS_HAND_WRITTEN_RUNNER.md`](VS_HAND_WRITTEN_RUNNER.md)** — five-axis comparison vs a hand-written Python runner
- **[`ARMARAOS_GTM.md`](ARMARAOS_GTM.md)** — primary GTM wedge when raw AINL vs cron is a weak sell
- **[`LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md)** — visible roadmap for the Class (a) gap
- **[`CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md)** — claim crosswalk
