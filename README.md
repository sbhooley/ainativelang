# AI Native Lang (AINL)

> AI-led co-development project, human-initiated by Steven Hooley (`x.com/sbhooley`, `stevenhooley.com`, `linkedin.com/in/sbhooley`). Attribution details: `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md` and `tooling/project_provenance.json`.

AI Native Lang (AINL) is a compact language and toolchain for agent-oriented workflows. The compiler emits canonical graph IR and compatibility `legacy.steps`; the runtime executes graph-first semantics through `runtime/engine.py`.

AINL is best understood as a **graph-canonical intermediate programming system** with:
- a compact textual surface for generation and transport,
- a compiler/runtime pair designed around deterministic IR,
- emitters for practical targets,
- and tooling for constrained decoding, diffing, patching, and evaluation.

## Status

AI Native Lang is an actively developed open-core project. The core compiler/runtime and graph tooling are real and usable; some language surfaces, examples, targets, and evaluation workflows are still being stabilized.

Public release expectations:
- the **graph-first compiler/runtime core** is the most stable part of the project,
- **server/OpenAPI/runtime/tooling** are the strongest current implementation lanes,
- some examples and compatibility artifacts are intentionally classified as non-strict or legacy,
- broad target coverage exists, but not every target is equally mature or equally validated.

For implementation and shipped-capability status, see:

- [docs/CONFORMANCE.md](docs/CONFORMANCE.md)
- [docs/RELEASE_READINESS.md](docs/RELEASE_READINESS.md)
- [docs/TARGETS_ROADMAP.md](docs/TARGETS_ROADMAP.md)
- [docs/AINL_CANONICAL_CORE.md](docs/AINL_CANONICAL_CORE.md)
- [docs/EXAMPLE_SUPPORT_MATRIX.md](docs/EXAMPLE_SUPPORT_MATRIX.md)
- [docs/SAFE_USE_AND_THREAT_MODEL.md](docs/SAFE_USE_AND_THREAT_MODEL.md)

## What AINL Is

AINL is not just "short syntax for prompts" and it is not yet trying to compete head-on with general-purpose human languages.

Today, the project is strongest as:
- an AI-oriented programming representation with canonical graph IR,
- a compiler front-end into multiple practical targets,
- a runtime for graph-executed workflows,
- and a training/evaluation surface for structured code generation systems.

## Token Efficiency

AINL greatly reduces token usage compared to generating Python/TypeScript directly:

- Complex monitors (email, calendar, db, svc, cache, queue) compile to **50–70k tokens** (program + runtime). The same logic in Python/TypeScript would be **3–5× larger** in the prompt and would lack strict validation, graph introspection, and multi-target emission.
- New monitors are often **~1k tokens** once the adapter layer exists. The compile‑once/run‑many model eliminates repeated code‑gen per run.
- After stabilization, AINL lowers per‑task token burn by **2–5×** for non‑trivial automation and still provides savings for simpler tasks due to DSL density.

Bottom line: AINL saves tokens while increasing capability and reliability.

## Standardized Health Envelope

All production monitors use a common message envelope for notifications:

```json
{
  "envelope": {"version":"1.0","generated_at":"<ISO>"},
  "module": "<monitor_name>",
  "status": "ok" | "alert",
  "ts": "<ISO>",
  "metrics": { ... },
  "history_24h": { ... },
  "meta": {}
}
```

This ensures consistent parsing for Telegram, dashboards, and downstream processing. See [`docs/STANDARDIZED_HEALTH_ENVELOPE.md`](docs/STANDARDIZED_HEALTH_ENVELOPE.md).

## Best Supported Today

- Canonical compile path in `compiler_v2.py`
- Graph-first runtime execution in `runtime/engine.py`
- Formal prefix grammar orchestration in `compiler_grammar.py`
- Graph normalization, diff, patch, and canonicalization tooling in `tooling/`
- Server/OpenAPI emission and runtime-backed execution flow
- Runtime-native adapters with contract tests: `http`, `sqlite`, `fs`, `tools`
- Runner service: `scripts/runtime_runner_service.py`

