# Changelog

## 1.0.12-local-agent-coordination-substrate (2026-03-09)

### Local Agent Coordination Substrate (extension/OpenClaw)
- Added a minimal local mailbox-style coordination adapter `agent` with a
  **narrow shared protocol surface**:
  - `agent.send_task(envelope) -> task_id (string)`
  - `agent.read_result(task_id) -> AgentTaskResult (dict)`
- Implemented the adapter as a sandboxed, file-backed extension under
  `AINL_AGENT_ROOT`:
  - tasks are appended to `tasks/openclaw_agent_tasks.jsonl`,
  - results are read from `results/<task_id>.json`,
  - all paths are checked via a sandbox root helper, and attempts to escape
    the sandbox or use filesystem root are rejected.
- Enforced that `AgentTaskResult` files must parse as JSON objects; invalid or
  non-object JSON now raise `AdapterError`.
- Locked the shared protocol surface in tests
  (`tests/test_agent_protocol_surface.py`) so only `send_task` and
  `read_result` remain part of the coordination API.

### Agent Coordination Contract and Examples
- Added `docs/AGENT_COORDINATION_CONTRACT.md` as the canonical design/spec for:
  - `AgentManifest`
  - `AgentTaskRequest`
  - `AgentTaskResult`
  and the local mailbox protocol under `AINL_AGENT_ROOT`.
- Documented the shared protocol boundary (Cursor ↔ OpenClaw) and explicitly
  excluded additional verbs such as `read_task` and `list_agents` from the
  shared surface.
- Added small extension/OpenClaw examples:
  - `examples/openclaw/agent_send_task.lang` — build and enqueue a minimal
    `AgentTaskRequest` and return the `task_id`.
  - `examples/openclaw/agent_read_result.lang` — read a single
    `AgentTaskResult` identified by `task_id`.
  - `examples/openclaw/token_cost_advice_request.lang` — enqueue a bounded
    token-cost advisory request for a Cursor-side agent.
  - `examples/openclaw/token_cost_advice_read.lang` — read the advisory
    `AgentTaskResult` for a known token-cost task id.
- Updated `docs/ADAPTER_REGISTRY.md` and `docs/EXAMPLE_SUPPORT_MATRIX.md` to
  classify the `agent` adapter and the new examples as extension/OpenClaw,
  noncanonical surfaces.

### Security Hardening
- Hardened the `agent` adapter sandbox:
  - rejected `AINL_AGENT_ROOT="/"` (filesystem root) as an invalid sandbox,
  - rejected `task_id` values containing path separators or `..` in
    `agent.read_result`,
  - ensured all file reads/writes go through a safe-path helper.
- Added tests in `tests/test_agent_send_task.py` to assert:
  - sandbox escapes are rejected,
  - filesystem-root sandboxing is rejected,
  - invalid and non-object JSON results are rejected.

## 1.0.11-extras-metrics-and-graph-dot (2026-03-09)

### Observability Helper: `extras.metrics`
- Extended the OpenClaw `extras` adapter with a new `metrics` verb that reads
  **precomputed JSON summaries** (e.g. from `scripts/summarize_runs.py`) and
  exposes a small, stable metrics envelope:
  - `run_count`, `ok_count`, `error_count`
  - `ok_ratio` (when `run_count > 0`)
  - `runtime_versions`
  - `result_kinds`, `trace_op_counts`, `label_counts`
  - `timestamps_present`
- Implemented `extras.metrics` as a **sandboxed, read-only** extension/OpenClaw
  helper:
  - summaries are resolved relative to `AINL_SUMMARY_ROOT` (default:
    `/tmp/ainl_summaries`),
  - attempts to escape the sandbox root raise `AdapterError`.
- Kept `extras.metrics` clearly **non-canonical** and outside the strict core:
  it is classified as `extension_openclaw`, `strict_contract: false`, and
  documented in `docs/ADAPTER_REGISTRY.md`.
- Added `tests/test_extras_metrics.py` to lock in the envelope shape and error
  behavior for missing files, invalid JSON, and non-object summaries.

