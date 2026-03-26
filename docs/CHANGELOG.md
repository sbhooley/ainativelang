# Changelog

## v1.2.9 (March 26, 2026) — PTC-Lisp hybrid integration polish (Phases 1–4.5)

- **feat(ptc)**: `adapters/ptc_runner.py` — opt-in PTC Runner adapter (HTTP + mock + subprocess mode via `AINL_PTC_USE_SUBPROCESS` / `AINL_PTC_RUNNER_CMD`); disabled by default; `AINL_ENABLE_PTC=true` or `--enable-adapter ptc_runner`; structured result envelope with `ok`, `result`, `beam_metrics`, `beam_telemetry`; health/status verbs; `_strip_private_keys` context firewall; registered in `ADAPTER_REGISTRY.json`, `tooling/adapter_manifest.json`, `tooling/effect_analysis.py`.
- **feat(ptc)**: `adapters/llm_query.py` — lightweight opt-in LLM query adapter mirroring `ptc_runner` structure; `run`/`query` verbs; `_strip_private_keys` at serialization boundary.
- **feat(ptc/modules)**: `modules/common/ptc_run.ainl` — thin syntactic-sugar wrapper over `ptc_runner run` with named frame variables and safe defaults for optional `signature` and `subagent_budget`.
- **feat(ptc/modules)**: `modules/common/ptc_parallel.ainl` — pcall-style fan-out orchestrator; respects `max_concurrent` cap; optional `queue.Put` side-channel.
- **feat(ptc/modules)**: `modules/common/recovery_loop.ainl` — bounded retry wrapper for `ptc_runner` calls based on `ok: false` envelope; `max_attempts` capped at 10.
- **feat(ptc/intelligence)**: `intelligence/signature_enforcer.py` — parse `# signature: ...` metadata, validate output shapes, `run_with_signature_retry` (max 3 attempts).
- **feat(ptc/intelligence)**: `intelligence/trace_export_ptc_jsonl.py` — export AINL trajectories in PTC-compatible JSONL; `_strip_private_keys`; `beam_metrics` and `beam_telemetry` fields.
- **feat(ptc/intelligence)**: `intelligence/context_firewall_audit.py` — audit `.ainl` source and trajectory files for `_`-prefixed key leakage; runnable via `scripts/run_intelligence.py`.
- **feat(ptc/intelligence)**: `intelligence/ptc_to_langgraph_bridge.py` — analyze `.ainl` source or trajectory for `ptc_runner` calls; emit LangGraph-compatible `create_ptc_tool_node` Python snippet.
- **feat(ptc/mcp)**: `scripts/ainl_mcp_server.py` — new tools: `ainl_ptc_signature_check`, `ainl_trace_export`, `ainl_ptc_run`, `ainl_ptc_health_check`, `ainl_ptc_audit` (combined signature + firewall report); wired into `tooling/mcp_exposure_profiles.json`.
- **feat(ptc/cli)**: `cli/main.py` — `ainl run-hybrid-ptc` subcommand: thin wrapper over `ainl run` with pre-configured defaults (mock mode, `ptc_runner` adapter, trace path); `--no-mock` and `--trace-jsonl` overrides.
- **feat(ptc/examples)**: `examples/hybrid_order_processor.ainl` — production hybrid example: parallel order batches, signature validation, recovery loop, `_` context firewall, trace/LangGraph bridge comments.
- **feat(ptc/examples)**: `examples/price_monitor.ainl` — second production example: parallel price monitoring with `ptc_parallel` + `recovery_loop` + `_` context firewall.
- **feat(ptc/docs)**: `docs/assets/ptc_flow.mmd` — Mermaid flow diagram: AINL graph → PTC modules → PTC Runner/BEAM → enriched envelope → trace export / LangGraph bridge → deployment.
- **feat(ptc/security)**: `tooling/security_profiles.json` — `ptc_sandbox_plus` named profile with `max_subagent_budget`, `trace_depth`, `max_concurrent_calls`.
- **docs(ptc)**: `docs/adapters/PTC_RUNNER.md` — full integration guide (setup, verbs, envelope, signature, context firewall, parallel, recovery, subprocess BEAM mode, LangGraph emission, MCP tools, Mermaid diagram, production examples).
- **docs(ptc)**: `WHITEPAPERDRAFT.md` §8.4 — PTC-Lisp hybrid integration positioning note.
- **docs(ptc)**: `README.md`, `docs/README.md`, `docs/INTELLIGENCE_PROGRAMS.md`, `docs/EXAMPLE_SUPPORT_MATRIX.md`, `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` — cross-references and quick-start callouts.

## v1.2.8 (March 25, 2026) — OpenClaw ops, intelligence hydration, graph-runtime docs

- **docs(whitepaper)**: **`WHITEPAPERDRAFT.md`** (v1.2.8 positioning, §6.6 graph pitfalls, §10.5 intelligence, §13.5 token caps, §17.1 shipped, appendix OpenClaw file map); supporting updates: **`docs/WHAT_IS_AINL.md`**, **`docs/DOCS_INDEX.md`**, **`docs/overview/README.md`**, **`docs/POST_RELEASE_ROADMAP.md`**
- **packaging**: **`pyproject.toml` / `ainl-lang` 1.2.8**; **`RUNTIME_VERSION`** **`1.2.8`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); **`CITATION.cff`** aligned. Reinstall or **`pip install -U -e .`** so CLI/MCP/runner **`runtime_version`** matches and **`__pycache__`** from older trees does not shadow updated modules.
- **feat(ops)**: rolling budget hydration for **`scripts/run_intelligence.py`**, **`tooling/intelligence_budget_hydrate.py`**, workspace env pin **`tooling/openclaw_workspace_env.example.sh`**, ops docs (**`docs/operations/*`**: profiles, token observability, workspace isolation, WASM/TTL/embedding notes).
- **docs(openclaw)**: **`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`** — agent-discoverable install/upgrade checklist (profiles, caps, cron, host bootstrap, verification); indexed from **`tooling/bot_bootstrap.json`**, **`HOST_PACK_OPENCLAW.md`**, **`DOCS_INDEX.md`**.
- **docs(openclaw)**: **`docs/operations/OPENCLAW_HOST_AINL_1_2_8.md`** — host briefing for **v1.2.8** (repo capabilities vs OpenClaw obligations: probe, rolling hydrate, profiles, bootstrap contract); **`openclaw_host_ainl_1_2_8`** in **`tooling/bot_bootstrap.json`**.
- **fix(graph)**: intelligence + **`modules/common/generic_memory.ainl`** — graph-safe **`X`** (no raw `{…}` literals), **`memory.list`** optional prefix via **`null`**, metadata **`valid_at`** / tags; see **`docs/RUNTIME_COMPILER_CONTRACT.md`** § graph pitfalls, **`docs/AINL_SPEC.md`**.

