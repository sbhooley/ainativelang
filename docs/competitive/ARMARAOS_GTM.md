# ArmaraOS go-to-market wedge (when raw AINL vs cron is weak)

Many mature teams already run **deterministic scripts + LLM at judgment gates**. For them, pitching "AINL saves 80% vs your cron job" fails — see **[`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md)**.

**ArmaraOS is the primary product wedge:** packaged agent OS + dashboard + validated **Hands** — not "replace your bash monitor with a compiler."

---

## Positioning one-liner

> **ArmaraOS runs agents; AINL compiles the deterministic work they repeat.** Download once, schedule validated workflows, audit executions — without re-prompting the model every cron tick.

---

## Who this is for

| Persona | Pain | ArmaraOS + AINL answer |
|---------|------|------------------------|
| **Solo operator / creator** | Agents burn tokens re-planning monitors and digests | **Hands** + scheduled **`ainl run`** — zero orchestration LLM on healthy paths |
| **Agent-heavy shop** | MCP tools ship broken orchestration | **Strict validate → compile → run** wizard; loop recovery seeds in chat |
| **Small team needing audit** | Scripts with no unified trace | JSONL execution tapes + dashboard usage/analytics |
| **Temporal-curious** | Don't want to hand-write worker boilerplate | Author **`.ainl`**, **`--emit temporal`** when durability is required |

**Not primary ICP:** Platform teams with mature runner fleets and zero LLM in deterministic paths (they are baseline B/C in **`WHEN_AINL_DOES_NOT_HELP.md`**).

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

- **[`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md)**
- **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)**
- **[`FROM_LANGGRAPH_TO_AINL.md`](FROM_LANGGRAPH_TO_AINL.md)**
- **[`AINL_AND_TEMPORAL.md`](AINL_AND_TEMPORAL.md)**