### Graph DOT Export Helper
- Added `scripts/render_graph.py` as a tiny helper to render compiled IR/graphs
  to DOT for visualization:
  - supports compiling `.ainl` / `.lang` files with `AICodeCompiler` or reading
    existing IR JSON,
  - groups IR nodes per label in DOT subgraphs,
  - labels nodes by op and adapter prefix (e.g. `R (http)`), and edges by
    control-flow port (`next`, `then`, `else`, etc.).
- Documented the helper and example usage in `docs/GRAPH_INTROSPECTION.md`
  without changing any compiler or runtime semantics.
- Added `tests/test_render_graph.py` to assert basic DOT structure and labeling.

### Autonomous Ops Example Pack Expansion
- Expanded `examples/autonomous_ops/` with additional extension/OpenClaw
  monitors:
  - `infrastructure_watchdog.lang`
  - `tiktok_sla_monitor.lang`
  - `lead_quality_audit.lang`
  - `token_cost_tracker.lang`
  - `canary_sampler.lang`
- Updated `examples/autonomous_ops/README.md`, `docs/EXAMPLE_SUPPORT_MATRIX.md`,
  and `tooling/artifact_profiles.json` to classify these as non-strict,
  extension/OpenClaw operational examples (not canonical core).

## 1.0.10-meta-monitoring-toolkits (2026-03-09)

### Run Summary Helper
- Added `scripts/summarize_runs.py` as a small meta-monitoring helper that
  aggregates one or more `RuntimeEngine.run(..., trace=True)` JSON payloads into
  a concise JSON summary:
  - `run_count` / `ok_count` / `error_count`
  - `runtime_versions`
  - `result_kinds` (Python type names of `result`)
  - `trace_op_counts` (per-op counts from traces)
  - `label_counts` (per-label trace event counts)
  - `timestamps_present` (currently `false`, since payloads do not include
    wall-clock timestamps)
- Kept the tool strictly read-only over existing payloads; it does not change
  any language, compiler, or runtime semantics.
- Added `tests/test_summarize_runs.py` to lock in the summary schema and basic
  aggregation behavior for single/multiple runs and list-of-payloads JSON input.
- Extended `docs/COMPILE_ONCE_RUN_MANY.md`, `README.md`, and `docs/DOCS_INDEX.md`
  with small notes on how to use the new run-summary helper.

## 1.0.9-autonomous-ops-and-http-envelopes (2026-03-09)

### Autonomous Ops Docs and Examples
- Added `docs/AUTONOMOUS_OPS_PLAYBOOK.md` as the central, truthful playbook for
  autonomous-agent use of AINL (compile-once/run-many, cooldown patterns,
  remediation flows, and current meta-monitoring limits).
- Added `examples/autonomous_ops/` with a small extension/OpenClaw
  autonomous-ops pack:
  - `status_snapshot_to_queue.lang`
  - `backup_freshness_to_queue.lang`
  - `pipeline_readiness_snapshot.lang`
  All are explicitly classified as `extension_openclaw`, non-canonical,
  non-strict-only snapshot emitters.
- Updated `examples/README.md`, `tooling/artifact_profiles.json`,
  `tooling/support_matrix.json`, and `docs/EXAMPLE_SUPPORT_MATRIX.md` to
  classify the autonomous-ops pack as compatible OpenClaw extension examples.

### Graph/IR Introspection and Operator UX
- Added `docs/GRAPH_INTROSPECTION.md` to document IR/graph emission, graph API
  helpers, normalization, and diffs.
- Added `scripts/inspect_ainl.py` as a tiny program-summary helper that prints
  `graph_semantic_checksum`, label/node counts, adapters, endpoints, and
  diagnostics without requiring users to read full IR JSON.
- Updated `README.md` and `docs/DOCS_INDEX.md` to link to the new graph
  introspection and inspect helper surfaces.

### Compile-Once / Run-Many Proof Pack
- Added `docs/COMPILE_ONCE_RUN_MANY.md` with a minimal, reproducible recipe to:
  - compile a program once and inspect IR/graph + checksum,
  - run with live adapters while recording calls,
  - replay deterministically from recorded adapter traces.
- Updated `README.md` and `docs/DOCS_INDEX.md` to expose the proof pack as the
  primary evidence surface for compile-once/run-many and deterministic replay.

