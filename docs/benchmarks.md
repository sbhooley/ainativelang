# Benchmarks and evidence

This page ties together the **size**, **runtime**, and **LLM-generation** benchmarks so you can defend AINL with numbers—not vibes.

### Benchmark highlights (March 2026)

> **Source of truth:** repository root **[`BENCHMARK.md`](../BENCHMARK.md)** (regenerate with `make benchmark`). Numbers below are **tiktoken cl100k_base** as in the Mode Comparison and legacy-inclusive sections.

Quick **size** snapshot:

| Lens | What it means | Headline ratios (tk) | Artifact coverage |
|------|----------------|----------------------|---------------------|
| **Strict-valid** | `canonical_strict_valid` | **6.60×** full_multitarget / **1.62×** minimal_emit | 12/12 (all viable) |
| **Public mixed, viable subset** | Representative **required-target** workloads; excludes curated low-emit / legacy rows | **~0.95×** full / **~0.80×** minimal_emit | **62/75** viable |
| **Compatibility only, viable** | Non-strict headline companion profile | **~0.80×** full / **~0.67×** minimal_emit | **50/63** viable |
| **Legacy-inclusive** | **All** paths in profile (honest aggregate drag from tiny shells) | e.g. `public_mixed` **minimal_emit ~0.22×**; **full_multitarget ~1.00×** | 75/75 |

**Transparency (mirrors `BENCHMARK.md` blockquotes):**

- **tiktoken cl100k_base** — markdown tables foreground tokenizer counts; JSON still stores the active CLI `--metric` (default `tiktoken`) for thresholds and economics.
- **Viable subset** — for `public_mixed` / `compatibility_only`, rules in `tooling/artifact_profiles.json` + emit heuristics; **legacy-inclusive** tables are always below the fold.
- **minimal_emit fallback stub** — tiny **python_api** async stub (~20–30 tk) when no selected target emits code.
- **Emitter compaction (Mar 2026)** — **`prisma`** and **`react_ts`** benchmark stubs shortened (~50–70% tk reduction on those lines in examples).
- **`--strict-mode`** — `scripts/benchmark_size.py` with **`--profile-name=canonical_strict_valid`** runs the compiler in strict reachability mode; see the strict callout in `BENCHMARK.md` when enabled.

## Why these benchmarks matter

AINL is **compile-once, run-many**: you pay LLM tokens (or human time) to author a program once, then the runtime executes the graph deterministically—no prompt loop on every invocation. The **runtime** benchmarks measure that second phase: wall-clock latency, RSS deltas, optional execution reliability, and (with `tiktoken`) source-token economics. The **size** benchmarks quantify how much emitted surface area you get per AINL artifact (profile- and mode-scoped), including **mean compile time over three timed compiles** so you can see compiler cost separately from emit size. Together, they show a different cost structure from “LLM re-generates orchestration code every time.”

Human-written baselines (`--compare-baselines`) anchor claims against real Python stacks (pure async vs LangGraph-style) using the same metrics where possible.

## Where to read results

- **Ecosystem import examples:** trees under **`examples/ecosystem/`** (Clawflows- and Agency-Agents-style Markdown → AINL) are **kept fresh via weekly auto-sync** from upstream [Clawflows](https://github.com/nikilster/clawflows) and [Agency-Agents](https://github.com/msitarzewski/agency-agents) repos — see [`.github/workflows/sync-ecosystem.yml`](../.github/workflows/sync-ecosystem.yml) and **[`docs/ECOSYSTEM_OPENCLAW.md`](ECOSYSTEM_OPENCLAW.md)**. **OpenClaw** and **ZeroClaw** both consume these paths (CLI, MCP, **OpenClaw skill** — **[`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**, or **ZeroClaw skill** — **[`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)**).
- **Human-readable size report (start here):** repository root **[`BENCHMARK.md`](../BENCHMARK.md)** — transparency notes at top; viable vs legacy-inclusive sections; per-artifact **Notes** column. On **ainativelang.com**, the same content is published as the [Benchmarks](/benchmark) page.
- **Machine-readable size JSON:** `tooling/benchmark_size.json` (schema `3.5+`).
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

If you use **`.venv-py310`** but still have a **`.venv`** directory, **`make`** prefers **`.venv`** first—either remove the unused env or run **`make benchmark-ci PYTHON=./.venv-py310/bin/python`** (after **`pip install -e ".[benchmark]"`** in that venv).

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
- `docs/OPENCLAW_INTEGRATION.md` — **OpenClaw skill**, **`ainl install-openclaw`**, and links to **`examples/ecosystem/`** (auto-sync, MCP importer tools)
- `docs/ZEROCLAW_INTEGRATION.md` — **ZeroClaw skill**, **`ainl install-zeroclaw`**, and links to **`examples/ecosystem/`** (auto-sync, MCP importer tools)
