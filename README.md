# AINL — AI-Native Lang

**AINL 1.0** — **AI-optimized**, non-human-readable-by-design programming language: one compact spec → React/TS, Python, Prisma, MT5, scrapers, web servers, dashboards, **OpenAPI**, **Docker**, and more. Built for agents and small models; compiles to canonical graph IR + legacy step-list; modern runtimes and production deployables.

- **Formal spec**: [docs/AINL_SPEC.md](docs/AINL_SPEC.md) — AINL 1.0 design principles, grammar, execution model, target matrix.
- **Conformance**: [docs/CONFORMANCE.md](docs/CONFORMANCE.md) — implementation status vs spec.
- **Targets roadmap**: [docs/TARGETS_ROADMAP.md](docs/TARGETS_ROADMAP.md) — tiers (today / next / production / ecosystem) for real-world and mass adoption.
- **Install guide**: [docs/INSTALL.md](docs/INSTALL.md) — cross-OS setup (Linux/macOS/Windows).
- **Local model eval**: [docs/OLLAMA_EVAL.md](docs/OLLAMA_EVAL.md) — evaluate Ollama models on AINL generation.
- **Structured tool API**: [docs/TOOL_API.md](docs/TOOL_API.md) — JSON request contract for agent loops.
- **Grammar reference**: [grammar.md](grammar.md) — ops and slots quick reference (v1.0).
- **Compiler**: `compiler_v2.py` — .lang → IR (nodes/edges + legacy.steps); emitters for React, FastAPI, Prisma, MT5, scraper, server, **OpenAPI**, **Docker**.
- **Runtime**: `runtime.py` + `adapters/` — run label steps (legacy.steps) with pluggable backends.

## Quick start

```bash
python -m pip install -e ".[dev,web]"
python run_tests_and_emit.py
python serve_dashboard.py
```

Open http://127.0.0.1:8765/ for the emitted dashboard; API at `/api/`.

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
| `grammar.md` | Ops/slots reference (v1.0) |
| `compiler_v2.py` | Parser + IR + all emitters (OpenAPI, Docker, K8s, Next/Vue/Svelte, SQL, env) |
| `runtime.py` | ExecutionEngine (run labels via adapters) |
| `adapters/` | Pluggable DB/API/Pay/Scrape (mock + base) |
| `grammar_constraint.py` | Next-valid-token constraint for constrained decoding (1B/3B models) |
| `scripts/validate_ainl.py` | CLI validator: compile .lang, print IR or emit artifact |
| `scripts/validator_app.py` | Web validator (FastAPI): POST .lang → validate, GET / for paste UI |
| `scripts/generate_synthetic_dataset.py` | Generate 10k+ valid .lang programs into `data/synthetic/` |
| `tests/test_conformance.py` | Conformance tests (IR shape + emit outputs); run with `pytest tests/test_conformance.py` |
| `tests/test_*.lang` | Example specs |
| `examples/` | Full-stack example apps (blog, ticketing, internal_tool, api_only, ecom) |
| `tests/emits/server/` | Emitted server (logging, rate limit, health/ready), static, ir.json, openapi.json, Dockerfile, docker-compose.yml, k8s.yaml |
| `.github/workflows/ci.yml` | CI: pytest conformance, emit pipeline, example validation |

## Dataset, validator, and tooling

- **Synthetic dataset**: `python3 scripts/generate_synthetic_dataset.py --count 10000 --out data/synthetic` — writes only programs that compile.
- **Validator CLI**: `python3 scripts/validate_ainl.py [file.lang] [--emit server|react|openapi|prisma|sql]`; stdin supported.
- **Validator web**: `uvicorn scripts.validator_app:app --port 8766` then open http://127.0.0.1:8766/ to paste and validate.
- **Installed CLIs**: `ainl-validate`, `ainl-validator-web`, `ainl-generate-dataset`, `ainl-compat-report`, `ainl-tool-api`, `ainl-ollama-eval`, `ainl-validate-examples`.
- **Tool API schema**: `tooling/ainl_tool_api.schema.json` (structured compile/validate/emit loop contract).
- **Next-valid tokens**: `from grammar_constraint import next_valid_tokens; next_valid_tokens("S core ")` for constrained decoding.
- **Conformance**: `pip install -r requirements-dev.txt && pytest tests/test_conformance.py -v`.
- **Examples**: `python3 scripts/validate_ainl.py examples/blog.lang --emit ir`

## Production: logging, rate limit, K8s

The emitted server includes **structured logging** (request_id, method, path, status, duration_ms) and optional **rate limiting** via env `RATE_LIMIT` (requests per minute per client; 0 = off). **Kubernetes**: emitted `k8s.yaml` (Deployment + Service, health/ready probes); use `compiler.emit_k8s(ir, with_ingress=True)` for Ingress.
