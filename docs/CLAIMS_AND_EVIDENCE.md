# Claims and reproducible evidence

This document maps **public-facing statements** in this repository to **defensible, reproducible artifacts**. It does **not** replace narrative reports or field analyses; it shows where numbers can be re-derived locally.

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

Other JSON under **`tooling/`** (for example **`artifact_profiles.json`**, **`mcp_exposure_profiles.json`**) support compiler and product defaults; they are **not** benchmark run outputs.

---

## 1. Orchestration tokens: compile-once vs prompt-loop (recurring jobs)

**Claims elsewhere:** “90–95% fewer tokens” vs prompt-loop agents on **recurring monitors, digests, scheduled jobs**; similar figures in OpenClaw bridge / cap-tuner docs for **stable paths**.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_compile_once_run_many.py`](../scripts/benchmark_compile_once_run_many.py) | Simulates repeated runs; compares compiled AINL vs prompt-loop baselines; writes tooling JSON + injects [`BENCHMARK.md`](../BENCHMARK.md). |
| Example workloads | [`examples/benchmark/enterprise_monitor.ainl`](../examples/benchmark/enterprise_monitor.ainl), [`examples/workflows/lead_enrichment.ainl`](../examples/workflows/lead_enrichment.ainl), [`examples/workflows/support_ticket_router.ainl`](../examples/workflows/support_ticket_router.ainl) (+ scenarios such as price monitor / ETL QC / RSS digest in the script). |
| Hub | [`docs/benchmarks.md`](benchmarks.md) § *Analytical orchestration-token economics*. |

**Honest scope:** Savings are **largest** when most runs need **no LLM** (healthy polls, cache hits, deterministic routing). Workloads that **invoke an LLM every run** (e.g. classify + draft) still gain from IR routing but show **smaller** ratios — see scenario tables in **`BENCHMARK.md`**.

---

## 2. Routing / classification: LLM-first vs compiled IR (“2–5×” class statements)

**Claims elsewhere:** Multi-step pipelines spend fewer tokens when routing lives in **IR branches** instead of repeated LLM orchestration.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_token_savings.py`](../scripts/benchmark_token_savings.py) | Three-way comparison (vanilla LLM-first, hand-optimized Python, compiled AINL); routing-depth sensitivity; injects **`BENCHMARK.md`**. |

---

## 3. Authoring density: AINL vs Python/TypeScript (“3–5×” class statements)

**Claims elsewhere:** Compact `.ainl` authoring vs equivalent imperative code **generated or written** for the same workflow.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_authoring_density.py`](../scripts/benchmark_authoring_density.py) | Token and line counts for paired programs; injects **`BENCHMARK.md`**. |
| Complex reference | [`examples/workflows/data_pipeline.ainl`](../examples/workflows/data_pipeline.ainl) vs verbose baselines under [`benchmarks/handwritten_baselines/authoring_density/`](../benchmarks/handwritten_baselines/authoring_density/). |

**Honest scope:** Line-count ratios for **complex** graphs reach the **3–5×** band vs LLM-style verbose Python; simple programs show lower token ratios — see interpretation block in **`BENCHMARK.md`**.

---

## 4. Emit / artifact size (“~1.02×”, “minimal_emit”, viable subset)

**Claims elsewhere:** README / integration docs cite **~1.02×** leverage on tokenizer-aligned **viable subset** workloads vs unstructured baselines.

**Evidence:**

| Artifact | Role |
|----------|------|
| [`scripts/benchmark_size.py`](../scripts/benchmark_size.py) | Primary size benchmark; profiles in [`tooling/artifact_profiles.json`](../tooling/artifact_profiles.json). |
| [`make benchmark`](../Makefile) / [`docs/benchmarks.md`](benchmarks.md) | Regenerates **`BENCHMARK.md`** size tables; separates **viable subset** vs **legacy-inclusive**. |

This metric is **not** the same as §1–3; do not mix **emit size** with **orchestration LLM tokens**.

---

## 5. Session bootstrap / bridge / startup context (“85–95%” class statements)

**Claims elsewhere:** Golden-path OpenClaw integration ([`docs/openclaw/AINL_INTEGRATION_GOLDEN.md`](openclaw/AINL_INTEGRATION_GOLDEN.md)), embedding pilots, startup clamps — **session** token footprint vs full memory dumps.

**Evidence:** Operational worksheets and live metering — [`docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`](operations/TOKEN_AND_USAGE_OBSERVABILITY.md); bridge sizing [`docs/openclaw/AINL_AUTO_TUNER.md`](openclaw/AINL_AUTO_TUNER.md). This is a **different surface** from §1 (scheduled graph execution). Where both appear, they are **complementary**, not duplicate proofs of the same quantity.

---

## 6. Field analyses, consultant reports, and agent_reports

**Role:** Narrative validation, operator experience, and third-party write-ups ([`agent_reports/`](../agent_reports/), [`AI_CONSULTANT_REPORT_APOLLO.md`](../AI_CONSULTANT_REPORT_APOLLO.md), etc.).

**Relationship to §1–4:** Useful context and quotes; **auditable reproduction** for headline economics should cite **`BENCHMARK.md`** and the **`scripts/benchmark_*.py`** family above.

---

## See also

- [`BENCHMARK.md`](../BENCHMARK.md) — regenerated tables and caveats  
- [`docs/benchmarks.md`](benchmarks.md) — commands, CI, glossary  
- [`docs/architecture/COMPILE_ONCE_RUN_MANY.md`](architecture/COMPILE_ONCE_RUN_MANY.md) — minimal deterministic proof pack  
- [`docs/competitive/README.md`](competitive/README.md) — comparative messaging + qualifier on matrix rows  
