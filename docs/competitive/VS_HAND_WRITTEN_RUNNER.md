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

We measure the same three workloads across three implementation styles:
**AINL**, **`competent_python`** baseline-B (the runner a senior engineer
writes in an afternoon), and **`production_grade`** baseline-B (with the
retry / structured-logging / circuit-breaker / hash-chained-audit surface a
production deployment needs). For runtime per-run token cost see the
"Prompt-loop agent" column on the right — it is the **baseline A** number
we are *not* claiming a moat against here.

**Tasks:**

1. HTTP health check + IR-routed severity + LLM alert only on incident.
2. Support-ticket triage (2 classify calls + 1 draft call, IR routing).
3. Multi-source order-processing pipeline (8 IR branches, 0–1 LLM call).

**Source paths**

| Style | Files | Note |
|---|---|---|
| **AINL** | [`examples/benchmark/enterprise_monitor.ainl`](../../examples/benchmark/enterprise_monitor.ainl), [`examples/workflows/support_ticket_router.ainl`](../../examples/workflows/support_ticket_router.ainl), [`examples/workflows/data_pipeline.ainl`](../../examples/workflows/data_pipeline.ainl) | strict-valid; CI enforces |
| **`competent_python`** (baseline B) | [`benchmarks/handwritten_baselines/authoring_density/`](../../benchmarks/handwritten_baselines/authoring_density/) — `enterprise_monitor.py`, `support_ticket_router.py`, `data_pipeline_competent.py` | runnable; no audit surface |
| **`production_grade`** (baseline B + ops surface) | [`benchmarks/handwritten_baselines/production/`](../../benchmarks/handwritten_baselines/production/) — `enterprise_monitor.py`, `support_ticket_router.py`, `data_pipeline.py` | measurement skeletons with retry/breaker/audit — see that folder's `README.md` |

---

## The five-axis comparison — measured

All numbers in this section are emitted by `scripts/benchmark_vs_hand_runner.py` and committed to [`tooling/benchmark_vs_hand_runner.json`](../../tooling/benchmark_vs_hand_runner.json). Re-run with `python scripts/benchmark_vs_hand_runner.py`.

<!-- benchmark:vs-hand-runner-begin -->
### Per-workload measurements

| Workload | Style | Tokens | LOC | Audit 0–8 | Token ratio vs AINL | LOC ratio vs AINL |
|---|---|---:|---:|---:|---:|---:|
| enterprise_monitor | `ainl` | 759 | 69 | 7/8 | — | — |
|  | `competent_python` | 1106 | 160 | 0/8 | 1.46× | 2.32× |
|  | `production_python` | 2842 | 365 | 5/8 | 3.74× | 5.29× |
| support_ticket_router | `ainl` | 909 | 80 | 7/8 | — | — |
|  | `competent_python` | 1426 | 180 | 0/8 | 1.57× | 2.25× |
|  | `production_python` | 3290 | 405 | 5/8 | 3.62× | 5.06× |
| data_pipeline | `ainl` | 1628 | 155 | 7/8 | — | — |
|  | `competent_python` | 1942 | 224 | 0/8 | 1.19× | 1.45× |
|  | `production_python` | 4681 | 499 | 6/8 | 2.88× | 3.22× |

### Audit checklist — by row

| Row | AINL | competent (mean) | production (mean) |
|---|:--:|:--:|:--:|
| `event_hash_chain` | ✓ | 0/3 | 3/3 |
| `per_step_inputs` | ✓ | 0/3 | 3/3 |
| `per_step_outputs` | ✓ | 0/3 | 3/3 |
| `adapter_args` | ✓ | 0/3 | 3/3 |
| `approval_gates` | ✓ | 0/3 | 1/3 |
| `config_snapshot` | ✓ | 0/3 | 3/3 |
| `replayable` | ✓ | 0/3 | 0/3 |
| `regulatory_grade` | — | 0/3 | 0/3 |
<!-- benchmark:vs-hand-runner-end -->

### Aggregate (mean across three workloads)