## Use With Care

- Compatibility examples are retained intentionally; do not assume all public examples are strict-valid.
- Some emitters are more mature than others; treat `docs/TARGETS_ROADMAP.md` as a capability map, not a promise that every target is equally production-ready.
- Model-training and benchmark artifacts are included, but they should be read together with `BENCHMARK.md`, `docs/OLLAMA_EVAL.md`, and `docs/TEST_PROFILES.md` rather than as standalone proof of maturity.

## Surfaces and usage lanes

### Core / safe-default surface

The core, safe-default entry path for AINL focuses on:

- the canonical compiler/runtime and graph IR (`compiler_v2.py`, `runtime/engine.py`),
- canonical language scope (`docs/AINL_CANONICAL_CORE.md`, `docs/AINL_SPEC.md`),
- strict/compatible examples classified in `docs/EXAMPLE_SUPPORT_MATRIX.md`,
- graph/IR tooling (`docs/GRAPH_INTROSPECTION.md`),
- server/OpenAPI emission and basic workflows.

### Advanced / operator-only / experimental surface

AINL also includes **advanced, extension/OpenClaw-oriented** features that are
**not** the safe-default entry path and are **not** a built-in secure
orchestration or multi-agent safety layer. These are intended for operators who
understand the risks and have added their own safeguards.

Key docs and tooling in this lane:

- `docs/SAFE_USE_AND_THREAT_MODEL.md` — safe use, threat model, and advisory vs enforced fields.
- `docs/AGENT_COORDINATION_CONTRACT.md` — AgentTaskRequest/AgentTaskResult/AgentManifest envelopes and local mailbox contract.
- `docs/EXAMPLE_SUPPORT_MATRIX.md` (OpenClaw compatibility family) — advanced coordination and OpenClaw examples.
- `tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py` — optional mailbox linter for advanced coordination usage.

These features are **extension-only**, **noncanonical**, and **not** presented
as the normal starting point for new users or unsupervised agents.

## Stability Boundaries

- **Canonical today**
  - compiler semantics and strict validation in `compiler_v2.py`
  - runtime semantics in `runtime/engine.py` (`RuntimeEngine`)
  - formal grammar orchestration in `compiler_grammar.py`
- **Compatibility surfaces**
  - `runtime/compat.py` and `runtime.py` are compatibility wrappers/re-exports
  - `grammar_constraint.py` is a compatibility composition layer over compiler-owned grammar
  - `legacy.steps` are compatibility IR fields
- **Artifact profile contract**
  - strict/non-strict/legacy expectations are explicitly defined in `tooling/artifact_profiles.json`
  - do not assume all examples are strict-valid
- **Support-level contract**
  - canonical/compatible/deprecated intent is declared in `tooling/support_matrix.json`
  - public recommended language scope is described in `docs/AINL_CANONICAL_CORE.md`

## Project Origin and AI-Led Development

AI Native Lang began from a human-initiated idea and has been developed in explicit human+AI
co-development from the start. AI systems have been active contributors in naming,
architecture, and implementation iteration; notably, the name **"AI Native Lang"**
was proposed by an AI model and adopted by the project.

The human initiator of AINL is **Steven Hooley**.

Public origin references:
- X: <https://x.com/sbhooley>
- Website: <https://stevenhooley.com>
- LinkedIn: <https://linkedin.com/in/sbhooley>

Timeline anchor: Foundational AI research and cross-platform experimentation by
the human founder began in **2024**. After partial loss of early artifacts, AINL
workstreams were rebuilt, retested, and formalized in overlapping phases through
**2025-2026**.

For full attribution context, see:
- [docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md](docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md)
- [tooling/project_provenance.json](tooling/project_provenance.json)
- [docs/CHANGELOG.md](docs/CHANGELOG.md)

## Start Here

