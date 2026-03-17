# AI Native Lang (AINL) Runtime Release Readiness

This document summarizes the current production-hardening surface and where each capability is implemented and validated.
Timeline anchor: Foundational AI research and cross-platform experimentation by
the human founder began in **2024**. After partial loss of early artifacts, AINL
workstreams were rebuilt, retested, and formalized in overlapping phases through
**2025-2026**.

Release communication for tagging is maintained at `docs/RELEASE_NOTES.md`.
Immediate post-release engineering priorities are tracked in `docs/POST_RELEASE_ROADMAP.md`.
Maintainer release execution steps are documented in `docs/RELEASING.md`.

## Scope Completed

- Frozen runtime semantics and execution policies
- Property/fuzz safety tests
- Side-effect recording and replay
- Runtime guardrails for untrusted programs
- Real-world HTTP adapter with contract tests
- CLI golden fixture execution
- Conformance + compatibility coverage
- Deployable runner service (sync + async + metrics + health)
- Capability grant model with restrictive-only merge and profile-based startup
- Mandatory default limits on all execution surfaces
- Structured audit logging (run events, adapter calls, policy rejections)
- Stronger adapter metadata (`destructive`, `network_facing`, `sandbox_safe`)
- MCP exposure profiles and startup-configurable MCP tool/resource scoping

## Public Stability Boundaries

Release packaging expects these boundaries to stay explicit:

- Canonical runtime semantics: `runtime/engine.py`
- Compatibility runtime facade only: `runtime/compat.py`, `runtime.py`
- Compiler/strict semantic ownership: `compiler_v2.py`
- Example/corpus/fixture strictness classes: `tooling/artifact_profiles.json`
- Strict adapter contract allowlist ownership: `tooling/effect_analysis.py`
- Safe optimization policy (benchmark/compaction without syntax drift): `docs/runtime/SAFE_OPTIMIZATION_POLICY.md`

## Capability Map (Code + Tests)

### 1) Runtime Semantics + Policy

- **Code**
  - `SEMANTICS.md`
  - `runtime/engine.py`
  - `runtime/compat.py`
  - `runtime.py` (compatibility re-export only)
  - `compiler_v2.py` (`ir_version`, `runtime_policy`, warnings)
- **Tests**
  - `tests/test_runtime_basic.py`
  - `tests/test_runtime_graph_only.py`
  - `tests/test_runtime_graph_only_negative.py`
  - `tests/test_runtime_parity.py`
  - `tests/test_runtime_api_compat.py`
  - `tests/test_runtime_compiler_conformance.py`

### 2) Graph/Step Execution Controls

- **Code**
  - `runtime/engine.py`
    - execution modes: `graph-preferred`, `steps-only`, `graph-only`
    - unknown-op policy: `skip|error`
- **Tests**
  - `tests/test_runtime_graph_only.py::test_graph_mode_is_canonical_when_graph_exists_unless_force_steps`
  - `tests/test_runtime_api_compat.py::test_runtime_unknown_op_policy_error_steps_mode`

### 3) Runtime Guardrails

- **Code**
  - `runtime/engine.py` limits:
    - `max_steps`
    - `max_depth`
    - `max_adapter_calls`
    - `max_time_ms`
    - `max_frame_bytes`
    - `max_loop_iters`
- **Tests**
  - `tests/test_runtime_limits.py`

### 4) Real-world Adapters: HTTP + SQLite + FS + Tools

- **Code**
  - `runtime/adapters/http.py` (`SimpleHttpAdapter`)
  - `runtime/adapters/sqlite.py` (`SimpleSqliteAdapter`)
  - `runtime/adapters/fs.py` (`SandboxedFileSystemAdapter`)
  - `runtime/adapters/tools.py` (`ToolBridgeAdapter`)
  - `runtime/adapters/base.py` (`HttpAdapter`, `get_http()`)
  - `runtime/adapters/__init__.py`
