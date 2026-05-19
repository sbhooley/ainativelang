# When AINL does not help (honest ICP filter)

This page exists so operators, reviewers, and community skeptics can **self-select out** without a sales conversation. It pairs with **[`CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md)** and the three-way benchmark in **[`scripts/benchmark_token_savings.py`](../../scripts/benchmark_token_savings.py)**.

**Short answer:** If your team already runs **deterministic scripts or runners** and invokes an LLM **only at genuine judgment gates**, AINL is usually **not** a token-savings play. The irreducible compiler benefit against that baseline is about **1.3–1.5× on routing tokens** — see **`tooling/token_savings_results.json`** → `methodology.savings_attribution.routing_elimination`.

---

## The three baselines (read this before any savings claim)

| Baseline | What it looks like | Typical AINL win | Worth adopting for tokens alone? |
|----------|-------------------|------------------|----------------------------------|
| **A. LLM-first / prompt-loop** | Agent re-prompts for routing, state, and next-step on every cron/webhook | **~90–95%** orchestration tokens on recurring monitors (see **`benchmark_compile_once_run_many.py`**) | **Often yes** |
| **B. Hand-optimized** | Deterministic runner + LLM only for classify/draft/content | **~1.3–1.5×** on routing (IR eliminates duplicate classify→route LLM steps) | **Usually no** — see non-token reasons below |
| **C. Pure deterministic** | Bash/Python/cron, **zero** LLM in the loop | **~0%** | **No** |

Most experienced platform teams are already **baseline B or C**. That is not a failure of AINL — it means they already applied the engineering discipline AINL formalizes.

---

## Workload patterns where AINL adds little or nothing

### Pure deterministic automation

**Examples:** Jira webhook → pytest runner; CSV diff; board sync; inbound email file check; Notion CRM row updates.

**Why AINL loses:** No LLM orchestration to eliminate. AINL runtime is an extra dependency for the same outcome.

**Better fit:** Keep your runner script. Optionally use AINL only if you need **strict graph validation**, **JSONL audit**, or **emit to Temporal/LangGraph** for durability — not for token math.

### Judgment-heavy semantic pipelines

**Examples:** Multi-phase content synthesis (summarize → critique → cross-link); creative manuscript tooling; outreach drafting.

**Why AINL loses:** The cost is **content LLM calls**, not routing. You cannot compile semantic reasoning into deterministic IR.

**Better fit:** LLM sessions with human review. Use AINL only for **deterministic glue** between phases (webhooks, cache, queue) if you want one auditable artifact.

### Already-gated email / triage pipelines

**Examples:** Runner checks inbox → spawn LLM session only when triage requires it.

**Why AINL loses:** This **is** baseline B. One semantic call at the gate is optimal.

**Better fit:** Keep the gate script. AINL helps only if the **routing tree below the gate** is large, changes often, and is currently maintained by multiple agents without compile-time checks.

### Low-volume ticket classifiers

**Examples:** Support tickets classified a few times per day with a stable category tree.

**Why AINL loses:** A Python `if category == "billing": …` table is fine at low volume. See **`examples/workflows/support_ticket_router.ainl`** — it exists, but the economic case needs **volume + change frequency + agent-authored maintenance**.

**Better fit:** Hand-written router until volume or compliance audit cost justifies a compiled graph.

---

## What AINL is still good for (even when tokens are not)

| Need | Why runner scripts fall short | AINL surface |
|------|------------------------------|--------------|
| **Agent-authored ops code** | Agents ship broken Python/orchestration | MCP wizard: validate → compile → run with **`ainl validate --strict`** |
| **Audit / compliance** | Ad-hoc logs across scripts | JSONL trajectory + hash-chained audit patterns |
| **Portable durability** | Hand-port to Temporal workers | **`--emit temporal`** from same `.ainl` source |
| **Cross-adapter orchestration** | N scripts + glue | Single IR graph: `http`, `cache`, `queue`, `llm`, … |
| **ArmaraOS product path** | Custom cron + dashboard glue | **Hands**, scheduled **`ainl run`**, graph memory, App Store |

See **[`ARMARAOS_GTM.md`](ARMARAOS_GTM.md)** for the primary product wedge when raw AINL vs cron is a weak sell.

---

## Fair questions from reviewers (and our answers)

### "Show me production where this saved real money vs Temporal or a standard runner."

**Status:** Committed operator evidence lives in **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)** (anonymized OpenClaw / ArmaraOS operator worksheets). **`COMPARISON_TABLE.md`** §G links the same rows.

**Honest scope:** Rows document **orchestration-token elimination** and **architectural efficiency** on OpenClaw-style workloads — not a head-to-head Temporal durability benchmark (different layer).

### "Your competitor table is empty."

**Status:** LangGraph **authoring** baselines for two reference workloads are in **`benchmarks/handwritten_baselines/competitive/langgraph/`**, with token counts in **`tooling/competitor_baseline_tokens.json`**. See **`COMPARISON_TABLE.md`** §A–B (updated from that artifact).

We still do **not** claim parity with Temporal server features or LangGraph streaming UX — see **[`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)**.

### "You're spread across too many domains."

**Public tier-1 surface (marketing + strict-valid references):**

- **`core`**, **`http`**, **`llm/*`**, **`cache`**, **`fs`**, **`memory`**, **`queue`**
- **MCP authoring** + **ArmaraOS bridge** (`ainl_graph_memory`, scheduled runs, Hands)

Community adapters (Solana, TikTok, CRM, …) remain in-repo for integrators but are **not** the headline ICP story.

---

## Decision tree (30 seconds)

```text
Does this workload call an LLM to decide routing/state on every run?
  NO  → AINL is unlikely to save tokens. Consider audit/emit/MCP/ArmaraOS only.
  YES → Is the team willing to compile once and run via ainl run / runner / Hand?
          NO  → Fix the agent loop first; AINL won't help until execution is deterministic.
          YES → Measure vs prompt-loop baseline (BENCHMARK.md compile-once scenarios).
                 If already hand-optimized scripts → expect ~1.3–1.5× routing win max.
```

---

## Related

- **[`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md)** — committed operator case blocks
- **[`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md)** — worksheet template + filled example
- **[`ARMARAOS_GTM.md`](ARMARAOS_GTM.md)** — product wedge (Hands, MCP, dashboard)
- **[`COMPETITIVE_MESSAGING.md`](COMPETITIVE_MESSAGING.md)** — persona messaging (includes qualifiers)
- **[`CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md)** — claim crosswalk