## v1.2.7 (March 24, 2026) — Hyperagent Research Pack (additive)

- **feat(cli)**: `ainl inspect <file.ainl> [--strict] [--json]` — dump full canonical IR JSON.
- **feat(runtime)**: `ainl run --trace-jsonl PATH|-` — structured JSONL execution tape (file or stdout).
- **feat(diagnostics)**: structured diagnostics expose `llm_repair_hint` for LLM-native repair loops.
- **feat(mcp)**: `ainl_fitness_report` and `ainl_ir_diff` tools for selection/mutation loops; `ainl_fitness_report` includes `fitness_score` with `fitness_components`/`weights`, plus adapter/operation/frame-key proxy metrics; `ainl_ir_diff` detects payload-level node data deltas (not only topology).
- **feat(schema)**: machine-readable schema seed `ainl.schema.json`.
- **docs**: `docs/EMBEDDING_RESEARCH_LOOPS.md`, `docs/operations/MCP_RESEARCH_CONTRACT.md`, `prompts/meta-agent/*`.

## v1.2.6 (March 24, 2026) — sandbox install hardening, wheel integrity gates, doctor command

- **fix(graph / intelligence)**: **`intelligence/token_aware_startup_context.lang`** and **`modules/common/generic_memory.ainl`** — avoid **`X {…}`** object literals (graph IR → **`unknown X fn: {`**); build filters/payloads with **`core.parse`**, **`obj`/`put`**, **`arr`**; merge list steps into one label (do not use **`J NextLabel`** as a jump); **`memory.list`** uses **`null`** for omitted **`record_id_prefix`**; **`memory_tags`** via **`X … (arr …)`**; **`valid_at`** from **`R core iso`**. Documented in **`docs/AINL_SPEC.md`**, **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/INTELLIGENCE_PROGRAMS.md`**, **`docs/adapters/MEMORY_CONTRACT.md`** § 3.4.
- **fix(lang/samples)**: intelligence programs, demos, and autonomous-ops examples — bind memory-contract frame variables with **`Set`** (`memory_namespace`, `memory_kind`, `memory_record_id`, …), not **`X`**, which parses the next token as `fn` (fixes `unknown X fn` / invalid `core.isNull` usage in scheduled OpenClaw flows). Documented in **`docs/AINL_SPEC.md`**, **`docs/INTELLIGENCE_PROGRAMS.md`**, **`docs/adapters/MEMORY_CONTRACT.md`**; module example comments in **`modules/common/access_aware_memory.ainl`**.
- **fix(packaging)**: include `runtime` and `runtime.*` in setuptools package discovery so wheel installs include `runtime.compat` and avoid wheel-only import regressions.
- **fix(skill-installer)**: `skills/ainl/install.sh` hardened for restricted environments (PEP 668 fallbacks), no `eval`, and idempotent PATH hint updates across `.bashrc`/`.zshrc`/`.profile`.
- **feat(cli)**: add `ainl doctor` for environment diagnostics (Python/import health, PATH checks, MCP config checks, `install-mcp --dry-run` checks).
- **feat(ci)**: add Linux/macOS install smoke matrix for Python 3.10–3.13 with normal, `--user`, and `--break-system-packages` install paths, plus `pip check`, `ainl --help`, and `ainl-mcp --help`.
- **feat(ci/release)**: add wheel-integrity CI and dedicated release gates (`twine check`, wheel import smoke for `runtime.compat/adapters/cli.main`, `pip check`, MCP dry-run installers).
- **feat(packaging/docs)**: add tested Python 3.13 MCP constraints (`constraints/py313-mcp.txt`) and document no-root install order (venv -> `--user` -> `--break-system-packages`) across install/release/skill docs.
- **feat(compiler/ir)**: add optional `execution_requirements` metadata (including `avm_policy_fragment`, isolation/capability/resource hints) for AVM/general sandbox handoff.
- **feat(runtime/sandbox)**: add unified optional sandbox shim (`runtime/sandbox_shim.py`) and light wiring in runner, MCP, and CLI runtime path with graceful fallback when no sandbox runtime is detected.
- **feat(cli)**: add `ainl generate-sandbox-config <file.ainl> [--target avm|firecracker|gvisor|k8s|general]`.
- **feat(trajectory)**: add optional trajectory JSONL fields when sandbox shim is connected (`avm_event_hash`, `sandbox_session_id`, `sandbox_provider`, `isolation_hash`).
- **docs(integration)**: update integration/ops/getting-started docs and whitepaper references for AVM + general sandbox deployment posture.

## v1.2.5 (March 23, 2026) — Hyperspace bridge + hybrid `S`, CI benchmark baselines, LangGraph emit

- **feat(compiler)**: **`S hybrid langgraph`**, **`S hybrid temporal`**, or both on one line — opt-in hybrid wrapper targets for **`minimal_emit`** / capability planning; stored as **`services.hybrid.emit`** (de-duped); strict mode rejects unknown targets
- **feat(tooling)**: legacy **`infer_artifact_capabilities`** (IRs without **`emit_capabilities`**) derives **`needs_langgraph`** / **`needs_temporal`** from **`services.hybrid.emit`**
- **feat(ci)**: **`benchmark-regression`** prefers committed **`tooling/benchmark_size_ci.json`** / **`tooling/benchmark_runtime_ci.json`** on the baseline SHA when present; falls back to full JSON reports; several jobs pinned to **Python 3.10**; **`make benchmark-ci`** prints resolved **`PYTHON`**
- **fix(emit/langgraph)**: emitted **`AinlHybridState`** uses plain **`dict`** fields so **LangGraph**’s **`get_type_hints`** path works on **Python 3.10**
- **test**: hybrid e2e (**`StateGraph.invoke`**, Temporal **`ActivityEnvironment`**), **`S hybrid`** and emission-planner legacy IR coverage
- **docs**: **`BENCHMARK.md`** (CI baseline rules), **`docs/AINL_SPEC.md`** / **`docs/language/grammar.md`** (**`S hybrid`**), **`docs/RELEASING.md`** (benchmark-ci commit step); expanded narrative **`docs/RELEASE_NOTES.md`** § **v1.2.5**; cross-links in **`README.md`**, **`docs/README.md`**, **`CONTRIBUTING.md`**, **`WHITEPAPERDRAFT.md`**, **`docs/POST_RELEASE_ROADMAP.md`**, **`docs/DOCS_INDEX.md`**, **`docs/WHAT_IS_AINL.md`**, **`WHAT_IS_AINL.md`**, **`docs/overview/README.md`**

### Hyperspace bridge (trajectory, common modules, local adapters, emitter)

- **feat(runtime)**: optional per-step **trajectory JSONL** (`--log-trajectory` / `AINL_LOG_TRAJECTORY`) — `docs/trajectory.md`
- **feat(modules)**: `modules/common/guard.ainl`, `session_budget.ainl`, `reflect.ainl` — token/time ceilings, budget accounting, reflect gates; `modules/common/README.md` updated
- **feat(adapters)**: local **`vector_memory`** (keyword-scored JSON store) and **`tool_registry`** (JSON tool catalog) under `adapters/`; CLI `--enable-adapter vector_memory|tool_registry`; documented in `docs/reference/ADAPTER_REGISTRY.md`, `docs/adapters/README.md`
- **feat(emit)**: **`--emit hyperspace`** via `scripts/validate_ainl.py` / **`ainl-validate`** — **`compiler_v2.AICodeCompiler.emit_hyperspace_agent`** emits a **single-file** Python agent: **base64 JSON** IR blob (`_IR_B64`), repo-root discovery for **`runtime/`** + **`adapters/`**, **`AdapterRegistry`** with **`core`**, **`vector_memory`**, **`tool_registry`**, **`RuntimeEngine`** (**`graph-preferred`**, **`step_fallback=True`**), **`run_ainl`**, **`__main__`**; **`AINL_LOG_TRAJECTORY`** → **`<source-stem>.trajectory.jsonl`** in cwd; optional **`hyperspace_sdk`** import with **`RuntimeWarning`** when absent (scaffold TODO for future SDK bridge)
- **feat(examples/teaching)**: **`examples/hyperspace_demo.ainl`**, **`examples/test_adapters_full.ainl`** — strict-valid dotted-verb demos; **`tooling/canonical_curriculum.json`** / **`scripts/build_canonical_training_pack.py`** outputs include these lessons
- **test(emit)**: hyperspace (and related) emitter coverage in **`tests/test_snapshot_emitters.py`**
- **docs**: **`docs/emitters/README.md`**, root **`README.md`**; hub links in `docs/README.md`, `docs/DOCS_INDEX.md`; `docs/runtime/README.md` (trajectory); `docs/examples/README.md` (phase-2 / hyperspace examples); `docs/language/AINL_CORE_AND_MODULES.md` §8 (guard/budget/reflect); `docs/INTELLIGENCE_PROGRAMS.md` (`infrastructure_watchdog.lang`); `docs/RUNTIME_COMPILER_CONTRACT.md` (trajectory note); **`docs/RELEASE_NOTES.md`** § **v1.2.5** — expanded **Hyperspace emitter** narrative
- **ops / examples**: `intelligence/infrastructure_watchdog.lang`, `scripts/morning_briefing.ainl` + wrapper, small `examples/test_*.ainl` harnesses; `.gitignore` **`runtime_runner.log`**
- **docs (primer policy)**: **`docs/WHAT_IS_AINL.md`** is the **canonical** “What is AINL?” document (stakeholder narrative + capability snapshot); repository root **`WHAT_IS_AINL.md`** is a **stub** pointing to it. **`README.md`**, **`docs/README.md`**, **`docs/DOCS_INDEX.md`**, **`docs/overview/README.md`**, **`WHITEPAPERDRAFT.md`** (§5.4 includes note, new §6.5 trajectory / Hyperspace) updated accordingly.

### Strict label dataflow and hybrid E2E (shipped with v1.2.5 line)

- **fix(strict)**: **`propagate_inter_label_entry_defs`** / merged entry defs in **`tooling/effect_analysis.py`** and **`compiler_v2._validate_graphs`** — variables live on all paths into a jumped-to label are recognized at that label (fewer false undefined-at-use errors on branch/cron monitor patterns)
- **test**: **`tests/test_inter_label_dataflow.py`**; Temporal **`execute_workflow`** path in **`tests/test_hybrid_emit_integration.py`** (**`WorkflowEnvironment`**, **`Worker`**, **`ThreadPoolExecutor`** activity executor)
- **tooling**: **`tooling/artifact_profiles.json`** strict-valid refresh (**`examples/cron/monitor_and_alert.ainl`**, **`corpus/example_monitor_alert/program.ainl`**, …); curriculum order bump + regenerated **`tooling/canonical_training_pack.json`** / **`tooling/training_packs/*`**; conformance syrupy snapshots under **`tests/snapshots/conformance/`**

## v1.2.4 (March 21, 2026)

**Addendum (2026-03-22).**

- **fix(apollo-x-bot)**: `gateway_server.py` — **`_classify_wants_envelope`** only when **`messages`** is a non-empty list (avoids **`envelope_missing_messages`** on **`classify_response=raw`** without messages; legacy tweet+prompt path); clearer bind error on **EADDRINUSE**; swallow **BrokenPipeError** / connection resets when the client disconnects early (timeouts).
- **fix(cli)**: **`ainl run --http-timeout-s`** help text — note LLM / bridge latency; default remains **5** (callers with slow routes must raise it).
- **fix(apollo-x-bot)**: **`openclaw-poll.sh`** / **`run-with-gateway.sh`** — **`--http-timeout-s 120`**, overridable via **`AINL_HTTP_TIMEOUT_S`**.
- **fix(graph)**: **`apollo-x-bot/ainl-x-promoter.ainl`** — **`promoter.process_tweet`** payload: stringify **`tweet`** directly for the bridge body; skip branch uses boolean **`true`** for JSON **`ok`** (strict-safe).
- **test**: **`tests/test_apollo_x_gateway.py`** — regression for classify **raw** without **messages**; expanded gateway coverage as applicable.
- **fix(compiler_v2)**: strict reachability — treat **If** as a valid label terminator (skip “exactly one J” false positive when **If** is last); include **If** when wiring **Loop**/**While** fall-through edges to following labels.
- **fix(demo)**: **`demo/infrastructure_watchdog.lang`** — restart services when down; verify after restart before alerting.
- **docs**: **`docs/reference/ADAPTER_REGISTRY.md`** §2.4.3 (**bridge** client timeout); **`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`** §7 (timeouts + **`llm.classify`** envelope rule); **`docs/OPENCLAW_INTEGRATION.md`** (Apollo promoter + **`openclaw-poll.sh`** pointer); **`apollo-x-bot/OPENCLAW_DEPLOY.md`** (**`AINL_HTTP_TIMEOUT_S`** / **`--http-timeout-s`**).