- Audience guide: `docs/AUDIENCE_GUIDE.md`
- Spec: `docs/AINL_SPEC.md`
- Canonical core: `docs/AINL_CANONICAL_CORE.md`
- Example support levels: `docs/EXAMPLE_SUPPORT_MATRIX.md`
- Graph/IR introspection: `docs/GRAPH_INTROSPECTION.md`
- Autonomous ops playbook: `docs/AUTONOMOUS_OPS_PLAYBOOK.md`
- Grammar reference: `docs/grammar.md`
- Conformance and strict policy: `docs/CONFORMANCE.md`
- Runtime/compiler ownership: `docs/RUNTIME_COMPILER_CONTRACT.md`
- Safe optimization guidance for benchmark/compaction work: `docs/SAFE_OPTIMIZATION_POLICY.md`
- Machine-readable support levels: `tooling/support_matrix.json`
- Release readiness matrix: `docs/RELEASE_READINESS.md`
- No-break migration tracker: `docs/NO_BREAK_MIGRATION_PLAN.md`
- Release notes draft (RC): `docs/RELEASE_NOTES_DRAFT.md`
- Maintainer release execution guide: `docs/RELEASING.md`
- Immediate post-release roadmap: `docs/POST_RELEASE_ROADMAP.md`
- Full docs map: `docs/DOCS_INDEX.md`
- Docs maintenance contract: `docs/DOCS_MAINTENANCE.md`
- Contributor guide: `CONTRIBUTING.md`
- Security and support: `SECURITY.md`, `SUPPORT.md`

For release-candidate contributor validation commands, see the RC checklist in `CONTRIBUTING.md`.

## Requirements

See [docs/INSTALL.md](docs/INSTALL.md) for full setup details.

At a minimum, contributors should expect:

- Python 3.x
- pip and virtual environment support
- Docker for container-based deployment flows
- platform-specific dependencies as documented in `docs/INSTALL.md`

## Quick start

```bash
python -m pip install -e ".[dev,web]"
.venv/bin/python scripts/run_test_profiles.py --profile core
python scripts/validate_ainl.py examples/hello.ainl --strict
```

For a quick look at the compiled graph/IR for any program:

```bash
ainl-validate examples/hello.ainl --strict --emit ir
```

See `docs/GRAPH_INTROSPECTION.md` for a full guide to IR/graph inspection and programmatic graph queries.

## Production deploy (Docker)

From repo root after emitting:

```bash
cd tests/emits/server
docker compose up --build
```

Or build image from repo root: `docker build -f tests/emits/server/Dockerfile .`

The emitted server also includes **openapi.json** for API docs, codegen, and gateways.

## Repo layout

| Path | Purpose |
|------|--------|
| `docs/AINL_SPEC.md` | AINL 1.0 formal spec: principles, grammar, execution, targets |
| `docs/CONFORMANCE.md` | Implementation conformance vs spec (IR shape, graph emission, P, meta) |
| `docs/TARGETS_ROADMAP.md` | Expanded targets for production and adoption |
| `docs/grammar.md` | Ops/slots reference (v1.0) |
| `compiler_v2.py` | Parser + IR + all emitters (OpenAPI, Docker, K8s, Next/Vue/Svelte, SQL, env) |
| `runtime/engine.py` | `RuntimeEngine` (graph-first execution; step fallback) |
| `runtime/compat.py` | `ExecutionEngine` compatibility shim over canonical runtime |
| `runtime.py` | compatibility re-export for historical imports |
| `adapters/` | Pluggable DB/API/Pay/Scrape (mock + base) |
| `compiler_grammar.py` | Compiler-owned formal prefix grammar/state machine (lexical + structural admissibility) |
| `grammar_priors.py` | Non-authoritative token sampling priors (state/class-driven; no formal rule ownership) |
| `grammar_constraint.py` | Thin compatibility layer that composes formal grammar + priors + pruning APIs |
| `docs/RUNTIME_COMPILER_CONTRACT.md` | Runtime/compiler/decoder ownership + conformance contract |
| `scripts/validate_ainl.py` | CLI validator: compile .lang, print IR or emit artifact |
| `scripts/validator_app.py` | Web validator (FastAPI): POST .lang → validate, GET / for paste UI |
| `scripts/generate_synthetic_dataset.py` | Generate 10k+ valid .lang programs into `data/synthetic/` |
| `tests/test_conformance.py` | Conformance tests (IR shape + emit outputs); run with `pytest tests/test_conformance.py` |
| `tests/test_*.lang` | Example specs |
| `examples/` | Example programs with explicit strict/non-strict classes (see `tooling/artifact_profiles.json`) |
| `tests/emits/server/` | Emitted server (logging, rate limit, health/ready), static, ir.json, openapi.json, Dockerfile, docker-compose.yml, k8s.yaml |
| `.github/workflows/ci.yml` | CI: pytest conformance, emit pipeline, example validation |

