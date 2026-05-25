# Claims and reproducible evidence

This document maps **public-facing statements** in this repository to **defensible, reproducible artifacts**. It does **not** replace narrative reports or field analyses; it shows where numbers can be re-derived locally.

> **Mandatory baseline qualifier.** Every numeric claim below is tagged with the baseline it requires. **Do not** quote any percentage / multiplier without the baseline tag. See [`docs/WHO_IS_THIS_FOR.md`](WHO_IS_THIS_FOR.md#the-three-baselines-the-most-important-framing-in-this-document) for the A/B/C definitions and [`docs/competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md) for the explicit B-comparison.
>
> - **Baseline A** — LLM re-prompts routing/state on every cron/webhook (prompt-loop agent)
> - **Baseline B** — Hand-optimized scripts + LLM only at judgment gates (competent platform team)
> - **Baseline C** — Pure deterministic runners, zero LLM in loop

**Quick rerun (updates sections in `BENCHMARK.md`):**

```bash
python scripts/benchmark_token_savings.py
python scripts/benchmark_compile_once_run_many.py
python scripts/benchmark_authoring_density.py
```

**Tokenizer:** tiktoken **cl100k_base** (billing-aligned with GPT-4o–class models) unless a doc explicitly states otherwise.

### Machine-readable outputs (`tooling/`)

These files are **committed** so diffs and CI can compare runs. They are the companion artifacts to **`BENCHMARK.md`** (human-readable tables and caveats).

| File | Produced by |
|------|-------------|
| [`tooling/token_savings_results.json`](../tooling/token_savings_results.json) | [`scripts/benchmark_token_savings.py`](../scripts/benchmark_token_savings.py) |
| [`tooling/compile_once_run_many_results.json`](../tooling/compile_once_run_many_results.json) | [`scripts/benchmark_compile_once_run_many.py`](../scripts/benchmark_compile_once_run_many.py) |
| [`tooling/authoring_density_results.json`](../tooling/authoring_density_results.json) | [`scripts/benchmark_authoring_density.py`](../scripts/benchmark_authoring_density.py) |
| [`tooling/benchmark_size.json`](../tooling/benchmark_size.json) | [`scripts/benchmark_size.py`](../scripts/benchmark_size.py) (`make benchmark`) |
| [`tooling/benchmark_size_ci.json`](../tooling/benchmark_size_ci.json) | CI / `make benchmark-ci` slice (same schema family, smaller run) |
| [`tooling/benchmark_runtime_results.json`](../tooling/benchmark_runtime_results.json) | [`scripts/benchmark_runtime.py`](../scripts/benchmark_runtime.py) |
| [`tooling/benchmark_runtime_ci.json`](../tooling/benchmark_runtime_ci.json) | CI runtime slice |
| [`tooling/benchmark_manifest.json`](../tooling/benchmark_manifest.json) | Profile/mode registry consumed by size benchmarking — not a “result” row, but versioned config |
| [`tooling/competitor_baseline_tokens.json`](../tooling/competitor_baseline_tokens.json) | [`scripts/benchmark_competitor_baselines.py`](../scripts/benchmark_competitor_baselines.py) — hand-written LangGraph + Python vs reference `.ainl` authoring tokens |
| [`tooling/production_evidence.json`](../tooling/production_evidence.json) | Committed operator case metadata — see [`docs/competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) |

Other JSON under **`tooling/`** (for example **`artifact_profiles.json`**, **`mcp_exposure_profiles.json`**) support compiler and product defaults; they are **not** benchmark run outputs.

---

## 1. Orchestration tokens: compile-once vs prompt-loop (recurring jobs)

**Baseline required:** **A** (prompt-loop agent re-invokes LLM on every run). **Not valid vs B or C.**

**Claims elsewhere:** “90–95% fewer tokens” vs prompt-loop agents on **recurring monitors, digests, scheduled jobs**; similar figures in OpenClaw bridge / cap-tuner docs for **stable paths**.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_compile_once_run_many.py`](../scripts/benchmark_compile_once_run_many.py) | Simulates repeated runs; compares compiled AINL vs prompt-loop baselines; writes tooling JSON + injects [`BENCHMARK.md`](../BENCHMARK.md). |
| Example workloads | [`examples/benchmark/enterprise_monitor.ainl`](../examples/benchmark/enterprise_monitor.ainl), [`examples/workflows/lead_enrichment.ainl`](../examples/workflows/lead_enrichment.ainl), [`examples/workflows/support_ticket_router.ainl`](../examples/workflows/support_ticket_router.ainl) (+ scenarios such as price monitor / ETL QC / RSS digest in the script). |
| Hub | [`docs/benchmarks.md`](benchmarks.md) § *Analytical orchestration-token economics*. |

**Honest scope:** Savings are **largest** when most runs need **no LLM** (healthy polls, cache hits, deterministic routing). Workloads that **invoke an LLM every run** (e.g. classify + draft) still gain from IR routing but show **smaller** ratios — see scenario tables in **`BENCHMARK.md`**.

**What this is NOT:** It is **not** a saving vs a hand-written Python runner that already only calls the LLM at the judgment gate. That comparison is **baseline B**, which yields ~1.3–1.5× — see [`competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md).

---

## 2. Routing / classification: LLM-first vs compiled IR (“2–5×” class statements)

**Baseline required:** **A vs C** (LLM-first vanilla vs compiled AINL) for the **2–7×** range. **B vs C** (hand-optimized vs compiled) is **~1.3–1.5×** — the irreducible compiler benefit. **Do not** quote 2–5× when talking to teams who already do baseline B.

**Claims elsewhere:** Multi-step pipelines spend fewer tokens when routing lives in **IR branches** instead of repeated LLM orchestration.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_token_savings.py`](../scripts/benchmark_token_savings.py) | Three-way comparison (vanilla LLM-first, hand-optimized Python, compiled AINL); routing-depth sensitivity; injects **`BENCHMARK.md`**. |

**Honest scope:** The `doc_processing` compiled path uses `doc_type_hint` from the frame (i.e. assumes upstream metadata supplies document type). In production, baseline B may still need one classify LLM call unless the type is guaranteed from upstream. The `support_triage` scenario uses **3** focused AINL calls vs **1** fat prompt-loop call — savings come from per-call prompt size, not call count. See module docstring in [`benchmark_token_savings.py`](../scripts/benchmark_token_savings.py) for details.

---

## 3. Authoring density: AINL vs Python/TypeScript (“3–5×” class statements)

**Baseline required:** Source-file tokens vs **LLM-style verbose Python** (for `data_pipeline`) or **idiomatic hand-written Python** (for simple programs). Mean across 4 programs is **~1.71×**; only the complex LLM-style-verbose comparison reaches the **2.5×** band; **3–5×** band is **line counts**, not tokens.

**Claims elsewhere:** Compact `.ainl` authoring vs equivalent imperative code **generated or written** for the same workflow.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_authoring_density.py`](../scripts/benchmark_authoring_density.py) | Token and line counts for paired programs; injects **`BENCHMARK.md`**. |
| Complex reference | [`examples/workflows/data_pipeline.ainl`](../examples/workflows/data_pipeline.ainl) vs verbose baselines under [`benchmarks/handwritten_baselines/authoring_density/`](../benchmarks/handwritten_baselines/authoring_density/). |

**Honest scope:** Line-count ratios for **complex** graphs reach the **3–5×** band vs LLM-style verbose Python; simple programs show lower token ratios — see interpretation block in **`BENCHMARK.md`**. This is an **authoring/generation** cost, not a runtime cost.

---

## 4. Emit / artifact size (“~1.02×”, “minimal_emit”, viable subset)

**Baseline required:** **Emit-size leverage**, not LLM tokens. This is a *generation expansion* metric, not a savings metric.

**Claims elsewhere:** README / integration docs cite **~1.02×** leverage on tokenizer-aligned **viable subset** workloads vs unstructured baselines.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_size.py`](../scripts/benchmark_size.py) | Primary size benchmark; profiles in [`tooling/artifact_profiles.json`](../tooling/artifact_profiles.json). |
| [`make benchmark`](../Makefile) / [`docs/benchmarks.md`](benchmarks.md) | Regenerates **`BENCHMARK.md`** size tables; separates **viable subset** vs **legacy-inclusive**. |

