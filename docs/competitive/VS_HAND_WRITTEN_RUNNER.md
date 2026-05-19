# AINL vs a hand-written runner (the honest comparison)

> **Read first:** [`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) — this page is the practitioner-focused companion. It concedes the token point against baseline **B** ("hand-optimized scripts + LLM only at judgment gates") and makes the case AINL has to make: **compile, audit, and emit**.

---

## TL;DR

If a competent platform engineer writes a deterministic runner in Python (cron + a few `if`/`elif` branches + an LLM call at a single judgment gate), AINL is **not going to save them tokens**. The irreducible compiler win on routing is **~1.3–1.5×** ([`token_savings_results.json`](../../tooling/token_savings_results.json) → `methodology.savings_attribution.routing_elimination`), which is real but not a buying decision.

AINL wins this comparison on **three axes that aren't tokens**:

1. **Compile-time correctness for agent-authored ops code.** When an agent writes a Python runner and it ships with a bug, the bug ships to production. When an agent writes `.ainl` and runs `ainl validate --strict`, the compiler rejects the broken graph before deployment.
2. **Same source, multiple deployment targets.** A hand-written runner is hand-ported to LangGraph for streaming or Temporal for durability. AINL emits both from the same `.ainl` source.
3. **Hash-chained JSONL audit trail.** A runner ships `print()` and `logger.info`. AINL produces a tamper-evident JSONL execution tape suitable for SOC 2 / HIPAA evidence bundles.

If none of those are pain points for you, **you are not our ICP** — and that is the honest answer, not a sales objection.

---

## The workload

We compare the same task three ways: **AINL**, **hand-written Python runner**, and (for context) **prompt-loop agent**.

**Task:** HTTP health check every 5 minutes. If response is non-200 or latency > 2s, escalate via Slack. Log every run for audit.

**Source paths**

| Implementation | Path |
|----------------|------|
| AINL graph | [`examples/benchmark/enterprise_monitor.ainl`](../../examples/benchmark/enterprise_monitor.ainl) |
| Hand-written Python runner | [`benchmarks/handwritten_baselines/competitive/runner/enterprise_monitor_runner.py`](../../benchmarks/handwritten_baselines/competitive/runner/enterprise_monitor_runner.py) *(TBD — see tracker)* |
| LangGraph (authoring baseline) | [`benchmarks/handwritten_baselines/competitive/langgraph/enterprise_monitor_langgraph.py`](../../benchmarks/handwritten_baselines/competitive/langgraph/enterprise_monitor_langgraph.py) |
| Prompt-loop baseline (modeled) | `scripts/benchmark_compile_once_run_many.py` → `enterprise_monitor` scenario |

---

## The five-axis comparison

| Axis | AINL | Hand-written runner | Prompt-loop agent |
|------|------|---------------------|-------------------|
| **Tokens per healthy run** | 0 | 0 | ~107 (modeled, [`compile_once_run_many_results.json`](../../tooling/compile_once_run_many_results.json)) |
| **Tokens per incident run** | ~50 (one alert summary call) | ~50 (one alert summary call) | ~157 (orchestrate + summarize) |
| **Source tokens (authoring)** | 759 tk ([`competitor_baseline_tokens.json`](../../tooling/competitor_baseline_tokens.json)) | ~1,106 tk (hand-optimized Python baseline) | n/a (prose spec) |
| **First-run correctness when an LLM authors the source** | High (`ainl validate --strict` rejects broken graphs at compile time) | Low–Medium (Python runs until it hits the bad branch in production) | Low (no compile step at all) |
| **Audit trail** | JSONL with hash-chained `event_hash` per step (`ainl audit verify-jsonl`) | `print()` / `logger.info` text logs | Best-case structured logs in agent harness |
| **Lift to Temporal for durability** | `ainl emit --target temporal` — zero LOC | Hand-port: rewrite as `@workflow.defn` worker, add activities, signals, retries | Hand-port from scratch |
| **Lift to LangGraph for streaming UI** | `ainl emit --target langgraph` — zero LOC | Hand-port | Hand-port |
| **Maintenance when adding a new branch** | Edit `.ainl`, re-run `ainl validate --strict`, re-deploy | Edit Python, hope test coverage is good | Edit prompt template, hope few-shot still works |

**Token-cost conclusion:** On the steady-state runtime cost dimension, **AINL ties the hand-written runner**. On per-run tokens both are 0 on healthy runs and equivalent on incident runs (assuming both call the LLM at the same gate). The ~1.3–1.5× routing edge from the benchmark suite applies only when the runner still has 1–2 routing LLM calls left to eliminate.

**Where AINL pulls ahead:** the non-token axes — compile-time correctness, multi-target emit, and hash-chained audit. **These are the only three things you should be selling against baseline B.**

---

## When the runner team should actually consider AINL

Use this checklist. If **two or more** of these are true, the conversation is worth having. If zero are true, AINL doesn't help you enough to be worth a new dependency.

- [ ] **An LLM (Cursor, Claude, an autonomous agent) writes our ops/runner code today**, and we have shipped broken Python from it more than once.
- [ ] **We need to emit Temporal workers** (or LangGraph streaming, or FastAPI servers) **from the same source spec** without re-authoring.
- [ ] **We have compliance requirements** (SOC 2 / HIPAA / similar) **that need tamper-evident execution traces**, not application logs.
- [ ] **We run more than ~30 recurring jobs** of similar shape and want **one strict-validated source format** for all of them.
- [ ] **Our runner stack is bash + Python + n8n + Make.com** and consolidation has business value beyond token math.

If your stack is 5 cron entries in a tidy `monitors/` Python package with a CI test suite, **AINL is the wrong tool**. Keep your runner. We tell you this in [`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) and we mean it.

