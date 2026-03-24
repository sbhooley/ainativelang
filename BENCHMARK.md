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

- `full_multitarget`: includes all benchmark targets for each artifact (compiler emitters + hybrid wrappers).
- `full_multitarget_core`: six compiler-backed emitters only (matches historical multitarget headline before hybrid wrappers).
- `minimal_emit`: includes only capability-required targets for each artifact.

## CI regression baselines (GitHub Actions)

The **`benchmark-regression`** workflow compares the freshly generated **CI slice** JSON (**`tooling/benchmark_size_ci.json`**, **`tooling/benchmark_runtime_ci.json`**) against files extracted from the **baseline git SHA** (merge base on PRs, `github.event.before` on pushes, else `origin/main`). **If `tooling/benchmark_size_ci.json` / `tooling/benchmark_runtime_ci.json` exist on that baseline commit, those are preferred** (apples-to-apples with the same profile/mode slice). Otherwise the job falls back to the full reports **`tooling/benchmark_size.json`** and **`tooling/benchmark_runtime_results.json`** when present. Regenerate the CI twins locally with **`make benchmark-ci`** (uses the same **`PYTHON`** resolution as **`make benchmark`**; override with **`PYTHON=...`**) and commit them when you want **`main`** to anchor CI-vs-CI regressions.

## Compiler IR Capability Contract

- `emit_capabilities.needs_python_api`: backend/API execution surface is required.
- `emit_capabilities.needs_react_ts`: frontend UI output is required.
- `emit_capabilities.needs_prisma`: schema/data model output is required.
- `emit_capabilities.needs_mt5`: MT5 strategy output is required.
- `emit_capabilities.needs_scraper`: scraper output is required.
- `emit_capabilities.needs_cron`: cron/scheduler output is required.
- `emit_capabilities.needs_langgraph` / `needs_temporal`: opt-in hybrid wrapper targets (default **false** in the compiler).
- `required_emit_targets.minimal_emit`: compiler-planned minimal target set (planner primary source).

## Comparative methodology (vs LangGraph, Temporal, prompt-loop frameworks)

Use this repo’s benchmarks to compare **authoring compactness** (tiktoken on `.ainl` vs emitted `--emit langgraph` / `--emit temporal` vs hand-written baselines) and **post-compile runtime** cost — not to claim parity with every hosted feature of other stacks.