This metric is **not** the same as §1–3; do not mix **emit size** with **orchestration LLM tokens**.

---

## 5. Session bootstrap / bridge / startup context (“85–95%” class statements)

**Baseline required:** Different surface from §1. Compares **session bootstrap context** vs full memory dumps in the OpenClaw integration path. **Do not** present alongside §1 percentages as if they were the same quantity.

**Claims elsewhere:** Golden-path OpenClaw integration ([`docs/openclaw/AINL_INTEGRATION_GOLDEN.md`](openclaw/AINL_INTEGRATION_GOLDEN.md)), embedding pilots, startup clamps — **session** token footprint vs full memory dumps.

**Evidence:** Operational worksheets and live metering — [`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](operations/TOKEN_AND_USAGE_OBSERVABILITY.md); bridge sizing [`docs/openclaw/AINL_AUTO_TUNER.md`](openclaw/AINL_AUTO_TUNER.md). This is a **different surface** from §1 (scheduled graph execution). Where both appear, they are **complementary**, not duplicate proofs of the same quantity.

---

## 6. Field analyses, consultant reports, and agent_reports

**Classification:** Operator field reports (project author / close collaborators) — **Class (b)** per [`competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) honesty disclosure. **Not Class (a)** third-party paying customer evidence.

**Role:** Narrative validation, operator experience, and write-ups ([`agent_reports/`](../agent_reports/), [`AI_CONSULTANT_REPORT_APOLLO.md`](../AI_CONSULTANT_REPORT_APOLLO.md), etc.).