### Adapter Result Envelopes (Descriptive Contracts)
- Extended `tooling/adapter_manifest.json` with `result_envelope` metadata for:
  - `http` (success envelope: `ok`, `status_code`, `error`, `body`, `headers`,
    `url`)
  - `queue` (enqueue envelope: `ok`, `message_id`, `queue_name`, `error`)
  - `svc` (extension/OpenClaw health envelope: `ok`, `status`, `latency_ms`,
    `error`)
- Updated `docs/ADAPTER_REGISTRY.md` to document the same envelopes and clearly
  mark `svc` as extension/OpenClaw-only (non-canonical).
- Added `tests/test_adapter_result_envelopes.py` to keep the manifest and docs
  aligned on result-envelope field sets.

### HTTP Success-Envelope Normalization
- Normalized the runtime HTTP adapter (`SimpleHttpAdapter`) to return an
  additive success envelope on 2xx responses while preserving legacy fields:
  - keep `status`, `body`, and `headers` behavior unchanged,
  - add `ok`, `status_code`, `error=None`, and `url` fields on success.
- Left non-2xx and transport failures unchanged: they still surface as
  `AdapterError` / `Err` and do not return a failure envelope in this pass.
- Updated `tests/test_http_adapter_contracts.py` to assert the new envelope
  fields alongside the legacy `status`/`body` behavior.
- Extended `docs/AUTONOMOUS_OPS_PLAYBOOK.md` with a small, truthful snippet
  showing how to use the HTTP success envelope for monitoring-oriented flows.

### Miscellaneous Operator-Facing Improvements
- Updated `docs/EXAMPLE_SUPPORT_MATRIX.md` to tag canonical examples with
  ops-oriented roles (branching, resilience, webhook remediation, cron/scraper).
- Kept all compiler and core control-flow semantics unchanged; this release is a
  packaging, documentation, and adapter-behavior-hardening pass for
  autonomous-agent use.

## 1.0.8-canonical-lane-classification (2026-03-09)

### Canonical Lane Definition
- Added `tooling/support_matrix.json` as the machine-readable support-level source
  for:
  - canonical vs compatible syntax intent
  - canonical vs compatible example families
  - current emitter support posture
- Added `docs/AINL_CANONICAL_CORE.md` to define the recommended public AINL lane
  separately from the full accepted compatibility surface.
- Added `docs/EXAMPLE_SUPPORT_MATRIX.md` to classify canonical and compatible
  repository examples for onboarding, training, and migration safety.

### Documentation Wiring
- Updated `README.md` to expose:
  - the canonical core doc
  - the example support matrix
  - the machine-readable support matrix
- Updated `docs/DOCS_INDEX.md` with canonical-lane entry points.
- Updated `examples/README.md` to reference the canonical-core and example
  support docs alongside the existing artifact profile contract.

### Regression Safety Net
- Added initial snapshot fixtures under `tests/fixtures/snapshots/` for:
  - canonical and selected compatibility compile outputs
  - selected emitter outputs
  - selected runtime path envelopes
- Added snapshot tests:
  - `tests/test_snapshot_compile_outputs.py`
  - `tests/test_snapshot_emitters.py`
  - `tests/test_snapshot_runtime_paths.py`
- Locked graph semantic checksums for current canonical examples plus one
  OpenClaw compatibility example and one golden compatibility example to make
  future compiler extraction/refactoring parity-visible.

### Warning-Only Canonical Linting
- Added compiler-side canonical guidance warnings without changing compile
  success behavior.
- Current warning-only lint coverage includes:
  - inline executable content on label declaration lines
  - split-token `R` request form instead of dotted `adapter.VERB`
  - `Call` without explicit `->out`
  - lowercase dotted adapter verbs in non-canonical request style
  - accepted-but-noncanonical compatibility ops such as `X`, `Loop`, and cache/queue policy helpers
- Added `scripts/validate_ainl.py --lint-canonical` to print warning diagnostics
  without failing validation.
- Added `tests/test_canonical_warning_lint.py` to lock the first guidance set.
- Added `scripts/refresh_snapshot_fixtures.py` to intentionally regenerate the
  compile/emitter/runtime snapshot baselines from current compiler/runtime behavior.

## 1.0.7-project-origin-attribution-hardening (2026-03-09)

### Provenance and Initiator Attribution
- Hardened public project-origin attribution across repository metadata and docs so
  downstream mirrors, archives, forks, and machine-indexed copies retain clear
  initiator evidence.
