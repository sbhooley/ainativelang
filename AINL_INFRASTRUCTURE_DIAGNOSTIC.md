# AINL Infrastructure Diagnostic Report — DEPRECATED

> **2026-05-19 audit:** This file was deprecated as part of the credibility/positioning pass tracked in [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](docs/competitive/LONG_TERM_FIXES_TRACKER.md) row **T1.11**.
>
> **Why:** The original report mixed real operator signals (17 active cron jobs on the project author's stack, 99.7% uptime metric) with **hypothetical** "traditional agent loop" baseline comparisons ($6.03/day orchestration vs $0.97/day AINL → $180.90/month savings). The same "**7.2×**" figure appeared here, in `AINL_COST_SAVINGS_REPORT.md`, and in `AINL_OPERATIONAL_DEPLOYMENT_REPORT.md` — each with slightly different framing — which made it easy to over-quote.
>
> **The original document is preserved unchanged** at [`archive/legacy_savings_reports/AINL_INFRASTRUCTURE_DIAGNOSTIC.md`](archive/legacy_savings_reports/AINL_INFRASTRUCTURE_DIAGNOSTIC.md) for provenance.

## Where to look instead

| What you wanted | Where it lives now |
|-----------------|--------------------|
| Reproducible orchestration-token benchmarks | [`docs/CLAIMS_AND_EVIDENCE.md`](docs/CLAIMS_AND_EVIDENCE.md) §1 + [`scripts/benchmark_compile_once_run_many.py`](scripts/benchmark_compile_once_run_many.py) |
| Operator field signals (Class b evidence) | [`docs/competitive/PRODUCTION_EVIDENCE.md`](docs/competitive/PRODUCTION_EVIDENCE.md) Cases 1–2 |
| Real uptime / reliability metrics | [`STATUS.yaml`](STATUS.yaml) (auto-refreshed by `scripts/refresh_repo_stats.py`); execution reliability percentages in [`tooling/benchmark_runtime_results.json`](tooling/benchmark_runtime_results.json) |
| Honest baseline filter | [`docs/competitive/WHEN_AINL_DOES_NOT_HELP.md`](docs/competitive/WHEN_AINL_DOES_NOT_HELP.md) |

**Going forward:** infrastructure diagnostics that include cost claims must source every numeric value from a committed JSON under `tooling/` (with the baseline tag attached) or be explicitly labeled as operator-specific scenario math.
