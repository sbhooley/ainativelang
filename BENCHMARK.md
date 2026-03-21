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

Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline.

## Size Drivers (Actionable Diagnosis)

### minimal_emit
- `canonical_strict_valid` top targets: python_api=771, cron=197, scraper=154
- `canonical_strict_valid` top artifacts: examples/scraper/basic_scraper.ainl=253, examples/web/basic_web_api.ainl=106, examples/monitor_escalation.ainl=98

## Residual Overhead Audit (minimal_emit)

### canonical_strict_valid
- `python_api` total=771; structure: decorator_chunks=5, function_def_chunks=6, imports_chunks=56, return_chunks=6, total_chunks=771
- `cron` total=197; structure: function_def_chunks=11, pass_chunks=6, schedule_comment_chunks=180, total_chunks=197
- `scraper` total=154; structure: function_def_chunks=4, imports_chunks=11, request_call_chunks=18, return_chunks=17, selector_chunks=22, total_chunks=154

## Details (minimal_emit)

| Profile | Artifact count | AINL source total | Aggregate generated output total | Aggregate ratio |
|---|---:|---:|---:|---:|
| canonical_strict_valid | 10 | 506 | 1122 | 2.22x |

### canonical_strict_valid
| Artifact | Class | AINL source | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets || est $4o (USD) | est $C-Son (USD) || Compile reliability |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---||---:||---:||---|
| examples/crud_api.ainl | strict-valid | 37 | - | 95 | - | - | - | - | 95 | 2.57x | python_api | 0.000678 | 0.000942 | 100% σ=0.019ms |
| examples/hello.ainl | strict-valid | 18 | - | 95 | - | - | - | - | 95 | 5.28x | python_api | 0.000678 | 0.000942 | 100% σ=0.002ms |
| examples/if_call_workflow.ainl | strict-valid | 83 | - | 95 | - | - | - | - | 95 | 1.14x | python_api | 0.000678 | 0.000942 | 100% σ=0.034ms |
| examples/monitor_escalation.ainl | strict-valid | 72 | - | - | - | - | - | 98 | 98 | 1.36x | cron | 0.000705 | 0.000981 | 100% σ=0.005ms |
| examples/rag_pipeline.ainl | strict-valid | 29 | - | 95 | - | - | - | - | 95 | 3.28x | python_api | 0.000678 | 0.000942 | 100% σ=0.010ms |
| examples/retry_error_resilience.ainl | strict-valid | 54 | - | 95 | - | - | - | - | 95 | 1.76x | python_api | 0.000678 | 0.000942 | 100% σ=0.002ms |
| examples/scraper/basic_scraper.ainl | strict-valid | 67 | - | - | - | - | 154 | 99 | 253 | 3.78x | scraper, cron | 0.001803 | 0.002505 | 100% σ=0.003ms |
| examples/status_branching.ainl | strict-valid | 48 | - | 95 | - | - | - | - | 95 | 1.98x | python_api | 0.000678 | 0.000942 | 100% σ=0.028ms |
| examples/web/basic_web_api.ainl | strict-valid | 32 | - | 106 | - | - | - | - | 106 | 3.31x | python_api | 0.000758 | 0.001053 | 100% σ=0.013ms |
| examples/webhook_automation.ainl | strict-valid | 66 | - | 95 | - | - | - | - | 95 | 1.44x | python_api | 0.000678 | 0.000942 | 100% σ=0.009ms |


## Handwritten baseline size comparison

**AINL emitted** aggregates use the active benchmark metric (`tiktoken`) and, when available, **tiktoken** (**cl100k_base**) on the same emitted bundle. **Pure / Lang** columns count only `pure_async_python.py` / `langgraph_version.py` in each group.

### Emit mode `minimal_emit`

| Workflow | AINL reference | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD | AINL `claude-3-5-sonnet` USD | HW `claude-3-5-sonnet` USD ||
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | 253 | 253 | 92 | 88 | 870 | 738 | 0.29x | 0.34x | 0.001803 | 0.011460 | 0.002505 | 0.015924 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | 95 | 95 | 71 | 77 | 700 | 754 | 0.14x | 0.13x | 0.000678 | 0.010365 | 0.000942 | 0.014403 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | 0 | 0 | 159 | 163 | 1584 | 1624 | 0.00x | 0.00x | 0.000000 | 0.022860 | 0.000000 | 0.031764 |

### Emit mode `full_multitarget`

| Workflow | AINL reference | AINL emit (active) | AINL emit (tiktoken) | Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk | AINL `gpt-4o` USD | HW `gpt-4o` USD | AINL `claude-3-5-sonnet` USD | HW `claude-3-5-sonnet` USD ||
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:||
| basic_scraper | `examples/scraper/basic_scraper.ainl` | 731 | 731 | 92 | 88 | 870 | 738 | 0.84x | 0.99x | 0.005208 | 0.011460 | 0.007236 | 0.015924 |
| retry_timeout_wrapper | `examples/retry_error_resilience.ainl` | 563 | 563 | 71 | 77 | 700 | 754 | 0.80x | 0.75x | 0.004015 | 0.010365 | 0.005580 | 0.014403 |
| token_budget_monitor | `openclaw/bridge/wrappers/token_budget_alert.ainl` | 563 | 563 | 159 | 163 | 1584 | 1624 | 0.36x | 0.35x | 0.004015 | 0.022860 | 0.005580 | 0.031764 |


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
