# AI Native Lang Size Benchmark

This benchmark measures AINL source compactness against generated implementation artifacts.
It is segmented by profile and mode; it is not a universal compactness claim across programming languages.

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

- Active metric: `tiktoken` (default **tiktoken** / **cl100k_base**).
- `tiktoken` uses `tooling/bench_metrics.py` (shared with runtime benchmarks).
- **Compile ms (mean×3):** mean wall time of three ``compile(..., emit_graph=True)`` calls per artifact (see JSON ``compile_time_ms_mean``); unrelated to optional compile-reliability batches.
- **Economics:** estimated LLM $/run from token budgets (see JSON `economics`).

## How To Read These Results

- Ratio `> 1`: generated output is larger than AINL source.
- Ratio `~ 1`: near parity.
- Ratio `< 1`: generated output is smaller than AINL source.
- `approx_chunks` is a useful lexical proxy, not exact LLM token billing.

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
- They are not guaranteed tokenizer-cost or LLM pricing results in `approx_chunks` mode.
- They are not a proxy for runtime performance or product quality by themselves.

## Mode Comparison (Headline + Mixed)

| Profile | Full aggregate ratio | Minimal aggregate ratio |
|---|---:|---:|
| canonical_strict_valid | 11.67x | 2.22x |
| public_mixed | 1.34x | 0.33x |
| compatibility_only | 1.15x | 0.29x |

Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline.

## Size Drivers (Actionable Diagnosis)

### full_multitarget
- `canonical_strict_valid` top targets: mt5=1770, prisma=1120, python_api=961
- `canonical_strict_valid` top artifacts: examples/scraper/basic_scraper.ainl=731, examples/monitor_escalation.ainl=661, examples/web/basic_web_api.ainl=574
- `public_mixed` top targets: mt5=11223, prisma=7704, react_ts=6373
- `public_mixed` top artifacts: examples/internal_tool.lang=993, examples/ticketing.lang=967, examples/ecom.lang=935
- `compatibility_only` top targets: mt5=9453, prisma=6584, react_ts=5433
- `compatibility_only` top artifacts: examples/internal_tool.lang=993, examples/ticketing.lang=967, examples/ecom.lang=935

### minimal_emit
- `canonical_strict_valid` top targets: python_api=771, cron=197, scraper=154
- `canonical_strict_valid` top artifacts: examples/scraper/basic_scraper.ainl=253, examples/web/basic_web_api.ainl=106, examples/monitor_escalation.ainl=98
- `public_mixed` top targets: prisma=3896, python_api=2598, cron=1278
- `public_mixed` top artifacts: examples/internal_tool.lang=665, examples/ticketing.lang=643, examples/ecom.lang=617
- `compatibility_only` top targets: prisma=3896, python_api=1827, react_ts=1203
- `compatibility_only` top artifacts: examples/internal_tool.lang=665, examples/ticketing.lang=643, examples/ecom.lang=617

## Residual Overhead Audit (minimal_emit)

### canonical_strict_valid
- `python_api` total=771; structure: decorator_chunks=5, function_def_chunks=6, imports_chunks=56, return_chunks=6, total_chunks=771
- `cron` total=197; structure: function_def_chunks=11, pass_chunks=6, schedule_comment_chunks=180, total_chunks=197
- `scraper` total=154; structure: function_def_chunks=4, imports_chunks=11, request_call_chunks=18, return_chunks=17, selector_chunks=22, total_chunks=154

### public_mixed
- `prisma` total=3896; structure: total_chunks=3896
- `python_api` total=2598; structure: decorator_chunks=103, function_def_chunks=120, imports_chunks=175, return_chunks=120, total_chunks=2598
- `cron` total=1278; structure: function_def_chunks=66, pass_chunks=39, schedule_comment_chunks=1173, total_chunks=1278

### compatibility_only
- `prisma` total=3896; structure: total_chunks=3896
- `python_api` total=1827; structure: decorator_chunks=98, function_def_chunks=114, imports_chunks=119, return_chunks=114, total_chunks=1827
- `react_ts` total=1203; structure: total_chunks=1203

## Details (full_multitarget)

| Profile | Artifact count | AINL source total | Aggregate generated output total | Aggregate ratio |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 10 | 506 | 5907 | 11.67x |
| public_mixed | 59 | 28065 | 37490 | 1.34x |
| compatibility_only | 49 | 27559 | 31583 | 1.15x |