| Axis | AINL | `competent_python` | `production_grade` | Prompt-loop (baseline A) |
|---|---:|---:|---:|---:|
| **Source tokens** (tiktoken cl100k_base) | 1× | 1.41× | 3.41× | n/a (prose spec) |
| **Source LOC** | 1× | 2.01× | 4.52× | n/a |
| **Audit posture** (8-row checklist; see [`benchmark_vs_hand_runner.json`](../../tooling/benchmark_vs_hand_runner.json) → `audit_rows`) | **7/8** | 0/8 | **5.33/8** | 0/8 |
| **Per-run tokens, healthy path** (modeled) | 0 | 0 | 0 | ~107 ([`compile_once_run_many_results.json`](../../tooling/compile_once_run_many_results.json)) |
| **Per-run tokens, incident path** | ~50 (1 summary call) | ~50 (1 summary call) | ~50 (1 summary call) | ~157 |
| **First-run correctness when an LLM authors the source** | `ainl validate --strict` rejects broken graphs | Python runs until it hits the bad branch | same as `competent_python` | no compile step at all |
| **Lift to Temporal worker** | `ainl emit --target temporal` — zero LOC | hand-port | hand-port | hand-port |
| **Lift to LangGraph node** | `ainl emit --target langgraph` — zero LOC | hand-port | hand-port | hand-port |

**Token-cost conclusion (unchanged from the qualitative argument):** at runtime, AINL ties a hand-written runner on a per-run basis. The wedge is *not* tokens.

**Source-cost story (measured, new):** the `competent_python` baseline is ~1.4× more source tokens than AINL for ~0/8 audit posture. The `production_grade` baseline is ~3.4× more source tokens to reach 5.33/8 audit posture — comparable to AINL's posture, at 3.4× the LOC. **AINL's measurable win against a competent runner is the audit / replay / multi-target-emit surface that ships at zero authoring cost, not raw tokens.**

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
# Five-axis baseline-B comparison (AINL vs competent_python vs production_grade)
python scripts/benchmark_vs_hand_runner.py
# → tooling/benchmark_vs_hand_runner.json
# → BENCHMARK.md vs-hand-runner section is rewritten in place
# → use --no-benchmark-md to skip the BENCHMARK.md rewrite

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

### What `production_grade` covers (and what it deliberately leaves out)

The `production_grade` baseline files are **measurement skeletons**, not deployed code. They were written to make the LOC / token / audit-checklist measurement defensible against the "you only counted skeleton code" critique — they ship the structural surface a senior engineer writes before going to production (typed retry/backoff, structured logging, circuit breaker, hash-chained audit JSONL, env-driven config) but they do *not* ship OTEL exporters, dead-letter queues, secret rotation, or liveness probes. A real deployment adds another 200–500 LOC for those concerns, which means this benchmark **understates** the source-size delta vs AINL on the observability axis. See [`benchmarks/handwritten_baselines/production/README.md`](../../benchmarks/handwritten_baselines/production/README.md) for the full caveat list.

### How the audit checklist is scored

The 8-row audit checklist is declared per-file in a `__benchmark_audit_checklist__` module constant (read via `ast.literal_eval`). The harness will not catch a lie there — the checklist is the declared score, not a static-analysis result. The rows are: `event_hash_chain`, `per_step_inputs`, `per_step_outputs`, `adapter_args`, `approval_gates`, `config_snapshot`, `replayable`, `regulatory_grade`. AINL is hard-coded to 7/8 (everything except `regulatory_grade`, which would require an external SOC 2 / HIPAA attestation we do not yet have) reflecting the runtime audit-trail guarantees in `runtime/engine.py` and the `ainl audit verify-jsonl` chain check.

---

## See also

- [`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) — baseline A / B / C decision tree
- [`COMPARISON_TABLE.md`](COMPARISON_TABLE.md) — committed numbers vs LangGraph authoring + emit footprint
- [`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md) — operator field reports + missing-evidence disclosure
- [`../CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) — every numeric claim mapped to its baseline + script
- [`LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md) — visible roadmap for closing remaining gaps
