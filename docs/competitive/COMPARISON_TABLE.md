# Comparison tables (committed data only)

Figures below are copied from **committed** artifacts only — **`BENCHMARK.md`**, **`tooling/benchmark_size.json`**, **`tooling/benchmark_runtime_results.json`**. **No hand-written baselines** for LangGraph / Temporal / prompt-loop columns exist in-repo; those cells stay **—** or **TBD**. **Do not** treat blank competitor columns as zero.

**Methodology:** [`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)

**Benchmark refresh (UTC, from JSON):** `tooling/benchmark_size.json` → `generated_at_utc` **2026-03-24T03:24:27.395076+00:00**; `tooling/benchmark_runtime_results.json` → `generated_at_utc` **2026-03-24T03:24:29.102226+00:00**.

## Takeaways

*Figures already in this page — not new runs.*

- **Authoring:** Hybrid monitor `.ainl` slices stay at **85–99** tk (cl100k_base) while **`full_multitarget`** emit on those paths is **~12.2k–12.5k** tk per LangGraph/Temporal bundle — **~125–144×** downstream vs source (§B).
- **Runtime bench (orchestration):** **`llm_tokens_estimated` = 0** and **`llm_calls` = 0** on the cited deterministic runs (§C); the benchmark does not log tokens inside your tools/models.
- **Headline emit expansion:** **`full_multitarget`** aggregate generated ÷ authoring is **~362.44×** across the **19** strict-valid paths (§A headline row + **`BENCHMARK.md`**).
- **Planner mode:** **`minimal_emit`** aggregate emitted size is **~0.76×** the same **2590** tk authoring sum (§A headline row + §B).

---

## A. Authoring compactness (tiktoken cl100k_base)

*Metric: `tiktoken` **cl100k_base** (`tooling/benchmark_size.json` → `metric`). Per-artifact field: `ainl_source_size`.*

| Metric | AINL (strict-valid `.ainl`) | LangGraph (Python) | Temporal (TypeScript/Python SDK) | Prompt-loop spec (e.g. JSON / prose) |
|--------|------------------------------|--------------------|-----------------------------------|----------------------------------------|
| Tokens (authoring) — **hybrid LangGraph slice** | **99** | — | — | — |
| Tokens (authoring) — **hybrid Temporal slice** | **85** | — | — | — |
| Tokens (authoring) — **headline set sum** | **2590** (sum of 19 paths) | — | — | — |
| Source file(s) | `examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl`; `examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl`; profile `canonical_strict_valid` artifact list in JSON | — | — | — |
| JSON path | `modes.full_multitarget.profiles[name=canonical_strict_valid].artifacts[].ainl_source_size` | — | — | — |
| Headline ratios (viable, tk) | **full_multitarget_core ~3.21×**; **full_multitarget ~362.44×**; **minimal_emit ~0.76×**; **19/19** viable | — | — | — |
| `BENCHMARK.md` anchor | [Mode Comparison (Headline + Mixed)](../../BENCHMARK.md#mode-comparison-headline--mixed) table row `canonical_strict_valid` | — | — | — |
| Notes | Competitor authoring tokens are **not** tracked in this repo. | — | — | — |

---

## B. Emit footprint (downstream bundle size)

*From **`tooling/benchmark_size.json`**, same profile **`canonical_strict_valid`**, mode noted per row. Fields: `targets.<emit>.size`, `targets.<emit>.ratio_vs_source`, `aggregate_generated_output_size`, `aggregate_ratio_vs_source`.*

| Target | AINL source (tk) | Emitted artifact(s) (tk) | Ratio (emit ÷ source) | JSON path (artifact + mode) |
|--------|------------------|----------------------------|-------------------------|----------------------------|
| `langgraph` | 99 | **12440** | **125.66×** | `full_multitarget` → `examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl` → `targets.langgraph` |
| `temporal` | 99 | **12491** | **126.17×** | same artifact → `targets.temporal` |
| `langgraph` | 85 | **12174** | **143.22×** | `full_multitarget` → `examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl` → `targets.langgraph` |
| `temporal` | 85 | **12223** | **143.80×** | same → `targets.temporal` |
| `langgraph` / `temporal` | 18 | **5123** / **5167** | **284.61×** / **287.06×** | `full_multitarget` → `examples/hello.ainl` → `targets.langgraph` / `targets.temporal` |
| **`minimal_emit` aggregate** (19 artifacts) | **2590** | **1977** | **0.76×** (aggregate ÷ source sum) | Sum of `aggregate_generated_output_size` / sum of `ainl_source_size` under `modes.minimal_emit` → `canonical_strict_valid` |
| `hyperspace` | — | — | — | **TBD** — `tooling/benchmark_size.json` `targets` array has no `hyperspace` emitter in schema **3.5** snapshot; add target + regenerate to fill. |
| `python_api` (FastAPI-shaped stub in bench) | 18 | **95** | **5.28×** | `full_multitarget` → `examples/hello.ainl` → `targets.python_api` |

---

## C. Recurring execution economics

*From **`tooling/benchmark_runtime_results.json`**, mode **`full_multitarget`**, profile **`canonical_strict_valid`**. Fields: `llm_tokens_estimated`, `llm_calls`, `llm_token_usage.note`.*

| Stack | LLM tokens / run (orchestration only) | Deterministic runner invoked? | Notes |
|-------|--------------------------------------|------------------------------|-------|
| AINL runtime (representative hybrid slices) | **0** (`llm_tokens_estimated`) | Yes | `examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl` and `examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl`: `llm_calls` **0**; `llm_token_usage.note` states runtime does not log LLM adapter tokens in this benchmark. |
| AINL runtime (`examples/hello.ainl`) | **0** | Yes | Same JSON paths: `modes.full_multitarget.profiles[name=canonical_strict_valid].artifacts[artifact=…]`. |
| LangGraph-only (typical agent loop) | — | — | **—** — no committed per-run token series for an external LangGraph loop. |
| Temporal-only worker | — | — | **—** — no committed orchestration-token baseline in-repo. |

---

## D. Strict compile / generation reliability

*LLM **generation** of source text (temperature=0, harness) — see **`docs/OLLAMA_EVAL.md`**. Expected report path **`data/evals/ollama_eval_report.json`** is **not** present in the committed tree.*

| Output type | N attempts | Strict-clean or valid % | Common failure modes |
|-------------|------------|-------------------------|----------------------|
| AINL source (Ollama / cloud eval) | — | **TBD — pending run** | Produce report with `ainl-ollama-eval` / `ainl-ollama-benchmark` per **`docs/OLLAMA_EVAL.md`**; commit `data/evals/ollama_eval_report.json` or summarized JSON to fill. |
| LangGraph Python | — | — | **—** — no committed codegen eval. |
| Temporal workflow code | — | — | **—** — no committed codegen eval. |

**Separate lane (not LLM generation):** deterministic **runtime** reliability after compile — `full_multitarget` / `canonical_strict_valid`: **11** artifacts `ok: true`, **8** `ok: false` on warmup (adapter gates, missing adapters, or parse errors). Example success: `monitoring_escalation.ainl` → `execution_reliability.success_rate` **1.0** (5/5). Example failure: `examples/hybrid/langchain_tool_demo.ainl` → `success_rate` **0.0** (capability gate). Path: `modes.full_multitarget.profiles[name=canonical_strict_valid].artifacts[]`.

---

## E. Post-compile runtime (`benchmark_runtime`)

*Mode **`full_multitarget`**, profile **`canonical_strict_valid`**. Fields: `latency_ms.p50_ms`, `latency_ms.p95_ms`, `peak_rss_delta_mb`. **Baseline** columns: no competitor timings in JSON — **—**.*

| Workload | AINL p50 ms | AINL p95 ms | Baseline p50 ms | Baseline p95 ms | RSS Δ notes |
|----------|-------------|-------------|-----------------|-----------------|-------------|
| `examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl` | **0.0246** | **0.0322** | — | — | **0.0** MB (`peak_rss_delta_mb`) |
| `examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl` | **0.0259** | **0.0357** | — | — | **0.0** MB |
| `examples/hello.ainl` | **0.0104** | **0.0108** | — | — | **0.0** MB |
| `examples/crud_api.ainl` | **0.0203** | **0.0222** | — | — | **0.0625** MB |

---

## F. Migration / emit latency (wall clock)

| Step | Command (exact) | Mean of 5 runs (s) | Machine notes |
|------|-----------------|-------------------|---------------|
| AINL → LangGraph | `time python3 scripts/validate_ainl.py --strict … --emit langgraph -o …` | **TBD — pending run** | Not captured in committed JSON; record manually if needed. |
| AINL → Temporal | `time python3 scripts/validate_ainl.py --strict … --emit temporal -o …` | **TBD — pending run** | Same. |

---

## G. OpenClaw / MCP production (anonymized)

*Worksheet: [`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md). No committed numeric rows in-repo.*

| Workload class | Host | Before | After (AINL + MCP) | Δ tokens/week (approx.) | Δ incidents/month |
|----------------|------|--------|--------------------|-------------------------|-------------------|
| — | — | — | — | **TBD** | **TBD** |

---

## Source manifest (traceability)

| Artifact | Role |
|----------|------|
| `tooling/benchmark_size.json` | `schema_version` **3.5**, `metric` **tiktoken**, `generated_at_utc` above; modes **`full_multitarget`**, **`minimal_emit`**; profile **`canonical_strict_valid`**. |
| `tooling/benchmark_runtime_results.json` | `schema_version` **1.2**, `generated_at_utc` above; mode **`full_multitarget`**, profile **`canonical_strict_valid`**. |
| `BENCHMARK.md` (repo root) | § **Mode Comparison (Headline + Mixed)**; § **Size Drivers** (top targets/artifacts, tk). |

When you regenerate benchmarks locally, **re-run extraction** (or update this file from fresh JSON) and bump the **Benchmark refresh** line at the top.
