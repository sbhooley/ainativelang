# AI Native Lang Size Benchmark

This benchmark measures AINL source compactness against generated implementation artifacts.
It is segmented by profile and mode; it is not a universal compactness claim across programming languages.

> **Sizing:** All markdown tables foreground **tiktoken** **cl100k_base** token counts (billing-accurate for GPT-4o-class models). JSON numeric fields still use the CLI `--metric`.
> **Emitters:** `prisma` and `react_ts` benchmark stubs were **compacted (Mar 2026)** for benchmark efficiency.
> **minimal_emit:** includes a tiny **python_api** async **fallback stub** when no selected target emits code.
> **Headline ratios:** **viable** subset for `public_mixed` / `compatibility_only` (legacy / pure-cron focus); **full legacy-inclusive** totals appear [below](#including-legacy-artifacts).

## Benchmark Profiles

- `canonical_strict_valid`: Primary public benchmark headline set (strict-valid canonical examples).
- `public_mixed`: Mixed public examples (strict-valid + non-strict-only), clearly labeled as mixed.
- `compatibility_only`: Compatibility-oriented examples only (non-strict/legacy classes). Not a headline set.

## Benchmark Modes

- `full_multitarget`: includes all benchmark targets for each artifact.
- `minimal_emit`: includes only capability-required targets for each artifact.

## Compiler IR Capability Contract

- `emit_capabilities.needs_python_api`: backend/API execution surface is required.
- `emit_capabilities.needs_react_ts`: frontend UI output is required.
- `emit_capabilities.needs_prisma`: schema/data model output is required.
- `emit_capabilities.needs_mt5`: MT5 strategy output is required.
- `emit_capabilities.needs_scraper`: scraper output is required.
- `emit_capabilities.needs_cron`: cron/scheduler output is required.
- `required_emit_targets.minimal_emit`: compiler-planned minimal target set (planner primary source).

## Metrics

- **Default / recommended:** `tiktoken` (**cl100k_base**) via `tooling/bench_metrics.py` (shared with runtime benchmarks).
- **Active CLI metric (JSON):** `tiktoken` — drives raw JSON sizes, economics basis, and viable-threshold comparisons where noted; markdown artifact tables still list **(tk)** for readability.
- **Compile ms (mean×3):** mean wall time of three ``compile(..., emit_graph=True)`` calls per artifact (see JSON ``compile_time_ms_mean``); unrelated to optional compile-reliability batches.
- **Economics:** estimated LLM $/run from token budgets (see JSON `economics`).

## How To Read These Results

- Ratio `> 1`: generated output is larger than AINL source.
- Ratio `~ 1`: near parity.
- Ratio `< 1`: generated output is smaller than AINL source.
- Summary and mode-comparison ratios in this document use **tiktoken** sums unless labeled otherwise; match them to the **(tk)** columns in detail tables.

## Full Multitarget vs Minimal Emit

- `full_multitarget` shows total downstream expansion potential across all emitters.
- `minimal_emit` is closer to practical deployment comparison because it emits only required targets.

## Why Some Ratios Got Worse After Truthfulness Fixes

- Ratios can worsen when examples are corrected to express capabilities they were already claiming publicly.
- This is expected: honest capability accounting increases counted generated output where prior under-emission existed.
- The result is less flattering but more trustworthy and action-guiding.

## What We Can Honestly Claim

- The benchmark is reproducible, profile-segmented, and mode-segmented.
- Minimal mode is the better comparison for practical deployment size discussions.
- Full mode is useful for measuring expansion leverage, not apples-to-apples terseness.

## What These Numbers Are Not

- They are not universal superiority claims over mainstream languages.
- They are not a substitute for measuring your own prompts: tiktoken counts are reproducible for this repo’s emitted text, but vendor tokenizers may differ slightly.
- They are not a proxy for runtime performance or product quality by themselves.

> **Viable subset (`public_mixed` / `compatibility_only`):** selection rules use the **CLI metric** (`tiktoken`) on JSON row fields — aggregate emit &lt; 50 (tiktoken units), large-source low-ratio heuristic (source ≥ 400, ratio &lt; 0.22), plus `viable_for_aggregate` overrides in `tooling/artifact_profiles.json`. **Markdown** headline ratios are recomputed in **tiktoken** for the same viable rows. Strict-valid rows in `public_mixed` stay viable. **Legacy-inclusive** totals: [Including Legacy Artifacts](#including-legacy-artifacts).

## Mode Comparison (Headline + Mixed)

| Profile | Full ratio (viable, tk) | Minimal ratio (viable, tk) | Viable artifacts |
|---|---:|---:|---|
| canonical_strict_valid | 6.60x | 1.62x | 12/12 |
| public_mixed | 0.95x | 0.80x | 62/75 |
| compatibility_only | 0.80x | 0.67x | 50/63 |

Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline.

## Size Drivers (Actionable Diagnosis)

- Values below are **tiktoken (tk)** on the same **viable** subset as headline drivers when applicable (CLI metric: `tiktoken`).

### full_multitarget
- `canonical_strict_valid` top targets (tk): mt5=2124, python_api=1151, scraper=1089
- `canonical_strict_valid` top artifacts (tk): examples/scraper/basic_scraper.ainl=591, examples/monitor_escalation.ainl=521, examples/web/basic_web_api.ainl=434
- `public_mixed` top targets (tk): mt5=11739, python_api=6113, scraper=5339
- `public_mixed` top artifacts (tk): examples/internal_tool.lang=787, examples/ticketing.lang=743, examples/ecom.lang=712
- `compatibility_only` top targets (tk): mt5=9615, python_api=4962, scraper=4250
- `compatibility_only` top artifacts (tk): examples/internal_tool.lang=787, examples/ticketing.lang=743, examples/ecom.lang=712

### minimal_emit
- `canonical_strict_valid` top targets (tk): python_api=961, cron=197, scraper=154
- `canonical_strict_valid` top artifacts (tk): examples/scraper/basic_scraper.ainl=253, examples/web/basic_web_api.ainl=106, examples/monitor_escalation.ainl=98
- `public_mixed` top targets (tk): python_api=2598, prisma=766, react_ts=667
- `public_mixed` top artifacts (tk): examples/internal_tool.lang=459, examples/ticketing.lang=419, examples/ecom.lang=394
- `compatibility_only` top targets (tk): python_api=1637, prisma=766, react_ts=667
- `compatibility_only` top artifacts (tk): examples/internal_tool.lang=459, examples/ticketing.lang=419, examples/ecom.lang=394

## Residual Overhead Audit (minimal_emit)

### canonical_strict_valid
- `python_api` total=961; structure: decorator_chunks=5, function_def_chunks=6, imports_chunks=70, return_chunks=6, total_chunks=961
- `cron` total=197; structure: function_def_chunks=11, pass_chunks=6, schedule_comment_chunks=180, total_chunks=197
- `scraper` total=154; structure: function_def_chunks=4, imports_chunks=11, request_call_chunks=18, return_chunks=17, selector_chunks=22, total_chunks=154

### public_mixed
- `python_api` total=2598; structure: decorator_chunks=103, function_def_chunks=120, imports_chunks=175, return_chunks=120, total_chunks=2598
- `prisma` total=766; structure: total_chunks=766
- `react_ts` total=667; structure: total_chunks=667

### compatibility_only
- `python_api` total=1637; structure: decorator_chunks=98, function_def_chunks=114, imports_chunks=105, return_chunks=114, total_chunks=1637
- `prisma` total=766; structure: total_chunks=766
- `react_ts` total=667; structure: total_chunks=667

## Details (full_multitarget)

| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |
|---|---:|---:|---:|---:|---:|
| canonical_strict_valid | 12 | 811 | 5353 | 6.60x | 0 |
| public_mixed | 62 | 31502 | 29843 | 0.95x | 13 |
| compatibility_only | 50 | 30691 | 24490 | 0.80x | 13 |

### canonical_strict_valid
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.506 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hello.ainl | strict-valid | 18 | 0.206 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 23.50x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.805 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.537 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.339 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.513 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 7.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.319 | 26 | 95 | 40 | 177 | 154 | 99 | 591 | 8.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.004210 |
| examples/status_branching.ainl | strict-valid | 48 | 0.460 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.021 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.63x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.700 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.65x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.258 | 26 | 106 | 40 | 177 | 85 | 0 | 434 | 13.56x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003097 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.581 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 6.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### public_mixed
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.634 | 26 | 128 | 76 | 219 | 85 | 0 | 534 | 4.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003810 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.064 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 2.20x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.841 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.38x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.195 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.986 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.818 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.25x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 1.507 | 26 | 95 | 73 | 210 | 85 | 0 | 489 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003482 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.806 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.37x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.054 | 26 | 95 | 66 | 197 | 85 | 0 | 469 | 0.73x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003340 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.762 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.74x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.177 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.621 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.75x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.441 | 26 | 95 | 127 | 257 | 85 | 0 | 590 | 0.28x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.004208 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.241 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.96x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.963 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 5.210 | 26 | 95 | 60 | 186 | 85 | 0 | 452 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003225 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.838 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.323 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.634 | 26 | 95 | 65 | 195 | 85 | 0 | 466 | 1.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003322 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.653 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.434 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.620 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.259 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/blog.lang | non-strict-only | 237 | 1.002 | 150 | 139 | 88 | 238 | 85 | 0 | 700 | 2.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.004987 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.489 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/crud_api.ainl | strict-valid | 37 | 0.474 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecom.lang | non-strict-only | 238 | 0.863 | 186 | 128 | 80 | 233 | 85 | 0 | 712 | 2.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005078 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.142 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.052 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.34x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.137 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.36x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.346 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.22x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.150 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.270 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.92x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.332 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.80x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.958 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.94x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.480 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.39x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.203 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.675 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 3.744 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.45x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.207 | 26 | 95 | 81 | 197 | 85 | 0 | 484 | 0.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003450 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 2.982 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.682 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.947 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.707 | 26 | 95 | 82 | 199 | 85 | 0 | 487 | 0.58x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003475 |
| examples/hello.ainl | strict-valid | 18 | 0.209 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 23.50x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.852 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.718 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.87x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.743 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.759 | 148 | 128 | 85 | 243 | 85 | 98 | 787 | 3.47x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005605 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.527 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.241 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.88x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.804 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.554 | 26 | 95 | 78 | 192 | 85 | 0 | 476 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.005 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 1.68x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.187 | 26 | 95 | 101 | 227 | 85 | 0 | 534 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.003810 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.967 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 3.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.839 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 1.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.945 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.15x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.330 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.12x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.297 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.11x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.437 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.50x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.315 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.68x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.256 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.55x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.936 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.669 | 26 | 107 | 62 | 211 | 85 | 0 | 491 | 1.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003498 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.653 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.04x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.394 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.500 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 7.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.326 | 26 | 95 | 40 | 177 | 154 | 99 | 591 | 8.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.004210 |
| examples/status_branching.ainl | strict-valid | 48 | 0.481 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ticketing.lang | non-strict-only | 274 | 1.192 | 183 | 152 | 84 | 239 | 85 | 0 | 743 | 2.71x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005298 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.346 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.63x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 3.100 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.65x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.280 | 26 | 106 | 40 | 177 | 85 | 0 | 434 | 13.56x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003097 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.670 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 6.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### compatibility_only
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.631 | 26 | 128 | 76 | 219 | 85 | 0 | 534 | 4.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003810 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.048 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 2.20x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 6.520 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.38x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.326 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 5.349 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.962 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.25x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.883 | 26 | 95 | 73 | 210 | 85 | 0 | 489 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003482 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.522 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.37x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 0.995 | 26 | 95 | 66 | 197 | 85 | 0 | 469 | 0.73x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003340 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.775 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.74x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.153 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.708 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.75x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.413 | 26 | 95 | 127 | 257 | 85 | 0 | 590 | 0.28x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.004208 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.304 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.96x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.964 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.378 | 26 | 95 | 60 | 186 | 85 | 0 | 452 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003225 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 2.580 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.283 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.684 | 26 | 95 | 65 | 195 | 85 | 0 | 466 | 1.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003322 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.795 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.356 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.709 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.258 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/blog.lang | non-strict-only | 237 | 0.973 | 150 | 139 | 88 | 238 | 85 | 0 | 700 | 2.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.004987 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.511 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/ecom.lang | non-strict-only | 238 | 0.897 | 186 | 128 | 80 | 233 | 85 | 0 | 712 | 2.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005078 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.149 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.080 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.34x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.205 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.36x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.347 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.22x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.267 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.274 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.92x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.360 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.80x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.994 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.94x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.585 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.39x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.235 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.208 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 4.530 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.45x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.359 | 26 | 95 | 81 | 197 | 85 | 0 | 484 | 0.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003450 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.018 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.824 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 3.016 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.930 | 26 | 95 | 82 | 199 | 85 | 0 | 487 | 0.58x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003475 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.716 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.87x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.700 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.836 | 148 | 128 | 85 | 243 | 85 | 98 | 787 | 3.47x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005605 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.235 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.88x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.772 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.620 | 26 | 95 | 78 | 192 | 85 | 0 | 476 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.056 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 1.68x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.095 | 26 | 95 | 101 | 227 | 85 | 0 | 534 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.003810 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.912 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 3.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.932 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 1.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.458 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.15x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.139 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.12x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.269 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.11x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.915 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.50x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.399 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.68x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.246 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.55x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.954 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.622 | 26 | 107 | 62 | 211 | 85 | 0 | 491 | 1.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003498 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.691 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.04x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ticketing.lang | non-strict-only | 274 | 1.238 | 183 | 152 | 84 | 239 | 85 | 0 | 743 | 2.71x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005298 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

## Details (minimal_emit)

| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |
|---|---:|---:|---:|---:|---:|
| canonical_strict_valid | 12 | 811 | 1312 | 1.62x | 0 |
| public_mixed | 32 | 5705 | 4578 | 0.80x | 43 |
| compatibility_only | 20 | 4894 | 3266 | 0.67x | 43 |

### canonical_strict_valid
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.507 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/hello.ainl | strict-valid | 18 | 0.200 | — | 95 | — | — | — | — | 95 | 5.28x | python_api |  | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.793 | — | 95 | — | — | — | — | 95 | 1.14x | python_api |  | 0.000678 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.594 | — | — | — | — | — | 98 | 98 | 1.36x | cron |  | 0.000705 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.351 | — | 95 | — | — | — | — | 95 | 3.28x | python_api |  | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.478 | — | 95 | — | — | — | — | 95 | 1.76x | python_api |  | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.312 | — | — | — | — | 154 | 99 | 253 | 3.78x | scraper, cron |  | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.510 | — | 95 | — | — | — | — | 95 | 1.98x | python_api |  | 0.000678 |
| examples/timeout_demo.ainl | strict-valid | 49 | 1.966 | — | 95 | — | — | — | — | 95 | 1.94x | python_api |  | 0.000678 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.736 | — | 95 | — | — | — | — | 95 | 0.37x | python_api |  | 0.000678 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.237 | — | 106 | — | — | — | — | 106 | 3.31x | python_api |  | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.568 | — | 95 | — | — | — | — | 95 | 1.44x | python_api |  | 0.000678 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### public_mixed
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.657 | — | 128 | 76 | — | — | — | 204 | 1.91x | python_api, prisma | (compacted prisma emitter) | 0.001455 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.091 | — | 34 | — | — | — | 0 | 34 | 0.18x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.815 | — | — | — | — | — | 98 | 98 | 0.07x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.324 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 5.057 | — | — | — | — | — | 98 | 98 | 0.04x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.827 | — | — | 69 | — | — | — | 69 | 0.18x | prisma | (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.905 | — | — | 73 | — | — | — | 73 | 0.18x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000520 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.722 | — | — | — | — | — | 99 | 99 | 0.07x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.841 | — | — | 66 | — | — | — | 66 | 0.10x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000472 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.774 | — | 34 | — | — | — | 0 | 34 | 0.14x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.181 | — | 95 | — | — | — | — | 95 | 0.18x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.656 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.339 | — | — | 127 | — | — | 0 | 127 | 0.06x | prisma, cron | (legacy excluded from viable) | 0.000902 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.205 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.075 | — | — | 69 | — | — | — | 69 | 0.15x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.562 | — | 95 | 60 | — | — | — | 155 | 0.15x | python_api, prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.001105 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.876 | — | — | — | — | — | 99 | 99 | 0.10x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.308 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.654 | — | — | 65 | — | — | — | 65 | 0.22x | prisma | (compacted prisma emitter) | 0.000467 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.621 | — | — | — | — | — | 98 | 98 | 0.10x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.423 | — | — | — | — | — | 98 | 98 | 0.09x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.753 | — | — | — | — | — | 98 | 98 | 0.08x | cron | (legacy excluded from viable) | 0.000705 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.245 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/blog.lang | non-strict-only | 237 | 0.979 | 150 | 139 | 88 | — | — | — | 377 | 1.59x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002687 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.519 | — | — | — | — | — | 98 | 98 | 1.34x | cron |  | 0.000705 |
| examples/crud_api.ainl | strict-valid | 37 | 0.476 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/ecom.lang | non-strict-only | 238 | 0.954 | 186 | 128 | 80 | — | — | — | 394 | 1.66x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002812 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.077 | — | 95 | — | — | — | — | 95 | 0.28x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.151 | — | 95 | — | — | — | — | 95 | 0.30x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.058 | — | 95 | — | — | — | — | 95 | 0.31x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.465 | — | 95 | — | — | — | — | 95 | 0.27x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.232 | — | 95 | — | — | — | — | 95 | 0.23x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.260 | — | 95 | — | — | — | — | 95 | 0.21x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.371 | — | 34 | — | — | — | 0 | 34 | 0.06x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.915 | — | 34 | — | — | — | 0 | 34 | 0.08x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.506 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.273 | — | 34 | — | — | — | 0 | 34 | 0.05x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.232 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 3.629 | — | 34 | — | — | — | 0 | 34 | 0.04x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 3.070 | — | — | 81 | — | — | 0 | 81 | 0.14x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000580 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.052 | — | — | 78 | — | — | 0 | 78 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.818 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.849 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.861 | — | — | 82 | — | — | 0 | 82 | 0.10x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000585 |
| examples/hello.ainl | strict-valid | 18 | 0.207 | — | 95 | — | — | — | — | 95 | 5.28x | python_api |  | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.816 | — | 95 | — | — | — | — | 95 | 1.14x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.714 | — | 95 | — | — | — | — | 95 | 0.42x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.735 | — | 95 | — | — | — | — | 95 | 0.39x | python_api |  | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.788 | 148 | 128 | 85 | — | — | 98 | 459 | 2.02x | react_ts, python_api, prisma, cron | (compacted prisma emitter) | 0.003272 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.566 | — | — | — | — | — | 98 | 98 | 1.36x | cron |  | 0.000705 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.230 | — | 95 | — | — | — | — | 95 | 0.87x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.776 | — | 95 | — | — | — | — | 95 | 0.27x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.504 | — | — | 78 | — | — | 0 | 78 | 0.16x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.170 | — | — | 78 | — | — | 0 | 78 | 0.28x | prisma, cron | (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.280 | — | — | 101 | — | — | 0 | 101 | 0.18x | prisma, cron | (legacy excluded from viable) | 0.000723 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.882 | — | — | 79 | — | — | 0 | 79 | 0.54x | prisma, cron | (compacted prisma emitter) | 0.000565 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.833 | — | — | 79 | — | — | 0 | 79 | 0.19x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.399 | — | 34 | — | — | — | 0 | 34 | 0.09x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.102 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.253 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.372 | — | 95 | — | — | — | — | 95 | 0.79x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.364 | — | 95 | — | — | — | — | 95 | 0.15x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.277 | — | 95 | — | — | — | — | 95 | 0.80x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 1.598 | — | 95 | — | — | — | — | 95 | 0.23x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.652 | — | 107 | 62 | — | — | — | 169 | 0.55x | python_api, prisma | (compacted prisma emitter) | 0.001203 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.620 | — | 95 | — | — | — | — | 95 | 1.13x | python_api |  | 0.000678 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.331 | — | 95 | — | — | — | — | 95 | 3.28x | python_api |  | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.476 | — | 95 | — | — | — | — | 95 | 1.76x | python_api |  | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.382 | — | — | — | — | 154 | 99 | 253 | 3.78x | scraper, cron |  | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.468 | — | 95 | — | — | — | — | 95 | 1.98x | python_api |  | 0.000678 |
| examples/ticketing.lang | non-strict-only | 274 | 1.081 | 183 | 152 | 84 | — | — | — | 419 | 1.53x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002988 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.085 | — | 95 | — | — | — | — | 95 | 1.94x | python_api |  | 0.000678 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.672 | — | 95 | — | — | — | — | 95 | 0.37x | python_api |  | 0.000678 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.225 | — | 106 | — | — | — | — | 106 | 3.31x | python_api |  | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.574 | — | 95 | — | — | — | — | 95 | 1.44x | python_api |  | 0.000678 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### compatibility_only
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.660 | — | 128 | 76 | — | — | — | 204 | 1.91x | python_api, prisma | (compacted prisma emitter) | 0.001455 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.033 | — | 34 | — | — | — | 0 | 34 | 0.18x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.924 | — | — | — | — | — | 98 | 98 | 0.07x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.352 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.978 | — | — | — | — | — | 98 | 98 | 0.04x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.847 | — | — | 69 | — | — | — | 69 | 0.18x | prisma | (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.835 | — | — | 73 | — | — | — | 73 | 0.18x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000520 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.738 | — | — | — | — | — | 99 | 99 | 0.07x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.085 | — | — | 66 | — | — | — | 66 | 0.10x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000472 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.739 | — | 34 | — | — | — | 0 | 34 | 0.14x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.210 | — | 95 | — | — | — | — | 95 | 0.18x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.666 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.426 | — | — | 127 | — | — | 0 | 127 | 0.06x | prisma, cron | (legacy excluded from viable) | 0.000902 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.251 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.057 | — | — | 69 | — | — | — | 69 | 0.15x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.494 | — | 95 | 60 | — | — | — | 155 | 0.15x | python_api, prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.001105 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.849 | — | — | — | — | — | 99 | 99 | 0.10x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.373 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.638 | — | — | 65 | — | — | — | 65 | 0.22x | prisma | (compacted prisma emitter) | 0.000467 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 4.421 | — | — | — | — | — | 98 | 98 | 0.10x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.373 | — | — | — | — | — | 98 | 98 | 0.09x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.743 | — | — | — | — | — | 98 | 98 | 0.08x | cron | (legacy excluded from viable) | 0.000705 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.244 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/blog.lang | non-strict-only | 237 | 1.084 | 150 | 139 | 88 | — | — | — | 377 | 1.59x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002687 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.491 | — | — | — | — | — | 98 | 98 | 1.34x | cron |  | 0.000705 |
| examples/ecom.lang | non-strict-only | 238 | 0.811 | 186 | 128 | 80 | — | — | — | 394 | 1.66x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002812 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.171 | — | 95 | — | — | — | — | 95 | 0.28x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.036 | — | 95 | — | — | — | — | 95 | 0.30x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.192 | — | 95 | — | — | — | — | 95 | 0.31x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.423 | — | 95 | — | — | — | — | 95 | 0.27x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.142 | — | 95 | — | — | — | — | 95 | 0.23x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.213 | — | 95 | — | — | — | — | 95 | 0.21x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.327 | — | 34 | — | — | — | 0 | 34 | 0.06x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.855 | — | 34 | — | — | — | 0 | 34 | 0.08x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.522 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.253 | — | 34 | — | — | — | 0 | 34 | 0.05x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.118 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 3.769 | — | 34 | — | — | — | 0 | 34 | 0.04x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.399 | — | — | 81 | — | — | 0 | 81 | 0.14x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000580 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.890 | — | — | 78 | — | — | 0 | 78 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.765 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.922 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.878 | — | — | 82 | — | — | 0 | 82 | 0.10x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000585 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.773 | — | 95 | — | — | — | — | 95 | 0.42x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.701 | — | 95 | — | — | — | — | 95 | 0.39x | python_api |  | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.831 | 148 | 128 | 85 | — | — | 98 | 459 | 2.02x | react_ts, python_api, prisma, cron | (compacted prisma emitter) | 0.003272 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.236 | — | 95 | — | — | — | — | 95 | 0.87x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.760 | — | 95 | — | — | — | — | 95 | 0.27x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.426 | — | — | 78 | — | — | 0 | 78 | 0.16x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.150 | — | — | 78 | — | — | 0 | 78 | 0.28x | prisma, cron | (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.232 | — | — | 101 | — | — | 0 | 101 | 0.18x | prisma, cron | (legacy excluded from viable) | 0.000723 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.901 | — | — | 79 | — | — | 0 | 79 | 0.54x | prisma, cron | (compacted prisma emitter) | 0.000565 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.838 | — | — | 79 | — | — | 0 | 79 | 0.19x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.409 | — | 34 | — | — | — | 0 | 34 | 0.09x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.111 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.313 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.373 | — | 95 | — | — | — | — | 95 | 0.79x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.369 | — | 95 | — | — | — | — | 95 | 0.15x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.240 | — | 95 | — | — | — | — | 95 | 0.80x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.928 | — | 95 | — | — | — | — | 95 | 0.23x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.570 | — | 107 | 62 | — | — | — | 169 | 0.55x | python_api, prisma | (compacted prisma emitter) | 0.001203 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.666 | — | 95 | — | — | — | — | 95 | 1.13x | python_api |  | 0.000678 |
| examples/ticketing.lang | non-strict-only | 274 | 1.096 | 183 | 152 | 84 | — | — | — | 419 | 1.53x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002988 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*


## Handwritten baseline size comparison

**AINL emitted** aggregates use the active benchmark metric (`tiktoken`) and, when available, **tiktoken** (**cl100k_base**) on the same emitted bundle. **Pure / Lang** columns count only `pure_async_python.py` / `langgraph_version.py` in each group.

### Emit mode `minimal_emit`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 253 | 253 | 92 | 88 | 870 | 738 | 0.29x | 0.34x | 0.001803 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 95 | 95 | 71 | 77 | 700 | 754 | 0.14x | 0.13x | 0.000678 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 34 | 34 | 159 | 163 | 1584 | 1624 | 0.02x | 0.02x | 0.000247 | 0.022860 |

### Emit mode `full_multitarget`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 591 | 591 | 92 | 88 | 870 | 738 | 0.68x | 0.80x | 0.004210 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 423 | 423 | 71 | 77 | 700 | 754 | 0.60x | 0.56x | 0.003018 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 423 | 423 | 159 | 163 | 1584 | 1624 | 0.27x | 0.26x | 0.003018 | 0.022860 |


## Including Legacy Artifacts

Legacy files (pure-cron shells, OpenClaw micro-wrappers, aggregate emit below the viable threshold, or paths marked `viable_for_aggregate: false`) are **still compiled and listed** in the per-artifact tables; they are **excluded only** from the **viable** summary rows above for `public_mixed` and `compatibility_only`. Canonical strict-valid profile totals are unchanged (all viable).

### full_multitarget — legacy-inclusive totals

| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 12 | 811 | 5353 | 6.60x |
| public_mixed | 75 | 35477 | 35395 | 1.00x |
| compatibility_only | 63 | 34666 | 30042 | 0.87x |

*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*

### minimal_emit — legacy-inclusive totals

| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 12 | 811 | 1312 | 1.62x |
| public_mixed | 75 | 35477 | 7873 | 0.22x |
| compatibility_only | 63 | 34666 | 6561 | 0.19x |

*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*

<!-- RUNTIME_BENCH_START -->
## Runtime Performance

Automated wall-clock and RSS measurements from ``scripts/benchmark_runtime.py`` using ``RuntimeEngine`` (graph-preferred). Latencies are **run_label** only after compile; compile time is averaged over 3 compiles per artifact.

- Generated (UTC): `2026-03-21T20:12:31.172217+00:00`
- Warm-up runs: **8**; timed runs per artifact: **20**
- Graph execution mode: `graph-preferred`
- **Source tokens:** ``ainl_source_tiktoken`` uses ``tooling/bench_metrics.tiktoken_count`` (**cl100k_base**).

| Profile | Artifacts | OK | Mean of per-artifact mean latency (ms) |
|---|---:|---:|---:|
| canonical_strict_valid (full_multitarget) | 12 | 7 | 0.20581279428110325 |
| canonical_strict_valid (minimal_emit) | 12 | 7 | 0.20617380754889122 |

### Sample: headline profile artifacts (mean run latency ms)

| Artifact | Class | src tk | compile ms (mean×3) | mean | p50 | p95 | min | max | RSS Δ MB | adapter calls || est `gpt-4o` USD/run || Reliability |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---||---:||---|
| examples/crud_api.ainl | strict-valid | 37 | 0.60 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.047 | 0 | 0.000265 | 100% σ=0.01ms |
| examples/hello.ainl | strict-valid | 18 | 0.25 | 0.01 | 0.01 | 0.02 | 0.01 | 0.07 | 0.031 | 1 | 0.000135 | 100% σ=0.00ms |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.93 | 0.04 | 0.04 | 0.04 | 0.04 | 0.07 | 0.016 | 1 | 0.000595 | 100% σ=0.01ms |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.40 | 0.02 | 0.02 | 0.02 | 0.02 | 0.03 | 0.000 | 1 | 0.000205 | 100% σ=0.00ms |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.53 | 0.03 | 0.03 | 0.03 | 0.02 | 0.04 | 0.000 | 3 | 0.000390 | 100% σ=0.00ms |
| examples/status_branching.ainl | strict-valid | 48 | 0.57 | 0.02 | 0.02 | 0.03 | 0.02 | 0.03 | 0.000 | 0 | 0.000345 | 100% σ=0.00ms |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.34 | 1.30 | 1.30 | 1.32 | 1.20 | 1.33 | 0.016 | 2 | 0.000347 | 100% σ=0.02ms |
| examples/crud_api.ainl | strict-valid | 37 | 0.59 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 0 | 0.000265 | 100% σ=0.00ms |
| examples/hello.ainl | strict-valid | 18 | 0.25 | 0.01 | 0.01 | 0.02 | 0.01 | 0.06 | 0.000 | 1 | 0.000135 | 100% σ=0.00ms |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.97 | 0.04 | 0.04 | 0.04 | 0.04 | 0.08 | 0.000 | 1 | 0.000595 | 100% σ=0.01ms |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.55 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 1 | 0.000205 | 100% σ=0.00ms |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.57 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.016 | 3 | 0.000390 | 100% σ=0.00ms |
| examples/status_branching.ainl | strict-valid | 48 | 0.59 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 0 | 0.000345 | 100% σ=0.01ms |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.38 | 1.30 | 1.30 | 1.31 | 1.29 | 1.32 | 0.000 | 2 | 0.000347 | 100% σ=0.01ms |

**LLM counters:** reserved for future agent/OpenAI adapter lanes; JSON ``llm_token_usage`` is **N/A** unless adapters report usage.

JSON: ``tooling/benchmark_runtime_results.json``
<!-- RUNTIME_BENCH_END -->
<!-- BASELINE_RUNTIME_BENCH_START -->
### Handwritten baseline runtime comparison

Mapped AINL rows use the **headline** profile from ``full_multitarget`` when that artifact appears in the current ``--profile-name`` selection. Handwritten runs use mocks; **adapter_calls** are N/A (no ``RuntimeEngine``). Costs use mapped **AINL source** tiktokens / combined handwritten ``.py`` sources with JSON ``economics`` assumptions.

| Workflow | AINL src tk | AINL mean (ms) | Pure mean (ms) | Lang mean (ms) | AINL RSS Δ | Pure RSS Δ | Lang RSS Δ | AINL/Pure | AINL/Lang | AINL `gpt-4o` USD | HW `gpt-4o` USD | AINL Rel | Pure Rel | Lang Rel | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| basic_scraper | 67 | — | 0.035 | 1.726 | — | 0.000 | 0.094 | — | — | 0.000475 | 0.011460 | 0% σ=0.00ms | 100% σ=0.00ms | 100% σ=0.12ms | Artifact not in current profile selection or runtime failed. |
| retry_timeout_wrapper | 54 | 0.026 | 1.284 | 4.039 | 0.000 | 0.000 | 0.016 | 0.02x | 0.01x | 0.000390 | 0.010365 | 100% σ=0.00ms | 100% σ=0.01ms | 100% σ=0.12ms | — |
| token_budget_monitor | 1047 | — | 0.213 | 4.309 | — | 0.000 | 0.078 | — | — | 0.007457 | 0.022860 | — | 100% σ=0.05ms | 100% σ=0.27ms | Artifact not in current profile selection or runtime failed. |
<!-- BASELINE_RUNTIME_BENCH_END -->
## Supported vs Unsupported Claims

- Supported: profile- and mode-scoped compactness comparisons for this benchmark setup.
- Supported: canonical strict-valid as primary headline profile.
- Unsupported: universal compactness claims versus Python/TypeScript/Rust/Go.
- Unsupported: treating **approx_chunks** or **nonempty_lines** JSON runs as exact OpenAI billing without cross-checking tiktoken.
- Note: source-text fallback remains as temporary legacy support for older IRs missing capability metadata.

## Recommended Next Benchmark Improvements

- Handwritten baselines live under `benchmarks/handwritten_baselines/`; use `--compare-baselines` on size/runtime scripts for tables vs mapped AINL artifacts.
- Add CI trend snapshots for both full and minimal modes.
- Optional: snapshot secondary `--metric` lanes (e.g. `nonempty_lines`) for structure-only regressions.

Conclusion: strongest current claim is compactness in canonical multi-target examples; language-surface changes are not required for these benchmark gains.

Selection source: `tooling/artifact_profiles.json`; planning source: `tooling/benchmark_manifest.json`.