## Dataset, validator, and tooling

- **Synthetic dataset**: `python3 scripts/generate_synthetic_dataset.py --count 10000 --out data/synthetic` — writes only programs that compile.
- **Validator CLI**: `python3 scripts/validate_ainl.py [file.lang] [--emit server|react|openapi|prisma|sql]`; stdin supported.
- **Validator web**: `uvicorn scripts.validator_app:app --port 8766` then open http://127.0.0.1:8766/ to paste and validate.
- **Installed CLIs**: `ainl-validate`, `ainl-validator-web`, `ainl-generate-dataset`, `ainl-compat-report`, `ainl-tool-api`, `ainl-ollama-eval`, `ainl-ollama-benchmark`, `ainl-validate-examples`, `ainl-check-viability`, `ainl-playbook-retrieve`, `ainl-test-runtime`, `ainl`.
- **Runtime modes**: `ainl run ... --execution-mode graph-preferred|steps-only|graph-only --unknown-op-policy skip|error`.
- **Strict literal policy**: in strict mode, bare identifier-like tokens in read positions are treated as variable refs; quote string literals explicitly (see `docs/RUNTIME_COMPILER_CONTRACT.md` and `docs/grammar.md`).
- **Golden fixtures**: `ainl golden` validates `examples/*.ainl` against `*.expected.json`.
- **Replay tooling**: `ainl run ... --record-adapters calls.json` and `ainl run ... --replay-adapters calls.json` for deterministic adapter replay.
- **Reference adapters**: `http`, `sqlite`, `fs` (sandboxed), and `tools` bridge with contract tests.
- **Runner service**: `ainl-runner-service` (FastAPI) with `/run`, `/enqueue`, `/result/{id}`, `/health`, `/ready`, and `/metrics`.
- **Tool API schema**: `tooling/ainl_tool_api.schema.json` (structured compile/validate/emit loop contract).
- **Formal prefix grammar (compiler-owned)**: `compiler_grammar.py` is the source of truth for prefix lexical/syntactic/scope admissibility.
- **Grammar ownership contract**:
  - Grammar law (slot transitions, semantic-prefix checks, lexical-prefix scanning, prefix apply) lives in `compiler_v2.py`.
  - Formal orchestration (state + admissibility) lives in `compiler_grammar.py`.
  - Non-authoritative sampling priors live in `grammar_priors.py`.
  - Compatibility composition APIs live in `grammar_constraint.py`.
- **Decoder helpers**:
  - `next_token_priors(prefix)` for curated suggestions
  - `next_token_mask(prefix, raw_candidates)` to prune model-token candidates
  - `next_valid_tokens(prefix)` as backward-compatible alias to priors
- **Prefix and runtime conformance tests**:
  - `tests/test_grammar_constraint_alignment.py`
  - `tests/test_runtime_compiler_conformance.py`
  - `tests/test_runtime_basic.py`
  - `tests/test_runtime_graph_only.py`
  - `tests/test_runtime_parity.py`
