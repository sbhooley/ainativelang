# Competitive

**Site mirror:** [`OVERVIEW.md`](OVERVIEW.md) (synced to ainativelang.com `/docs/competitive/`; `README.md` is not synced).

**Path tip:** filenames are **case-sensitive** on Linux and in URLs — the methodology doc is exactly **`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`** (not `versus_…`).

Use this section for comparative framing such as “AINL vs X” and category-definition materials.

Comparative docs should be grounded in **shipped** behavior (compiler, runtime, emitters, MCP) and link to **reproducible** benchmarks where numbers are claimed.

**Orchestration-token / density claims:** cite **[`BENCHMARK.md`](../BENCHMARK.md)** and the analytical scripts documented in **[`docs/benchmarks.md`](../benchmarks.md)** § *Analytical orchestration-token economics* (`scripts/benchmark_token_savings.py`, `benchmark_compile_once_run_many.py`, `benchmark_authoring_density.py`); full crosswalk **[`docs/CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md)**. [`COMPETITIVE_MESSAGING.md`](COMPETITIVE_MESSAGING.md) includes an explicit qualifier on the token-efficiency matrix row.

## Guides (v1.2.5+ baseline; **v1.8.0** target line — PyPI after publish — **`docs/RELEASING.md`**)

- **[`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md)** — honest ICP filter and baseline A/B/C matrix (read before citing savings).
- **[`ARMARAOS_GTM.md`](ARMARAOS_GTM.md)** — primary product wedge: Hands, MCP, dashboard (not "replace your cron").
- **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)** — committed operator case tables + JSON mirror.
- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)** — 15-minute onboarding from graph-first Python to AINL + optional `--emit langgraph`.
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)** — keep AINL as source of truth; emit Temporal modules when you need durability workers.
- **[`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md)** — worksheet + filled OpenClaw examples.
- **[`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)** — commands and tables for head-to-head methodology using `BENCHMARK.md` / `benchmark_runtime`.
- **[`COMPARISON_TABLE.md`](COMPARISON_TABLE.md)** — metrics × stack; LangGraph authoring baselines + production §G rows.

## Related sections

- Fundamentals: [`../fundamentals/README.md`](../fundamentals/README.md)
- Case studies: [`../case_studies/README.md`](../case_studies/README.md)
- Architecture: [`../architecture/README.md`](../architecture/README.md)
- Hybrid emitters: [`../HYBRID_GUIDE.md`](../HYBRID_GUIDE.md)
- Benchmarks hub: [`../benchmarks.md`](../benchmarks.md)