- **Step-by-step commands and honest boundaries:** [`docs/competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](docs/competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)
- **Onboarding + positioning (no fake numbers):** [`docs/competitive/FROM_LANGGRAPH_TO_AINL.md`](docs/competitive/FROM_LANGGRAPH_TO_AINL.md), [`docs/competitive/AINL_AND_TEMPORAL.md`](docs/competitive/AINL_AND_TEMPORAL.md)
- **OpenClaw / MCP production worksheet:** [`docs/competitive/OPENCLAW_PRODUCTION_SAVINGS.md`](docs/competitive/OPENCLAW_PRODUCTION_SAVINGS.md)
- **Comparison tables** ([`docs/competitive/COMPARISON_TABLE.md`](docs/competitive/COMPARISON_TABLE.md)): committed benchmark figures + **TBD** where noted.

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

| Profile | Full core ratio (viable, tk) | Full+hybrid ratio (viable, tk) | Minimal ratio (viable, tk) | Viable artifacts |
|---|---:|---:|---:|---|
| canonical_strict_valid | 3.21x | 362.44x | 0.76x | 19/19 |
| public_mixed | 1.02x | 321.80x | 0.73x | 72/85 |
| compatibility_only | 0.84x | 318.38x | 0.71x | 53/66 |

Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline.

## Size Drivers (Actionable Diagnosis)

- Values below are **tiktoken (tk)** on the same **viable** subset as headline drivers when applicable (CLI metric: `tiktoken`).

### full_multitarget
- `canonical_strict_valid` top targets (tk): temporal=465660, langgraph=464733, mt5=3363
- `canonical_strict_valid` top artifacts (tk): examples/test_phase2_common_modules.ainl=239433, examples/hyperspace_demo.ainl=220396, examples/test_adapters_full.ainl=87005
- `public_mixed` top targets (tk): temporal=5357109, langgraph=5353690, mt5=13509
- `public_mixed` top artifacts (tk): examples/autonomous_ops/infrastructure_watchdog.lang=854974, examples/autonomous_ops/monitor_system.lang=735494, examples/autonomous_ops/lead_quality_audit.lang=525930
- `compatibility_only` top targets (tk): temporal=4891449, langgraph=4888957, mt5=10146
- `compatibility_only` top artifacts (tk): examples/autonomous_ops/infrastructure_watchdog.lang=854974, examples/autonomous_ops/monitor_system.lang=735494, examples/autonomous_ops/lead_quality_audit.lang=525930

### full_multitarget_core
- `canonical_strict_valid` top targets (tk): mt5=3363, python_api=1816, scraper=1684
- `canonical_strict_valid` top artifacts (tk): examples/scraper/basic_scraper.ainl=591, examples/monitor_escalation.ainl=521, examples/web/basic_web_api.ainl=434
- `public_mixed` top targets (tk): mt5=13509, python_api=7063, scraper=6189
- `public_mixed` top artifacts (tk): examples/internal_tool.lang=787, examples/ticketing.lang=743, examples/ecom.lang=712
- `compatibility_only` top targets (tk): mt5=10146, python_api=5247, scraper=4505
- `compatibility_only` top artifacts (tk): examples/internal_tool.lang=787, examples/ticketing.lang=743, examples/ecom.lang=712

### minimal_emit
- `canonical_strict_valid` top targets (tk): python_api=1626, cron=197, scraper=154
- `canonical_strict_valid` top artifacts (tk): examples/scraper/basic_scraper.ainl=253, examples/web/basic_web_api.ainl=106, examples/monitor_escalation.ainl=98
- `public_mixed` top targets (tk): python_api=3548, prisma=766, react_ts=667
- `public_mixed` top artifacts (tk): examples/internal_tool.lang=459, examples/ticketing.lang=419, examples/ecom.lang=394
- `compatibility_only` top targets (tk): python_api=1922, prisma=766, react_ts=667
- `compatibility_only` top artifacts (tk): examples/internal_tool.lang=459, examples/ticketing.lang=419, examples/ecom.lang=394

## Residual Overhead Audit (minimal_emit)

### canonical_strict_valid
- `python_api` total=1626; structure: decorator_chunks=5, function_def_chunks=6, imports_chunks=119, return_chunks=6, total_chunks=1626
- `cron` total=197; structure: function_def_chunks=11, pass_chunks=6, schedule_comment_chunks=180, total_chunks=197
- `scraper` total=154; structure: function_def_chunks=4, imports_chunks=11, request_call_chunks=18, return_chunks=17, selector_chunks=22, total_chunks=154

### public_mixed
- `python_api` total=3548; structure: decorator_chunks=103, function_def_chunks=120, imports_chunks=245, return_chunks=120, total_chunks=3548
- `prisma` total=766; structure: total_chunks=766
- `react_ts` total=667; structure: total_chunks=667

### compatibility_only
- `python_api` total=1922; structure: decorator_chunks=98, function_def_chunks=114, imports_chunks=126, return_chunks=114, total_chunks=1922
- `prisma` total=766; structure: total_chunks=766
- `react_ts` total=667; structure: total_chunks=667

## Details (full_multitarget)

| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |
|---|---:|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 938707 | 362.44x | 0 |
| public_mixed | 72 | 33390 | 10744872 | 321.80x | 13 |
| compatibility_only | 53 | 30800 | 9806165 | 318.38x | 13 |

### canonical_strict_valid
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.556 | 26 | 95 | 40 | 177 | 85 | 0 | 22231 | 600.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.158395 |
| examples/hello.ainl | strict-valid | 18 | 0.214 | 26 | 95 | 40 | 177 | 85 | 0 | 10713 | 595.17x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.076330 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 0.331 | 26 | 95 | 40 | 177 | 85 | 0 | 28903 | 125.12x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.205937 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.461 | 26 | 95 | 40 | 177 | 85 | 0 | 25354 | 256.10x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.180652 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.449 | 26 | 95 | 40 | 177 | 85 | 0 | 24820 | 292.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.176843 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 15.230 | 26 | 95 | 40 | 177 | 85 | 0 | 220396 | 427.12x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.570328 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.831 | 26 | 95 | 40 | 177 | 85 | 0 | 31899 | 384.33x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.227282 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.557 | 26 | 95 | 40 | 177 | 85 | 98 | 25411 | 352.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.181053 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.380 | 26 | 95 | 40 | 177 | 85 | 0 | 16260 | 560.69x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.115852 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.519 | 26 | 95 | 40 | 177 | 85 | 0 | 21127 | 391.24x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.150528 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.357 | 26 | 95 | 40 | 177 | 154 | 99 | 21759 | 324.76x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.155035 |
| examples/status_branching.ainl | strict-valid | 48 | 0.508 | 26 | 95 | 40 | 177 | 85 | 0 | 20343 | 423.81x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.144948 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 1.515 | 26 | 95 | 40 | 177 | 85 | 0 | 87005 | 215.36x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.619915 |
| examples/test_nested.ainl | strict-valid | 20 | 0.238 | 26 | 95 | 40 | 177 | 85 | 0 | 12369 | 618.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.088127 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 20.970 | 26 | 95 | 40 | 177 | 85 | 0 | 239433 | 564.70x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.705960 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.126 | 26 | 95 | 40 | 177 | 85 | 0 | 24877 | 507.69x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.177250 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.843 | 26 | 95 | 40 | 177 | 85 | 0 | 65239 | 254.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.464830 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.288 | 26 | 106 | 40 | 177 | 85 | 0 | 15426 | 482.06x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.109912 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.674 | 26 | 95 | 40 | 177 | 85 | 0 | 25142 | 380.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.179138 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### public_mixed
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.722 | 26 | 128 | 76 | 219 | 85 | 0 | 40776 | 381.08x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.290535 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.169 | 26 | 95 | 40 | 177 | 85 | 0 | 66706 | 347.43x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.475282 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.998 | 26 | 95 | 40 | 177 | 85 | 98 | 460235 | 335.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.279175 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.367 | 26 | 95 | 68 | 202 | 85 | 0 | 230960 | 369.54x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.645598 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 5.199 | 26 | 95 | 40 | 177 | 85 | 98 | 854974 | 384.78x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 6.091695 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.949 | 26 | 95 | 69 | 204 | 85 | 0 | 161027 | 419.34x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.147315 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.911 | 26 | 95 | 73 | 210 | 85 | 0 | 146911 | 363.64x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.046740 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.882 | 26 | 95 | 40 | 177 | 85 | 99 | 525930 | 371.16x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.747255 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.094 | 26 | 95 | 66 | 197 | 85 | 0 | 246817 | 384.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.758573 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.862 | 26 | 95 | 40 | 177 | 85 | 0 | 71607 | 294.68x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.510197 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.199 | 26 | 95 | 40 | 177 | 85 | 0 | 194859 | 376.18x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.388373 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.772 | 26 | 95 | 68 | 202 | 85 | 0 | 247316 | 391.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.762133 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.937 | 26 | 95 | 127 | 257 | 85 | 0 | 735494 | 347.42x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted react_ts emitter) | 5.240400 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.263 | 26 | 95 | 40 | 177 | 85 | 0 | 78295 | 362.48x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.557852 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.027 | 26 | 95 | 69 | 204 | 85 | 0 | 179175 | 394.66x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.276622 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.559 | 26 | 95 | 60 | 186 | 85 | 0 | 386538 | 370.96x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 2.754090 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.823 | 26 | 95 | 40 | 177 | 85 | 99 | 425224 | 414.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.029723 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 2.030 | 26 | 95 | 40 | 177 | 85 | 0 | 78243 | 365.62x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.557485 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.721 | 26 | 95 | 65 | 195 | 85 | 0 | 116938 | 399.11x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.833190 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.950 | 26 | 95 | 40 | 177 | 85 | 98 | 354901 | 348.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 2.528672 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.273 | 26 | 95 | 40 | 177 | 85 | 98 | 422677 | 388.13x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.011575 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.807 | 26 | 95 | 40 | 177 | 85 | 98 | 479721 | 378.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.418015 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.279 | 26 | 95 | 40 | 177 | 85 | 0 | 11919 | 322.14x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.084925 |
| examples/blog.lang | non-strict-only | 237 | 0.976 | 150 | 139 | 88 | 238 | 85 | 0 | 79652 | 336.08x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.567525 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.526 | 26 | 95 | 40 | 177 | 85 | 98 | 27253 | 373.33x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.194178 |
| examples/crud_api.ainl | strict-valid | 37 | 0.492 | 26 | 95 | 40 | 177 | 85 | 0 | 22231 | 600.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.158395 |
| examples/ecom.lang | non-strict-only | 238 | 1.016 | 186 | 128 | 80 | 233 | 85 | 0 | 75625 | 317.75x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.538833 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.241 | 26 | 95 | 40 | 177 | 85 | 0 | 67697 | 196.79x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.482343 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.110 | 26 | 95 | 40 | 177 | 85 | 0 | 65117 | 206.07x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.463960 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.128 | 26 | 95 | 40 | 177 | 85 | 0 | 65699 | 211.25x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.468108 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.536 | 26 | 95 | 40 | 177 | 85 | 0 | 81359 | 234.46x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.579685 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.327 | 26 | 95 | 40 | 177 | 85 | 0 | 75277 | 179.66x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.536350 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.230 | 26 | 95 | 40 | 177 | 85 | 0 | 79163 | 172.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.564040 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.471 | 26 | 95 | 40 | 177 | 85 | 0 | 128797 | 244.40x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.917680 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.970 | 26 | 95 | 40 | 177 | 85 | 0 | 106711 | 236.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.760315 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.549 | 26 | 95 | 40 | 177 | 85 | 0 | 255053 | 233.14x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.817252 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.339 | 26 | 95 | 40 | 177 | 85 | 0 | 172629 | 244.52x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.229980 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.256 | 26 | 95 | 40 | 177 | 85 | 0 | 228451 | 233.35x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.627712 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 4.042 | 26 | 95 | 40 | 177 | 85 | 0 | 208019 | 221.30x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.482138 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 3.222 | 26 | 95 | 81 | 197 | 85 | 0 | 138666 | 233.05x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.987997 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.139 | 26 | 95 | 78 | 191 | 85 | 0 | 182623 | 257.22x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.301192 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.889 | 26 | 95 | 79 | 192 | 85 | 0 | 171005 | 239.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.218415 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 3.232 | 26 | 95 | 79 | 192 | 85 | 0 | 180703 | 253.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.287513 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 3.025 | 26 | 95 | 82 | 199 | 85 | 0 | 198167 | 236.48x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.411938 |
| examples/hello.ainl | strict-valid | 18 | 0.221 | 26 | 95 | 40 | 177 | 85 | 0 | 10713 | 595.17x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.076330 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 0.315 | 26 | 95 | 40 | 177 | 85 | 0 | 28903 | 125.12x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.205937 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.602 | 26 | 95 | 40 | 177 | 85 | 0 | 25354 | 256.10x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.180652 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.441 | 26 | 95 | 40 | 177 | 85 | 0 | 24820 | 292.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.176843 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 14.476 | 26 | 95 | 40 | 177 | 85 | 0 | 220396 | 427.12x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.570328 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.830 | 26 | 95 | 40 | 177 | 85 | 0 | 31899 | 384.33x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.227282 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.714 | 26 | 95 | 40 | 177 | 85 | 0 | 43523 | 192.58x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.310105 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.855 | 26 | 95 | 40 | 177 | 85 | 0 | 45725 | 189.73x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.325795 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.793 | 148 | 128 | 85 | 243 | 85 | 98 | 70561 | 310.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.502750 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.532 | 26 | 95 | 40 | 177 | 85 | 98 | 25411 | 352.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.181053 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.240 | 26 | 95 | 40 | 177 | 85 | 0 | 21349 | 195.86x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.152110 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.843 | 26 | 95 | 40 | 177 | 85 | 0 | 105399 | 302.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.750970 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.753 | 26 | 95 | 78 | 192 | 85 | 0 | 178614 | 368.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 1.272630 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.246 | 26 | 95 | 78 | 191 | 85 | 0 | 105791 | 373.82x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.753760 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 4.092 | 26 | 95 | 101 | 227 | 85 | 0 | 177973 | 315.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted react_ts emitter) | 1.268058 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.932 | 26 | 95 | 79 | 192 | 85 | 0 | 59607 | 405.49x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.424705 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.929 | 26 | 95 | 79 | 192 | 85 | 0 | 141852 | 338.55x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.010700 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.398 | 26 | 95 | 40 | 177 | 85 | 0 | 128647 | 349.58x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.916608 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.164 | 26 | 95 | 40 | 177 | 85 | 0 | 78933 | 209.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.562397 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.265 | 26 | 95 | 40 | 177 | 85 | 0 | 81903 | 214.41x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.583562 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.400 | 26 | 95 | 40 | 177 | 85 | 0 | 69926 | 577.90x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.498225 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.560 | 26 | 95 | 40 | 177 | 85 | 0 | 239688 | 382.89x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 1.707780 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.250 | 26 | 95 | 40 | 177 | 85 | 0 | 22464 | 188.77x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.160057 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.921 | 26 | 95 | 40 | 177 | 85 | 0 | 120052 | 287.21x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.855375 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.684 | 26 | 107 | 62 | 211 | 85 | 0 | 101195 | 330.70x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.721015 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.635 | 26 | 95 | 40 | 177 | 85 | 0 | 26633 | 317.06x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.189760 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.377 | 26 | 95 | 40 | 177 | 85 | 0 | 16260 | 560.69x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.115852 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.568 | 26 | 95 | 40 | 177 | 85 | 0 | 21127 | 391.24x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.150528 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.393 | 26 | 95 | 40 | 177 | 154 | 99 | 21759 | 324.76x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.155035 |
| examples/status_branching.ainl | strict-valid | 48 | 0.511 | 26 | 95 | 40 | 177 | 85 | 0 | 20343 | 423.81x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.144948 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.414 | 26 | 95 | 40 | 177 | 85 | 0 | 18271 | 493.81x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.130180 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 2.439 | 26 | 95 | 40 | 177 | 85 | 0 | 87005 | 215.36x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.619915 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.602 | 26 | 95 | 40 | 177 | 85 | 0 | 22725 | 541.07x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.161920 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.391 | 26 | 95 | 40 | 177 | 85 | 0 | 18229 | 607.63x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.129880 |
| examples/test_nested.ainl | strict-valid | 20 | 0.292 | 26 | 95 | 40 | 177 | 85 | 0 | 12369 | 618.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.088127 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 20.144 | 26 | 95 | 40 | 177 | 85 | 0 | 239433 | 564.70x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.705960 |
| examples/ticketing.lang | non-strict-only | 274 | 1.200 | 183 | 152 | 84 | 239 | 85 | 0 | 92415 | 337.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.658458 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.124 | 26 | 95 | 40 | 177 | 85 | 0 | 24877 | 507.69x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.177250 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.934 | 26 | 95 | 40 | 177 | 85 | 0 | 65239 | 254.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.464830 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.245 | 26 | 106 | 40 | 177 | 85 | 0 | 15426 | 482.06x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.109912 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.605 | 26 | 95 | 40 | 177 | 85 | 0 | 25142 | 380.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.179138 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### compatibility_only
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.716 | 26 | 128 | 76 | 219 | 85 | 0 | 40776 | 381.08x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.290535 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.290 | 26 | 95 | 40 | 177 | 85 | 0 | 66706 | 347.43x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.475282 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 7.783 | 26 | 95 | 40 | 177 | 85 | 98 | 460235 | 335.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.279175 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.470 | 26 | 95 | 68 | 202 | 85 | 0 | 230960 | 369.54x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.645598 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 7.475 | 26 | 95 | 40 | 177 | 85 | 98 | 854974 | 384.78x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 6.091695 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 1.179 | 26 | 95 | 69 | 204 | 85 | 0 | 161027 | 419.34x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.147315 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 1.222 | 26 | 95 | 73 | 210 | 85 | 0 | 146911 | 363.64x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.046740 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 15.286 | 26 | 95 | 40 | 177 | 85 | 99 | 525930 | 371.16x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.747255 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 22.870 | 26 | 95 | 66 | 197 | 85 | 0 | 246817 | 384.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.758573 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 3.956 | 26 | 95 | 40 | 177 | 85 | 0 | 71607 | 294.68x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.510197 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.229 | 26 | 95 | 40 | 177 | 85 | 0 | 194859 | 376.18x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.388373 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 2.020 | 26 | 95 | 68 | 202 | 85 | 0 | 247316 | 391.94x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.762133 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 19.322 | 26 | 95 | 127 | 257 | 85 | 0 | 735494 | 347.42x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted react_ts emitter) | 5.240400 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.505 | 26 | 95 | 40 | 177 | 85 | 0 | 78295 | 362.48x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.557852 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.278 | 26 | 95 | 69 | 204 | 85 | 0 | 179175 | 394.66x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.276622 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 5.265 | 26 | 95 | 60 | 186 | 85 | 0 | 386538 | 370.96x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 2.754090 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 2.111 | 26 | 95 | 40 | 177 | 85 | 99 | 425224 | 414.45x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.029723 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.444 | 26 | 95 | 40 | 177 | 85 | 0 | 78243 | 365.62x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.557485 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 1.430 | 26 | 95 | 65 | 195 | 85 | 0 | 116938 | 399.11x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.833190 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 4.929 | 26 | 95 | 40 | 177 | 85 | 98 | 354901 | 348.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 2.528672 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 3.028 | 26 | 95 | 40 | 177 | 85 | 98 | 422677 | 388.13x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.011575 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.830 | 26 | 95 | 40 | 177 | 85 | 98 | 479721 | 378.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 3.418015 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.313 | 26 | 95 | 40 | 177 | 85 | 0 | 11919 | 322.14x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.084925 |
| examples/blog.lang | non-strict-only | 237 | 1.017 | 150 | 139 | 88 | 238 | 85 | 0 | 79652 | 336.08x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.567525 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.546 | 26 | 95 | 40 | 177 | 85 | 98 | 27253 | 373.33x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.194178 |
| examples/ecom.lang | non-strict-only | 238 | 2.396 | 186 | 128 | 80 | 233 | 85 | 0 | 75625 | 317.75x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.538833 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.710 | 26 | 95 | 40 | 177 | 85 | 0 | 67697 | 196.79x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.482343 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.232 | 26 | 95 | 40 | 177 | 85 | 0 | 65117 | 206.07x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.463960 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.333 | 26 | 95 | 40 | 177 | 85 | 0 | 65699 | 211.25x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.468108 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.758 | 26 | 95 | 40 | 177 | 85 | 0 | 81359 | 234.46x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.579685 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.352 | 26 | 95 | 40 | 177 | 85 | 0 | 75277 | 179.66x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.536350 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.318 | 26 | 95 | 40 | 177 | 85 | 0 | 79163 | 172.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.564040 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.536 | 26 | 95 | 40 | 177 | 85 | 0 | 128797 | 244.40x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.917680 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 2.351 | 26 | 95 | 40 | 177 | 85 | 0 | 106711 | 236.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.760315 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.733 | 26 | 95 | 40 | 177 | 85 | 0 | 255053 | 233.14x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.817252 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.533 | 26 | 95 | 40 | 177 | 85 | 0 | 172629 | 244.52x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.229980 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.666 | 26 | 95 | 40 | 177 | 85 | 0 | 228451 | 233.35x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.627712 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 4.074 | 26 | 95 | 40 | 177 | 85 | 0 | 208019 | 221.30x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.482138 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.471 | 26 | 95 | 81 | 197 | 85 | 0 | 138666 | 233.05x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.987997 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.386 | 26 | 95 | 78 | 191 | 85 | 0 | 182623 | 257.22x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.301192 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.874 | 26 | 95 | 79 | 192 | 85 | 0 | 171005 | 239.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.218415 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 3.152 | 26 | 95 | 79 | 192 | 85 | 0 | 180703 | 253.09x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.287513 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.969 | 26 | 95 | 82 | 199 | 85 | 0 | 198167 | 236.48x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.411938 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.789 | 26 | 95 | 40 | 177 | 85 | 0 | 43523 | 192.58x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.310105 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.846 | 26 | 95 | 40 | 177 | 85 | 0 | 45725 | 189.73x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.325795 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.880 | 148 | 128 | 85 | 243 | 85 | 98 | 70561 | 310.84x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.502750 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.267 | 26 | 95 | 40 | 177 | 85 | 0 | 21349 | 195.86x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.152110 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.815 | 26 | 95 | 40 | 177 | 85 | 0 | 105399 | 302.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.750970 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.688 | 26 | 95 | 78 | 192 | 85 | 0 | 178614 | 368.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 1.272630 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.272 | 26 | 95 | 78 | 191 | 85 | 0 | 105791 | 373.82x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.753760 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.399 | 26 | 95 | 101 | 227 | 85 | 0 | 177973 | 315.00x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted react_ts emitter) | 1.268058 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.968 | 26 | 95 | 79 | 192 | 85 | 0 | 59607 | 405.49x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.424705 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 3.350 | 26 | 95 | 79 | 192 | 85 | 0 | 141852 | 338.55x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 1.010700 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.787 | 26 | 95 | 40 | 177 | 85 | 0 | 128647 | 349.58x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.916608 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.193 | 26 | 95 | 40 | 177 | 85 | 0 | 78933 | 209.93x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.562397 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.235 | 26 | 95 | 40 | 177 | 85 | 0 | 81903 | 214.41x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.583562 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.445 | 26 | 95 | 40 | 177 | 85 | 0 | 69926 | 577.90x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.498225 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.646 | 26 | 95 | 40 | 177 | 85 | 0 | 239688 | 382.89x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 1.707780 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.274 | 26 | 95 | 40 | 177 | 85 | 0 | 22464 | 188.77x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.160057 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 1.248 | 26 | 95 | 40 | 177 | 85 | 0 | 120052 | 287.21x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.855375 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.747 | 26 | 107 | 62 | 211 | 85 | 0 | 101195 | 330.70x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.721015 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.673 | 26 | 95 | 40 | 177 | 85 | 0 | 26633 | 317.06x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.189760 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.378 | 26 | 95 | 40 | 177 | 85 | 0 | 18271 | 493.81x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.130180 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.496 | 26 | 95 | 40 | 177 | 85 | 0 | 22725 | 541.07x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.161920 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.439 | 26 | 95 | 40 | 177 | 85 | 0 | 18229 | 607.63x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter); (compacted react_ts emitter) | 0.129880 |
| examples/ticketing.lang | non-strict-only | 274 | 1.446 | 183 | 152 | 84 | 239 | 85 | 0 | 92415 | 337.28x | react_ts, python_api, prisma, mt5, scraper, cron, langgraph, temporal | (compacted prisma emitter) | 0.658458 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

## Details (full_multitarget_core)

| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |
|---|---:|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 8314 | 3.21x | 0 |
| public_mixed | 72 | 33390 | 34073 | 1.02x | 13 |
| compatibility_only | 53 | 30800 | 25759 | 0.84x | 13 |

### canonical_strict_valid
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.540 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hello.ainl | strict-valid | 18 | 0.215 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 23.50x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 0.335 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.413 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 4.27x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.394 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 4.98x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 14.465 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.810 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.521 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.382 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.502 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 7.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.331 | 26 | 95 | 40 | 177 | 154 | 99 | 591 | 8.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.004210 |
| examples/status_branching.ainl | strict-valid | 48 | 0.483 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 1.439 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.05x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_nested.ainl | strict-valid | 20 | 0.231 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 21.15x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 20.714 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.00x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.042 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.63x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.757 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.65x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.294 | 26 | 106 | 40 | 177 | 85 | 0 | 434 | 13.56x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003097 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.642 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 6.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### public_mixed
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.606 | 26 | 128 | 76 | 219 | 85 | 0 | 534 | 4.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003810 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.185 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 2.20x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.879 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.38x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.392 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 5.120 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.933 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.25x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.898 | 26 | 95 | 73 | 210 | 85 | 0 | 489 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003482 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 3.869 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.37x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.044 | 26 | 95 | 66 | 197 | 85 | 0 | 469 | 0.73x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003340 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.792 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.74x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.131 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 2.149 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.75x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 15.494 | 26 | 95 | 127 | 257 | 85 | 0 | 590 | 0.28x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.004208 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.296 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.96x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 0.995 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.457 | 26 | 95 | 60 | 186 | 85 | 0 | 452 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003225 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.708 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.228 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.712 | 26 | 95 | 65 | 195 | 85 | 0 | 466 | 1.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003322 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.619 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.885 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.578 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.349 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/blog.lang | non-strict-only | 237 | 0.965 | 150 | 139 | 88 | 238 | 85 | 0 | 700 | 2.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.004987 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.556 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/crud_api.ainl | strict-valid | 37 | 0.476 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecom.lang | non-strict-only | 238 | 0.885 | 186 | 128 | 80 | 233 | 85 | 0 | 712 | 2.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005078 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.155 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.180 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.34x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.100 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.36x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.416 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.22x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.292 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.411 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.92x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.517 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.80x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.911 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.94x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.534 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.39x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.254 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.382 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 10.433 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.45x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 11.496 | 26 | 95 | 81 | 197 | 85 | 0 | 484 | 0.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003450 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 11.691 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 17.184 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 14.065 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 14.559 | 26 | 95 | 82 | 199 | 85 | 0 | 487 | 0.58x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003475 |
| examples/hello.ainl | strict-valid | 18 | 0.864 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 23.50x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 1.307 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.874 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 4.27x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.428 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 4.98x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 29.951 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.834 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.759 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.87x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.913 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.886 | 148 | 128 | 85 | 243 | 85 | 98 | 787 | 3.47x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005605 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.532 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.236 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.88x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.821 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.711 | 26 | 95 | 78 | 192 | 85 | 0 | 476 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.093 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 1.68x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.168 | 26 | 95 | 101 | 227 | 85 | 0 | 534 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.003810 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 1.039 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 3.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.978 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 1.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.398 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.15x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.692 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.12x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.158 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.11x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.423 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.50x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 3.069 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.68x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.261 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.55x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.981 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.748 | 26 | 107 | 62 | 211 | 85 | 0 | 491 | 1.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003498 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.700 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.04x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.419 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.551 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 7.83x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.352 | 26 | 95 | 40 | 177 | 154 | 99 | 591 | 8.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.004210 |
| examples/status_branching.ainl | strict-valid | 48 | 0.479 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.377 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 1.496 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.05x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.538 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 10.07x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.383 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_nested.ainl | strict-valid | 20 | 0.217 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 21.15x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 20.261 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.00x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ticketing.lang | non-strict-only | 274 | 1.225 | 183 | 152 | 84 | 239 | 85 | 0 | 743 | 2.71x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005298 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.134 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 8.63x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.989 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.65x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.230 | 26 | 106 | 40 | 177 | 85 | 0 | 434 | 13.56x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003097 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.602 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 6.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### compatibility_only
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.612 | 26 | 128 | 76 | 219 | 85 | 0 | 534 | 4.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003810 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.286 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 2.20x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 12.556 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.38x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.965 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 7.965 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.908 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.25x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.912 | 26 | 95 | 73 | 210 | 85 | 0 | 489 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003482 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.055 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.37x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.120 | 26 | 95 | 66 | 197 | 85 | 0 | 469 | 0.73x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003340 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.791 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.74x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.300 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.82x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.946 | 26 | 95 | 68 | 202 | 85 | 0 | 476 | 0.75x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 63.349 | 26 | 95 | 127 | 257 | 85 | 0 | 590 | 0.28x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.004208 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.344 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.96x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.203 | 26 | 95 | 69 | 204 | 85 | 0 | 479 | 1.06x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003415 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.773 | 26 | 95 | 60 | 186 | 85 | 0 | 452 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003225 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 2.123 | 26 | 95 | 40 | 177 | 85 | 99 | 522 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003720 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.628 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.670 | 26 | 95 | 65 | 195 | 85 | 0 | 466 | 1.59x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003322 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 4.247 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.51x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.389 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.48x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 3.024 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 0.41x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.283 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/blog.lang | non-strict-only | 237 | 1.207 | 150 | 139 | 88 | 238 | 85 | 0 | 700 | 2.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.004987 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.543 | 26 | 95 | 40 | 177 | 85 | 98 | 521 | 7.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003715 |
| examples/ecom.lang | non-strict-only | 238 | 0.980 | 186 | 128 | 80 | 233 | 85 | 0 | 712 | 2.99x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005078 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.416 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.23x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.147 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.34x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.133 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.36x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.628 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.22x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.398 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.296 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.92x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.581 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.80x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 2.315 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.94x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.915 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.39x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.499 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.756 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 4.197 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.45x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.611 | 26 | 95 | 81 | 197 | 85 | 0 | 484 | 0.81x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003450 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.135 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.905 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 2.955 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 0.67x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.796 | 26 | 95 | 82 | 199 | 85 | 0 | 487 | 0.58x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003475 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.803 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.87x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.752 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.76x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.839 | 148 | 128 | 85 | 243 | 85 | 98 | 787 | 3.47x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005605 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.281 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.88x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.807 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.21x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.595 | 26 | 95 | 78 | 192 | 85 | 0 | 476 | 0.98x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003397 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.724 | 26 | 95 | 78 | 191 | 85 | 0 | 475 | 1.68x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003385 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.273 | 26 | 95 | 101 | 227 | 85 | 0 | 534 | 0.95x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted react_ts emitter) | 0.003810 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.989 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 3.24x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 3.050 | 26 | 95 | 79 | 192 | 85 | 0 | 477 | 1.14x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003400 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.429 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.15x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.138 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.12x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.220 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.11x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.414 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.50x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.403 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 0.68x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.242 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 3.55x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.966 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 1.01x | react_ts, python_api, prisma, mt5, scraper, cron | (legacy excluded from viable); (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.686 | 26 | 107 | 62 | 211 | 85 | 0 | 491 | 1.60x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003498 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.597 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 5.04x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.340 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 11.43x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.492 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 10.07x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.428 | 26 | 95 | 40 | 177 | 85 | 0 | 423 | 14.10x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter); (compacted react_ts emitter) | 0.003018 |
| examples/ticketing.lang | non-strict-only | 274 | 1.145 | 183 | 152 | 84 | 239 | 85 | 0 | 743 | 2.71x | react_ts, python_api, prisma, mt5, scraper, cron | (compacted prisma emitter) | 0.005298 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

## Details (minimal_emit)

| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |
|---|---:|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 1977 | 0.76x | 0 |
| public_mixed | 42 | 7593 | 5528 | 0.73x | 43 |
| compatibility_only | 23 | 5003 | 3551 | 0.71x | 43 |

### canonical_strict_valid
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/crud_api.ainl | strict-valid | 37 | 0.472 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/hello.ainl | strict-valid | 18 | 0.272 | — | 95 | — | — | — | — | 95 | 5.28x | python_api |  | 0.000678 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 0.310 | — | 95 | — | — | — | — | 95 | 0.41x | python_api |  | 0.000678 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.484 | — | 95 | — | — | — | — | 95 | 0.96x | python_api |  | 0.000678 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.434 | — | 95 | — | — | — | — | 95 | 1.12x | python_api |  | 0.000678 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 14.569 | — | 95 | — | — | — | — | 95 | 0.18x | python_api |  | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.906 | — | 95 | — | — | — | — | 95 | 1.14x | python_api |  | 0.000678 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.507 | — | — | — | — | — | 98 | 98 | 1.36x | cron |  | 0.000705 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.337 | — | 95 | — | — | — | — | 95 | 3.28x | python_api |  | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.526 | — | 95 | — | — | — | — | 95 | 1.76x | python_api |  | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.335 | — | — | — | — | 154 | 99 | 253 | 3.78x | scraper, cron |  | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.464 | — | 95 | — | — | — | — | 95 | 1.98x | python_api |  | 0.000678 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 2.196 | — | 95 | — | — | — | — | 95 | 0.24x | python_api |  | 0.000678 |
| examples/test_nested.ainl | strict-valid | 20 | 0.223 | — | 95 | — | — | — | — | 95 | 4.75x | python_api |  | 0.000678 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 21.640 | — | 95 | — | — | — | — | 95 | 0.22x | python_api |  | 0.000678 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.082 | — | 95 | — | — | — | — | 95 | 1.94x | python_api |  | 0.000678 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 3.145 | — | 95 | — | — | — | — | 95 | 0.37x | python_api |  | 0.000678 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.229 | — | 106 | — | — | — | — | 106 | 3.31x | python_api |  | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 0.599 | — | 95 | — | — | — | — | 95 | 1.44x | python_api |  | 0.000678 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### public_mixed
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.888 | — | 128 | 76 | — | — | — | 204 | 1.91x | python_api, prisma | (compacted prisma emitter) | 0.001455 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.197 | — | 34 | — | — | — | 0 | 34 | 0.18x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 7.446 | — | — | — | — | — | 98 | 98 | 0.07x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.776 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 6.197 | — | — | — | — | — | 98 | 98 | 0.04x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 1.041 | — | — | 69 | — | — | — | 69 | 0.18x | prisma | (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.907 | — | — | 73 | — | — | — | 73 | 0.18x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000520 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.439 | — | — | — | — | — | 99 | 99 | 0.07x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.166 | — | — | 66 | — | — | — | 66 | 0.10x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000472 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 1.158 | — | 34 | — | — | — | 0 | 34 | 0.14x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.307 | — | 95 | — | — | — | — | 95 | 0.18x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.672 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 17.398 | — | — | 127 | — | — | 0 | 127 | 0.06x | prisma, cron | (legacy excluded from viable) | 0.000902 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.333 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.101 | — | — | 69 | — | — | — | 69 | 0.15x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 5.755 | — | 95 | 60 | — | — | — | 155 | 0.15x | python_api, prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.001105 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.961 | — | — | — | — | — | 99 | 99 | 0.10x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.654 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.657 | — | — | 65 | — | — | — | 65 | 0.22x | prisma | (compacted prisma emitter) | 0.000467 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 4.283 | — | — | — | — | — | 98 | 98 | 0.10x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.446 | — | — | — | — | — | 98 | 98 | 0.09x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.778 | — | — | — | — | — | 98 | 98 | 0.08x | cron | (legacy excluded from viable) | 0.000705 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.387 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/blog.lang | non-strict-only | 237 | 1.033 | 150 | 139 | 88 | — | — | — | 377 | 1.59x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002687 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.567 | — | — | — | — | — | 98 | 98 | 1.34x | cron |  | 0.000705 |
| examples/crud_api.ainl | strict-valid | 37 | 0.623 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/ecom.lang | non-strict-only | 238 | 0.975 | 186 | 128 | 80 | — | — | — | 394 | 1.66x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002812 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.243 | — | 95 | — | — | — | — | 95 | 0.28x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.233 | — | 95 | — | — | — | — | 95 | 0.30x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.088 | — | 95 | — | — | — | — | 95 | 0.31x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.519 | — | 95 | — | — | — | — | 95 | 0.27x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.173 | — | 95 | — | — | — | — | 95 | 0.23x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.395 | — | 95 | — | — | — | — | 95 | 0.21x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.479 | — | 34 | — | — | — | 0 | 34 | 0.06x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.961 | — | 34 | — | — | — | 0 | 34 | 0.08x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.666 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.600 | — | 34 | — | — | — | 0 | 34 | 0.05x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 5.261 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 3.966 | — | 34 | — | — | — | 0 | 34 | 0.04x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.679 | — | — | 81 | — | — | 0 | 81 | 0.14x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000580 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.161 | — | — | 78 | — | — | 0 | 78 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 3.120 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 3.437 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.902 | — | — | 82 | — | — | 0 | 82 | 0.10x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000585 |
| examples/hello.ainl | strict-valid | 18 | 0.212 | — | 95 | — | — | — | — | 95 | 5.28x | python_api |  | 0.000678 |
| examples/hybrid/langchain_tool_demo.ainl | strict-valid | 231 | 0.308 | — | 95 | — | — | — | — | 95 | 0.41x | python_api |  | 0.000678 |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.461 | — | 95 | — | — | — | — | 95 | 0.96x | python_api |  | 0.000678 |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.412 | — | 95 | — | — | — | — | 95 | 1.12x | python_api |  | 0.000678 |
| examples/hyperspace_demo.ainl | strict-valid | 516 | 14.709 | — | 95 | — | — | — | — | 95 | 0.18x | python_api |  | 0.000678 |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.949 | — | 95 | — | — | — | — | 95 | 1.14x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.734 | — | 95 | — | — | — | — | 95 | 0.42x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.718 | — | 95 | — | — | — | — | 95 | 0.39x | python_api |  | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.894 | 148 | 128 | 85 | — | — | 98 | 459 | 2.02x | react_ts, python_api, prisma, cron | (compacted prisma emitter) | 0.003272 |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.525 | — | — | — | — | — | 98 | 98 | 1.36x | cron |  | 0.000705 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.233 | — | 95 | — | — | — | — | 95 | 0.87x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.905 | — | 95 | — | — | — | — | 95 | 0.27x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 4.565 | — | — | 78 | — | — | 0 | 78 | 0.16x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.127 | — | — | 78 | — | — | 0 | 78 | 0.28x | prisma, cron | (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.284 | — | — | 101 | — | — | 0 | 101 | 0.18x | prisma, cron | (legacy excluded from viable) | 0.000723 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.898 | — | — | 79 | — | — | 0 | 79 | 0.54x | prisma, cron | (compacted prisma emitter) | 0.000565 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.891 | — | — | 79 | — | — | 0 | 79 | 0.19x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.580 | — | 34 | — | — | — | 0 | 34 | 0.09x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.344 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.161 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.394 | — | 95 | — | — | — | — | 95 | 0.79x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.360 | — | 95 | — | — | — | — | 95 | 0.15x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.239 | — | 95 | — | — | — | — | 95 | 0.80x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 1.035 | — | 95 | — | — | — | — | 95 | 0.23x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.559 | — | 107 | 62 | — | — | — | 169 | 0.55x | python_api, prisma | (compacted prisma emitter) | 0.001203 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.684 | — | 95 | — | — | — | — | 95 | 1.13x | python_api |  | 0.000678 |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.351 | — | 95 | — | — | — | — | 95 | 3.28x | python_api |  | 0.000678 |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.488 | — | 95 | — | — | — | — | 95 | 1.76x | python_api |  | 0.000678 |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | 0.317 | — | — | — | — | 154 | 99 | 253 | 3.78x | scraper, cron |  | 0.001803 |
| examples/status_branching.ainl | strict-valid | 48 | 0.484 | — | 95 | — | — | — | — | 95 | 1.98x | python_api |  | 0.000678 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.388 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/test_adapters_full.ainl | strict-valid | 404 | 1.584 | — | 95 | — | — | — | — | 95 | 0.24x | python_api |  | 0.000678 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.470 | — | 95 | — | — | — | — | 95 | 2.26x | python_api |  | 0.000678 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.421 | — | 95 | — | — | — | — | 95 | 3.17x | python_api |  | 0.000678 |
| examples/test_nested.ainl | strict-valid | 20 | 0.260 | — | 95 | — | — | — | — | 95 | 4.75x | python_api |  | 0.000678 |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 20.101 | — | 95 | — | — | — | — | 95 | 0.22x | python_api |  | 0.000678 |
| examples/ticketing.lang | non-strict-only | 274 | 1.239 | 183 | 152 | 84 | — | — | — | 419 | 1.53x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002988 |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.175 | — | 95 | — | — | — | — | 95 | 1.94x | python_api |  | 0.000678 |
| examples/timeout_memory_prune_demo.ainl | strict-valid | 256 | 2.913 | — | 95 | — | — | — | — | 95 | 0.37x | python_api |  | 0.000678 |
| examples/web/basic_web_api.ainl | strict-valid | 32 | 0.242 | — | 106 | — | — | — | — | 106 | 3.31x | python_api |  | 0.000758 |
| examples/webhook_automation.ainl | strict-valid | 66 | 1.309 | — | 95 | — | — | — | — | 95 | 1.44x | python_api |  | 0.000678 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*

### compatibility_only
| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes || est $4o (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---||---:|
| examples/api_only.lang | non-strict-only | 107 | 0.651 | — | 128 | 76 | — | — | — | 204 | 1.91x | python_api, prisma | (compacted prisma emitter) | 0.001455 |
| examples/autonomous_ops/backup_freshness_to_queue.lang | non-strict-only | 192 | 1.064 | — | 34 | — | — | — | 0 | 34 | 0.18x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/canary_sampler.lang | non-strict-only | 1370 | 5.976 | — | — | — | — | — | 98 | 98 | 0.07x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/duplicate_detection.lang | non-strict-only | 625 | 1.355 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/infrastructure_watchdog.lang | non-strict-only | 2222 | 5.037 | — | — | — | — | — | 98 | 98 | 0.04x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/invoice_aging.lang | non-strict-only | 384 | 0.962 | — | — | 69 | — | — | — | 69 | 0.18x | prisma | (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/lead_aging.lang | non-strict-only | 404 | 0.909 | — | — | 73 | — | — | — | 73 | 0.18x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000520 |
| examples/autonomous_ops/lead_quality_audit.lang | non-strict-only | 1417 | 4.173 | — | — | — | — | — | 99 | 99 | 0.07x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/lead_score_drift.lang | non-strict-only | 642 | 1.022 | — | — | 66 | — | — | — | 66 | 0.10x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000472 |
| examples/autonomous_ops/memory_prune.lang | non-strict-only | 243 | 0.974 | — | 34 | — | — | — | 0 | 34 | 0.14x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/meta_monitor.lang | non-strict-only | 518 | 1.122 | — | 95 | — | — | — | — | 95 | 0.18x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/autonomous_ops/missing_fields.lang | non-strict-only | 631 | 1.652 | — | — | 68 | — | — | — | 68 | 0.11x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000487 |
| examples/autonomous_ops/monitor_system.lang | non-strict-only | 2117 | 16.800 | — | — | 127 | — | — | 0 | 127 | 0.06x | prisma, cron | (legacy excluded from viable) | 0.000902 |
| examples/autonomous_ops/pipeline_readiness_snapshot.lang | non-strict-only | 216 | 1.631 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/revenue_forecast.lang | non-strict-only | 454 | 1.210 | — | — | 69 | — | — | — | 69 | 0.15x | prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.000490 |
| examples/autonomous_ops/service_health_trends.lang | non-strict-only | 1042 | 4.777 | — | 95 | 60 | — | — | — | 155 | 0.15x | python_api, prisma | (legacy excluded from viable); (compacted prisma emitter) | 0.001105 |
| examples/autonomous_ops/session_continuity.lang | non-strict-only | 1026 | 1.983 | — | — | — | — | — | 99 | 99 | 0.10x | cron | (legacy excluded from viable) | 0.000708 |
| examples/autonomous_ops/status_snapshot_to_queue.lang | non-strict-only | 214 | 1.349 | — | 34 | — | — | — | 0 | 34 | 0.16x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/autonomous_ops/tiktok_health.lang | non-strict-only | 293 | 0.742 | — | — | 65 | — | — | — | 65 | 0.22x | prisma | (compacted prisma emitter) | 0.000467 |
| examples/autonomous_ops/tiktok_sla_monitor.lang | non-strict-only | 1019 | 3.740 | — | — | — | — | — | 98 | 98 | 0.10x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_budget_tracker.lang | non-strict-only | 1089 | 2.267 | — | — | — | — | — | 98 | 98 | 0.09x | cron | (legacy excluded from viable) | 0.000705 |
| examples/autonomous_ops/token_cost_tracker.lang | non-strict-only | 1266 | 2.777 | — | — | — | — | — | 98 | 98 | 0.08x | cron | (legacy excluded from viable) | 0.000705 |
| examples/bad_include.ainl | non-strict-only | 37 | 0.320 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/blog.lang | non-strict-only | 237 | 1.023 | 150 | 139 | 88 | — | — | — | 377 | 1.59x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002687 |
| examples/cron/monitor_and_alert.ainl | non-strict-only | 73 | 0.556 | — | — | — | — | — | 98 | 98 | 1.34x | cron |  | 0.000705 |
| examples/ecom.lang | non-strict-only | 238 | 0.846 | 186 | 128 | 80 | — | — | — | 394 | 1.66x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002812 |
| examples/ecosystem/agency-agents/accounts-payable-agent/converted.ainl | non-strict-only | 344 | 1.201 | — | 95 | — | — | — | — | 95 | 0.28x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/agents-orchestrator/converted.ainl | non-strict-only | 316 | 1.085 | — | 95 | — | — | — | — | 95 | 0.30x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/engineering-frontend-developer/converted.ainl | non-strict-only | 311 | 1.146 | — | 95 | — | — | — | — | 95 | 0.31x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/frontend-wizard/converted.ainl | non-strict-only | 347 | 1.348 | — | 95 | — | — | — | — | 95 | 0.27x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/mcp-builder/converted.ainl | non-strict-only | 419 | 1.307 | — | 95 | — | — | — | — | 95 | 0.23x | python_api |  | 0.000678 |
| examples/ecosystem/agency-agents/specialized-workflow-architect/converted.ainl | non-strict-only | 460 | 1.306 | — | 95 | — | — | — | — | 95 | 0.21x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/ecosystem/clawflows/check-calendar/converted.ainl | non-strict-only | 527 | 2.519 | — | 34 | — | — | — | 0 | 34 | 0.06x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/check-email/converted.ainl | non-strict-only | 452 | 1.925 | — | 34 | — | — | — | 0 | 34 | 0.08x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-briefing/converted.ainl | non-strict-only | 1094 | 4.346 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/morning-journal/converted.ainl | non-strict-only | 706 | 3.462 | — | 34 | — | — | — | 0 | 34 | 0.05x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/plan-week/converted.ainl | non-strict-only | 979 | 4.228 | — | 34 | — | — | — | 0 | 34 | 0.03x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/ecosystem/clawflows/prep-tomorrow/converted.ainl | non-strict-only | 940 | 3.656 | — | 34 | — | — | — | 0 | 34 | 0.04x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/golden/01_web_server.ainl | non-strict-only | 595 | 2.454 | — | — | 81 | — | — | 0 | 81 | 0.14x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000580 |
| examples/golden/02_dashboard.ainl | non-strict-only | 710 | 3.214 | — | — | 78 | — | — | 0 | 78 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/golden/03_scraper.ainl | non-strict-only | 713 | 2.759 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/04_alerting_monitor.ainl | non-strict-only | 714 | 3.986 | — | — | 79 | — | — | 0 | 79 | 0.11x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/golden/05_file_processor.ainl | non-strict-only | 838 | 2.801 | — | — | 82 | — | — | 0 | 82 | 0.10x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000585 |
| examples/integrations/executor_bridge_adapter_min.ainl | non-strict-only | 226 | 0.748 | — | 95 | — | — | — | — | 95 | 0.42x | python_api |  | 0.000678 |
| examples/integrations/executor_bridge_min.ainl | non-strict-only | 241 | 0.765 | — | 95 | — | — | — | — | 95 | 0.39x | python_api |  | 0.000678 |
| examples/internal_tool.lang | non-strict-only | 227 | 0.778 | 148 | 128 | 85 | — | — | 98 | 459 | 2.02x | react_ts, python_api, prisma, cron | (compacted prisma emitter) | 0.003272 |
| examples/openclaw/agent_read_result.lang | non-strict-only | 109 | 0.236 | — | 95 | — | — | — | — | 95 | 0.87x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/agent_send_task.lang | non-strict-only | 349 | 0.772 | — | 95 | — | — | — | — | 95 | 0.27x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/backup_manager.lang | non-strict-only | 485 | 3.552 | — | — | 78 | — | — | 0 | 78 | 0.16x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.lang | non-strict-only | 283 | 2.240 | — | — | 78 | — | — | 0 | 78 | 0.28x | prisma, cron | (compacted prisma emitter) | 0.000562 |
| examples/openclaw/daily_digest.strict.lang | non-strict-only | 565 | 3.486 | — | — | 101 | — | — | 0 | 101 | 0.18x | prisma, cron | (legacy excluded from viable) | 0.000723 |
| examples/openclaw/daily_lead_summary.lang | non-strict-only | 147 | 0.979 | — | — | 79 | — | — | 0 | 79 | 0.54x | prisma, cron | (compacted prisma emitter) | 0.000565 |
| examples/openclaw/infrastructure_watchdog.lang | non-strict-only | 419 | 2.936 | — | — | 79 | — | — | 0 | 79 | 0.19x | prisma, cron | (legacy excluded from viable); (compacted prisma emitter) | 0.000565 |
| examples/openclaw/lead_enrichment.lang | non-strict-only | 368 | 2.498 | — | 34 | — | — | — | 0 | 34 | 0.09x | cron, python_api | (fallback stub); (legacy excluded from viable) | 0.000247 |
| examples/openclaw/memory_daily_log_note.lang | non-strict-only | 376 | 1.202 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/memory_token_cost_state.lang | non-strict-only | 382 | 1.217 | — | 95 | — | — | — | — | 95 | 0.25x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_read.lang | non-strict-only | 121 | 0.388 | — | 95 | — | — | — | — | 95 | 0.79x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/monitor_status_advice_request.lang | non-strict-only | 626 | 1.388 | — | 95 | — | — | — | — | 95 | 0.15x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_read.lang | non-strict-only | 119 | 0.241 | — | 95 | — | — | — | — | 95 | 0.80x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/token_cost_advice_request.lang | non-strict-only | 418 | 0.881 | — | 95 | — | — | — | — | 95 | 0.23x | python_api | (legacy excluded from viable) | 0.000678 |
| examples/openclaw/webhook_handler.lang | non-strict-only | 306 | 1.783 | — | 107 | 62 | — | — | — | 169 | 0.55x | python_api, prisma | (compacted prisma emitter) | 0.001203 |
| examples/openclaw_full_unification.ainl | non-strict-only | 84 | 0.606 | — | 95 | — | — | — | — | 95 | 1.13x | python_api |  | 0.000678 |
| examples/test_X_sub.ainl | non-strict-only | 37 | 0.407 | — | 95 | — | — | — | — | 95 | 2.57x | python_api |  | 0.000678 |
| examples/test_if_var.ainl | non-strict-only | 42 | 0.492 | — | 95 | — | — | — | — | 95 | 2.26x | python_api |  | 0.000678 |
| examples/test_mul.ainl | non-strict-only | 30 | 0.376 | — | 95 | — | — | — | — | 95 | 3.17x | python_api |  | 0.000678 |
| examples/ticketing.lang | non-strict-only | 274 | 1.235 | 183 | 152 | 84 | — | — | — | 419 | 1.53x | react_ts, python_api, prisma | (compacted prisma emitter) | 0.002988 |

*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*


## Handwritten baseline size comparison

**AINL emitted** aggregates use the active benchmark metric (`tiktoken`) and, when available, **tiktoken** (**cl100k_base**) on the same emitted bundle. **Pure / Lang** columns count only `pure_async_python.py` / `langgraph_version.py` in each group.

### Emit mode `minimal_emit`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 253 | 253 | 92 | 88 | 870 | 738 | 0.29x | 0.34x | 0.001803 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 95 | 95 | 71 | 77 | 700 | 754 | 0.14x | 0.13x | 0.000678 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 34 | 34 | 159 | 163 | 1584 | 1624 | 0.02x | 0.02x | 0.000247 | 0.022860 |

### Emit mode `full_multitarget_core`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 591 | 591 | 92 | 88 | 870 | 738 | 0.68x | 0.80x | 0.004210 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 423 | 423 | 71 | 77 | 700 | 754 | 0.60x | 0.56x | 0.003018 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 423 | 423 | 159 | 163 | 1584 | 1624 | 0.27x | 0.26x | 0.003018 | 0.022860 |

### Emit mode `full_multitarget`

| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD ||
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | — | 21759 | 21759 | 92 | 88 | 870 | 738 | 25.01x | 29.48x | 0.155035 | 0.011460 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | — | 21127 | 21127 | 71 | 77 | 700 | 754 | 30.18x | 28.02x | 0.150528 | 0.010365 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | — | 293855 | 293855 | 159 | 163 | 1584 | 1624 | 185.51x | 180.95x | 2.093717 | 0.022860 |


## Including Legacy Artifacts

Legacy files (pure-cron shells, OpenClaw micro-wrappers, aggregate emit below the viable threshold, or paths marked `viable_for_aggregate: false`) are **still compiled and listed** in the per-artifact tables; they are **excluded only** from the **viable** summary rows above for `public_mixed` and `compatibility_only`. Canonical strict-valid profile totals are unchanged (all viable).

### full_multitarget — legacy-inclusive totals

| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 938707 | 362.44x |
| public_mixed | 85 | 37365 | 12015091 | 321.56x |
| compatibility_only | 66 | 34775 | 11076384 | 318.52x |

*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*

### full_multitarget_core — legacy-inclusive totals

| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 8314 | 3.21x |
| public_mixed | 85 | 37365 | 39625 | 1.06x |
| compatibility_only | 66 | 34775 | 31311 | 0.90x |

*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*

### minimal_emit — legacy-inclusive totals

| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 19 | 2590 | 1977 | 0.76x |
| public_mixed | 85 | 37365 | 8823 | 0.24x |
| compatibility_only | 66 | 34775 | 6846 | 0.20x |

*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*

<!-- RUNTIME_BENCH_START -->
## Runtime Performance

Automated wall-clock and RSS measurements from ``scripts/benchmark_runtime.py`` using ``RuntimeEngine`` (graph-preferred). Latencies are **run_label** only after compile; compile time is averaged over 3 compiles per artifact.

- Generated (UTC): `2026-03-24T03:24:29.102226+00:00`
- Warm-up runs: **8**; timed runs per artifact: **20**
- Graph execution mode: `graph-preferred`
- **Source tokens:** ``ainl_source_tiktoken`` uses ``tooling/bench_metrics.tiktoken_count`` (**cl100k_base**).

| Profile | Artifacts | OK | Mean of per-artifact mean latency (ms) |
|---|---:|---:|---:|
| canonical_strict_valid (full_multitarget) | 19 | 11 | 0.19772255565674807 |
| canonical_strict_valid (minimal_emit) | 19 | 11 | 0.19587255135940557 |

### Sample: headline profile artifacts (mean run latency ms)

| Artifact | Class | src tk | compile ms (mean×3) | mean | p50 | p95 | min | max | RSS Δ MB | adapter calls || est `gpt-4o` USD/run || Reliability |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---||---:||---|
| examples/crud_api.ainl | strict-valid | 37 | 0.73 | 0.02 | 0.02 | 0.02 | 0.02 | 0.03 | 0.062 | 0 | 0.000265 | 100% σ=0.01ms |
| examples/hello.ainl | strict-valid | 18 | 0.23 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.000 | 1 | 0.000135 | 100% σ=0.00ms |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.45 | 0.03 | 0.02 | 0.03 | 0.02 | 0.03 | 0.000 | 2 | 0.000708 | 100% σ=0.01ms |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.46 | 0.03 | 0.03 | 0.04 | 0.02 | 0.04 | 0.000 | 2 | 0.000610 | 100% σ=0.01ms |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.98 | 0.06 | 0.04 | 0.11 | 0.04 | 0.11 | 0.000 | 1 | 0.000595 | 100% σ=0.01ms |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.61 | 0.02 | 0.02 | 0.03 | 0.02 | 0.03 | 0.000 | 1 | 0.000517 | 100% σ=0.00ms |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.46 | 0.02 | 0.02 | 0.03 | 0.02 | 0.03 | 0.000 | 1 | 0.000205 | 100% σ=0.01ms |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.58 | 0.03 | 0.03 | 0.03 | 0.03 | 0.04 | 0.016 | 3 | 0.000390 | 100% σ=0.01ms |
| examples/status_branching.ainl | strict-valid | 48 | 0.77 | 0.02 | 0.02 | 0.03 | 0.02 | 0.03 | 0.000 | 0 | 0.000345 | 100% σ=0.00ms |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 22.30 | 0.64 | 0.60 | 0.83 | 0.55 | 1.15 | 0.000 | 38 | 0.003023 | 100% σ=0.03ms |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.20 | 1.29 | 1.30 | 1.33 | 1.18 | 1.33 | 0.000 | 2 | 0.000347 | 100% σ=0.01ms |
| examples/crud_api.ainl | strict-valid | 37 | 0.64 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 0 | 0.000265 | 100% σ=0.00ms |
| examples/hello.ainl | strict-valid | 18 | 0.23 | 0.01 | 0.01 | 0.01 | 0.01 | 0.01 | 0.000 | 1 | 0.000135 | 100% σ=0.01ms |
| examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl | strict-valid | 99 | 0.46 | 0.02 | 0.02 | 0.02 | 0.02 | 0.03 | 0.000 | 2 | 0.000708 | 100% σ=0.00ms |
| examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl | strict-valid | 85 | 0.45 | 0.02 | 0.02 | 0.03 | 0.02 | 0.06 | 0.000 | 2 | 0.000610 | 100% σ=0.00ms |
| examples/if_call_workflow.ainl | strict-valid | 83 | 0.88 | 0.04 | 0.04 | 0.04 | 0.04 | 0.07 | 0.000 | 1 | 0.000595 | 100% σ=0.00ms |
| examples/monitor_escalation.ainl | strict-valid | 72 | 0.62 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 1 | 0.000517 | 100% σ=0.00ms |
| examples/rag_pipeline.ainl | strict-valid | 29 | 0.38 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 1 | 0.000205 | 100% σ=0.00ms |
| examples/retry_error_resilience.ainl | strict-valid | 54 | 0.53 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.000 | 3 | 0.000390 | 100% σ=0.01ms |
| examples/status_branching.ainl | strict-valid | 48 | 0.57 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.000 | 0 | 0.000345 | 100% σ=0.00ms |
| examples/test_phase2_common_modules.ainl | strict-valid | 424 | 22.20 | 0.64 | 0.60 | 0.78 | 0.56 | 1.22 | 0.000 | 38 | 0.003023 | 100% σ=0.02ms |
| examples/timeout_demo.ainl | strict-valid | 49 | 2.29 | 1.31 | 1.30 | 1.35 | 1.29 | 1.37 | 0.000 | 2 | 0.000347 | 100% σ=0.08ms |

**LLM counters:** reserved for future agent/OpenAI adapter lanes; JSON ``llm_token_usage`` is **N/A** unless adapters report usage.

JSON: ``tooling/benchmark_runtime_results.json``
<!-- RUNTIME_BENCH_END -->
<!-- BASELINE_RUNTIME_BENCH_START -->
### Handwritten baseline runtime comparison

Mapped AINL rows use the **headline** profile from ``full_multitarget`` when that artifact appears in the current ``--profile-name`` selection. Handwritten runs use mocks; **adapter_calls** are N/A (no ``RuntimeEngine``). Costs use mapped **AINL source** tiktokens / combined handwritten ``.py`` sources with JSON ``economics`` assumptions.

| Workflow | AINL src tk | AINL mean (ms) | Pure mean (ms) | Lang mean (ms) | AINL RSS Δ | Pure RSS Δ | Lang RSS Δ | AINL/Pure | AINL/Lang | AINL `gpt-4o` USD | HW `gpt-4o` USD | AINL Rel | Pure Rel | Lang Rel | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| basic_scraper | 67 | — | 0.034 | 1.765 | — | 0.000 | 0.047 | — | — | 0.000475 | 0.011460 | 0% σ=0.00ms | 100% σ=0.00ms | 100% σ=0.07ms | Artifact not in current profile selection or runtime failed. |
| retry_timeout_wrapper | 54 | 0.031 | 1.280 | 4.068 | 0.016 | 0.000 | 0.094 | 0.02x | 0.01x | 0.000390 | 0.010365 | 100% σ=0.01ms | 100% σ=0.02ms | 100% σ=0.24ms | — |
| token_budget_monitor | 1047 | — | 0.233 | 4.227 | — | 0.000 | 0.078 | — | — | 0.007457 | 0.022860 | — | 100% σ=0.01ms | 100% σ=0.17ms | Artifact not in current profile selection or runtime failed. |
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