**Relationship to §1–4:** Useful context and quotes; **auditable reproduction** for headline economics should cite **`BENCHMARK.md`** and the **`scripts/benchmark_*.py`** family above.

**Committed operator tables:** [`docs/competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) + [`tooling/production_evidence.json`](../tooling/production_evidence.json) — anonymized OpenClaw / modeled deployment rows for public review. **Current Class (a) row count: 0** — tracked in [`competitive/LONG_TERM_FIXES_TRACKER.md`](competitive/LONG_TERM_FIXES_TRACKER.md) row **T2.7**.

**Honest ICP filter:** [`docs/WHO_IS_THIS_FOR.md`](WHO_IS_THIS_FOR.md) — when hand-optimized runners already capture most value (~**1.3–1.5×** routing win vs baseline B). Companion: [`competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md) — five-axis comparison conceding tokens and selling compile/audit/emit.

---

## 7. LangGraph authoring baselines (reference workloads)

**Baseline required:** **Authoring tokens only** (source-file tiktoken counts on hand-written LangGraph Python vs `.ainl`). **Not** a runtime / per-execution token comparison. Runtime LangGraph token series remain **TBD** — tracker row **T2.1**.

**Claims elsewhere:** AINL source is more compact than hand-written LangGraph for the same semantics.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`benchmarks/handwritten_baselines/competitive/langgraph/`](../benchmarks/handwritten_baselines/competitive/langgraph/) | Hand-written LangGraph for `enterprise_monitor` and `support_ticket_router` |
| [`scripts/benchmark_competitor_baselines.py`](../scripts/benchmark_competitor_baselines.py) | tiktoken counts → [`tooling/competitor_baseline_tokens.json`](../tooling/competitor_baseline_tokens.json) |
| [`docs/competitive/COMPARISON_TABLE.md`](competitive/COMPARISON_TABLE.md) §A | Published ratios (LangGraph ÷ AINL ≈ **1.9–2.0×** on reference workloads) |

**Honest scope:** Authoring size only — not LangGraph worker runtime latency vs AINL runtime.

---

## 8. Temporal comparisons (pending)

**Baseline required:** Authoring-only (per planned methodology). **No** Temporal runtime comparison planned — Temporal's value is durability, not per-step orchestration cost. AINL `--emit temporal` produces Temporal workflows; AINL does not replace Temporal's worker engine.

**Status:** **TBD.** Hand-written Temporal baselines for `enterprise_monitor` and `support_ticket_router` are tracked at [`competitive/LONG_TERM_FIXES_TRACKER.md`](competitive/LONG_TERM_FIXES_TRACKER.md) row **T2.2**. Scaffold: [`scripts/benchmark_temporal_authoring.py`](../scripts/benchmark_temporal_authoring.py).

---

## 9. AINL vs hand-written Python runner (the baseline B comparison)

**Baseline required:** **B** (deterministic runner + LLM only at judgment gates). This is the comparison sophisticated platform engineers will demand.