- **packaging**: **`pyproject.toml` / `ainl-lang`** **1.2.4**; **`RUNTIME_VERSION`** (`runtime/engine.py`, mirrored `tests/emits/server/runtime/engine.py`) **1.2.4**; language server **`serverInfo.version`** and runner service **FastAPI** `app.version` follow **`RUNTIME_VERSION`** (runner: `scripts/runtime_runner_service.py`; LSP: `langserver.py`)
- **feat(modules)**: `modules/common/access_aware_memory.ainl` — opt-in **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, **`LACCESS_LIST_SAFE`** (graph-safe list touches via While + index); header warnings and usage notes for graph vs ForEach
- **fix(runtime)**: resolve bare label targets against include **alias** from call stack (`_resolve_label_key` in `runtime/engine.py`) so nested **If** / **Loop** / **Call** / **While** reach **`alias/label`** keys after merge
- **docs**: `modules/common/README.md`; refresh root **`README.md`**, **`WHAT_IS_AINL.md`**, **`docs/WHAT_IS_AINL.md`**, **`WHITEPAPERDRAFT.md`**, **`docs/RELEASE_NOTES.md`**, **`docs/POST_RELEASE_ROADMAP.md`**, **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/README.md`**, **`docs/adapters/README.md`**, **`docs/DOCS_INDEX.md`**, **`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`** (sample `runtime_version` in JSON)
- **test**: `tests/test_demo_enforcer.py` (demo compile + access-aware smoke; graph-only bare-label regression)
- **fix(programs)**: `S` is parsed as **`service mode path`** (three slots); patterns like **`S core memory cron "0 * * * *"`** wrongly set **`path` to `cron`** and drop the schedule. Restored **`S core cron "<expr>"`** (and equivalent) in **`intelligence/token_aware_startup_context.lang`**, **`intelligence/session_continuity_enhanced.lang`**, **`intelligence/proactive_session_summarizer.lang`**, **`demo/session_continuity.lang`**, and **`examples/autonomous_ops/memory_prune.lang`**.
- **fix(programs)**: **`examples/autonomous_ops/meta_monitor.lang`** — replace invalid **`S cron`** + **`Cr`** with **`S cache cron "*/15 * * * *"`** (aligned with **`demo/meta_monitor.lang`**).
- **tooling**: **`scripts/validate_s_cron_schedules.py`** and console script **`ainl-validate-s-cron`** (`pyproject.toml`) — fail CI/local runs on malformed **`S`+`cron`** lines; **`tests/test_s_cron_schedule_lines.py`** keeps the rule green.
- **docs**: **`docs/CRON_ORCHESTRATION.md`** — new § **`S` line shape (cron schedules)** and § **Security: queues, notifications, and secrets**; **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/DOCS_INDEX.md`**; web mirror **`ainativelangweb/content/docs/RUNTIME_COMPILER_CONTRACT.mdx`**.
- **docs(intelligence)**: **`intelligence/token_aware_startup_context2.lang`** — explicit **legacy** header; prefer **`token_aware_startup_context.lang`** for production (budget gate + structured memory + access-aware reads).
- **bench**: regenerate **`BENCHMARK.md`**, **`tooling/benchmark_size.json`**, **`tooling/benchmark_runtime_results.json`**, and CI twins **`tooling/benchmark_size_ci.json`** / **`tooling/benchmark_runtime_ci.json`** via **`make benchmark`** / **`make benchmark-ci`**; refresh **`README.md`** and **`docs/benchmarks.md`** headline table (e.g. **19** strict-valid, **`public_mixed`** path counts + viable ratios; **`make benchmark`** uses **`--mode wide`**: **`full_multitarget_core`** + **`full_multitarget`** + **`minimal_emit`**).
- **interop**: optional **`[interop]`** extra in **`pyproject.toml`** (**langgraph**, **temporalio**, **aiohttp**); **`[benchmark]`** also lists **`temporalio`** for hybrid smoke tests — see **`docs/PACKAGING_AND_INTEROP.md`**.