- **Conformance**: `pip install -r requirements-dev.txt && pytest tests/test_conformance.py -v`.
- **Runtime subset tests**: `python scripts/run_runtime_tests.py` (or `ainl-test-runtime`).
- **Test profiles**: `.venv/bin/python scripts/run_test_profiles.py --profile <name>` (see `docs/TEST_PROFILES.md`).
- **Docs contract guard**: `ainl-check-docs` (or `python scripts/check_docs_contracts.py --scope all`) for cross-link/staleness/coupling checks.
- **Pre-commit (recommended)**: `pre-commit install` to run docs/quality hooks locally before commit.
- **Examples**: `python3 scripts/validate_ainl.py examples/blog.lang --emit ir`
- **Artifact compile profiles**: `tooling/artifact_profiles.json` is the source of truth for strict-valid vs non-strict-only vs legacy-compat examples/corpus/fixtures.
- **Strict example check**: `python3 scripts/validate_ainl.py examples/hello.ainl --strict`
- **Compile-once / run-many proof pack**: see `docs/COMPILE_ONCE_RUN_MANY.md` for a minimal end-to-end recipe (compile → inspect IR → run with adapters → replay from recorded calls).
- **Corpus layout checks**: `pytest tests/test_corpus_layout.py -v`
- **Corpus eval modes**: `python scripts/evaluate_corpus.py --mode dual` (strict + runtime views)
- **Corpus validation**: `python scripts/validate_corpus.py --include-negatives`
- **Approximate size benchmark**: `.venv/bin/python scripts/benchmark_size.py` compares AINL source size vs per-target generated outputs; outputs are written to `tooling/benchmark_size.json` and `BENCHMARK.md` (default metric `approx_chunks`; tokenizer-accurate mode requires optional `--metric tiktoken`).
- **Program summary helper**: `python scripts/inspect_ainl.py examples/hello.ainl` prints checksum, label/node counts, adapters, endpoints, and diagnostics for quick operator review.
- **Run summary helper**: `python scripts/summarize_runs.py run1.json run2.json` aggregates `RuntimeEngine.run(..., trace=True)` payloads into a small JSON health summary (run counts, op/label counts, result kinds, runtime versions).
- **Fine-tune bootstrap**: `bash scripts/setup_finetune_env.sh`
- **Fast fine-tune run**: `.venv-ci-smoke/bin/python scripts/finetune_ainl.py --profile fast --epochs 1 --seed 42`
- **Post-train inference (stable)**: `.venv/bin/python scripts/infer_ainl_lora.py --adapter-path models/ainl-phi3-lora --max-new-tokens 120 --device cpu`

## Production: logging, rate limit, K8s

The emitted server includes **structured logging** (request_id, method, path, status, duration_ms) and optional **rate limiting** via env `RATE_LIMIT` (requests per minute per client; 0 = off). **Kubernetes**: emitted `k8s.yaml` (Deployment + Service, health/ready probes); use `compiler.emit_k8s(ir, with_ingress=True)` for Ingress.

## CI profiles

Default pytest profile runs the stable core suite. Integration suites are separated:

- `core` (default): `pytest -m "not integration and not emits and not lsp"`
- `emits`: emitted artifact validation
- `lsp`: language server smoke test
- `integration` / `full`: broader checks including integration paths

Use `.venv/bin/python scripts/run_test_profiles.py --profile <name>` for consistent local/CI behavior.

## Community and Support

- Contribution workflow: `CONTRIBUTING.md`
- Contributor behavior policy: `CODE_OF_CONDUCT.md`
- Security reporting: `SECURITY.md`
- Support expectations and channels: `SUPPORT.md`
- Commercial/licensing inquiries: `COMMERCIAL.md`

## Licensing

AI Native Lang uses an open-core licensing model.

### Open Core

Designated core code in this repository is licensed under the Apache License 2.0.
See `LICENSE`.

### Documentation and Content

Non-code docs/content are licensed under `LICENSE.docs`, unless noted otherwise.

### Models, Weights, and Data Assets

Model/checkpoint/data-style artifacts may be governed by separate terms.
See `MODEL_LICENSE.md`.

### Commercial Offerings

Some hosted/enterprise/premium capabilities are available under separate
commercial terms. See `COMMERCIAL.md`.

### Trademarks

`AINL` and `AI Native Lang` branding rights are governed separately from code
licenses. See `TRADEMARKS.md`.