### canonical_strict_valid
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.572 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 15.22x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/hello.ainl | strict-valid | 18 | 0.184 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 31.28x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.619 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 6.78x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.583 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 9.18x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.338 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 19.41x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.397 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 10.43x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.320 | 94 | 95 | 112 | 177 | 154 | 99 | 731 | 10.91x | react_ts, python_api, prisma, mt5, scraper, cron | 0.005208 |
| examples/status_branching.ainl | strict-valid | 48 | 0.461 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 11.73x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.214 | 94 | 106 | 112 | 177 | 85 | 0 | 574 | 17.94x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004095 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.514 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 8.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |

### public_mixed
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.541 | 94 | 128 | 155 | 219 | 85 | 0 | 681 | 6.36x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004855 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 0.918 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.93x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 4.752 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.033 | 94 | 95 | 142 | 202 | 85 | 0 | 618 | 0.99x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004410 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.231 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.30x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.733 | 94 | 95 | 143 | 204 | 85 | 0 | 621 | 1.62x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.783 | 94 | 95 | 147 | 210 | 85 | 0 | 631 | 1.56x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004495 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.062 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 0.47x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 0.882 | 94 | 95 | 140 | 197 | 85 | 0 | 611 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004352 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 220 | 0.386 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 3.01x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 498 | 0.963 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 1.33x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.366 | 94 | 95 | 142 | 202 | 85 | 0 | 618 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004410 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 12.753 | 94 | 95 | 213 | 257 | 85 | 0 | 744 | 0.35x | react_ts, python_api, prisma, mt5, scraper, cron | 0.005302 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 0.967 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.790 | 94 | 95 | 143 | 204 | 85 | 0 | 621 | 1.37x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 3.358 | 94 | 95 | 135 | 186 | 85 | 0 | 595 | 0.57x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004240 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.448 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 0.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.077 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.63x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.573 | 94 | 95 | 139 | 195 | 85 | 0 | 608 | 2.08x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004335 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 2.978 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 1.964 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.142 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.52x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/blog.lang | non-strict-only | 237 | 0.801 | 275 | 139 | 170 | 238 | 85 | 0 | 907 | 3.83x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006468 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.426 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 9.05x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/crud_api.ainl | strict-valid | 37 | 0.380 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 15.22x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/ecom.lang | non-strict-only | 238 | 0.806 | 329 | 128 | 160 | 233 | 85 | 0 | 935 | 3.93x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006663 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 1.920 | 94 | 95 | 159 | 197 | 85 | 0 | 630 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004492 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 2.424 | 94 | 95 | 156 | 191 | 85 | 0 | 621 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.136 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.302 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.832 | 94 | 95 | 160 | 199 | 85 | 0 | 633 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004510 |
| examples/hello.ainl | strict-valid | 18 | 0.162 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 31.28x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.683 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 6.78x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.538 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.49x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.636 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.34x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.613 | 273 | 128 | 166 | 243 | 85 | 98 | 993 | 4.37x | react_ts, python_api, prisma, mt5, scraper, cron | 0.007075 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.404 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 9.18x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.205 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 5.17x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.714 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 2.617 | 94 | 95 | 156 | 192 | 85 | 0 | 622 | 1.28x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004432 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 1.563 | 94 | 95 | 156 | 191 | 85 | 0 | 621 | 2.19x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 2.468 | 94 | 95 | 183 | 227 | 85 | 0 | 684 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004875 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.673 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 4.24x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.164 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 1.49x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 1.849 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 349 | 0.941 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 361 | 0.889 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.56x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.325 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 4.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.099 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 0.90x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.197 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 4.73x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.817 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.35x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.252 | 94 | 107 | 138 | 211 | 85 | 0 | 635 | 2.08x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004525 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.270 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 19.41x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.366 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 10.43x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.279 | 94 | 95 | 112 | 177 | 154 | 99 | 731 | 10.91x | react_ts, python_api, prisma, mt5, scraper, cron | 0.005208 |
| examples/status_branching.ainl | strict-valid | 48 | 0.383 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 11.73x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/ticketing.lang | non-strict-only | 274 | 0.891 | 326 | 152 | 165 | 239 | 85 | 0 | 967 | 3.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006895 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.183 | 94 | 106 | 112 | 177 | 85 | 0 | 574 | 17.94x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004095 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.437 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 8.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |

