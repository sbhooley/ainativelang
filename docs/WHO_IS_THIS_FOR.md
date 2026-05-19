# Who is AINL for?

> **Status: canonical.** This is the single source of truth for AINL's ideal customer profile (ICP) and anti-ICP. The README's 60-second filter is a teaser; everything sales, marketing, and onboarding material should link here for the full picture. Companion docs: [`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) for what we'll defend with measured artifacts, and [`competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) for what's deployed today.

**Short answer.** AINL is the right tool when your **agents author orchestration code**, your **recurring jobs re-prompt an LLM to decide routing** on every run, or your **compliance audit story is "scattered scripts and `logger.info`"**. It is *not* the right tool when your team already runs deterministic scripts with the LLM only at genuine judgment gates — that team is already doing the right thing, and AINL's irreducible win against that baseline is roughly **1.3–1.5×** on routing tokens. We'd rather you self-select out in five minutes than spend a week on a tool that doesn't fit.

---

## The 60-second filter

A slightly-expanded version of the table in the [README](../README.md#is-ainl-for-you-60-second-filter):

| ✅ AINL is a good fit if… | ❌ AINL is *not* a good fit if… |
|:--|:--|
| Your agents (Cursor, Claude Code, autonomous loops) **author runner / orchestration code** and have shipped broken Python or YAML more than once | You write all your runners by hand and your CI test suite catches the bugs |
| You run **20+ recurring monitor / digest / scheduled jobs** that currently **re-prompt an LLM on every run** to decide routing, state, or next step | You already have deterministic runners with the LLM only at genuine judgment gates — congrats, you are **baseline B** below and AINL's win against you is ~1.3–1.5× on routing only |
| You need **the same workflow source** to emit to LangGraph **and** Temporal **and** FastAPI without re-authoring | One target is fine for you forever |
| You have **compliance audit needs** (SOC 2 / HIPAA / similar) that want tamper-evident execution traces, not application logs | `logger.info` is enough for your team |
| You want **strict compile-time validation** of agent workflows before they hit production | Runtime exceptions are fine, you have alerting and on-call rotation |
| You ship an **end-user-facing agent product** (consumer / prosumer) and need a download-once schedule-validated-workflows path | You're a platform team with a runner fleet and zero LLM in deterministic paths |

If you check two or more left-column rows, keep reading. If you check zero, the rest of this document explains *why* and saves you the install — we mean it.

---

## The three baselines (the most important framing in this document)

Every "AINL saves X% on tokens" claim is implicitly **vs. a specific baseline**. Without naming the baseline, savings numbers are marketing noise. We name three.

| Baseline | What it looks like in practice | Typical AINL win | Worth adopting for token savings alone? |
|----------|--------------------------------|------------------|------------------------------------------|
| **A — LLM-first / prompt-loop** | Agent re-prompts an LLM for routing, state, and next-step on every cron / webhook tick | **~90–95%** orchestration tokens on recurring monitors (see [`scripts/benchmark_compile_once_run_many.py`](../scripts/benchmark_compile_once_run_many.py)) | **Often yes** |
| **B — Hand-optimized** | Deterministic runner / scripts + LLM only for classify / draft / content judgment | **~1.3–1.5×** on routing (IR eliminates duplicate classify→route LLM steps) | **Usually no** — see [non-token reasons below](#what-ainl-is-still-good-for-when-tokens-arent-the-play) |
| **C — Pure deterministic** | Bash / Python / cron, **zero** LLM in the loop | **~0%** | **No** |

Most experienced platform teams are already **baseline B or C**. **That is not a failure of AINL** — it means they already applied the engineering discipline AINL formalizes. They might still adopt AINL for *non-token reasons* (audit, multi-target emit, agent-authored ops); they should not adopt AINL on a "save tokens" pitch.

The methodology behind these numbers, including the analytical token counter and the compile-once / run-many model, lives in [`docs/CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) and [`BENCHMARK.md`](../BENCHMARK.md). The measured AINL vs hand-written Python comparison is in [`docs/competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md).

---

## Personas where AINL fits today

| Persona | Pain | AINL + ArmaraOS answer |
|---------|------|--------------------------|
| **Solo operator / creator** running their own agent stack | Agents burn tokens re-planning monitors and digests on every tick; cron logs are a mess | **Hands** + scheduled **`ainl run`** — zero orchestration LLM on healthy paths; usage and audit visible in the desktop dashboard |
| **Agent-heavy shop** where MCP tools or chat-style agents are the dominant interface | Agent-authored orchestration ships broken; failures repeat because there's no compile-time validation | MCP wizard: **`ainl_get_started` → `ainl_validate` → `ainl_compile` → `ainl_run`** with **`wizard_state_json`**; the agent compiles before it executes side effects |
| **Small team needing audit** without enterprise infrastructure | Scripts log to stdout; auditors want a unified trace | JSONL execution tapes, hash-chained `audit_trail` adapter, run records readable by humans and `ainl audit verify-jsonl` |
| **Temporal-curious** team that doesn't want to hand-write workers yet | Maintaining Temporal workflow code feels heavy for the level of durability needed | Author **`.ainl`** once, **`--emit temporal`** when durability is required, **`--emit langgraph`** when LLM-streaming UX is required |
| **Compliance-led shop** (SOC 2 in progress, HIPAA boundary) | Need to prove orchestration is deterministic at run-time and gated at compile-time | Strict-mode compile blocks unsafe constructs; security profiles + adapter privilege tiers gate side effects; audit JSONL is the artifact auditors actually want |
| **Researcher / educator** who wants to reason about agent workflows formally | Treating "LLM + Python glue" as a research artifact is awkward | AINL IR is a small, public, deterministic graph IR — citable, reproducible, comparable across runs |

**Not primary ICP.** Platform teams with mature runner fleets and zero LLM in deterministic paths. They are baseline B/C. We are happy to be wrong about this for any specific team that runs the [decision tree](#decision-tree-30-seconds) and disagrees.

---

## Workload patterns where AINL adds little or nothing

### Pure deterministic automation

**Examples.** Jira webhook → pytest runner; CSV diff; board sync; inbound email file check; Notion CRM row updates.

**Why AINL loses.** No LLM orchestration to eliminate. The AINL runtime is an extra dependency for the same outcome.

**Better fit.** Keep your runner script. Optionally use AINL only if you need **strict graph validation**, **JSONL audit**, or **`--emit temporal`** durability — not for token math.

### Judgment-heavy semantic pipelines

**Examples.** Multi-phase content synthesis (summarize → critique → cross-link); creative manuscript tooling; outreach drafting; "meta-synthesis" over a knowledge base.

**Why AINL loses.** The cost is **content LLM calls**, not routing. You cannot compile semantic reasoning into deterministic IR — the whole point of those calls is that they need judgment.

**Better fit.** LLM sessions with human review. Use AINL only as **deterministic glue** between phases (webhooks, cache, queue) if you want one auditable artifact spanning multiple semantic stages.

### Already-gated triage / email pipelines

**Examples.** Runner checks inbox → spawns an LLM session only when triage requires it.

**Why AINL loses.** This **is** baseline B. One semantic call at the gate is optimal. AINL formalizes the pattern; it doesn't improve the economics.

**Better fit.** Keep the gate script. AINL helps only if the **routing tree below the gate** is large, changes often, and is currently maintained by multiple agents without compile-time checks.

### Low-volume ticket / classification routing

**Examples.** Support tickets classified a few times per day with a stable category tree.

**Why AINL loses.** A Python `if category == "billing": …` table is fine at low volume. The economic case for compiled routing needs **volume + change frequency + agent-authored maintenance**, not just "we have a ticket system."

**Better fit.** Hand-written router until volume or compliance audit cost justifies a compiled graph. See [`examples/workflows/support_ticket_router.ainl`](../examples/workflows/support_ticket_router.ainl) for the AINL version of this pattern, kept for the cases where it does justify itself.

---

## What AINL is still good for when tokens aren't the play

Even if your token math doesn't favor AINL, these are real reasons to adopt it. None of them are token-savings claims:

| Need | Why hand-written scripts fall short | Where AINL helps |
|------|--------------------------------------|-------------------|
| **Agent-authored ops code** | Agents reliably ship broken Python or YAML; humans catch maybe 80% in review | MCP authoring wizard: `ainl_get_started` → `ainl_validate --strict` → `ainl_compile` → `ainl_run`; the compiler is the agent's auto-corrector |
| **Audit / compliance** | Ad-hoc logs across scripts; auditors want a unified trace | JSONL execution tapes, hash-chained `audit_trail`, `ainl audit verify-jsonl` |
| **Portable durability** | Hand-port your orchestration to Temporal workers when durability matters | `--emit temporal` from the same `.ainl` source; one author-time artifact, multiple deploy-time runtimes |
| **Cross-adapter orchestration with one source of truth** | N runner scripts plus glue plus a Slack notifier plus a Postgres write plus a queue flush | Single IR graph spans `http`, `cache`, `queue`, `llm/*`, `audit_trail`, … with one strict-validated artifact |
| **Product path for end-user agents** | Custom cron + dashboard + permission glue per app | ArmaraOS **Hands**, scheduled `ainl run`, graph memory, App Store — see [`competitive/ARMARAOS_GTM.md`](competitive/ARMARAOS_GTM.md) |
| **Formal reasoning over workflows** | Compare "LLM + Python glue" across runs is impossible | IR `--inspect`, `--visualize`, deterministic diff, run-snapshot fingerprinting |

If at least one row in this table is a real pain you have, AINL is worth a one-week evaluation regardless of where your token math lands.

---

## Decision tree (30 seconds)

```text
Does this workload call an LLM to decide routing / state on every run?

  NO  → AINL is unlikely to save tokens.
        Consider it only for audit / multi-target emit / MCP authoring / ArmaraOS product path.

  YES → Is your team willing to compile once and run via `ainl run` / runner service / Hand?

          NO  → Fix the agent loop first. AINL doesn't help until execution is deterministic.

          YES → Measure against the prompt-loop baseline using
                `scripts/benchmark_compile_once_run_many.py`.
                If your starting point is already hand-optimized scripts,
                expect ~1.3–1.5× routing win — make the decision on non-token reasons.
```

---

## Fair questions reviewers ask (and our honest answers)

### "Show me production where this saved real money vs Temporal or a standard runner."

The status: committed operator evidence lives in [`competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) (anonymized OpenClaw / ArmaraOS operator worksheets, classified by evidence tier `(a)`–`(d)`). [`competitive/COMPARISON_TABLE.md`](competitive/COMPARISON_TABLE.md) §G links the same rows.

The honest scope: those rows document **orchestration-token elimination** and **architectural efficiency** on OpenClaw-style workloads. They are not a head-to-head Temporal durability benchmark — that's a different layer and we don't claim parity there.

### "Your competitor table is empty."

The status: LangGraph **authoring** baselines for two reference workloads are in [`benchmarks/handwritten_baselines/competitive/langgraph/`](../benchmarks/handwritten_baselines/competitive/langgraph/), with token counts in [`tooling/competitor_baseline_tokens.json`](../tooling/competitor_baseline_tokens.json). The full crosswalk is in [`competitive/COMPARISON_TABLE.md`](competitive/COMPARISON_TABLE.md) §A–B and the measured hand-written Python comparison is in [`competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md).

We still do **not** claim parity with Temporal's server features or LangGraph's streaming UX — see [`competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md) for the boundary.

### "You're spread across too many domains."

The marketing surface and the supported-but-niche surface are now explicit:

- **Core orchestration primitives (29 adapters):** `core`, `http`, `fs`, `memory`, `cache`, `queue`, `sqlite`, the major databases, `audit_trail`, `tool_registry`, `llm/*`, the MCP authoring layer, the ArmaraOS bridge. **These are the ICP.**
- **Extended catalog (16 adapters):** Solana, TikTok, browser automation, niche interop bridges. Fully supported, in the same package, but not the headline story.

The split, the rationale, and the per-adapter list live in [`adapters/ADAPTER_TIERS.md`](adapters/ADAPTER_TIERS.md). Nothing has been deprecated.

### "Is this an enterprise product?"

The maintainer-team's product wedge today is **ArmaraOS for individuals + small operator teams** — see [`competitive/ARMARAOS_GTM.md`](competitive/ARMARAOS_GTM.md). Enterprise-grade SLAs, compliance attestations, and managed services are described in [`COMMERCIAL.md`](../COMMERCIAL.md) and are explicitly separate from the open-source surface. **Enterprise does not require holding $AINL tokens** — see [`enterprise/ENTERPRISE_FAQ.md`](enterprise/ENTERPRISE_FAQ.md).

### "Who actually builds this?"

Founder-led, multi-contributor, AI-assisted from day one. Active human maintainers: **Steven B Hooley** (founder), **Terrance Schonleber**, **Kobe Welker**. Distinct AI co-author identities (`hermes_ainl`, `ainl king`, `plushify`, `ainl agent`) are listed in [`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Live, reproducible commit counts are in [`tooling/token_status.json`](../tooling/token_status.json).

---

## Where to go next (depending on what you ticked)

| If you're… | Read next |
|---|---|
| Already convinced and want to install | [README → install](../README.md#for-agents--install-ainl-one-step) or [getting started](getting_started/README.md) |
| Considering the desktop product | [`competitive/ARMARAOS_GTM.md`](competitive/ARMARAOS_GTM.md), then [ainativelang.com/armaraos](https://ainativelang.com/armaraos) |
| Sales / messaging copy author | [`competitive/COMPETITIVE_MESSAGING.md`](competitive/COMPETITIVE_MESSAGING.md), then this doc |
| Reviewer / skeptic running a one-week eval | [`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md), [`competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md), [`competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) |
| Compliance / audit lead | [`enterprise/SHARED_RESPONSIBILITY.md`](enterprise/SHARED_RESPONSIBILITY.md), [`enterprise/SOC2_CHECKLIST.md`](enterprise/SOC2_CHECKLIST.md), [`operations/AINL_SOC2_CONTROL_MAPPING.md`](operations/AINL_SOC2_CONTROL_MAPPING.md) |
| Contributor (human or AI) | [`AUDIENCE_GUIDE.md`](AUDIENCE_GUIDE.md) for entry-point routing, then [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |

---

## Document hygiene

This page replaces the standalone `docs/competitive/WHEN_AINL_DOES_NOT_HELP.md` (now a pointer stub). The persona table that previously lived in `docs/competitive/ARMARAOS_GTM.md` has been absorbed here; `ARMARAOS_GTM.md` continues to own ArmaraOS-specific positioning, the stack diagram, and product-page messaging. The README's 60-second filter is the teaser; this is the long-form answer.

If you find the same ICP statement made differently in two places in the repo, the canonical wording is the wording on this page.