**Status:** **Measured** as of 2026-05-19. Companion doc: [`competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md). Implementing script: [`../scripts/benchmark_vs_hand_runner.py`](../scripts/benchmark_vs_hand_runner.py). Committed data: [`../tooling/benchmark_vs_hand_runner.json`](../tooling/benchmark_vs_hand_runner.json). Sources measured: AINL `.ainl` + competent baseline-B + production-grade baseline-B for three workloads (`enterprise_monitor`, `support_ticket_router`, `data_pipeline`).

**Measured results (mean across the three workloads):**

| Comparison | Source tokens vs AINL | Source LOC vs AINL | Audit checklist (0–8) |
|---|---:|---:|---:|
| AINL (reference)                       | 1.00× | 1.00× | **7/8** |
| `competent_python` (no audit surface)  | **1.41×** | **2.01×** | 0/8 |
| `production_grade` (retry/breaker/hash-chained JSONL) | **3.41×** | **4.52×** | 5.33/8 |

**Per-run tokens (modeled, identical across all three Python variants):** ties AINL at 0 on healthy runs and ~50 on incident runs (single summary LLM call). The wedge is **not** runtime tokens.

**What this row claims:**

- Tokens per run: **tie** (confirmed: 0 on healthy runs in all three implementations).
- Source tokens: **AINL ahead** but only ~1.4× vs a competent runner; ~3.4× vs a production-grade runner with audit surface.
- LLM-authored first-run correctness: **AINL ahead** (compiler rejects broken graphs at `ainl validate --strict`; Python runs until the bad branch is hit). This dimension is qualitative — not quantified in the benchmark.
- Lift to Temporal LOC: **AINL ahead by orders of magnitude** (`--emit temporal` vs hand-port). Not quantified in this benchmark yet; tracked at T2.2.
- Audit posture: **AINL ahead by construction** — 7/8 vs `competent_python` 0/8 vs `production_grade` 5.33/8 mean. The 8th row (`regulatory_grade`) requires an external attestation we do not yet have.

**What we will NOT claim:** that AINL saves tokens vs a competent hand-written runner. It does not, and pretending it does loses sophisticated reviewers permanently. The measured ratio is a small source-size win, **not a runtime cost moat**.

**Caveats:** the `production_grade` Python variants are measurement skeletons (retry/breaker/audit surface; no OTEL exporter, no Prometheus, no DLQ, no Kubernetes liveness). A real production deployment adds another 200–500 LOC for those concerns — meaning this benchmark **understates** AINL's LOC advantage on the observability axis. See [`../benchmarks/handwritten_baselines/production/README.md`](../benchmarks/handwritten_baselines/production/README.md) for the explicit caveat list.

## 10. Common false or exaggerated claims (crosswalk to STATUS.yaml)

The following claims have appeared in operator posts, agent reports, or social media. They are mapped here to their actual status so reviewers can quickly verify or reject them.

| Claim | Actual status | STATUS.yaml key | Evidence or refutation |
|-------|---------------|-----------------|----------------------|
| "Graphs compile to bare metal / machine code" | **Never** — no native codegen exists | `marketing_claims_boundary.bare_metal_compilation` | AINL compiles to IR JSON; executed by Python `RuntimeEngine` |
| "AINL v1.8.2" (or any version ahead of release) | **False** — current release is per `pyproject.toml` | `marketing_claims_boundary.version_marketing` | Check `pyproject.toml` `version` field |
| "Graphs compile to WebAssembly / run in browser" | **Never shipped** — WASM adapter calls modules, not compile-to-wasm | `marketing_claims_boundary.whole_graph_wasm_emit` | `runtime/adapters/wasm.py` is call-out only; no `ainl emit --target wasm` |
| "Type checker rejects tensor/string mismatches" | **Aspirational** — `--strict` checks syntax/adapter names, not type shapes | `marketing_claims_boundary.tensor_type_system` | No shape/tensor type system in compiler or runtime |
| "AINL workflows run on-chain as smart contracts" | **Never** — Solana adapter calls RPC; no on-chain graph execution | `aspirational_not_built` (no entry; inherently false) | `adapters/solana.py` is an RPC client, not a contract deployer |
| "90–95% cost savings" (without baseline qualifier) | **Misleading without baseline A** | `docs/CLAIMS_AND_EVIDENCE.md` §1 | Only valid vs baseline A (prompt-loop); ~1.3–1.5× vs baseline B |

**Operator guardrails:** See [`docs/operations/OPERATOR_MARKETING_GUARDRAILS.md`](operations/OPERATOR_MARKETING_GUARDRAILS.md) for the full claim checklist.

---

## See also

- [`BENCHMARK.md`](../BENCHMARK.md) — regenerated tables and caveats  
- [`docs/benchmarks.md`](benchmarks.md) — commands, CI, glossary  
- [`docs/architecture/COMPILE_ONCE_RUN_MANY.md`](architecture/COMPILE_ONCE_RUN_MANY.md) — minimal deterministic proof pack  
- [`docs/WHO_IS_THIS_FOR.md`](WHO_IS_THIS_FOR.md) — canonical ICP, baseline A/B/C, decision tree  
- [`docs/competitive/VS_HAND_WRITTEN_RUNNER.md`](competitive/VS_HAND_WRITTEN_RUNNER.md) — five-axis baseline B comparison (concedes tokens)  
- [`docs/competitive/PRODUCTION_EVIDENCE.md`](competitive/PRODUCTION_EVIDENCE.md) — committed operator cases + Class (a) gap disclosure  
- [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](competitive/LONG_TERM_FIXES_TRACKER.md) — visible roadmap for evidence + scope work  
- [`docs/competitive/ARMARAOS_GTM.md`](competitive/ARMARAOS_GTM.md) — primary product wedge  
- [`docs/competitive/README.md`](competitive/README.md) — comparative hub  
- [`docs/competitive/COMPARISON_TABLE.md`](competitive/COMPARISON_TABLE.md) — committed numbers + LangGraph baselines  