### compatibility_only
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.498 | 94 | 128 | 155 | 219 | 85 | 0 | 681 | 6.36x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004855 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 0.863 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.93x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 4.538 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.116 | 94 | 95 | 142 | 202 | 85 | 0 | 618 | 0.99x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004410 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.301 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.30x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.714 | 94 | 95 | 143 | 204 | 85 | 0 | 621 | 1.62x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.732 | 94 | 95 | 147 | 210 | 85 | 0 | 631 | 1.56x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004495 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.135 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 0.47x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 0.900 | 94 | 95 | 140 | 197 | 85 | 0 | 611 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004352 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 220 | 0.373 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 3.01x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 498 | 1.126 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 1.33x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.409 | 94 | 95 | 142 | 202 | 85 | 0 | 618 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004410 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 12.742 | 94 | 95 | 213 | 257 | 85 | 0 | 744 | 0.35x | react_ts, python_api, prisma, mt5, scraper, cron | 0.005302 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 0.972 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.939 | 94 | 95 | 143 | 204 | 85 | 0 | 621 | 1.37x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 3.232 | 94 | 95 | 135 | 186 | 85 | 0 | 595 | 0.57x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004240 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.443 | 94 | 95 | 112 | 177 | 85 | 99 | 662 | 0.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004718 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 0.987 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.63x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.632 | 94 | 95 | 139 | 195 | 85 | 0 | 608 | 2.08x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004335 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.038 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 1.955 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.220 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 0.52x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/blog.lang | non-strict-only | 237 | 0.739 | 275 | 139 | 170 | 238 | 85 | 0 | 907 | 3.83x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006468 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.446 | 94 | 95 | 112 | 177 | 85 | 98 | 661 | 9.05x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004712 |
| examples/ecom.lang | non-strict-only | 238 | 0.686 | 329 | 128 | 160 | 233 | 85 | 0 | 935 | 3.93x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006663 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 1.880 | 94 | 95 | 159 | 197 | 85 | 0 | 630 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004492 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 2.342 | 94 | 95 | 156 | 191 | 85 | 0 | 621 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.245 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.388 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 0.87x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.303 | 94 | 95 | 160 | 199 | 85 | 0 | 633 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004510 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.545 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.49x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.652 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 2.34x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.739 | 273 | 128 | 166 | 243 | 85 | 98 | 993 | 4.37x | react_ts, python_api, prisma, mt5, scraper, cron | 0.007075 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.189 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 5.17x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.725 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.454 | 94 | 95 | 156 | 192 | 85 | 0 | 622 | 1.28x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004432 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 1.571 | 94 | 95 | 156 | 191 | 85 | 0 | 621 | 2.19x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004428 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 2.364 | 94 | 95 | 183 | 227 | 85 | 0 | 684 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004875 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.803 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 4.24x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.318 | 94 | 95 | 157 | 192 | 85 | 0 | 623 | 1.49x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004443 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 1.867 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 349 | 0.947 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.61x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 361 | 0.894 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.56x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.398 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 4.65x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.074 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 0.90x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.197 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 4.73x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.766 | 94 | 95 | 112 | 177 | 85 | 0 | 563 | 1.35x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004015 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.190 | 94 | 107 | 138 | 211 | 85 | 0 | 635 | 2.08x | react_ts, python_api, prisma, mt5, scraper, cron | 0.004525 |
| examples/ticketing.lang | non-strict-only | 274 | 1.075 | 326 | 152 | 165 | 239 | 85 | 0 | 967 | 3.53x | react_ts, python_api, prisma, mt5, scraper, cron | 0.006895 |

## Details (minimal_emit)

| Profile | Artifact count | AINL source total | Aggregate generated output total | Aggregate ratio |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 10 | 506 | 1122 | 2.22x |
| public_mixed | 59 | 28065 | 9129 | 0.33x |
| compatibility_only | 49 | 27559 | 8007 | 0.29x |

### canonical_strict_valid
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.373 | - | 95 | - | - | - | - | 95 | 2.57x | python_api | 0.000678 |
| examples/hello.ainl | strict-valid | 18 | 0.169 | - | 95 | - | - | - | - | 95 | 5.28x | python_api | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.701 | - | 95 | - | - | - | - | 95 | 1.14x | python_api | 0.000678 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.430 | - | - | - | - | - | 98 | 98 | 1.36x | cron | 0.000705 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.301 | - | 95 | - | - | - | - | 95 | 3.28x | python_api | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.402 | - | 95 | - | - | - | - | 95 | 1.76x | python_api | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.327 | - | - | - | - | 154 | 99 | 253 | 3.78x | scraper, cron | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.362 | - | 95 | - | - | - | - | 95 | 1.98x | python_api | 0.000678 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.177 | - | 106 | - | - | - | - | 106 | 3.31x | python_api | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.431 | - | 95 | - | - | - | - | 95 | 1.44x | python_api | 0.000678 |

