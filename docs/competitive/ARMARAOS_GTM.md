# ArmaraOS go-to-market wedge (when raw AINL vs cron is weak)

> **Canonical ICP lives elsewhere.** The "who is this for" question for AINL as a whole is answered in **[`../WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md)** — this document is **ArmaraOS-specific product positioning**: the stack diagram, install paths, persona-to-message mapping, and reference Hands. Read the canonical ICP doc first if you're trying to decide whether AINL fits your workload; come here for the *product* angle once you've decided AINL is in the running.

Many mature teams already run **deterministic scripts + LLM at judgment gates**. For them, pitching "AINL saves 80% vs your cron job" fails — see [`../WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md) for the full anti-pitch.

**ArmaraOS is the primary product wedge:** packaged agent OS + dashboard + validated **Hands** — not "replace your bash monitor with a compiler."

---

## Positioning one-liner

> **ArmaraOS runs agents; AINL compiles the deterministic work they repeat.** Download once, schedule validated workflows, audit executions — without re-prompting the model every cron tick.

---

## Who this is for (canonical version)

The full persona table — solo operators, agent-heavy shops, small teams needing audit, Temporal-curious teams, compliance-led shops, researchers — and the "not primary ICP" boundary live in [`../WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md#personas-where-ainl-fits-today). What this doc adds on top of that is the **product mapping** below: which ArmaraOS capability each persona reaches for first.

---

## The stack (what ships together)

```text
┌─────────────────────────────────────────────────────────┐
│  ArmaraOS desktop / daemon (~32 MB)                     │
│  Dashboard · chat · cron · MCP · graph memory           │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ainl-mcp            scheduled            App Store
   (authoring)         ainl run             (Hands)
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
              AI_Native_Lang compiler + runtime
              (strict IR · adapters · audit JSONL)
```

---

## Tier-1 capabilities (lead with these)

1. **Hands (openfang-hands packages)** — `ainl emit --target armaraos` produces **`HAND.toml`**, IR JSON, **`security.json`**. Operators install from App Store; kernel schedules runs.
2. **MCP authoring loop** — `ainl_get_started` → `ainl_validate` → `ainl_compile` → `ainl_run` with **`wizard_state_json`**. Agents compile before they execute side effects.
3. **Scheduled deterministic execution** — kernel injects **`AINL_ALLOW_IR_DECLARED_ADAPTERS=1`** on cron children; **`bundle.ainlbundle`** for graph-memory round-trip.
4. **Graph memory + persona** — Rust **`ainl_memory.db`** per agent; extractor/tagger optional; pairs with procedural **`memory.patch`** on Python side.
5. **Dashboard observability** — usage, eco mode, graph-memory prompt accounting, orchestration traces.

**De-emphasize in headline GTM:** 67 adapters, Solana, TikTok, blockchain — document for integrators, not homepage hero.

---

## Reference Hands / programs (strict-valid)

| Program | Role | LLM at runtime |
|---------|------|----------------|
| [`examples/benchmark/enterprise_monitor.ainl`](../../examples/benchmark/enterprise_monitor.ainl) | HTTP health monitor | **0** when healthy; 1 on incident |
| [`examples/workflows/support_ticket_router.ainl`](../../examples/workflows/support_ticket_router.ainl) | Triage + draft | 3 content calls; **0** routing tokens |
| [`examples/workflows/data_pipeline.ainl`](../../examples/workflows/data_pipeline.ainl) | Multi-adapter ETL | Deterministic + adapter I/O |
| [`openclaw/bridge/wrappers/token_budget_alert.ainl`](../../openclaw/bridge/wrappers/token_budget_alert.ainl) | OpenClaw daily budget digest | **0** (bridge adapters only) |

---

## Messaging vs raw AINL

| Message | Use when |
|---------|----------|
| "Download ArmaraOS — agents + dashboard + Hands" | Consumer / prosumer landing (**ainativelang.com**) |
| "Add `ainl-mcp` to your existing agent" | OpenClaw / Cursor / Claude Code integrators |
| "90–95% vs prompt-loop agents on recurring jobs" | Teams still re-prompting every cron (baseline A) |
| "Compile-once audit trail + strict validation" | Compliance, agent-authored ops |
| ~~"Replace your runner scripts"~~ | **Avoid** for baseline B/C teams |

---

## Install paths (copy-ready)

```bash
# Desktop product (recommended for non-developers)
# https://ainativelang.com/armaraos

# Existing MCP agent
pipx install 'ainativelang[mcp]' && ainl setup --auto

# ArmaraOS daemon MCP merge
ainl install-mcp --host armaraos
```

Hub docs: **[`docs/ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md)**, **`armaraos/docs/scheduled-ainl.md`**, **`armaraos/docs/mcp-a2a.md`**.

---

## Related

- **[`../WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md)** — canonical ICP and anti-ICP
- **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)**
- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)**
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)**
