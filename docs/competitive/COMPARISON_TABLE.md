# Comparison tables (fill from your benchmark runs)

Use these **empty templates** when publishing head-to-head evidence. Replace `—` with numbers, dates, and notes from **`BENCHMARK.md`**, **`tooling/benchmark_size.json`**, **`tooling/benchmark_runtime_results.json`**, and any LLM-generation harness (**`docs/OLLAMA_EVAL.md`**). Do not ship invented figures.

**Methodology:** [`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)

---

## A. Authoring compactness (tiktoken cl100k_base)

*Same workload / same logical monitor or workflow. Rows: tokenizer counts on the artifact as stored in git.*

| Metric | AINL (strict-valid `.ainl`) | LangGraph (Python) | Temporal (TypeScript/Python SDK) | Prompt-loop spec (e.g. JSON / prose) |
|--------|------------------------------|--------------------|-----------------------------------|----------------------------------------|
| Tokens (authoring) | — | — | — | — |
| Source file(s) | — | — | — | — |
| Date / commit SHA | — | — | — | — |
| Notes | — | — | — | — |

---

## B. Emit footprint (downstream bundle size)

*After `python3 scripts/validate_ainl.py --strict … --emit …`. Sum all emitted files where multiple.*

| Target | AINL source (tk) | Emitted artifact(s) (tk) | Ratio (emit ÷ source) | Date / SHA |
|--------|------------------|----------------------------|-------------------------|------------|
| `langgraph` | — | — | — | — |
| `temporal` | — | — | — | — |
| `hyperspace` | — | — | — | — |
| `server` (FastAPI) | — | — | — | — |
| `minimal_emit` planner bundle | — | — | — | — |

---

## C. Recurring execution economics

*Per scheduled or repeated run, after the graph is compiled.*

| Stack | LLM tokens / run (orchestration only) | Deterministic runner invoked? | Notes |
|-------|--------------------------------------|------------------------------|-------|
| AINL runtime / runner / MCP execute | — | Yes | — |
| LangGraph-only (typical agent loop) | — | — | — |
| Temporal-only worker | — | — | — |

---

## D. Strict compile / generation reliability

*Fixed temperature, fixed prompt template, N attempts.*

| Output type | N attempts | Strict-clean or valid % | Common failure modes |
|-------------|------------|-------------------------|----------------------|
| AINL source | — | — | — |
| LangGraph Python | — | — | — |
| Temporal workflow code | — | — | — |

---

## E. Post-compile runtime (from `benchmark_runtime`)

| Workload id / golden | AINL p50 ms | AINL p95 ms | Baseline p50 ms | Baseline p95 ms | RSS Δ notes |
|----------------------|-------------|-------------|-----------------|-----------------|-------------|
| — | — | — | — | — | — |

---

## F. Migration / emit latency (wall clock)

| Step | Command (exact) | Mean of 5 runs (s) | Machine notes |
|------|-----------------|-------------------|---------------|
| AINL → LangGraph | `time python3 scripts/validate_ainl.py --strict … --emit langgraph -o …` | — | — |
| AINL → Temporal | `time python3 scripts/validate_ainl.py --strict … --emit temporal -o …` | — | — |

---

## G. OpenClaw / MCP production (anonymized)

*Prefer linking to a filled **[`OPENCLAW_PRODUCTION_SAVINGS.md`](OPENCLAW_PRODUCTION_SAVINGS.md)** worksheet; keep PII out of this table.*

| Workload class | Host | Before | After (AINL + MCP) | Δ tokens/week (approx.) | Δ incidents/month |
|----------------|------|--------|--------------------|-------------------------|-------------------|
| — | — | — | — | — | — |