### public_mixed
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.481 | - | 128 | 155 | - | - | - | 283 | 2.64x | python_api, prisma | 0.002020 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 0.902 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 4.441 | - | - | - | - | - | 98 | 98 | 0.07x | cron | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.035 | - | - | 142 | - | - | - | 142 | 0.23x | prisma | 0.001012 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.329 | - | - | - | - | - | 98 | 98 | 0.04x | cron | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.775 | - | - | 143 | - | - | - | 143 | 0.37x | prisma | 0.001022 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.886 | - | - | 147 | - | - | - | 147 | 0.36x | prisma | 0.001045 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.200 | - | - | - | - | - | 99 | 99 | 0.07x | cron | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 0.903 | - | - | 140 | - | - | - | 140 | 0.22x | prisma | 0.000997 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 220 | 0.384 | - | - | - | - | - | 99 | 99 | 0.45x | cron | 0.000708 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 498 | 0.969 | - | - | - | - | - | 98 | 98 | 0.20x | cron | 0.000705 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.295 | - | - | 142 | - | - | - | 142 | 0.23x | prisma | 0.001012 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 12.559 | - | - | 213 | - | - | 0 | 213 | 0.10x | prisma, cron | 0.001517 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.065 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.807 | - | - | 143 | - | - | - | 143 | 0.31x | prisma | 0.001022 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 3.414 | - | 95 | 135 | - | - | - | 230 | 0.22x | python_api, prisma | 0.001643 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.496 | - | - | - | - | - | 99 | 99 | 0.10x | cron | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.044 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.506 | - | - | 139 | - | - | - | 139 | 0.47x | prisma | 0.000992 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 2.823 | - | - | - | - | - | 98 | 98 | 0.10x | cron | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 1.821 | - | - | - | - | - | 98 | 98 | 0.09x | cron | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.196 | - | - | - | - | - | 98 | 98 | 0.08x | cron | 0.000705 |
| examples/blog.lang | non-strict-only | 237 | 0.732 | 275 | 139 | 170 | - | - | - | 584 | 2.46x | react_ts, python_api, prisma | 0.004163 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.395 | - | - | - | - | - | 98 | 98 | 1.34x | cron | 0.000705 |
| examples/crud_api.ainl | strict-valid | 37 | 0.406 | - | 95 | - | - | - | - | 95 | 2.57x | python_api | 0.000678 |
| examples/ecom.lang | non-strict-only | 238 | 0.824 | 329 | 128 | 160 | - | - | - | 617 | 2.59x | react_ts, python_api, prisma | 0.004398 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 1.774 | - | - | 159 | - | - | 0 | 159 | 0.27x | prisma, cron | 0.001135 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 2.404 | - | - | 156 | - | - | 0 | 156 | 0.22x | prisma, cron | 0.001118 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.236 | - | - | 157 | - | - | 0 | 157 | 0.22x | prisma, cron | 0.001120 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.466 | - | - | 157 | - | - | 0 | 157 | 0.22x | prisma, cron | 0.001120 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.737 | - | - | 160 | - | - | 0 | 160 | 0.19x | prisma, cron | 0.001140 |
| examples/hello.ainl | strict-valid | 18 | 0.157 | - | 95 | - | - | - | - | 95 | 5.28x | python_api | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.589 | - | 95 | - | - | - | - | 95 | 1.14x | python_api | 0.000678 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.536 | - | 95 | - | - | - | - | 95 | 0.42x | python_api | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.568 | - | 95 | - | - | - | - | 95 | 0.39x | python_api | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.580 | 273 | 128 | 166 | - | - | 98 | 665 | 2.93x | react_ts, python_api, prisma, cron | 0.004743 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.408 | - | - | - | - | - | 98 | 98 | 1.36x | cron | 0.000705 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.192 | - | 95 | - | - | - | - | 95 | 0.87x | python_api | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.729 | - | 95 | - | - | - | - | 95 | 0.27x | python_api | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 2.921 | - | - | 156 | - | - | 0 | 156 | 0.32x | prisma, cron | 0.001118 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 1.699 | - | - | 156 | - | - | 0 | 156 | 0.55x | prisma, cron | 0.001118 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 2.443 | - | - | 183 | - | - | 0 | 183 | 0.32x | prisma, cron | 0.001308 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.718 | - | - | 157 | - | - | 0 | 157 | 1.07x | prisma, cron | 0.001120 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.254 | - | - | 157 | - | - | 0 | 157 | 0.37x | prisma, cron | 0.001120 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.244 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 349 | 0.986 | - | 95 | - | - | - | - | 95 | 0.27x | python_api | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 361 | 1.102 | - | 95 | - | - | - | - | 95 | 0.26x | python_api | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.362 | - | 95 | - | - | - | - | 95 | 0.79x | python_api | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.165 | - | 95 | - | - | - | - | 95 | 0.15x | python_api | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.210 | - | 95 | - | - | - | - | 95 | 0.80x | python_api | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.824 | - | 95 | - | - | - | - | 95 | 0.23x | python_api | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.258 | - | 107 | 138 | - | - | - | 245 | 0.80x | python_api, prisma | 0.001750 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.319 | - | 95 | - | - | - | - | 95 | 3.28x | python_api | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.441 | - | 95 | - | - | - | - | 95 | 1.76x | python_api | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.255 | - | - | - | - | 154 | 99 | 253 | 3.78x | scraper, cron | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.419 | - | 95 | - | - | - | - | 95 | 1.98x | python_api | 0.000678 |
| examples/ticketing.lang | non-strict-only | 274 | 0.926 | 326 | 152 | 165 | - | - | - | 643 | 2.35x | react_ts, python_api, prisma | 0.004585 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.176 | - | 106 | - | - | - | - | 106 | 3.31x | python_api | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.440 | - | 95 | - | - | - | - | 95 | 1.44x | python_api | 0.000678 |

