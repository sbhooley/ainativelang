# Agent reports

This directory holds **research notes, field analyses, and LLM-assisted reviews** (e.g. cost-savings discussions, integration notes, exploratory write-ups). They are **not** independent third-party audits and should **not** be treated as proof of correctness, security, or production readiness.

**Committed operator evidence (tables + JSON):** [`docs/competitive/PRODUCTION_EVIDENCE.md`](../docs/competitive/PRODUCTION_EVIDENCE.md) · [`tooling/production_evidence.json`](../tooling/production_evidence.json)

**Honest savings scope:** [`docs/competitive/WHEN_AINL_DOES_NOT_HELP.md`](../docs/competitive/WHEN_AINL_DOES_NOT_HELP.md) — baseline A (prompt-loop) vs B (hand-optimized scripts) vs C (pure deterministic).

**Marketing guardrails:** [`docs/operations/OPERATOR_MARKETING_GUARDRAILS.md`](../docs/operations/OPERATOR_MARKETING_GUARDRAILS.md) — rules for operators and agents making public claims about AINL capabilities.

For engineering truth boundaries, use:

- **`STATUS.yaml`** — shipped vs aspirational
- **`tests/`** and CI — behavior and regressions
- **`AGENTS.md`** — operational gotchas for contributors and coding agents
- **`docs/CLAIMS_AND_EVIDENCE.md`** — claim crosswalk to reproducible scripts