- **Tests**
  - `tests/test_http_adapter_contracts.py`
  - `tests/test_sqlite_adapter_contracts.py`
  - `tests/test_fs_adapter_contracts.py`
  - `tests/test_tools_adapter_contracts.py`
    - input validation
    - allowlist behavior
    - timeout/error mapping
    - request/response shape

### 5) Side-effect Logging + Replay

- **Code**
  - `tests/helpers/recording_adapters.py`
    - `RecordingAdapter`
    - `RecordingAdapterRegistry`
    - `ReplayAdapterRegistry`
- **Tests**
  - `tests/test_replay_determinism.py`
  - `tests/property/test_runtime_equivalence.py::test_property_steps_vs_graph_side_effect_log_equivalence`

### 6) Property/Fuzz Safety

- **Code**
  - `tests/property/test_runtime_equivalence.py`
  - `tests/property/test_ir_fuzz_safety.py`
- **Tests**
  - same files (Hypothesis-backed)

### 7) API Ergonomics

- **Code**
  - `runtime/engine.py`
    - `RuntimeEngine.run(code, frame, ...)`
    - `trace_sink`
    - trace events include `lineno`
- **Tests**
  - `tests/test_runtime_api_compat.py::test_runtime_engine_run_wrapper`
  - `tests/test_runtime_api_compat.py::test_runtime_trace_sink_receives_events`

### 8) CLI + Golden Fixtures

- **Code**
  - `cli/main.py`
    - `run` mode/policy/limits flags
    - `golden` command
    - `--trace-out`
  - `examples/*.expected.json` (golden command executes only examples with matching expected files)
  - `tooling/artifact_profiles.json` (strict/non-strict/legacy classification for examples/corpus/fixtures)
- **Tests**
  - `tests/test_runtime_api_compat.py::test_cli_golden_examples_pass`
  - `tests/test_artifact_profiles.py`

### 9) Conformance + Runtime Test Entrypoint

- **Code**
  - `scripts/run_runtime_tests.py`
  - `tests/test_conformance.py`
  - `docs/CONFORMANCE.md`
  - `docs/RUNTIME_COMPILER_CONTRACT.md`
- **Tests**
  - `tests/test_conformance.py`
  - `tests/test_runtime_compiler_conformance.py`
  - `tests/test_grammar_constraint_alignment.py`

### 12) Reproducible Size Benchmark Surface

- **Code**
  - `scripts/benchmark_size.py` (manifest-driven benchmark over canonical public artifacts)
- **Artifacts**
  - `tooling/benchmark_size.json` (machine-readable output)
  - `BENCHMARK.md` (human-readable table)
- **Policy**
  - default metric is `approx_chunks` (approximate lexical-size proxy)
  - tokenizer-accurate counting is optional via `--metric tiktoken` when available

### 11) Strict Dataflow and Literal Ambiguity Contract

- **Code**
  - `compiler_v2.py` (`_analyze_step_rw`, strict dataflow diagnostics, quoted-literal handling hints)
  - `tooling/effect_analysis.py` (defined-before-use model used by strict validation)
- **Policy**
  - strict mode keeps defined-before-use enabled
  - bare identifier-like tokens in read positions are treated as variable references
  - string literals must be quoted in strict mode
- **Tests**
  - `tests/test_runtime_compiler_conformance.py` strict quoted-vs-bare matrix:
    - `Set.ref`, `Filt.value`, `CacheGet.key`, `CacheGet.fallback`, `CacheSet.value`, `QueuePut.value`

### 10) Runner Service (Deployable Product Surface)

- **Code**
  - `scripts/runtime_runner_service.py`
  - `services/runtime_runner/Dockerfile`
  - `services/runtime_runner/docker-compose.yml`
- **Behavior**
  - sync execution: `POST /run`
  - async execution: `POST /enqueue`, `GET /result/{id}`
  - health/readiness: `GET /health`, `GET /ready`
  - runtime metrics: `GET /metrics`
  - capability discovery: `GET /capabilities` (adapters, verbs, effects, privilege tiers)
  - compile cache + structured logs + trace IDs
  - optional policy validation before execution (`forbidden_adapters`, `forbidden_effects`, `forbidden_effect_tiers`, `forbidden_privilege_tiers`)