### compatibility_only
| Artifact | Class | AINL source | Compile ms (mean×3) | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.511 | - | 128 | 155 | - | - | - | 283 | 2.64x | python_api, prisma | 0.002020 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 0.927 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 4.833 | - | - | - | - | - | 98 | 98 | 0.07x | cron | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.037 | - | - | 142 | - | - | - | 142 | 0.23x | prisma | 0.001012 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 4.074 | - | - | - | - | - | 98 | 98 | 0.04x | cron | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.720 | - | - | 143 | - | - | - | 143 | 0.37x | prisma | 0.001022 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.719 | - | - | 147 | - | - | - | 147 | 0.36x | prisma | 0.001045 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.049 | - | - | - | - | - | 99 | 99 | 0.07x | cron | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 0.831 | - | - | 140 | - | - | - | 140 | 0.22x | prisma | 0.000997 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 220 | 0.441 | - | - | - | - | - | 99 | 99 | 0.45x | cron | 0.000708 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 498 | 0.932 | - | - | - | - | - | 98 | 98 | 0.20x | cron | 0.000705 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.297 | - | - | 142 | - | - | - | 142 | 0.23x | prisma | 0.001012 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 12.493 | - | - | 213 | - | - | 0 | 213 | 0.10x | prisma, cron | 0.001517 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 0.977 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.864 | - | - | 143 | - | - | - | 143 | 0.31x | prisma | 0.001022 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 3.538 | - | 95 | 135 | - | - | - | 230 | 0.22x | python_api, prisma | 0.001643 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.724 | - | - | - | - | - | 99 | 99 | 0.10x | cron | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 0.952 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.531 | - | - | 139 | - | - | - | 139 | 0.47x | prisma | 0.000992 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.107 | - | - | - | - | - | 98 | 98 | 0.10x | cron | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 1.968 | - | - | - | - | - | 98 | 98 | 0.09x | cron | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.309 | - | - | - | - | - | 98 | 98 | 0.08x | cron | 0.000705 |
| examples/blog.lang | non-strict-only | 237 | 0.744 | 275 | 139 | 170 | - | - | - | 584 | 2.46x | react_ts, python_api, prisma | 0.004163 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.407 | - | - | - | - | - | 98 | 98 | 1.34x | cron | 0.000705 |
| examples/ecom.lang | non-strict-only | 238 | 0.756 | 329 | 128 | 160 | - | - | - | 617 | 2.59x | react_ts, python_api, prisma | 0.004398 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 1.776 | - | - | 159 | - | - | 0 | 159 | 0.27x | prisma, cron | 0.001135 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 2.293 | - | - | 156 | - | - | 0 | 156 | 0.22x | prisma, cron | 0.001118 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.188 | - | - | 157 | - | - | 0 | 157 | 0.22x | prisma, cron | 0.001120 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.325 | - | - | 157 | - | - | 0 | 157 | 0.22x | prisma, cron | 0.001120 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.193 | - | - | 160 | - | - | 0 | 160 | 0.19x | prisma, cron | 0.001140 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.578 | - | 95 | - | - | - | - | 95 | 0.42x | python_api | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.632 | - | 95 | - | - | - | - | 95 | 0.39x | python_api | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.601 | 273 | 128 | 166 | - | - | 98 | 665 | 2.93x | react_ts, python_api, prisma, cron | 0.004743 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.226 | - | 95 | - | - | - | - | 95 | 0.87x | python_api | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.710 | - | 95 | - | - | - | - | 95 | 0.27x | python_api | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 2.712 | - | - | 156 | - | - | 0 | 156 | 0.32x | prisma, cron | 0.001118 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 1.629 | - | - | 156 | - | - | 0 | 156 | 0.55x | prisma, cron | 0.001118 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 2.561 | - | - | 183 | - | - | 0 | 183 | 0.32x | prisma, cron | 0.001308 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.721 | - | - | 157 | - | - | 0 | 157 | 1.07x | prisma, cron | 0.001120 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.300 | - | - | 157 | - | - | 0 | 157 | 0.37x | prisma, cron | 0.001120 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.105 | - | - | - | - | - | 0 | 0 | 0.00x | cron | 0.000000 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 349 | 0.878 | - | 95 | - | - | - | - | 95 | 0.27x | python_api | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 361 | 0.984 | - | 95 | - | - | - | - | 95 | 0.26x | python_api | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.315 | - | 95 | - | - | - | - | 95 | 0.79x | python_api | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.121 | - | 95 | - | - | - | - | 95 | 0.15x | python_api | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.196 | - | 95 | - | - | - | - | 95 | 0.80x | python_api | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.859 | - | 95 | - | - | - | - | 95 | 0.23x | python_api | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.396 | - | 107 | 138 | - | - | - | 245 | 0.80x | python_api, prisma | 0.001750 |
| examples/ticketing.lang | non-strict-only | 274 | 0.967 | 326 | 152 | 165 | - | - | - | 643 | 2.35x | react_ts, python_api, prisma | 0.004585 |


