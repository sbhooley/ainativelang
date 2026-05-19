# AINL Cost Savings Report — DEPRECATED

> **2026-05-19 audit:** This file was deprecated as part of the credibility/positioning pass tracked in [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](docs/competitive/LONG_TERM_FIXES_TRACKER.md) row **T1.11**.
>
> **Why:** The original report cited a **"7.2× cost reduction"** and **"$180.90/month savings"** derived from the project author's own "AINL King" operator deployment (17 cron jobs). Those numbers are real **operator** outputs but mixed methodologies, and the same figures appeared in **three different files** with **three different framings**, which made them too easy to over-quote without the baseline qualifier.
>
> **The original document is preserved unchanged** at [`archive/legacy_savings_reports/AINL_COST_SAVINGS_REPORT.md`](archive/legacy_savings_reports/AINL_COST_SAVINGS_REPORT.md) for provenance.

## Where to look instead

| What you wanted | Where it lives now |
|-----------------|--------------------|
| Reproducible orchestration-token benchmarks (baseline A vs C) | [`docs/CLAIMS_AND_EVIDENCE.md`](docs/CLAIMS_AND_EVIDENCE.md) §1, §2 + [`BENCHMARK.md`](BENCHMARK.md) + [`scripts/benchmark_*.py`](scripts/) |
| Operator field reports (Class b evidence) | [`docs/competitive/PRODUCTION_EVIDENCE.md`](docs/competitive/PRODUCTION_EVIDENCE.md) Cases 1–2 |
| Honest baseline filter (A/B/C) | [`docs/competitive/WHEN_AINL_DOES_NOT_HELP.md`](docs/competitive/WHEN_AINL_DOES_NOT_HELP.md) |
| Comparison vs hand-written runner (baseline B) | [`docs/competitive/VS_HAND_WRITTEN_RUNNER.md`](docs/competitive/VS_HAND_WRITTEN_RUNNER.md) |
| Class (a) third-party deployments | **0 committed yet** — tracked at [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](docs/competitive/LONG_TERM_FIXES_TRACKER.md) row **T2.7** |

**Going forward:** all cost-savings claims live in `docs/CLAIMS_AND_EVIDENCE.md` (with baseline tags) and `docs/competitive/PRODUCTION_EVIDENCE.md` (with classification labels). New numbers should not appear in additional top-level reports.
