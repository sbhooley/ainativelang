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