- Recorded the human initiator explicitly as **Steven Hooley** with public references:
  - <https://x.com/sbhooley>
  - <https://stevenhooley.com>
  - <https://linkedin.com/in/sbhooley>
- Updated attribution-bearing surfaces:
  - `README.md`
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
  - `docs/DOCS_INDEX.md`
  - `docs/PROVENANCE_AND_RELEASE_EVIDENCE.md`
  - `docs/GITHUB_RELEASE_CHECKLIST.md`
  - `CITATION.cff`
  - `pyproject.toml`
  - `NOTICE`
  - `tooling/project_provenance.json`
- Added emitted-artifact provenance hardening in `compiler_v2.py` so generated
  server, OpenAPI, frontend, SQL, env, deployment, and runbook outputs carry
  explicit project-origin references.

### Public Release Positioning Polish
- Refined the top-level README to present AINL more clearly as a graph-first
  AI-native language/toolchain and intermediate programming system.
- Added a more public-facing breakdown of:
  - what AINL is,
  - what is best supported today,
  - where users should still exercise caution.
- Updated `docs/AUDIENCE_GUIDE.md` with a path for first-time public evaluators.
- Added `docs/NO_BREAK_MIGRATION_PLAN.md` as the operator-grade milestone tracker
  for compatibility-preserving canonical convergence.
- Linked the no-break migration plan from:
  - `README.md`
  - `docs/DOCS_INDEX.md`
  - `docs/POST_RELEASE_ROADMAP.md`

## 1.0.6-runtime-compiler-contract-canonicalization (2026-03-03)

### Runtime Canonical Ownership
- Finalized canonical runtime execution ownership in `runtime/engine.py` (`RuntimeEngine`).
- Replaced independent runtime logic in `runtime.py` with compatibility re-exports only.
- Added compatibility shim `runtime/compat.py`:
  - preserves historical `ExecutionEngine` API
  - bridges legacy adapters into canonical runtime adapter interfaces.
- Updated `runtime/__init__.py` exports to make canonical + compatibility surfaces explicit.

### Compiler-Owned Runtime Contract Helpers
- Added compiler-owned helpers in `compiler_v2.py` and switched runtime to consume them:
  - `runtime_normalize_label_id()`
  - `runtime_normalize_node_id()`
  - `runtime_canonicalize_r_step()`
- Reduced runtime duplication for label/node normalization and R-step shape interpretation.

### Runtime/Compiler Semantic Alignment
- Hardened step/graph parity around:
  - `Call` out-binding and `_call_result` compatibility behavior
  - `Err`/`Retry` explicit `@nX` targeting
  - `Loop`/`While` deterministic behavior and limits
  - capability ops (`CacheGet`, `CacheSet`, `QueuePut`, `Tx`, `Enf`)
- Broadened retry applicability and aligned strict graph-port validation so retry/error ports are accepted on executable source ops (not only `R`), matching runtime behavior.

### Strict Dataflow Model Hardening (Compiler-Owned)
- Fixed static-analysis gap for `Call ->out ... Retry @nX ... J out` strict paths.
- Improved compiler read/write analysis (`_analyze_step_rw`) to reflect runtime semantics:
  - explicit `Call` writes
  - literal-aware read filtering in key ops.
- Added strict quoted-literal policy enforcement via compile/dataflow behavior:
  - in strict mode, bare identifier-like tokens in read positions are treated as variable references
  - string literals must be quoted.
- Added explicit strict error guidance to quote literals when undefined-var failures indicate likely literal intent.

### Test Coverage Expansion
- Added/expanded runtime/compiler contract tests:
  - `tests/test_runtime_compiler_conformance.py`
  - updates in `tests/test_runtime_basic.py`
  - updates in `tests/test_runtime_graph_only.py`
  - updates in `tests/test_runtime_parity.py`
  - fixture additions in `tests/conformance_runtime/fixtures/retry_at_node.json`
- Added strict matrix coverage for quoted-vs-bare behavior in:
  - `Set.ref`
  - `Filt.value`
  - `CacheGet.key`
  - `CacheGet.fallback`
  - `CacheSet.value`
  - `QueuePut.value`.

