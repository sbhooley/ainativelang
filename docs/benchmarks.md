# Benchmarks and evidence

This page ties together the **size**, **runtime**, and **LLM-generation** benchmarks so you can defend AINL with numbers—not vibes.

## Why these benchmarks matter

AINL is **compile-once, run-many**: you pay LLM tokens (or human time) to author a program once, then the runtime executes the graph deterministically—no prompt loop on every invocation. The **runtime** benchmarks measure that second phase: wall-clock latency, RSS deltas, optional execution reliability, and (with `tiktoken`) source-token economics. The **size** benchmarks quantify how much emitted surface area you get per AINL artifact (profile- and mode-scoped), including **mean compile time over three timed compiles** so you can see compiler cost separately from emit size. Together, they show a different cost structure from “LLM re-generates orchestration code every time.”

Human-written baselines (`--compare-baselines`) anchor claims against real Python stacks (pure async vs LangGraph-style) using the same metrics where possible.

## Where to read results

- **Human-readable size report:** repository root `BENCHMARK.md` (generated; commit when refreshing public numbers). On **ainativelang.com**, the same content is published as the [Benchmarks](/benchmark) page.
- **Machine-readable size JSON:** `tooling/benchmark_size.json` (schema `3.3+`).
- **Runtime JSON:** `tooling/benchmark_runtime_results.json` (generated; tracked in git as the CI baseline when committed).
- **LLM eval / multi-model bench:** `docs/OLLAMA_EVAL.md` — local Ollama plus optional **Anthropic Claude** via `ainl-ollama-benchmark --cloud-model …` (`pip install -e ".[anthropic]"`, `ANTHROPIC_API_KEY`).

## Key metrics (quick glossary)

| Area | What we measure |
|------|-----------------|
| **Size** | `tiktoken` (cl100k_base) on source and emitted bundles; aggregate ratios; optional cost estimates; **Compile ms (mean×3)** per artifact |
| **Runtime** | Post-compile execution latency, peak RSS Δ, adapter/trace stats; optional reliability batches; scalability probe on a golden workflow |
| **Economics** | Estimated USD per run/generation from shared pricing tables in `tooling/bench_metrics.py` (assumption-driven where adapters do not report usage) |
| **Reliability** | Success rate + timing σ for extra compile or execution repetitions (workloads remain deterministic; reliability catches flakes and env drift) |
| **LLM bench** | Pass rate, viability gate, errors, retries, wall time — comparable columns for Ollama vs cloud |

## Local commands

Full local run (updates `BENCHMARK.md` + default JSON paths):

```bash
pip install -e ".[dev,benchmark]"
make benchmark
```

The **`[benchmark]`** extra includes **`aiohttp`** and **`langgraph`** so runtime benchmarks with **`--compare-baselines`** can execute handwritten `pure_async_python.py` / `langgraph_version.py` stacks (without them, those groups are skipped with a warning).

CI-style (JSON only, smaller runtime sampling; matches the spirit of the `benchmark-regression` workflow):

```bash
make benchmark-ci
```

Size-only or runtime-only:

```bash
python scripts/benchmark_size.py --compare-baselines --cost-model gpt-4o
python scripts/benchmark_runtime.py --compare-baselines --reliability-runs 5 --cost-model gpt-4o
```

Regression helper (compare two JSON reports):

```bash
python scripts/compare_benchmark_json.py \
  --old-json tooling/benchmark_size.json \
  --new-json tooling/benchmark_size_ci.json \
  --threshold 0.10
```

## CI

Pull requests and pushes run **`benchmark-regression`** (see `.github/workflows/ci.yml`): benchmarks execute on Ubuntu, JSON artifacts upload, and `compare_benchmark_json.py` gates regressions against the baseline commit when baseline files exist in git.

## See also

- `scripts/benchmark_size.py`, `scripts/benchmark_runtime.py`, `tooling/bench_metrics.py`
- `docs/TEST_PROFILES.md` — pytest profile matrix
- `docs/architecture/COMPILE_ONCE_RUN_MANY.md` — architectural framing
