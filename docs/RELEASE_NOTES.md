# Release notes

## AINL v1.2.4 — Access-aware memory helpers, graph label resolution, docs (2026-03-21)

Follow-up to v1.2.3 focused on **opt-in access metadata** on top of Memory Contract v1.1, **runtime correctness for included subgraphs** in graph mode, and **documentation** so hosts can choose graph-safe list paths.

- **`modules/common/access_aware_memory.ainl`:** optional **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, and graph-safe **`LACCESS_LIST_SAFE`** (While + index loop; no `ForEach` in IR). Header documents graph-preferred limitations for `LACCESS_LIST` (ForEach not lowered to `Loop` today) and points callers at **`LACCESS_LIST_SAFE`** for full per-item touches. Uses **`Call`** chains and **`X … put …`** for metadata patches where needed for reliable execution.
- **Runtime (`runtime/engine.py`):** **`_resolve_label_key`** qualifies bare branch / loop / call targets (e.g. `_child`) against the current **`alias/…`** stack frame so graph (and step) execution reaches merged **`alias/child`** labels after `include`. Preserves behavior for programs that already use fully qualified ids.
- **Demos:** `demo/session_budget_enforcer.lang` and `demo/memory_distill_example.lang` keep **`include` lines before the first top-level `S` / `E`** so module labels merge; access-aware usage remains documented in-module.
- **Tests:** `tests/test_demo_enforcer.py` — compile + memory adapter checks; regression for bare child label resolution in graph-only mode.
- **Packaging / version surfaces:** **`pyproject.toml` / PyPI `ainl-lang` 1.2.4**; **`RUNTIME_VERSION` 1.2.4** in `runtime/engine.py` (mirrored under `tests/emits/server/runtime/engine.py`) for run payloads, MCP, and **`/capabilities`**; language server **`serverInfo.version`** (`langserver.py`) and HTTP runner **OpenAPI** `app.version` (`scripts/runtime_runner_service.py`) use the same **`RUNTIME_VERSION`** string; **`CITATION.cff`** sets software **`version`** / **`date-released`** to match.
- **Docs:** `modules/common/README.md` indexes shared helpers (include-before-`S`, `LACCESS_LIST` vs `LACCESS_LIST_SAFE`). Root **`README.md`**, **`WHAT_IS_AINL.md`**, **`docs/WHAT_IS_AINL.md`**, **`WHITEPAPERDRAFT.md`**, **`docs/POST_RELEASE_ROADMAP.md`**, **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/README.md`**, **`docs/adapters/README.md`**, **`docs/DOCS_INDEX.md`**, **`docs/CHANGELOG.md`**, and this file updated to match.

---

## AINL v1.2.3 — Shared memory include modules across monitors (2026-03-20)

This release consolidates repeated memory logic in production monitor programs into reusable include modules while preserving deterministic runtime behavior.

- **New shared include modules:**
  - `modules/common/token_cost_memory.ainl` for `workflow` namespace monitor state/history
  - `modules/common/ops_memory.ainl` for `ops` namespace monitor events/history
- **Program rollout:** monitor-heavy flows in `demo/` and `examples/autonomous_ops/` now call shared `WRITE`/`LIST` labels instead of repeating inline `memory.put` / `memory.list` construction.
- **Deterministic filter consistency:** migrated history reads now consistently use bounded filters (`updated_after`, `tags_any`, `source`, `limit`) to reduce noise and preserve predictable replay behavior.
- **Metadata consistency:** migrated writes consistently carry deterministic metadata envelopes (`source`, `confidence`, `tags`, `valid_at`) aligned with Memory Contract v1.1.
- **Strict memory adapter contract expansion:** strict-mode allowlist now includes `memory.PUT` / `GET` / `APPEND` / `LIST` / `DELETE` / `PRUNE`, and compiler-owned keying now correctly maps `R memory <verb> ...` forms to `memory.<VERB>` for validation.
- **Conformance coverage:** adds memory continuity snapshot coverage (`memory_continuity_runtime`) via `tests/data/conformance/session_budget_memory_trace.ainl`, plus tokenizer-round-trip coverage of `demo/session_budget_enforcer.lang`.
- **PNG visualizer demo:** adds `examples/timeout_memory_prune_demo.ainl` and committed image artifact `docs/assets/timeout_memory_prune_flow.png` for memory-heavy flow export docs.
- **Behavior preserved:** record kinds, payload shapes, TTLs, and existing alert/control logic remain unchanged; this is a structural maintainability pass, not a semantic runtime shift.

---

## AINL v1.2.2 — Memory v1.1 deterministic metadata and filters (2026-03-20)

Follow-up additive release focused on memory ergonomics and capability discoverability while preserving deterministic behavior and backward compatibility.

- **Memory metadata (additive):** `memory` records can now carry deterministic optional metadata fields (`source`, `confidence`, `tags`, `valid_at`).
- **Deterministic list filters:** `memory.list` adds bounded filters (`tags_any`, `tags_all`, created/updated windows, `source`, `valid_at` windows) with deterministic ordering and pagination (`limit`, `offset`).
- **Retention hooks:** namespace-level TTL defaults and prune strategies are now host-configurable (`default_ttl_by_namespace`, `prune_strategy_by_namespace`).
- **Operational counters:** adapter responses now include portable cumulative stats (`operations`, `reads`, `writes`, `pruned`).
- **Capability profile hint:** `tooling/capabilities.json` now advertises `memory_profile` (`v1.1-deterministic-metadata`) so hosts/workflows can branch safely by supported memory contract level.
- **Guardrails preserved:** no vector semantics, no fuzzy/semantic retrieval, and no policy cognition added to core memory/runtime semantics.

---

## AINL v1.2.0 — Includes, graph visualizer, structured diagnostics (2026-03-20)

Follow-up open-core release after the first public baseline. See **`docs/CHANGELOG.md`** for the full entry.

- **Compile-time `include`:** merge shared `.ainl` modules under **`alias/LABEL`**; strict ENTRY/EXIT contracts; starter modules under `modules/common/`.
- **Mermaid graph CLI:** **`ainl visualize`** / **`ainl-visualize`** — paste output into [mermaid.live](https://mermaid.live); clusters match include aliases.
- **Image export for visualizer:** `ainl visualize ... --png out.png` / `--svg out.svg` (with `--width`/`--height`; extension auto-detect via `-o file.png|.jpg|.jpeg|.svg`), powered by Playwright.
- **Timeout include demo:** `examples/timeout_demo.ainl` shows strict-safe include usage with `modules/common/timeout.ainl`.
- **Diagnostics:** structured **`Diagnostic`** output, **`--diagnostics-format`**, optional **rich** CLI; shared with validate and visualize failure paths.
- **Conformance matrix:** `make conformance` now runs the full parallelized snapshot suite (tokenizer round-trip, IR canonicalization, strict validation, runtime parity, emitter stability), with CI execution on push/PR and generated status artifacts under `tests/snapshots/conformance/`.
- **Docs:** **`docs/WHAT_IS_AINL.md`**, README quick-start, **`WHITEPAPERDRAFT.md`** 1.2.0, **`docs/POST_RELEASE_ROADMAP.md`** (shipped vs next), **`SEMANTICS.md`** / **`RUNTIME_COMPILER_CONTRACT.md`** notes on includes.

---

# AINL v1.1.0 — First Public GitHub Release (Open-Core Baseline)

This is the first public GitHub release of **AINL** as an open-core baseline.

This release focuses on **clarity, trust, and explicit boundaries** more than feature expansion. The repository now makes a clear distinction between canonical compiler-owned behavior, compatibility paths, and intentionally non-strict artifacts used for migration, examples, or legacy workflows.

## Highlights

* Compiler, runtime, grammar, and strict adapter ownership boundaries are now explicitly documented and reflected in tests.
* Strict vs non-strict artifacts are machine-classified and validated in CI.
* Public contributor onboarding has been tightened across README, CONTRIBUTING, support/security docs, templates, and release docs.
* Compatibility paths remain intentional and documented; no hidden semantic widening was introduced for release convenience.

## Canonical Surfaces In This Release

These are the primary source-of-truth surfaces in the current architecture:

* **Compiler semantics and strict validation:** `compiler_v2.py`
* **Runtime execution ownership:** `runtime/engine.py`
* **Runtime compatibility wrapper only:** `runtime.py`, `runtime/compat.py`
* **Formal grammar orchestration:** `compiler_grammar.py`
* **Strict adapter contract allowlist/effect ownership:** `tooling/effect_analysis.py`
* **Artifact strictness classification ownership:** `tooling/artifact_profiles.json`

## Compatibility and Non-Strict Policy

AINL currently ships with explicit compatibility and non-strict surfaces. These are intentional.

* `ExecutionEngine` remains available as a compatibility API for historical imports.
* `legacy.steps` remains supported as compatibility IR.
* Compatibility and non-strict artifacts are explicitly classified rather than treated as accidental drift.
* `examples/golden/*.ainl` are compatibility-focused examples and are **not** strict conformance targets.

Source of truth:

* `tooling/artifact_profiles.json`
* `tests/test_artifact_profiles.py`

## Contributor Experience Improvements

This release also tightens the public repo surface for first-time external contributors:

* clearer README boundaries and entrypoints
* concrete pre-PR validation commands in `CONTRIBUTING.md`
* release/readiness/runbook docs for maintainers
* support/security/governance docs that are GitHub-safe and truthful
* issue / PR templates aligned with artifact-profile awareness

## CI and Validation

CI and release verification now explicitly include:

* core test profile execution
* artifact strict/non-strict verification
* docs contract checks
* compatibility-focused parser/OpenAPI gates
* profile-aware validation for release-facing examples and fixtures

### Advanced coordination (extension / OpenClaw, experimental)

**ZeroClaw** (skill + **`ainl install-zeroclaw`** + **`ainl-mcp`**) is documented separately in **`docs/ZEROCLAW_INTEGRATION.md`** and is not the same as the OpenClaw bridge / coordination substrate below.

This release also includes a **local, file-backed coordination substrate** and
OpenClaw-oriented examples. These features are:

- **extension-only and noncanonical** — implemented via the `agent` adapter and
  OpenClaw extension adapters (`extras`, `svc`, `tiktok`, etc.),
- **advanced / operator-only** — intended for operators and advanced users who
  understand the risks and have their own safety, approval, and policy layers,
- **advisory and local-first** — built around local mailbox-style files under
  `AINL_AGENT_ROOT`, with advisory `AgentTaskRequest` / `AgentTaskResult`
  envelopes, and no built-in routing, authentication, or encryption.

These coordination features are **not**:

- a built-in secure multi-tenant messaging fabric,
- a general-purpose orchestration engine,
- a swarm/multi-agent safety layer,
- or a policy/approval enforcement system.

Upstream provides:

- the minimal coordination contract in `docs/advanced/AGENT_COORDINATION_CONTRACT.md`,
- explicit safe-use and threat-model guidance in `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`,
- a coordination baseline and mailbox validator
  (`tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py`)
  so advanced users can check that envelopes remain on upstream rails.

Operators who choose to use these features are responsible for:

- routing, retries, and scheduling,
- authentication and authorization,
- encryption and transport security,
- human approvals, policy enforcement, and production safety.

### Security, sandbox, and operator deployment

This release includes a structured security and operator deployment story:

- **Adapter privilege-tier metadata** — every adapter in
  `tooling/adapter_manifest.json` now carries a `privilege_tier` (`pure`,
  `local_state`, `network`, `operator_sensitive`). This is advisory metadata
  used by policy validators and security reports, not a runtime semantic.
- **Policy-gated `/run`** — the runner service optionally validates compiled IR
  against a declarative policy (`forbidden_adapters`, `forbidden_effects`,
  `forbidden_effect_tiers`, `forbidden_privilege_tiers`) before execution.
  Violations return HTTP 403 with structured errors.
- **`/capabilities` endpoint** — exposes available adapters, verbs, effect
  defaults, recommended lanes, and privilege tiers for orchestrator discovery.
- **Named security profiles** — `tooling/security_profiles.json` packages
  recommended adapter allowlists, privilege-tier restrictions, and runtime
  limits for four common deployment scenarios: `local_minimal`,
  `sandbox_compute_and_store`, `sandbox_network_restricted`, `operator_full`.
- **Security/privilege report** — `tooling/security_report.py` generates a
  per-label, per-graph privilege map (adapters, verbs, tiers, plus
  `destructive`/`network_facing`/`sandbox_safe` metadata) in both
  human-readable and JSON formats.
- **Capability grant model** — restrictive-only host handshake mechanism
  (`tooling/capability_grant.py`). Each execution surface (runner, MCP server)
  loads a server-level grant from a named security profile at startup via
  `AINL_SECURITY_PROFILE` / `AINL_MCP_PROFILE`. Callers can tighten
  restrictions per-request but never widen beyond the server grant.
  See `docs/operations/CAPABILITY_GRANT_MODEL.md`.
- **Mandatory default limits** — runner and MCP surfaces enforce conservative
  ceilings (`max_steps`, `max_depth`, `max_adapter_calls`, etc.) by default;
  callers can only make limits stricter.
- **Structured audit logging** — the runner emits structured JSON log events
  (`run_start`, `adapter_call`, `run_complete`, `run_failed`,
  `policy_rejected`) with UTC timestamps, trace IDs, result hashes (no raw
  payloads), and redacted arguments. See `docs/operations/AUDIT_LOGGING.md`.
- **Stronger adapter metadata** — `tooling/adapter_manifest.json` (schema 1.1)
  now includes `destructive`, `network_facing`, `sandbox_safe` boolean fields
  per adapter; policy validator supports `forbidden_destructive`.
- **Sandbox and orchestration docs** —
  `docs/operations/SANDBOX_EXECUTION_PROFILE.md`,
  `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`,
  `docs/operations/RUNTIME_CONTAINER_GUIDE.md`, and
  `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` provide prescriptive guidance
  for deploying AINL in sandboxed, containerized, and operator-controlled
  environments.
- **MCP server (workflow-level integration)** — a thin, stdio-only MCP server
  (`scripts/ainl_mcp_server.py`, CLI entrypoint `ainl-mcp`) exposes
  workflow-focused tools (`ainl_validate`, `ainl_compile`, `ainl_capabilities`,
  `ainl_security_report`, `ainl_run`) and resources
  (`ainl://adapter-manifest`, `ainl://security-profiles`) to MCP-compatible
  hosts such as Gemini CLI, Claude Code, Codex-style agent SDKs, and other
  MCP hosts. It is vendor-neutral, runs with safe-default restrictions
  (core-only adapters, conservative limits, hardcoded `local_minimal`-style
  policy), supports startup-configurable **MCP exposure profiles** and
  env-var-based tool/resource scoping, and does not add HTTP transport, raw
  adapter execution, advanced coordination, memory mutation semantics, or
  gateway/control-plane behavior in this release.

AINL does **not** claim to be a sandbox, security platform, or hosted
orchestration layer. Containment, network policy, process isolation,
authentication, and multi-tenant isolation remain the responsibility of the
hosting environment.

## Current Milestone Summary

This release represents a stable, green, release-candidate baseline:

- **Python 3.10+** is the official minimum; metadata, docs, bootstrap, and CI
  (3.10 + 3.11) are aligned.
- **Core test profile is fully green** (403 tests, 0 failures).
- **MCP v1 server** is implemented, tested, and documented with a quickstart
  and minimal example flow.
- **Runner service** uses modern FastAPI lifespan handlers; no deprecation
  warnings remain in the core profile.
- **Security/operator surfaces** (capability grant model, privilege tiers,
  policy validator, named security profiles, mandatory default limits,
  structured audit logging, stronger adapter metadata, security report) are
  coherent and cross-linked.
- **Docs IA** is reorganized by user intent with section READMEs, compatibility
  stubs, and a root navigation hub (`docs/README.md`).

### Start here

| Path | First step | Details |
|------|-----------|---------|
| **CLI only** | `ainl-validate examples/hello.ainl --strict` | See `docs/INSTALL.md` |
| **HTTP runner** | `POST /run` with `{"code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x"}` | See `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` |
| **MCP host** | `pip install -e ".[mcp]" && ainl-mcp` | See section 9 of the external orchestration guide |

## Known Non-Blocking Follow-Ups

* Some compatibility and legacy surfaces remain intentionally non-strict.
* Structured diagnostics can continue improving as a first-class compiler contract.
* Compatibility retirement remains future roadmap work, not part of this release.

## Recommended Next Priorities

See:

* `docs/POST_RELEASE_ROADMAP.md`
* `docs/issues/README.md`

## Project Entry Points

* Project overview: `README.md`
* Getting started: `docs/getting_started/README.md`
* Contributor guide: `CONTRIBUTING.md`
* Release readiness: `docs/RELEASE_READINESS.md`
* Release operations: `docs/RELEASING.md`
* Conformance details: `docs/CONFORMANCE.md`
