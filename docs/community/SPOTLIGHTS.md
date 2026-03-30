# Community spotlights

Monthly highlights of real AINL programs, contributors, and outcomes. Entries are curated; submit ideas via [GitHub Discussions](https://github.com/sbhooley/ainativelang/discussions).

---

## Template (copy for each month)

```markdown
## YYYY-MM — [Project title]

**Project:** [One line: what it does]

**Savings / outcome:** [e.g. cost multiple, latency, audit wins]

**Link:** [.ainl in repo](url) · [report or blog](url)

**Contributor:** [Name or handle] · [org if public]

**Notes:** [Optional: stack, emit target, OpenClaw/cron, etc.]
```

---

## 2026-03 — Email volume monitor → escalation (OpenClaw)

**Project:** Routine monitoring workflow that checks inbox volume, applies policy gates, and escalates when thresholds are exceeded — compiled once, no orchestration LLM at runtime.

**Savings / outcome:** ~7.2× lower aggregate cost vs equivalent agent-loop monitoring (see cost report); JSONL execution tape for audit.

**Link:** [`examples/monitor_escalation.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/monitor_escalation.ainl) · [`openclaw/bridge/wrappers/email_monitor.ainl`](https://github.com/sbhooley/ainativelang/blob/main/openclaw/bridge/wrappers/email_monitor.ainl) · [AINL_COST_SAVINGS_REPORT.md](https://github.com/sbhooley/ainativelang/blob/main/AINL_COST_SAVINGS_REPORT.md)

**Contributor:** AINL team (internal dogfood) — story: [Built with AINL: OpenClaw monitoring](https://ainativelang.com/blog/built-with-ainl-openclaw-monitoring-cheaper) (when published on site)

**Notes:** OpenClaw cron + Hermes-friendly emits; strict compiler validation before deploy.

---

## 2026-03 — Solana balance monitor + budget alert (external builder)

**Project:** Deterministic Solana balance checker with policy-style budget gates and branch outcomes — **zero runtime LLM cost**, full JSONL audit tape when traced.

**Savings / outcome:** No orchestration tokens on the monitoring path; predictable RPC-only cost; execution tape supports compliance and incident review.

**Link:** [`examples/monitoring/solana-balance.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/monitoring/solana-balance.ainl) · [Solana quickstart](https://github.com/sbhooley/ainativelang/blob/main/docs/solana_quickstart.md)

**Contributor:** External builder — *adapted from Solana treasury monitoring needs; shared with the community. [Share your own in Discussions #14.](https://github.com/sbhooley/ainativelang/discussions/14)*

**Notes:** Uses `solana.GET_BALANCE` + `core.gt` budget gate; swap pubkey and thresholds for your treasury. See `docs/solana_quickstart.md` for `[solana]` extra and dry-run.

---

## 2026-03 — RAG cache warmer (independent developer)

**Project:** Simple vector index **cache warmer** — upserts chunk placeholders into `vector_memory`, verifies with `SEARCH`, gated by an explicit ops budget branch — **strict validation**, **zero runtime orchestration LLM**.

**Savings / outcome:** Deterministic priming path vs ad-hoc embedding scripts; predictable adapter surface; JSONL tape when traced.

**Link:** [`examples/rag/cache-warmer.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/rag/cache-warmer.ainl) · [`examples/test_adapters_full.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/test_adapters_full.ainl) (related adapter patterns)

**Contributor:** Independent developer — *built while migrating from a LangChain embedding pipeline; no runtime orchestration LLM needed. [Share a similar story in Discussions #14.](https://github.com/sbhooley/ainativelang/discussions/14)*

**Notes:** Run with `--enable-adapter vector_memory`. Tune `ops_budget` / `ops_used` or replace with your metering source.

---

## 2026-03 — CRM simple lead router (independent builder)

**Project:** **Deterministic lead router** with **policy gates** and **full audit tape** — score-based branch (sales vs nurture), **ops budget gate**, routing decisions written to SQLite via **`crm_db.P`**; strict validation, **zero runtime orchestration LLM**.

**Savings / outcome:** Deterministic routing vs ad-hoc LLM classification loops; recurring orchestration token cost stays at **0**; JSONL tape for compliance review when traced.

**Link:** [`examples/crm/simple-lead-router.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/crm/simple-lead-router.ainl) · [`adapters/crm_db.py`](https://github.com/sbhooley/ainativelang/blob/main/adapters/crm_db.py)

**Contributor:** Independent builder — *replaced a prompt-based routing step with a compiled AINL graph; auditable branching was the key selling point internally. [Add your routing or CRM story in Discussions #14.](https://github.com/sbhooley/ainativelang/discussions/14)*

**Notes:** Set `CRM_DB_PATH` or default workspace DB; use `R crm_db.P` dotted form for strict mode. Tune `lead_score` / thresholds for your funnel.

---

## 2026-03 — Enterprise audit-log demo (compliance-focused team)

**Project:** Self-contained monitoring slice with explicit **policy thresholds**, deterministic **policy gate** evaluation (`lat_bad`, `err_bad`), and full JSONL execution tape — designed specifically as an **auditor-reviewable artifact** for SOC 2 evidence bundles.

**Savings / outcome:** Concrete, replay-oriented audit evidence (tape + `ainl check --strict` output) instead of reconstructing intent from chat logs; maps directly to CC7.2 (monitoring) and CC8.1 (change management) discussion points.

**Link:** [`examples/enterprise/audit-log-demo.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/enterprise/audit-log-demo.ainl) · [SOC 2 alignment checklist](https://github.com/sbhooley/ainativelang/blob/main/docs/enterprise/SOC2_CHECKLIST.md)

**Contributor:** Compliance-focused team evaluating AINL for a regulated stack — *shared as a reference pattern for audit-driven deployments. [Share your own compliance workflow in Discussions #16.](https://github.com/sbhooley/ainativelang/discussions/16)*

**Notes:** Core-only (no external adapter); run with `--trace-jsonl audit.tape.jsonl` and archive alongside the commit SHA and `ainl check --strict` output for your evidence bundle.
