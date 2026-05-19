# AINL Operational Deployment Report — DEPRECATED

> **2026-05-19 audit:** This file was deprecated as part of the credibility/positioning pass tracked in [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](docs/competitive/LONG_TERM_FIXES_TRACKER.md) row **T1.11**.
>
> **Why:** The original report described a real operator deployment ("The AINL King" / 17 cron jobs on the project author's OpenClaw stack) but framed the comparison as "$180.90/month savings vs traditional agent loops (7.2× cheaper)" — a figure that was modeled, not invoiced. The same "**7.2×**" number was also published in `AINL_COST_SAVINGS_REPORT.md` and `AINL_INFRASTRUCTURE_DIAGNOSTIC.md` with different methodologies, which made it too easy to over-quote.
>
> **The original document is preserved unchanged** at [`archive/legacy_savings_reports/AINL_OPERATIONAL_DEPLOYMENT_REPORT.md`](archive/legacy_savings_reports/AINL_OPERATIONAL_DEPLOYMENT_REPORT.md) for provenance.

## Where to look instead

| What you wanted | Where it lives now |
|-----------------|--------------------|
| Operator deployment (Class b evidence) — what actually runs | [`docs/competitive/PRODUCTION_EVIDENCE.md`](docs/competitive/PRODUCTION_EVIDENCE.md) Cases 1–2 |
| Modeled cost savings (Class c reproducible) | [`docs/CLAIMS_AND_EVIDENCE.md`](docs/CLAIMS_AND_EVIDENCE.md) §1 + [`scripts/benchmark_compile_once_run_many.py`](scripts/benchmark_compile_once_run_many.py) |
| Honest baseline filter — when AINL doesn't help | [`docs/competitive/WHEN_AINL_DOES_NOT_HELP.md`](docs/competitive/WHEN_AINL_DOES_NOT_HELP.md) |
| Five-axis comparison vs hand-written runner | [`docs/competitive/VS_HAND_WRITTEN_RUNNER.md`](docs/competitive/VS_HAND_WRITTEN_RUNNER.md) |

**Going forward:** operational deployment write-ups go into `docs/case_studies/` with explicit Class (a/b/c/d) classification per row in `tooling/production_evidence.json` (schema 1.1+).