### Documentation and Cross-Linking
- Added runtime/compiler contract document: `docs/RUNTIME_COMPILER_CONTRACT.md`.
- Updated cross-links and status docs to reflect canonical runtime ownership and strict literal policy:
  - `README.md`
  - `docs/DOCS_INDEX.md`
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/CONFORMANCE.md`
  - `docs/grammar.md`
  - `docs/RELEASE_READINESS.md`
  - `docs/AI_AGENT_CONTINUITY.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
- Added long-term docs governance contract: `docs/DOCS_MAINTENANCE.md`.
- Expanded schema/profile cross-linking for small and large agents:
  - `docs/IR_SCHEMA.md`
  - `docs/GRAPH_SCHEMA.md`
  - `docs/AINL_V0_9_PROFILE.md`
  - `docs/PATTERNS.md`
  - `docs/TOOL_API.md`
  - `docs/INSTALL.md`
  - `docs/AINL_CORE_AND_MODULES.md`
  - `docs/AINL_EXTENSIONS.md`
- Added docs automation and governance guardrails:
  - `scripts/check_docs_contracts.py` (stale-phrase, link-style, required-link, semantics-doc-coupling checks)
  - `ainl-check-docs` CLI entrypoint
  - `.venv/bin/python scripts/run_test_profiles.py --profile docs`
  - `.pre-commit-config.yaml` local hook (`ainl-docs-contract`) for pre-push/pre-commit parity with CI
  - CI job `.github/workflows/ci.yml` -> `docs-contract`
  - PR checklist updates in `.github/pull_request_template.md`

## 1.0.5-grammar-runtime-contract-hardening (2026-03-03)

### Compiler-Owned Prefix/Grammar Contract
- Moved remaining decoding transition ownership to compiler helpers in `compiler_v2.py`:
  - `grammar_scan_lexical_prefix_state`
  - `grammar_next_slot_classes`
  - `grammar_prefix_line_ok`
  - `grammar_apply_candidate_to_prefix`
  - `grammar_active_label_scope`
  - `grammar_prefix_completable`
- Kept `compiler_grammar.py` as formal-only orchestration (state + admissibility).
- Isolated non-authoritative sampling into `grammar_priors.py`.
- Kept compatibility composition in `grammar_constraint.py`.

### Formal/Prior Layering Tightening
- Removed formal matcher fallback to prior samples; formal class matching is compiler-owned only.
- Reworked priors to consume formal state/classes from callers (no reach-back imports into formal core).
- Added typed protocol contracts for prior-state input to reduce silent drift risk.
- Added compiler-owned constants for decoder control classes (`NEWLINE`, `QUOTE_CLOSE`, etc.).

### Conformance Test Expansion
- Added corpus-driven transition tests for `prefix + candidate -> next prefix` invariants.
- Added corpus-wide class/sample/mask round-trip checks ensuring surviving candidates keep prefixes completable.
- Added structural-vs-strict boundary tests to preserve distinction between prefix plausibility and strict compile validity.
- Added runtime/compiler conformance tests to validate execution against compiler-emitted step schema for:
  - `Call` out-binding
  - `If`, `Err`, `Retry`, `CacheGet`, `CacheSet`, `QueuePut`, `Tx`, `Enf`

### Documentation and Cross-Linking
- Added/updated ownership contract references across:
  - `README.md`
  - `docs/DOCS_INDEX.md`
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/RUNTIME_COMPILER_CONTRACT.md`
  - `docs/RELEASE_READINESS.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
  - `docs/AI_AGENT_CONTINUITY.md`

## 1.0.4-documentation-timeline-correction (2026-03-03)

### Historical Provenance Correction
- Corrected prior timeline wording that implied AINL-origin work began in early 2025.
- Updated project chronology to reflect:
  - **2024** foundational AI research and cross-platform experimentation by the human founder.
  - Partial loss of early artifacts, followed by explicit rebuild/retest/revalidation.
  - **2025-2026** formalization, implementation expansion, and release hardening of AINL.