## v1.2.3 (March 20, 2026)

- **bench(docs)**: major **size benchmark** documentation refresh (Mar 2026): default **tiktoken cl100k_base** in **`BENCHMARK.md`** tables; **viable subset** vs **legacy-inclusive** dual reporting; **minimal_emit** **python_api fallback stub** and **prisma** / **react_ts** **compaction** called out in transparency notes; JSON schema **`3.5+`**; hub **`docs/benchmarks.md`** highlights table; README / **`WHITEPAPERDRAFT.md`** §12 / cross-links updated. *Representative headline:* `public_mixed` **minimal_emit ~1.02×** on **viable** rows (46/59); legacy-inclusive minimal **~0.24×** shown separately.
- **docs(ops)**: add **`docs/operations/UNIFIED_MONITORING_GUIDE.md`** (unified AINL + OpenClaw monitoring); expand **`docs/openclaw/BRIDGE_TOKEN_BUDGET_ALERT.md`**; cross-link hub from **`docs/README.md`**, **`docs/DOCS_INDEX.md`**, **`docs/operations/README.md`**, **`docs/CRON_ORCHESTRATION.md`**, **`docs/AINL_CANONICAL_CORE.md`**, **`docs/ainl_openclaw_unified_integration.md`**, **`docs/adapters/*`**, **`docs/BOT_ONBOARDING.md`**, **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`**, **`docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md`**, **`docs/operations/AUTONOMOUS_OPS_MONITORS.md`**, **`docs/advanced/README.md`**, **`docs/adapters/MEMORY_CONTRACT.md`**; standardize daily memory path **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**; refresh **`openclaw/bridge/README.md`** monitoring tables and env reference
- **feat(modules)**: add reusable memory helper include modules for production monitor flows:
  - `modules/common/token_cost_memory.ainl` for deterministic `workflow` namespace writes/lists
  - `modules/common/ops_memory.ainl` for deterministic `ops` namespace writes/lists
- **refactor(programs)**: migrate monitor-heavy `demo/` and `examples/autonomous_ops/` workflows from repeated inline memory logic to shared include calls while preserving payloads, record kinds, tags, TTLs, and control-flow behavior
- **feat(programs)**: normalize deterministic filters across migrated history reads (`updated_after`, `tags_any`, `source`, `limit`) and standardize metadata envelopes on writes (`source`, `confidence`, `tags`, `valid_at`)
- **docs(ops)**: refresh autonomous ops documentation to reflect include-helper architecture and current monitor implementation posture
- **feat(strict)**: allowlist `memory.PUT` / `GET` / `APPEND` / `LIST` / `DELETE` / `PRUNE` in `tooling/effect_analysis.py` and treat `R memory <verb> …` steps as `memory.<VERB>` for strict adapter checks
- **test(conformance)**: add `memory_continuity_runtime` snapshot category and `tests/data/conformance/session_budget_memory_trace.ainl`; extend tokenizer round-trip with `demo/session_budget_enforcer.lang` and IR canonicalization for the trace golden
- **docs(examples)**: add `examples/timeout_memory_prune_demo.ainl`, committed `docs/assets/timeout_memory_prune_flow.png`, README **Memory & State** pointer to `demo/session_budget_enforcer.lang`, and visualizer PNG example command

## v1.2.2 (March 20, 2026)

- **feat(memory)**: implement Memory Contract v1.1 additive runtime support in `runtime/adapters/memory.py`:
  - optional deterministic metadata envelope fields (`source`, `confidence`, `tags`, `valid_at`)
  - deterministic `memory.list` bounded filters (`tags_any`, `tags_all`, created/updated windows, `source`, `valid_at` windows, `limit`, `offset`)
  - namespace retention hooks (`default_ttl_by_namespace`, `prune_strategy_by_namespace`)
  - portable operational counters in adapter responses (`stats.operations`, `stats.reads`, `stats.writes`, `stats.pruned`)
- **feat(capabilities)**: add capability-advertised memory profile in `tooling/capabilities.json` (`memory_profile: "v1.1-deterministic-metadata"`) with schema support in `tooling/capabilities.schema.json`
- **test(memory)**: extend `tests/test_memory_adapter.py` for metadata round-trip, deterministic list filters/pagination, retention hooks, and operational counters
- **docs(memory)**: align `docs/adapters/MEMORY_CONTRACT.md` and `docs/reference/CAPABILITY_REGISTRY.md` with shipped v1.1 additive behavior

## v1.2.1 (March 20, 2026)

- **feat(visualizer)**: add image export for `ainl visualize` via Playwright (`--png`, `--svg`, `--width`, `--height`, and extension auto-detect for `.png`/`.jpg`/`.jpeg`/`.svg`)
- **test(visualizer)**: add `tests/test_visualizer.py` smoke coverage for PNG/SVG generation
- **docs(examples)**: add `examples/timeout_demo.ainl` and expand README/docs guidance for starter timeout module and visualizer image export usage
- **fix(readme)**: remove duplicate badge block and switch release badge to latest tag endpoint

## v1.2.0 (March 20, 2026)

- **feat**: subgraph includes & modules (compile-time composition, alias prefixing, ENTRY/EXIT contract)
- **feat**: graph visualizer CLI (`ainl visualize` → Mermaid with clusters, synthetic call edges)
- **feat**: full conformance matrix runner (`make conformance`) with snapshot categories for tokenizer, IR, strict validation, runtime parity, and emitter stability
- **fix**: preserve `__literal_fields` through include merge + lowering
- **docs**: updated README/docs hubs for conformance command, CI gate, and generated conformance artifacts

### Packaging (v1.2.0)

- **`pyproject.toml` / `ainl-lang`:** version **1.2.0**.
- **`RUNTIME_VERSION`** (`runtime/engine.py`, mirrored `tests/emits/server/runtime/engine.py`): **1.2.0** (runner/MCP payloads, `/capabilities`, `ainl run --json`).
- **Language server** initialize `serverInfo.version` and **runner service** OpenAPI app version: **1.2.0**.

### Highlights

- **Includes (compile-time composition):** top-level **`include path [as alias]`** merges submodule labels into the parent IR as **`alias/LABEL`** (e.g. `retry/ENTRY`, `retry/EXIT_OK`). Strict mode enforces **ENTRY / EXIT_*** shapes for included graphs. Starter modules: `modules/common/retry.ainl`, `modules/common/timeout.ainl`. Tests: `tests/test_includes.py`.
- **Graph visualizer CLI:** **`ainl visualize`** / **`ainl-visualize`** / `scripts/visualize_ainl.py` — strict compile → **Mermaid** `graph TD` from **`ir["labels"]`**; **subgraph** clusters per include alias; **synthetic** `Call → callee entry` edges with a `%%` comment; flags `--no-clusters`, `--labels-only`, `-o -`. Fixture: `examples/bad_include.ainl`.
- **Structured diagnostics:** native **`Diagnostic`** rows, **`--diagnostics-format`** (`auto` | `plain` | `rich` | `json`), merge **dedup** (native-first), optional **rich** stderr with `pip install -e ".[dev]"` — used by **`ainl-validate`** and **`ainl visualize`** (and the language server path).
- **Strict literals / dataflow:** quote string payloads where strict dataflow expects literals (e.g. **`J "ok"`**); aligned with **`docs/RUNTIME_COMPILER_CONTRACT.md`** and conformance tests.

### Documentation

- Root **`README.md`** (quick-start write → validate → visualize → run, includes, visualize flags, **`docs/WHAT_IS_AINL.md`** link), **`WHAT_IS_AINL.md`**, **`docs/WHAT_IS_AINL.md`**, **`WHITEPAPERDRAFT.md`** (v1.2.0, §5.4–5.5), **`docs/POST_RELEASE_ROADMAP.md`**, **`docs/CONFORMANCE.md`**, **`SEMANTICS.md`**, **`docs/architecture/GRAPH_INTROSPECTION.md`**, **`docs/INSTALL.md`**, **`docs/DOCS_INDEX.md`**, **`docs/overview/README.md`**, **`docs/README.md`**.

---

## Tooling — graph visualizer CLI (Mermaid) (2026-03-20)

### Features

- **`scripts/visualize_ainl.py`** — strict compile → **Mermaid** `graph TD` from `ir["labels"]`; subgraph clusters by `include` alias; synthetic `Call →` entry edges with `%%` comment; `--no-clusters`, `--labels-only`; structured diagnostics on failure (reuse `validate_ainl` formatters).
- **`ainl-visualize`** console script and **`ainl visualize`** subcommand (`cli/main.py`, `pyproject.toml`).
- **`examples/bad_include.ainl`** — fixture for visualize/strict error demos.

### Documentation

- Root `README.md` (Visualize your workflow, mermaid.live walkthrough), `.gitignore` (`hello.mmd`).
- `docs/architecture/GRAPH_INTROSPECTION.md` §7 (Mermaid), §8 (DOT; former §6), fixed duplicate §5 → §6 record/replay.
- `docs/INSTALL.md`, `docs/DOCS_INDEX.md`, `docs/README.md`, `docs/architecture/README.md`, `docs/reference/GRAPH_SCHEMA.md`.

---

## Compiler — diagnostics merge dedup + `--diagnostics-format` (2026-03-09)

### Behavior

- **`compiler_v2`**: After merging native and string-derived diagnostics, **deduplicate** by `(kind, message body)` with `Line N:` stripped; **native rows first** so spans, `label_id`, and suggestions win over parsed duplicates.
- **`ainl-validate`**: **`--diagnostics-format=auto|plain|json|rich`** (default `auto`). **`--json-diagnostics`** remains an alias for `json`. **`--no-color`** forces plain output instead of rich.

### Documentation

- `README.md`, `docs/INSTALL.md`.

---

## Compiler — structured diagnostics + `ainl-validate` CLI (2026-03-09)

### Features

- **`compiler_diagnostics.py`** — `Diagnostic`, `CompilerContext`, `CompilationDiagnosticError`; native diagnostics merged with legacy `errors` strings.
- **Strict-mode native diagnostics** in `compiler_v2.py` for: arity (`min_slots`), unknown module prefix, **duplicate `Lxx:`** (strict-only legacy error; non-strict still merges bodies), **undeclared endpoint label**, **undeclared targeted label** (control-flow refs). Spans, `suggested_fix`, `related_span`, and label close-match hints where applicable.
- **`ainl-validate` / `scripts/validate_ainl.py`** — `--strict` wires structured diagnostics by default; stderr shows a numbered report (3-line source context, carets for spans). **`--json-diagnostics`** prints diagnostics JSON only to stdout on failure. **`rich`** (optional dev extra) enables styled output; plain ANSI or no-color when rich is missing or `--no-color` / non-TTY.
- **Tests:** `tests/test_diagnostics.py` (structured round-trip, phase-2 sites, formatter smoke).

### Documentation

- `README.md`, `docs/INSTALL.md`, `docs/architecture/GRAPH_INTROSPECTION.md`, `docs/CONFORMANCE.md`, `docs/POST_RELEASE_ROADMAP.md`, `pyproject.toml` (`rich` in `[project.optional-dependencies] dev`).

---

## Documentation — agent reports & intelligence hub (2026-03-19)

### Documentation

- **`agent_reports/README.md`** — index of OpenClaw **field reports** (distinct from `CONSULTANT_REPORTS.md` / `AI_CONSULTANT_REPORT_*.md`).
- **`docs/INTELLIGENCE_PROGRAMS.md`** — map of `intelligence/*.lang`, host responsibilities, and `scripts/run_intelligence.py`.
- **`scripts/run_intelligence.py`** — dev runner for `context` / `summarizer` / `consolidation` / `continuity` / `all` (OpenClaw monitor registry).
- **`CONSULTANT_REPORTS.md`**, **`docs/DOCS_INDEX.md`**, **`docs/AI_AGENT_CONTINUITY.md`**, **`AI_AGENT_QUICKSTART_OPENCLAW.md`**, **`README.md`** — cross-links to the above.
- **Field report:** `agent_reports/ainl-king-openclaw-2026-03-19.md` (Day 2 — AINL King; merged via PR #2).

## 1.1.1 — Runtime correctness fixes and adapter extensions (2026-03-09)

### Bug fixes

- **Compiler: X-step S-expression paren stripping** — `X dst (core.add 3 4)`
  and similar paren-form X expressions now parse correctly. The tokenizer does
  not treat `(` and `)` as delimiters, so the leading `(` was attaching to the
  function name and the entire `core.*` engine branch was unreachable dead code.
  Fixed in both X-step parser paths in `compiler_v2.py`. Snapshot updated for
  `examples/openclaw/daily_digest.lang` which uses `(core.div ...)` and
  `(core.gt ...)`.

- **Runtime: `J` variable resolution** — `J var` was returning the raw token
  string `"var"` instead of resolving `var` from the execution frame. Fixed
  with a one-line `_resolve()` call in `runtime/engine.py`. This was a silent
  correctness bug since the original release; every program using `J` for its
  return value was affected. Snapshots updated.

### New adapter verbs (OpenClaw extension level)

- **`web.search`** — new `WebAdapter` in `adapters/openclaw_integration.py`
  backed by OpenRouter/Perplexity. Returns search results for use in
  intelligence digest and monitoring workflows. Requires `OPENROUTER_API_KEY`.

- **`tiktok.recent`** — new verb on the `TikTokAdapter` for retrieving recent
  posts/metrics with a configurable limit.

- **`core.idiv`** — integer division builtin added to `CoreBuiltinAdapter`
  in `runtime/adapters/builtins.py`. Available as both `R core.idiv` and
  `X dst (core.idiv a b)` in X expressions.

- **`memory` `ops` namespace** — `ops` added to the valid namespace whitelist
  in the memory adapter for operational metrics and monitor state storage.

### Dependency

- `requests>=2.28.0` declared under `[project.optional-dependencies] openclaw`
  in `pyproject.toml`. The `WebAdapter` uses it; previously relied on silently
  as a transitive dep.

### Documentation

- `docs/INSTALL.md`: recommended **Python 3.10** layout using `.venv-py310` and
  `PYTHON_BIN=python3.10` bootstrap; agents/CI parity note.
- `scripts/bootstrap.sh`: `PYTHON_BIN` / `VENV_DIR` env vars + 3.10 minimum check.
- `scripts/precommit_docs_contract.sh` + `.pre-commit-config.yaml`: docs contract
  hook resolves Python via `.venv-py310`, then `.venv`, then `python3` (no bare
  `python` on PATH required).

- `docs/AINL_SPEC.md`: `X`, `Loop`, `While`, `ForEach` added to grammar and
  slot rules tables; `J` description clarified to say "resolve from frame".
- `docs/ainl_runtime_spec.md`: X fn list updated (`idiv`, `concat`, `join`,
  `ite`/`if`, `core.*` prefix form, paren syntax); `J` semantics note added.
- `docs/reference/ADAPTER_REGISTRY.md`: `web` adapter added; `tiktok.recent`
  and `core.idiv`/`IDIV` documented; `memory` `ops` namespace noted.
- `docs/adapters/MEMORY_CONTRACT.md`: `ops` namespace added to v1 whitelist.

---

## 1.1.0 — First Public Release Candidate (2026-03-09)

### Baseline
- Official Python minimum raised to **3.10+**; metadata, docs, bootstrap, and CI
  (3.10 + 3.11) aligned.
- Core test profile fully green (403 tests, 0 failures).

### MCP Server (v1)
- Added `scripts/ainl_mcp_server.py` — a thin, stdio-only MCP server exposing
  `ainl_validate`, `ainl_compile`, `ainl_capabilities`, `ainl_security_report`,
  and `ainl_run` as MCP tools, plus `ainl://adapter-manifest` and
  `ainl://security-profiles` as MCP resources.
- Safe-default posture: core-only adapters, conservative limits, hardcoded
  `local_minimal`-style policy.
- Quickstart and end-to-end example in
  `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` section 9.

### Security & Operator Surfaces
- Adapter privilege-tier metadata in `tooling/adapter_manifest.json`.
- Policy validator supports `forbidden_privilege_tiers`.
- Named security profiles in `tooling/security_profiles.json`.
- Security/privilege introspection via `tooling/security_report.py`.
- Sandbox, orchestration, and threat-model docs shipped.

### Documentation
- `docs/` reorganized into intent-based sections (overview, fundamentals,
  getting_started, architecture, runtime, language, adapters, emitters,
  examples, case_studies, competitive, operations, advanced, reference) with
  section READMEs, compatibility stubs, and a root navigation hub.
- README: added "Choose Your Path" mode chooser (CLI / runner / MCP) with a
  single canonical example shown three ways.
- Getting-started guide enriched with integration paths and core-first guidance.
- Release notes finalized with current milestone summary.

### Polish
- Runner service migrated from deprecated `@app.on_event` to FastAPI lifespan
  handlers.
- Memory tooling migrated from `datetime.utcnow()` to timezone-aware UTC
  helpers.
- Repo hygiene: scratch files removed, `.gitignore` tightened.

Full details: `docs/RELEASE_NOTES.md`.

---

## 1.0.15-memory-v1-and-interoperability (2026-03-09)

### OpenClaw Autonomous Ops Programs and Docs
- Added new autonomous ops programs (OpenClaw-created): `memory_prune`, `meta_monitor`, `session_continuity`, `token_budget_tracker`, and `monitor_system` (reference shape). Demo and `examples/autonomous_ops/` copies added; existing monitors (canary_sampler, infrastructure_watchdog, lead_quality_audit, tiktok_sla_monitor, token_cost_tracker) updated.
- New docs: `docs/operations/AUTONOMOUS_OPS_MONITORS.md` (monitor index and schedules), `docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md`. OpenClaw implementation notes: `openclaw/MEMORY_PRUNE_IMPLEMENTATION.md`, `openclaw/META_MONITOR_IMPLEMENTATION.md`, `openclaw/SESSION_CONTINUITY_IMPLEMENTATION.md`, `openclaw/TOKEN_BUDGET_TRACKER_IMPLEMENTATION.md`, plus update docs for existing monitors.
- Updated `docs/DOCS_INDEX.md` (links to autonomous ops monitors and standardized health envelope), `docs/EXAMPLE_SUPPORT_MATRIX.md` and `examples/autonomous_ops/README.md` (new programs table), `tooling/artifact_profiles.json` (new example paths). Config externalization and related OpenClaw notes in `openclaw/CONFIG_EXTERNALIZATION.md`, `openclaw/CANARY_SAMPLER_UPDATE.md`, etc.

### Extension-Level Memory Adapter and Contract (v1)
- Added an extension-level `memory` adapter backed by SQLite with explicit record
  identity `(namespace, record_kind, record_id)` and three core verbs:
  - `memory.put(namespace, record_kind, record_id, payload, ttl_seconds?)`
  - `memory.get(namespace, record_kind, record_id)`
  - `memory.append(namespace, record_kind, record_id, entry, ttl_seconds?)`
- Documented the v1 contract in `docs/adapters/MEMORY_CONTRACT.md`, including:
  - namespace whitelist and recommended record kinds,
  - advisory TTL semantics,
  - validation expectations and backend schema.
- Marked the adapter as `extension_openclaw` / non-canonical in
  `tooling/adapter_manifest.json` and `docs/reference/ADAPTER_REGISTRY.md`.

### Memory Validator/Linter and JSON Bridges
- Added an extension-only validator/linter for memory envelopes:
  - `tooling/memory_validator.py`
  - `scripts/validate_memory_records.py`
- Implemented JSON/JSONL export/import tooling on top of the SQLite store:
  - `tooling/memory_bridge.py`
  - `scripts/export_memory_records.py`
  - `scripts/import_memory_records.py`
- These tools:
  - treat the `memory_records` table as source of truth,
  - export canonical envelopes including `provenance` and `flags`,
  - import validated envelopes back into the store while preserving provenance
    and flags inside `payload._provenance` / `payload._flags`.

### Markdown Bridges and Legacy Migration
- Added a one-way, human-facing markdown export for daily logs:
  - `tooling/memory_markdown_bridge.py`
  - `scripts/export_memory_daily_log_markdown.py`
  - maps `daily_log.note` records to `memory/daily_log/YYYY/YYYY-MM-DD.md`.
- Added curated, frontmatter-based markdown import for long-term kinds:
  - `tooling/memory_markdown_import.py`
  - `scripts/import_memory_markdown.py`
  - supports `long_term.project_fact` and `long_term.user_preference` only.
- Added a narrow legacy migration helper to bootstrap from existing note habits:
  - `tooling/memory_migrate.py`
  - `scripts/migrate_memory_legacy.py`
  - migrates `MEMORY.md` sections to `long_term.project_fact` and
    `memory/YYYY-MM-DD.md` files to `daily_log.note`.

### Discovery/Enumeration: `memory.list`
- Extended the `memory` adapter with a fourth verb:
  - `memory.list(namespace, record_kind?, record_id_prefix?, updated_since?)`
- Provides structured enumeration of records without returning payloads:
  - filters by namespace (required), optional kind, optional record_id prefix,
    and optional `updated_since` (ISO timestamp on `updated_at`),
  - returns deterministic, lightweight summaries
    (`record_kind`, `record_id`, `created_at`, `updated_at`, `ttl_seconds`).
- Documented this as **discovery-only**, not a general query/search surface, and
  updated tests and docs to keep the adapter manifest, registry, and contract
  aligned.

### Lifecycle Cleanup: `memory.delete`
- Added an exact-key lifecycle verb:
  - `memory.delete(namespace, record_kind, record_id)`
- Provides explicit deletion for a single record identified by its canonical
  key, returning `{ok, deleted}` and leaving neighboring records untouched.
- Kept this strictly **non-bulk** and **non-query**: no predicates, no
  wildcard/batch deletion, and no TTL/prune semantics in this pass.

### TTL Pruning: `memory.prune`
- Added an operator-oriented TTL prune helper:
  - `memory.prune(namespace?)`
- Removes only records whose `ttl_seconds` is set and whose `created_at +
  ttl_seconds` lies strictly in the past, optionally scoped to a single
  namespace.
- Does **not** provide predicate-based/bulk deletion or broader retention
  policy logic; it is a small explicit cleanup tool on top of the existing
  TTL semantics.

## 1.0.14-advanced-coordination-governance (2026-03-09)

### Safe Use, Threat Model, and Advanced Framing
- Added `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` to describe:
  - what the local coordination substrate assumes (local-first, file-backed,
    sandboxed roots, external orchestrator),
  - what it does **not** provide (no built-in auth, encryption, policy, or
    multi-tenant isolation),
  - the threat model and trust assumptions for coordination usage,
  - and a clear split between **supported safe-default use** and
    **advanced/unsupported-by-default** patterns.
- Updated `README.md` and `docs/DOCS_INDEX.md` to clearly separate:
  - **core / safe-default** surfaces (compiler/runtime/IR, canonical examples),
  - **advanced / operator-only / experimental** surfaces (OpenClaw extensions,
    coordination docs, and examples).

### Coordination Validator and Mailbox Linter (extension-only)
- Added an extension-only coordination schema validator and mailbox linter:
  - `tooling/coordination_validator.py`
  - `scripts/validate_coordination_mailbox.py`
- The validator checks `AgentTaskRequest` and `AgentTaskResult` envelopes in
  JSON/JSONL files against the minimal upstream schema documented in
  `docs/advanced/AGENT_COORDINATION_CONTRACT.md` and reports malformed or drifted
  envelopes.
- This tooling is **optional**, **additive**, and **non-semantic**: it does not
  change compiler/runtime behavior and is intended as governance and
  compatibility support for advanced coordination users.

### Advanced Coordination Labeling and Release Checklist
- Tightened framing for advanced coordination/OpenClaw examples:
  - added "advanced / operator-only / advisory-only" notes to key examples under
    `examples/openclaw/`,
  - updated `docs/EXAMPLE_SUPPORT_MATRIX.md` to describe the OpenClaw family as
    advanced, extension-only, and not a safe default for unsupervised agents.
- Marked the `agent` adapter as **advanced, opt-in** in `docs/reference/ADAPTER_REGISTRY.md`
  and reiterated its extension-only, noncanonical status.
- Extended `docs/RELEASE_NOTES_DRAFT.md` with a short "Advanced coordination"
  section clarifying that:
  - coordination is experimental/operator-only,
  - coordination is local/file-backed and advisory,
  - upstream does **not** claim it is a secure multi-agent or orchestration
    platform by default.
- Updated `docs/GITHUB_RELEASE_CHECKLIST.md` with coordination-specific items:
  - protocol surface tests,
  - baseline verification,
  - mailbox validator run on baseline artifacts,
  - and a check that core vs advanced framing remains intact in
    `README.md` and `docs/DOCS_INDEX.md`.

## 1.0.13-coordination-baseline-and-monitor-advisory (2026-03-09)

### Coordination Baseline (docs-only)
- Added a human-visible coordination baseline section to
  `docs/advanced/AGENT_COORDINATION_CONTRACT.md`:
  - records the current baseline id:
    `coordination-baseline-2026-03-09-token-and-monitor-advisory`,
  - lists the required coordination artifacts (docs, examples, and sample
    result/snapshot JSON files) that both Cursor-side and OpenClaw-side
    environments should have on disk before controlled validation.
- Clarified usage guidance:
  - missing or renamed coordination artifacts should be treated as
    **repo-state drift**, not as a protocol change,
  - protocol-shaping artifacts should not be silently recreated without
    updating the documented baseline in a follow-up change.

### Monitor-Status Advisory Review Workflow
- Added extension/OpenClaw examples for a bounded monitor-status advisory loop
  built on top of the existing `agent` coordination substrate:
  - `examples/openclaw/monitor_status_advice_request.lang` — assembles a small
    snapshot of monitor IDs, services, statuses, and recent `last_ok` /
    `last_error` timestamps, wraps it in an `AgentTaskRequest`, and enqueues it
    via `agent.send_task` (returning the `task_id`).
  - `examples/openclaw/monitor_status_advice_read.lang` — reads a single
    advisory `AgentTaskResult` for a known monitor-status task id via
    `agent.read_result`.
- Added `examples/openclaw/monitor_status_example_snapshot.json` as a small,
  non-semantic JSON snapshot illustrating the payload shape used in the
  request example.
- Updated `docs/advanced/AGENT_COORDINATION_CONTRACT.md` and `docs/EXAMPLE_SUPPORT_MATRIX.md`
  to describe and classify the new monitor-status advisory workflow as
  extension/OpenClaw, noncanonical, local-first, file-backed, sandboxed, and
  advisory-only.

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
- Added `docs/advanced/AGENT_COORDINATION_CONTRACT.md` as the canonical design/spec for:
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
- Updated `docs/reference/ADAPTER_REGISTRY.md` and `docs/EXAMPLE_SUPPORT_MATRIX.md` to
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
  documented in `docs/reference/ADAPTER_REGISTRY.md`.
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
- Documented the helper and example usage in `docs/architecture/GRAPH_INTROSPECTION.md`
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
- Extended `docs/architecture/COMPILE_ONCE_RUN_MANY.md`, `README.md`, and `docs/DOCS_INDEX.md`
  with small notes on how to use the new run-summary helper.

## 1.0.9-autonomous-ops-and-http-envelopes (2026-03-09)

### Autonomous Ops Docs and Examples
- Added `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md` as the central, truthful playbook for
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
- Added `docs/architecture/GRAPH_INTROSPECTION.md` to document IR/graph emission, graph API
  helpers, normalization, and diffs.
- Added `scripts/inspect_ainl.py` as a tiny program-summary helper that prints
  `graph_semantic_checksum`, label/node counts, adapters, endpoints, and
  diagnostics without requiring users to read full IR JSON.
- Updated `README.md` and `docs/DOCS_INDEX.md` to link to the new graph
  introspection and inspect helper surfaces.

### Compile-Once / Run-Many Proof Pack
- Added `docs/architecture/COMPILE_ONCE_RUN_MANY.md` with a minimal, reproducible recipe to:
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
- Updated `docs/reference/ADAPTER_REGISTRY.md` to document the same envelopes and clearly
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
- Extended `docs/operations/AUTONOMOUS_OPS_PLAYBOOK.md` with a small, truthful snippet
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
  - `docs/architecture/ARCHITECTURE_OVERVIEW.md`
  - `docs/CONFORMANCE.md`
  - `docs/language/grammar.md`
  - `docs/RELEASE_READINESS.md`
  - `docs/AI_AGENT_CONTINUITY.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
- Added long-term docs governance contract: `docs/DOCS_MAINTENANCE.md`.
- Expanded schema/profile cross-linking for small and large agents:
  - `docs/reference/IR_SCHEMA.md`
  - `docs/reference/GRAPH_SCHEMA.md`
  - `docs/reference/AINL_V0_9_PROFILE.md`
  - `docs/PATTERNS.md`
  - `docs/reference/TOOL_API.md`
  - `docs/INSTALL.md`
  - `docs/language/AINL_CORE_AND_MODULES.md`
  - `docs/language/AINL_EXTENSIONS.md`
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
  - `docs/architecture/ARCHITECTURE_OVERVIEW.md`
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
  - `docs/architecture/ARCHITECTURE_OVERVIEW.md`
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
  - `docs/architecture/ARCHITECTURE_OVERVIEW.md`
  - `docs/CONTRIBUTING_AI_AGENTS.md`
  - `docs/reference/GLOSSARY.md`
  - `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md`
- Added OpenClaw integration guide: `docs/adapters/OPENCLAW_ADAPTERS.md`
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