## Handwritten baseline size comparison

**AINL emitted** aggregates use the active benchmark metric (`tiktoken`) and, when available, **tiktoken** (**cl100k_base**) on the same emitted bundle. **Pure / Lang** columns count only `pure_async_python.py` / `langgraph_version.py` in each group.

### Emit mode `minimal_emit`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 253 | 253 | 92 | 88 | 870 | 738 | 0.29x | 0.34x | 0.001803 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 95 | 95 | 71 | 77 | 700 | 754 | 0.14x | 0.13x | 0.000678 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 0 | 0 | 159 | 163 | 1584 | 1624 | 0.00x | 0.00x | 0.000000 | 0.022860 |

### Emit mode `full_multitarget`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 731 | 731 | 92 | 88 | 870 | 738 | 0.84x | 0.99x | 0.005208 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 563 | 563 | 71 | 77 | 700 | 754 | 0.80x | 0.75x | 0.004015 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 563 | 563 | 159 | 163 | 1584 | 1624 | 0.36x | 0.35x | 0.004015 | 0.022860 |


## Supported vs Unsupported Claims

- Supported: profile- and mode-scoped compactness comparisons for this benchmark setup.
- Supported: canonical strict-valid as primary headline profile.
- Unsupported: universal compactness claims versus Python/TypeScript/Rust/Go.
- Unsupported: guaranteed pricing impact from default lexical metrics.
- Note: source-text fallback remains as temporary legacy support for older IRs missing capability metadata.

## Recommended Next Benchmark Improvements

- Handwritten baselines live under `benchmarks/handwritten_baselines/`; use `--compare-baselines` on size/runtime scripts for tables vs mapped AINL artifacts.
- Add CI trend snapshots for both full and minimal modes.
- Add tokenizer-metric lane when dependency pinning is available.

Conclusion: strongest current claim is compactness in canonical multi-target examples; language-surface changes are not required for these benchmark gains.

Selection source: `tooling/artifact_profiles.json`; planning source: `tooling/benchmark_manifest.json`.
