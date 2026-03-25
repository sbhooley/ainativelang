# Competitive

**Site mirror:** [`OVERVIEW.md`](OVERVIEW.md) (synced to ainativelang.com `/docs/competitive/`; `README.md` is not synced).

**Path tip:** filenames are **case-sensitive** on Linux and in URLs — the methodology doc is exactly **`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`** (not `versus_…`).

Use this section for comparative framing such as “AINL vs X” and category-definition materials.

Comparative docs should be grounded in **shipped** behavior (compiler, runtime, emitters, MCP) and link to **reproducible** benchmarks where numbers are claimed.

## Guides (v1.2.5+)

- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)** — 15-minute onboarding from graph-first Python to AINL + optional `--emit langgraph`.
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)** — keep AINL as source of truth; emit Temporal modules when you need durability workers.
- **[`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md)** — template for anonymized production savings worksheets (no fabricated stats).
- **[`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)** — commands and tables for head-to-head methodology using `BENCHMARK.md` / `benchmark_runtime`.
- **[`COMPARISON_TABLE.md`](COMPARISON_TABLE.md)** — metrics × stack; populated from committed benchmarks, **TBD** where we have no data.

## Related sections

- Fundamentals: [`../fundamentals/README.md`](../fundamentals/README.md)
- Case studies: [`../case_studies/README.md`](../case_studies/README.md)
- Architecture: [`../architecture/README.md`](../architecture/README.md)
- Hybrid emitters: [`../HYBRID_GUIDE.md`](../HYBRID_GUIDE.md)
- Benchmarks hub: [`../benchmarks.md`](../benchmarks.md)