- **Tests**
  - `tests/test_runner_service.py`
  - `tests/test_runner_service_capabilities.py`

### 13) Security and Operator Deployment Surface

- **Code**
  - `tooling/adapter_manifest.json` (privilege tiers per adapter)
  - `tooling/security_profiles.json` (named deployment profiles)
  - `tooling/security_report.py` (per-label/per-graph privilege map)
  - `tooling/policy_validator.py` (privilege-tier-aware policy enforcement)
- **Behavior**
  - each adapter carries a `privilege_tier` (`pure`, `local_state`, `network`, `operator_sensitive`)
  - security report generates human-readable and JSON privilege maps for compiled workflows
  - named security profiles package adapter allowlists, privilege-tier restrictions, and runtime limits for deployment scenarios
  - policy validator supports `forbidden_privilege_tiers` to reject workflows by privilege class
- **Tests**
  - `tests/test_security_report.py`
  - `tests/test_policy_validator.py`
  - `tests/test_runner_service_capabilities.py`
- **Docs**
  - `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
  - `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
  - `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`

### 14) MCP Server (Workflow-Level Integration Surface)

- **Code**
  - `scripts/ainl_mcp_server.py`
- **Behavior**
  - exposes a thin, stdio-only MCP server (`ainl-mcp`) that registers:
    - tools: `ainl_validate`, `ainl_compile`, `ainl_capabilities`,
      `ainl_security_report`, `ainl_run`
    - resources: `ainl://adapter-manifest`, `ainl://security-profiles`
  - reuses existing compiler, policy validator, security-report tooling, and
    runtime engine rather than adding new semantics
  - `ainl_run` executes with safe-default restrictions:
    - core-only adapter allowlist
    - hardcoded, conservative runtime limits
    - `local_minimal`-style policy (forbidden `local_state`, `network`,
      `operator_sensitive` privilege tiers), with caller policies only allowed
      to add further restrictions
  - designed as a workflow-level integration surface for MCP-compatible hosts
    (e.g. Gemini CLI, Claude Code, Codex-style agent SDKs, generic MCP hosts),
    not as an agent host or orchestration platform
  - no HTTP transport, startup config/profile loading, raw adapter execution,
    advanced coordination exposure, or memory mutation tools in this release
- **Tests**
  - `tests/test_mcp_server.py` (tool shapes, policy/limit defaults, resource
    access)
- **Docs**
  - `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` (section **9**)
  - `README.md` (operations and tooling reference sections)

## CI / Verification Command Set

Core confidence suite:

```bash
python scripts/run_test_profiles.py --profile core
```

Integration confidence suite:

```bash
python scripts/run_test_profiles.py --profile integration
```

Full confidence suite:

```bash
python scripts/run_test_profiles.py --profile full
```

Adapter manifest consistency:

```bash
pytest tests/test_adapter_manifest.py -v
```

Artifact profile consistency:

```bash
pytest tests/test_artifact_profiles.py -v
```

## Release Notes Checklist

- [x] Semantic contracts documented
- [x] Runtime/compiler contract documented and cross-linked
- [x] Safety limits implemented and tested
- [x] Adapter contracts covered
- [x] Replay determinism covered
- [x] CLI golden fixtures available
- [x] Conformance suite passing
- [x] Adapter privilege-tier metadata populated
- [x] Policy validator supports privilege-tier restrictions
- [x] Named security profiles packaged
- [x] Security report tooling available
- [x] `/capabilities` exposes privilege tiers
- [x] Sandbox/orchestration/threat-model docs shipped
- [x] MCP v1 server implemented, tested, and documented
- [x] Python 3.10+ baseline aligned across metadata, docs, bootstrap, and CI
- [x] Core test profile fully green (403/0)
- [x] FastAPI deprecation warnings resolved (lifespan handlers)
- [x] Getting-started guide with three integration paths (CLI / runner / MCP)
- [x] Release notes finalized