---

## What we are *not* claiming

- We are **not** claiming AINL is faster than a hand-written Python runner. Both run in milliseconds. Latency is not the wedge.
- We are **not** claiming AINL replaces Temporal's durability guarantees. Temporal is a worker engine with history persistence. AINL emits to Temporal; it does not compete with the durability layer.
- We are **not** claiming AINL has a smaller dependency footprint than `python -m monitors.health_check`. It does not.
- We are **not** claiming **token savings vs a competent baseline B runner.** The benchmark says ~1.3–1.5× on routing only, and a runner that already has zero routing LLM calls saves zero against AINL.

---

## Reproducing the comparison

```bash
# Source-token comparison (AINL vs hand-written Python vs LangGraph)
python scripts/benchmark_competitor_baselines.py
# → tooling/competitor_baseline_tokens.json

# Three-way runtime comparison (LLM-first vs hand-optimized vs compiled AINL)
python scripts/benchmark_token_savings.py
# → tooling/token_savings_results.json
# → savings_attribution.routing_elimination is the B-vs-C ratio (~1.4× on doc_processing)

# Compile-once vs prompt-loop (the 90–95% figure — only valid vs baseline A)
python scripts/benchmark_compile_once_run_many.py
# → tooling/compile_once_run_many_results.json
```

Pending additions (tracked in [`LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md)):

- `benchmarks/handwritten_baselines/competitive/runner/enterprise_monitor_runner.py` — the hand-written Python runner baseline this doc references.
- `scripts/benchmark_vs_hand_runner.py` — script that scores **AINL vs hand-written runner** on the five axes above (tokens, source size, compile-time error catch rate when LLM-authored, emit lift time, audit completeness).

When those land, this doc will be updated with concrete numbers in the table above; the qualitative `LOC` / `Lift` cells will become measured `≈ N hours` / `≈ N LOC` cells.

---

## See also

- [`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) — baseline A / B / C decision tree
- [`COMPARISON_TABLE.md`](COMPARISON_TABLE.md) — committed numbers vs LangGraph authoring + emit footprint
- [`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md) — operator field reports + missing-evidence disclosure
- [`../CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) — every numeric claim mapped to its baseline + script
- [`LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md) — visible roadmap for closing remaining gaps