- Standardized this corrected timeline anchor across project-facing docs:
  - `README.md`
  - `CONTRIBUTING.md`
  - `docs/AUDIENCE_GUIDE.md`
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/RELEASE_READINESS.md`
  - `docs/CONFORMANCE.md`
  - `docs/AINL_SPEC.md`
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
  - `CITATION.cff`

## 1.0.3-documentation-timeline-clarity (2026-03-03)

> Note: historical start-date wording in this entry is superseded and corrected by `1.0.4-documentation-timeline-correction`.

### Project Timeline Clarification
- Documented an explicit historical timeline confirming that AINL research and project initiation began in **early 2025**.
- Added phase framing to reduce ambiguity about when work occurred:
  - **Early 2025**: concept definition, AI-native language research, and naming/design exploration.
  - **Mid 2025**: grammar/spec experimentation, compiler direction setting, and first IR-shape validation loops.
  - **Late 2025**: implementation expansion across compiler/runtime paths, emitter surface growth, and conformance-first test structuring.
  - **Early 2026**: runtime/platform hardening, adapter contract coverage, alignment/eval gate maturity, and publication/operations documentation.
- Added explicit note that phases overlap by design and were developed iteratively in parallel tracks
  (research, development, and implementation were not strictly linear).
- Updated cross-reference documentation (`README.md`, `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`, `docs/DOCS_INDEX.md`)
  so timeline context is discoverable from both onboarding and release-history entry points.

## 1.0.2-alignment-docs-and-gates (2026-03-03)

### Evaluation and Alignment Pipeline
- Added hard trend quality gates with threshold/regression checks and non-zero failure mode in `scripts/analyze_eval_trends.py`.
- Added machine-readable run health output `corpus/curated/alignment_run_health.json` in `scripts/run_alignment_cycle.sh`.
- Added prompt-length bucketing support across eval/sweep/cycle for shape-stability and better diagnostics.
- Added optional quantized eval/infer lane (`--quantization-mode none|dynamic-int8`) with safe fallback behavior.
- Added bounded host-side canonicalization controls:
  - `--canonicalize-chunk-lines`
  - `--canonicalize-max-lines`

### Diagnostics
- Added per-length-bucket diagnostics in model eval output:
  - rates, timing totals, failure families, and per-bucket constraint health.
- Extended trend output with bucket-level summary pointers:
  - worst strict bucket
  - slowest bucket
  - quantization metadata

### Documentation
- Added `docs/DOCS_INDEX.md` as a top-level orientation map.
- Added `docs/AI_AGENT_CONTINUITY.md` for handoff and persistence protocol.
- Added `docs/TRAINING_ALIGNMENT_RUNBOOK.md` for full train/sweep/gate operations.
- Added publication-layer docs:
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
  - `docs/GLOSSARY.md`
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
- Added OpenClaw integration guide: `docs/OPENCLAW_ADAPTERS.md`
- Added consultant report template and index:
  - `AI_CONSULTANT_REPORT_TEMPLATE.md`
  - `CONSULTANT_REPORTS.md`
  - `AI_CONSULTANT_REPORT_APOLLO.md` (Apollo's OpenClaw integration analysis)
- Added OpenClaw agent quickstart: `AI_AGENT_QUICKSTART_OPENCLAW.md`
- Updated `docs/FINETUNE_GUIDE.md` to link and use the new runbook.
- Added publication/trust/community artifacts:
  - `docs/AUDIENCE_GUIDE.md`
  - `docs/GITHUB_RELEASE_CHECKLIST.md`
  - `CODE_OF_CONDUCT.md`
  - `SECURITY.md`
  - `CITATION.cff`
  - `.github/ISSUE_TEMPLATE/bug_report.yml`
  - `.github/ISSUE_TEMPLATE/feature_request.yml`
  - `.github/pull_request_template.md`
- Added Option C legal/package baseline files:
  - `LICENSE` (Apache-2.0)
  - `LICENSE.docs`
  - `COMMERCIAL.md`
  - `TRADEMARKS.md`
  - `MODEL_LICENSE.md`
  - `NOTICE`
- Updated `README.md`, `CONTRIBUTING.md`, `docs/DOCS_INDEX.md`, and `CITATION.cff`
  to reflect open-core licensing structure and DCO expectations.

## 1.0.1-runtime-platform (2026-02-22)

### Runtime
- Added execution mode policy controls: `graph-preferred`, `steps-only`, and `graph-only`.
- Added unknown-op policy controls: `skip` and `error`, with explicit behavior in both step and graph execution.
- Added IR/version compatibility guard: runtime validates `ir_version` major compatibility.
- Added runtime metadata and ergonomics:
  - `RuntimeEngine.run(...)` convenience wrapper
  - `runtime_version` in run payloads
  - `trace_sink` callback for streaming trace events
  - `lineno` included in trace events
- Added production guardrails:
  - `max_steps`
  - `max_depth`
  - `max_adapter_calls`
  - `max_time_ms`
  - `max_frame_bytes`
  - `max_loop_iters` (applies across loop paths)
- Hardened frame semantics and variable validation:
  - explicit failures for missing destination variables in `Set`, `Filt`, `Sort`, and `X`.
- Refactored runtime internals to reduce semantic drift:
  - shared step execution helpers (`_exec_step` and common op helpers)
  - shared graph error-routing helper for `err` edge + active handler fallback + recursion guard.
- Improved graph traversal performance with indexed edge lookups for common `(from, port, to_kind)` access.

### CLI
- Extended `ainl run` with:
  - execution mode and unknown-op policy flags
  - guardrail limit flags
  - `--trace-out` to write trace JSON
  - `--record-adapters` and `--replay-adapters` for deterministic adapter replay workflows.
- Added pretty runtime error formatting with source snippet + caret output in non-JSON mode.
- Added `ainl golden` command for fixture-driven verification using `examples/*.ainl` + `*.expected.json`.
- Enhanced `ainl check` output with `ir_version` and compiler warnings.
- Added direct adapter bootstrapping flags to `ainl run` for `http`, `sqlite`, `fs`, `tools`, and `ext`.

### Adapters
- Added `SimpleHttpAdapter` (`runtime/adapters/http.py`) with:
  - method allowlist
  - timeout handling
  - host allowlist
  - JSON/text request-response handling
  - response-size guard
  - consistent `AdapterError` mapping for transport/status/validation failures.
- Added replay/recording adapter registries in runtime package:
  - `RecordingAdapterRegistry`
  - `ReplayAdapterRegistry`
- Added `SimpleSqliteAdapter` (`runtime/adapters/sqlite.py`) with query/execute contract, allow-write policy, and table allowlist support.
- Added `SandboxedFileSystemAdapter` (`runtime/adapters/fs.py`) with sandbox-root confinement, extension policy, and size caps.
- Added `ToolBridgeAdapter` (`runtime/adapters/tools.py`) for tool-call bridging with tool allowlist and error mapping.
- Added `HttpAdapter` support in adapter base and registry accessor (`get_http()`).
- Added registry accessors for `sqlite`, `fs`, and `tools`.

### Tests
- Added property/fuzz suites (Hypothesis):
  - step-vs-graph equivalence
  - randomized IR safety checks.
- Added runtime guardrail tests (`max_*` limits).
- Added HTTP adapter contract tests (validation, timeout, error mapping, request/response shape).
- Added deterministic replay test (live run vs replay output/log parity).
- Added runtime API/compat tests:
  - `ir_version`/`runtime_policy` presence
  - unsupported IR rejection
  - unknown-op policy enforcement
  - trace sink and wrapper behavior
  - CLI golden pass.
- Added runtime conformance fixture harness with trace-signature expectations.
- Updated conformance assertions for endpoint layout compatibility.

### Documentation
- Added/updated:
  - `SEMANTICS.md` (frozen runtime semantics)
  - `docs/RELEASE_READINESS.md` (capability-to-test/file handoff map)
  - `docs/INSTALL.md` (runtime adapter CLI examples, record/replay usage)
  - README runtime/replay/golden usage notes.

### Runner Service
- Added deployable runtime runner service:
  - `scripts/runtime_runner_service.py`
  - endpoints: `/run`, `/enqueue`, `/result/{id}`, `/health`, `/ready`, `/metrics`
  - compile cache + async job worker + structured logs + trace IDs
- Added deployment artifacts:
  - `services/runtime_runner/Dockerfile`
  - `services/runtime_runner/docker-compose.yml`
- Added service test coverage:
  - `tests/test_runner_service.py`

### Verification
- Consolidated matrix result after this release set:
  - **68 passed / 0 failed**
  - Property + runtime + adapter contract + replay + compat + conformance suites all green.
