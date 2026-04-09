# Release notes

## AINL v1.4.6 — Samples + OpenSpace harness (2026-04-11)

**PyPI / runtime:** **`ainativelang` 1.4.6** — **`RUNTIME_VERSION` `1.4.6`**.

- **Samples:** **`apollo-x-bot/api-cost-monitor.ainl`**, **`demo/test_openspace_http.ainl`**, and root **`run_openspace_test.py`** (portable paths) for OpenSpace / promoter experiments.
- See **`docs/CHANGELOG.md`** § v1.4.6.

## AINL v1.4.5 — ArmaraOS MCP env merge + MCP authoring + compiler diagnostics (2026-04-10)

**PyPI / runtime:** **`ainativelang` 1.4.5** — **`RUNTIME_VERSION` `1.4.5`**.

- **ArmaraOS / install-mcp:** re-running **`ainl install-mcp --host armaraos`** merges **`env`** forward lists into **existing** `ainl` MCP server blocks (idempotent union); no manual **`config.toml`** edits for new env knobs.
- **MCP server:** **`ainl://authoring-cheatsheet`** resource; validate telemetry; incremental hardening for agent-facing validate/compile flows.
- **Compiler:** structured **`contract_violation_reason`** on include diagnostics; stricter graph validation reporting; strict-mode exemption when a label’s last step is an inner **`Loop`** / **`While`**.
- See **`docs/CHANGELOG.md`** § v1.4.5 for the full conventional-commit list.

## AINL v1.4.4 — Packaging + Solana emitter alignment (2026-04-09)

**PyPI / runtime:** **`ainativelang` 1.4.4** — **`RUNTIME_VERSION` `1.4.4`**.

- **Packaging:** version surfaces aligned (PyPI, `RUNTIME_VERSION`, citation metadata, bot bootstrap JSON).
- **Emit:** `emit_solana_client` header uses live **`RUNTIME_VERSION`** so emitted Solana clients stay in sync with the runtime.

## AINL v1.4.3 — MCP per-run adapter configuration (2026-04-08)

**PyPI / runtime:** **`ainativelang` 1.4.3** — **`RUNTIME_VERSION` `1.4.3`**.

- **MCP:** `ainl_run` now accepts an optional `adapters` argument to enable **scoped** runtime adapters per call (e.g. `http` with host allowlist, sandboxed `fs`, file-backed `cache`, optional `sqlite`). This allows agent workflows to do necessary I/O without requiring end users to edit global config.
- **Docs:** capability grant model docs aligned with current runner/MCP defaults.

## AINL v1.4.2 — Intelligence policy, MCP/runner alignment, compiler + tooling (2026-04-07)

**PyPI / runtime:** **`ainativelang` 1.4.2** — **`RUNTIME_VERSION` `1.4.2`**.

- **Runtime / ops:** **`AINL_ALLOW_IR_DECLARED_ADAPTERS`**; intelligence **`intelligence/`** paths opt in when unset; **`ainl run`** registers **`web`**, **`tiktok`**, **`queue`**; MCP and HTTP runner grant alignment; see **`docs/CHANGELOG.md`** § v1.4.2.
- **Compiler / tooling:** strict-mode fixes for **`J`** label jumps; expanded adapter effect coverage and **`tooling/adapter_manifest.json`**; intelligence graphs + **`demo/.ainl-library-skip`** for App Store filtering.

## AINL v1.4.1 — Wishlist smoke + offline LLM provider (2026-04-03)

**PyPI / runtime:** **`ainativelang` 1.4.1** — **`RUNTIME_VERSION` `1.4.1`**.

- **Offline LLM provider** (`offline`): use in **`config.yaml`** `llm.fallback_chain` for deterministic **`R llm.COMPLETION`** without API keys (see **`examples/wishlist/fixtures/llm_offline.yaml`** and **`05b_unified_llm_offline_config.ainl`**).
- **Core:** **`R core.GET`** is implemented on **`CoreBuiltinAdapter`** (structured field reads).
- **CI:** strict wishlist validation + smoke runs for graphs **01** and **05b** in **`parser-compat`**.

## AINL v1.4.0 — ArmaraOS host pack + release readiness (2026-04-01)

**PyPI / runtime:** **`ainativelang` 1.4.0** — **`RUNTIME_VERSION` `1.4.0`**.

- **ArmaraOS integration (host pack):** ArmaraOS support is first-class and optional (no hard dependency on the `armaraos` binary). Docs: `docs/ARMARAOS_INTEGRATION.md` and `docs/getting_started/HOST_MCP_INTEGRATIONS.md`.
- **MCP bootstrap:** `ainl install-mcp --host armaraos` now supports ArmaraOS’ `~/.armaraos/config.toml` format (`[[mcp_servers]]`).
- **Emit to hand package:** `ainl emit --target armaraos` produces `HAND.toml`, `<stem>.ainl.json`, `security.json`, and a README.
- **Release hardening:** fixed ArmaraOS emitter wiring and integration tests; unified ArmaraOS env var aliases (`ARMARAOS_*` canonical, `OPENFANG_*` legacy-compatible).

## AINL v1.3.3 — PyYAML for MCP server imports (2026-03-29)

**PyPI / runtime:** **`ainl` 1.3.3** — **`RUNTIME_VERSION` `1.3.3`**; **`PyYAML`** is a **core dependency** so **`ainl-mcp`** imports succeed on clean **`pip install ainativelang[mcp]`** (CI **wheel-integrity**). See **`docs/CHANGELOG.md`** § v1.3.3.

## AINL v1.3.2 — Core httpx/requests dependencies (2026-03-29)

**PyPI / runtime:** **`ainl` 1.3.2** — **`RUNTIME_VERSION` `1.3.2`**; **`httpx`** and **`requests`** are now **core dependencies** so wheel installs and **`ainl`** entrypoint imports succeed after **`pip install ainativelang[mcp]`** (fixes **`ModuleNotFoundError: requests`** from **`adapters.llm.ollama`** during CI smoke). See **`docs/CHANGELOG.md`** § v1.3.2.

## AINL v1.3.1 — Solana strict graphs + lexer/runtime polish (2026-03-29)

**PyPI / runtime:** **`ainl` 1.3.1** — **`RUNTIME_VERSION` `1.3.1`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); language server **`serverInfo.version`** and runner **OpenAPI** **`app.version`** follow **`RUNTIME_VERSION`**; **`CITATION.cff`** aligned. See `docs/CHANGELOG.md` v1.3.0 + v1.3.1 for full details (Hermes/OpenClaw + Solana/lexer updates).

- **Solana strict graphs:** `examples/solana_demo.ainl` and `examples/prediction_market_demo.ainl` are now first-class **strict-valid** examples and appear in `tooling/artifact_profiles.json`, `tooling/canonical_curriculum.json`, and the canonical training packs.
- **Prediction markets:** `adapters/solana.py` supports DERIVE_PDA with **single-quoted JSON** seeds (e.g. `'["market","ID"]'`), strict GET_PYTH_PRICE (legacy + PriceUpdateV2), HERMES_FALLBACK, and dry-run envelopes for INVOKE / TRANSFER / TRANSFER_SPL under `AINL_DRY_RUN=1`.
- **Lexer alignment:** `tokenize_line_lossless` and the legacy `tokenize_line` agree on decoded **bare/string** token values, including single-quoted strings; compile always uses the lossless tokenizer.
- **Discoverability:** `docs/solana_quickstart.md`, Solana onboarding cross-links in `docs/emitters/README.md` and `examples/README.md`, README callouts, and root `CONTRIBUTING.md` (release version + Solana pointers) so agents and operators find the Solana onboarding path quickly.

## AINL v1.3.0 — Hermes Agent + OpenClaw integration improvements (2026-03-27)

**PyPI / runtime:** **`ainl` 1.3.0** — **`RUNTIME_VERSION` `1.3.0`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); language server **`serverInfo.version`** and runner **OpenAPI** **`app.version`** follow **`RUNTIME_VERSION`**; **`CITATION.cff`** aligned.

### Hermes Agent (official host)

- **`ainl install-mcp --host hermes`** / **`ainl hermes-install`** writes **`~/.hermes/config.yaml`** **`mcp_servers.ainl`**, installs **`~/.hermes/bin/ainl-run`**, and prints a PATH hint.
- **Skill pack:** **`skills/hermes/`** — installer plus bridge helpers for ingest/export loops.
- **Emitter:** **`ainl compile --emit hermes-skill`** (and **`--target hermes`**) produces a drop-in Hermes skill bundle (**`SKILL.md`**, **`workflow.ainl`**, **`ir.json`**) for deterministic runs via MCP **`ainl_run`**.
- **`ainl doctor`** recognizes Hermes YAML (**`~/.hermes/config.yaml`** **`mcp_servers:`**) and validates **`ainl`** MCP registration without a YAML parser dependency.
- **Docs:** **`docs/integrations/hermes-agent.md`**, **`docs/HERMES_INTEGRATION.md`**; README / docs hub cross-link **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**.

### OpenClaw integration improvements (Top 5)

- **`ainl install openclaw --workspace PATH`** — one-command setup with a health table, **`--dry-run`** preview, and idempotent gold-standard cron registration.
- **`ainl status`** — unified view of workspace, weekly budget, cron health, drift, and 7-day token usage; weekly budget uses **`_read_weekly_remaining_rollup`** (legacy **`weekly_remaining_v1`** table when non-null, else **`memory_records`** aggregate).
- **Self-healing bootstrap** and **`ainl doctor --ainl`** for OpenClaw + AINL integration validation.
- **Clearer errors** with actionable fix suggestions.
- **Docs:** progressive disclosure — **`docs/QUICKSTART_OPENCLAW.md`** first, full depth in **`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`** and related ops guides.
- **Fix:** weekly budget in **`ainl status`** reads modern **`memory_records`** primary storage correctly (legacy table still bootstrapped for compatibility).

See **`docs/CHANGELOG.md`** § **v1.3.0** for the same items in conventional-commit form.

### Optional adapter: tiered code context (`code_context`)

- **Adapter:** **`adapters/code_context.py`** — index a local tree to JSON; TF–IDF tiered chunks (`INDEX`, `QUERY_CONTEXT`, `GET_FULL_SOURCE`, **`STATS`**); import graph **`GET_DEPENDENCIES`**, impact + PageRank **`GET_IMPACT`**, TF–IDF greedy packing **`COMPRESS_CONTEXT`**. Enable on **`ainl run`**: **`--enable-adapter code_context`** (host MCP bootstrap does **not** turn this on). Env: **`AINL_CODE_CONTEXT_STORE`**.
- **Docs / demo:** **`docs/adapters/CODE_CONTEXT.md`**, **`examples/code_context_demo.ainl`**, catalog **`docs/reference/ADAPTER_REGISTRY.md`** §9. Tiered design: [BradyD2003/ctxzip](https://github.com/BradyD2003/ctxzip), Brady Drexler. Graph/impact/packing ideas: [chrismicah/forgeindex](https://github.com/chrismicah/forgeindex), Chris Micah.

## AINL v1.2.10 — PyPI visualize packaging fix (2026-03-27)

**PyPI / runtime:** **`ainl` 1.2.10** — **`RUNTIME_VERSION` `1.2.10`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); language server **`serverInfo.version`** and runner **OpenAPI** **`app.version`** follow **`RUNTIME_VERSION`**; **`CITATION.cff`** aligned.

- **Wheel/PyPI fix for `ainl visualize`:** setuptools package discovery now explicitly includes **`intelligence`** and **`intelligence.*`**, and the package now ships **`intelligence/__init__.py`**.
- **User-visible impact:** clean installs via **`pip install ainativelang`** now support the documented quickstart end-to-end, including **`ainl visualize main.ainl --output graph.mmd`**.
- **Docs/release sync:** release metadata and release-facing docs are aligned to **v1.2.10** so install docs, changelog, and website release indicators match shipped behavior.

## AINL v1.2.8 — OpenClaw intelligence ops + graph-runtime alignment (2026-03-25)

**PyPI / runtime:** **`ainl` 1.2.8** — **`RUNTIME_VERSION` `1.2.8`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); language server **`serverInfo.version`** and runner **OpenAPI** **`app.version`** follow **`RUNTIME_VERSION`**; **`CITATION.cff`** aligned. After pulling, reinstall the package (**`pip install -U -e .`**) or recreate the venv if you see stale **`runtime_version`** or import shadowing from **`__pycache__`**.

- Rolling budget → monitor cache hydration for **`scripts/run_intelligence.py`**; workspace path pin script; expanded **`docs/operations/`** (profiles, token usage, workspace isolation, host pack).
- **OpenClaw + AINL gold standard:** **`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`** — install/upgrade checklist (profiles, caps, cron, bootstrap, verification); **`tooling/bot_bootstrap.json`** → **`openclaw_ainl_gold_standard`**.
- **OpenClaw host briefing (v1.2.8):** **`docs/operations/OPENCLAW_HOST_AINL_1_2_8.md`** — what the repo ships vs what the host must wire; **`openclaw_host_ainl_1_2_8`**.
- Graph-safe patterns for intelligence programs and **`generic_memory`**: avoid **`X {…}`** object literals; use **`null`** for omitted **`memory.list`** prefix; RFC3339 **`valid_at`**; documented in **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/AINL_SPEC.md`**, **`docs/adapters/MEMORY_CONTRACT.md`**.
- **Whitepaper + primer sync:** **`WHITEPAPERDRAFT.md`** updated for v1.2.8 (OpenClaw positioning, §6.6 graph pitfalls, §10.5 intelligence runner, §13.5 token caps, appendix file map); **`docs/WHAT_IS_AINL.md`**, **`docs/DOCS_INDEX.md`**, **`docs/overview/README.md`**, **`docs/POST_RELEASE_ROADMAP.md`**.

## AINL v1.2.7 — Hyperagent Research Pack (additive) (2026-03-24)

- Added `ainl inspect <file.ainl> [--strict] [--json]` to dump full canonical IR JSON.
- Added `ainl run --trace-jsonl PATH|-` for structured JSONL execution tape output (file or stdout).
- Structured diagnostics now expose `llm_repair_hint` for LLM-native repair loops.
- MCP added `ainl_fitness_report` and `ainl_ir_diff` tools for selection/mutation loops.
- `ainl_fitness_report` now includes `fitness_score` with transparent `fitness_components`/`weights`, plus adapter/operation/frame-key proxy metrics.
- `ainl_ir_diff` now detects payload-level node data deltas (not only topology rewires/add/remove).
- Added machine-readable schema seed `ainl.schema.json`.
- Added research docs/prompts: `docs/EMBEDDING_RESEARCH_LOOPS.md`, `docs/operations/MCP_RESEARCH_CONTRACT.md`, `prompts/meta-agent/*`.

## AINL v1.2.6 — install hardening + wheel/release gates + doctor diagnostics (2026-03-24)

**PyPI / runtime:** **`ainl` 1.2.6** — **`RUNTIME_VERSION` `1.2.6`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**).

- **Wheel packaging fix:** setuptools package discovery now includes `runtime` and `runtime.*` so wheel installs ship `runtime.compat` and avoid wheel-only import failures.
- **Sandbox/no-root install hardening:** `skills/ainl/install.sh` now uses safe pip fallback modes for restricted hosts (venv/default, then `--user`, then `--break-system-packages`), avoids `eval`, and applies idempotent PATH hints across common shell rc files.
- **CI hardening:** new install smoke matrix (Linux + macOS, Python 3.10–3.13) validates default install, `--user`, and `--break-system-packages`, then runs `ainl --help`, `ainl-mcp --help`, and `python -m pip check`.
- **Container smoke coverage:** CI now runs non-root install smoke inside `python:3.10/3.11/3.12/3.13-slim` containers to better match hosted Docker environments.
- **Wheel integrity gate:** CI now builds wheel, installs wheel (non-editable), and verifies `import runtime.compat, adapters, cli.main`.
- **Release automation:** new `Release Gates` workflow enforces wheel import smoke + `pip check` + `ainl install-mcp --host openclaw|zeroclaw --dry-run`.
- **Runtime diagnostics:** new `ainl doctor` command verifies Python/import/PATH/MCP health in one command and reports actionable warnings/failures.
- **Python 3.13 constraints:** add `constraints/py313-mcp.txt` as tested MCP stack pins for sandbox hosts, with a monthly `Constraints Health` workflow to catch dependency drift.
- **Sandbox/AVM metadata (additive):** compiler now emits optional `execution_requirements` plus `avm_policy_fragment` in IR for policy/config handoff without changing runtime semantics.
- **Unified sandbox shim (optional):** runner, MCP, and CLI `ainl run` now use `runtime/sandbox_shim.py` (`SandboxClient.try_connect`) for AVM/general sandbox detection with one-line graceful fallback.
- **New CLI helper:** `ainl generate-sandbox-config <file.ainl> [--target avm|firecracker|gvisor|k8s|general]` outputs ready-to-merge AVM/general sandbox config fragments.
- **Trajectory enrichment (optional):** per-step JSONL can include `avm_event_hash`, `sandbox_session_id`, `sandbox_provider`, and `isolation_hash` when a sandbox runtime is connected (no-op otherwise).

## AINL v1.2.5 — Hyperspace + hybrid interop + CI baselines (2026-03-23)

**PyPI / runtime:** **`ainl` 1.2.5** — **`RUNTIME_VERSION` `1.2.5`** in **`runtime/engine.py`** (mirrored **`tests/emits/server/runtime/engine.py`**); language server **`serverInfo.version`** and runner **OpenAPI** **`app.version`** follow **`RUNTIME_VERSION`**; **`CITATION.cff`** **`version` / `date-released`** aligned. Oversight / schema fixtures (e.g. **`tests/test_oversight.py`**, **`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`** samples) use **`1.2.5`**.

### Trajectory, modules, local adapters, Hyperspace emit

- **Runtime:** optional per-step **trajectory JSONL** (`--log-trajectory` / **`AINL_LOG_TRAJECTORY`**) — **`docs/trajectory.md`**, **`docs/RUNTIME_COMPILER_CONTRACT.md`**
- **Modules:** **`modules/common/guard.ainl`**, **`session_budget.ainl`**, **`reflect.ainl`** (ceilings, budget, reflect gates); **`modules/common/README.md`**
- **Adapters:** **`vector_memory`**, **`tool_registry`** (local JSON stores); CLI **`--enable-adapter`**; **`docs/reference/ADAPTER_REGISTRY.md`**, **`docs/adapters/README.md`**

#### Hyperspace agent emitter (`--emit hyperspace`)

- **CLI:** **`python3 scripts/validate_ainl.py <file.ainl> --strict --emit hyperspace -o <agent.py>`** (same flag on **`ainl-validate`**). **`docs/emitters/README.md`**, root **`README.md`** happy path.
- **Implementation:** **`compiler_v2.AICodeCompiler.emit_hyperspace_agent`** generates a **single-file Python module** that:
  - Embeds the compiled IR as **base64-encoded JSON** (`_IR_B64`) so the artifact is self-contained.
  - Walks up from the script / cwd to find a checkout with **`runtime/engine.py`** and **`adapters/`**, then prepends that **repo root** to **`sys.path`** (run from repo root is still the supported default).
  - Builds an **`AdapterRegistry`** allowing **`core`**, **`vector_memory`**, and **`tool_registry`**, registers the local **`VectorMemoryAdapter`** / **`ToolRegistryAdapter`**, and constructs **`RuntimeEngine`** in **`graph-preferred`** mode with **`step_fallback=True`**.
  - Exposes **`run_ainl(label=None, frame=None)`** (default label from **`default_entry_label()`**) and a **`__main__`** that logs and prints the result.
  - Honors **`AINL_LOG_TRAJECTORY`** (`1` / `true` / `yes` / `on`) → **`<source-stem>.trajectory.jsonl`** in the current working directory (stem derived from **`-o`** / source path).
- **Optional SDK hook:** tries **`import hyperspace_sdk`**; if missing, emits a **`RuntimeWarning`** and runs **AINL-only** (scaffold **`TODO`** for future Agent/Session bridge). When the SDK is present, **`__main__`** logs that the native bridge is not wired yet and still executes the graph directly.
- **Examples / teaching:** **`examples/hyperspace_demo.ainl`** (guard + session_budget + dotted **`vector_memory`** / **`tool_registry`** verbs); **`examples/test_adapters_full.ainl`** for adapter consolidation; both are **strict-valid** and appear in **`tooling/canonical_curriculum.json`** / rebuilt **`tooling/canonical_training_pack.json`** and **`tooling/training_packs/`** exports.
- **Tests:** emitter snapshots in **`tests/test_snapshot_emitters.py`** (where applicable).

- **Docs / ops:** hub updates (**`docs/README.md`**, **`docs/DOCS_INDEX.md`**, **`docs/runtime/README.md`**, **`docs/examples/README.md`**); **`docs/language/AINL_CORE_AND_MODULES.md`** §8; intelligence / briefing examples; **`docs/WHAT_IS_AINL.md`** as canonical primer (**`WHAT_IS_AINL.md`** stub); **`WHITEPAPERDRAFT.md`** (trajectory / Hyperspace)

### LangGraph / Temporal hybrid

- **`langchain_tool`** adapter (tools bridge) — **`adapters/langchain_tool.py`**, **`examples/hybrid/langchain_tool_demo.ainl`**, tests
- **Wrappers:** **`runtime/wrappers/langgraph_wrapper.py`** (`run_ainl_graph`), **`temporal_wrapper.py`** (`execute_ainl_activity`); **`scripts/emit_langgraph.py`**, **`scripts/emit_temporal.py`**; **`validate_ainl.py --emit langgraph|temporal`**
- **`S hybrid langgraph` / `temporal`:** DSL opt-in for **`minimal_emit`** / planners; IR **`services.hybrid.emit`**; spec **`docs/AINL_SPEC.md`** §2.3.1, **`docs/language/grammar.md`**, **`docs/HYBRID_GUIDE.md`**, **`examples/hybrid/`**, **`docs/hybrid/OPERATOR_RUNBOOK.md`**, **`docs/PACKAGING_AND_INTEROP.md`**, **`docs/RELEASING.md`**
- **LangGraph emit fix:** **`AinlHybridState`** uses plain **`dict`** fields for **Python 3.10** + **langgraph** **`get_type_hints`**
- **Tests:** **`StateGraph.invoke`** e2e (optional **langgraph**); Temporal **`ActivityEnvironment`** e2e (optional **temporalio**); **`WorkflowEnvironment.execute_workflow`** e2e with a **`Worker`** and sync activities (**`tests/test_hybrid_emit_integration.py`**); **`S hybrid`** + emission-planner coverage

### Strict compiler and conformance (label dataflow)

- **Strict dataflow:** inter-label edges (**If** / **Loop** / **While** / **Call** → target labels) now merge **live variable** sets at label entry ( **`tooling/effect_analysis.py`**: forward fixpoint + **`propagate_inter_label_entry_defs`**; **`compiler_v2._validate_graphs`** seeds HTTP endpoint entry defs). Reduces false **undefined at use** reports when a variable is defined on all paths into a jumped-to label (e.g. monitor **`J metrics`** on the “ok” branch).
- **Tests / artifacts:** **`tests/test_inter_label_dataflow.py`**; **`tooling/artifact_profiles.json`** and **`tooling/canonical_curriculum.json`** updated for newly strict-clean examples (**`examples/cron/monitor_and_alert.ainl`**, **`corpus/example_monitor_alert/program.ainl`**, etc.); conformance snapshots refreshed under **`tests/snapshots/conformance/`**.

### CI, benchmarks, Makefile

- **`benchmark-regression`:** prefers **`tooling/benchmark_size_ci.json`** / **`tooling/benchmark_runtime_ci.json`** on the baseline SHA when committed; else full **`benchmark_size.json`** / **`benchmark_runtime_results.json`**; **Python 3.10** on listed jobs
- **`make benchmark` / `make benchmark-ci`:** echo resolved **`PYTHON`** (prefer **`.venv-py310`** per **`Makefile`**)
- **`BENCHMARK.md`**, **`docs/benchmarks.md`:** document CI baseline preference

### Competitive & comparisons (positioning + evidence)

- **`docs/competitive/`** — onboarding (**`FROM_LANGGRAPH_TO_AINL.md`**, **`AINL_AND_TEMPORAL.md`**), benchmark methodology (**`VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`**), comparison tables (**`COMPARISON_TABLE.md`** — committed figures + **TBD** rows), and OpenClaw savings worksheet (**`OPENCLAW_PRODUCTION_SAVINGS.md`**). Public hub: **`OVERVIEW.md`** (on **[ainativelang.com](https://ainativelang.com)** as **`/docs/competitive/OVERVIEW`** after the web repo runs **`npm run sync-content`** and a production deploy). **Live comparison tables:** **[ainativelang.com/docs/competitive/COMPARISON_TABLE](https://ainativelang.com/docs/competitive/COMPARISON_TABLE)**.

See **`docs/CHANGELOG.md`** § **v1.2.5** for the same items in changelog form.

---

## AINL v1.2.4 — Access-aware memory helpers, graph label resolution, docs (2026-03-21)

Follow-up to v1.2.3 focused on **opt-in access metadata** on top of Memory Contract v1.1, **runtime correctness for included subgraphs** in graph mode, and **documentation** so hosts can choose graph-safe list paths.

- **`modules/common/access_aware_memory.ainl`:** optional **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, and graph-safe **`LACCESS_LIST_SAFE`** (While + index loop; no `ForEach` in IR). Header documents graph-preferred limitations for `LACCESS_LIST` (ForEach not lowered to `Loop` today) and points callers at **`LACCESS_LIST_SAFE`** for full per-item touches. Uses **`Call`** chains and **`X … put …`** for metadata patches where needed for reliable execution.
- **Runtime (`runtime/engine.py`):** **`_resolve_label_key`** qualifies bare branch / loop / call targets (e.g. `_child`) against the current **`alias/…`** stack frame so graph (and step) execution reaches merged **`alias/child`** labels after `include`. Preserves behavior for programs that already use fully qualified ids.
- **Demos:** `demo/session_budget_enforcer.lang` and `demo/memory_distill_example.lang` keep **`include` lines before the first top-level `S` / `E`** so module labels merge; access-aware usage remains documented in-module.
- **Tests:** `tests/test_demo_enforcer.py` — compile + memory adapter checks; regression for bare child label resolution in graph-only mode.
- **Packaging / version surfaces:** **`pyproject.toml` / PyPI `ainl` 1.2.4**; **`RUNTIME_VERSION` 1.2.4** in `runtime/engine.py` (mirrored under `tests/emits/server/runtime/engine.py`) for run payloads, MCP, and **`/capabilities`**; language server **`serverInfo.version`** (`langserver.py`) and HTTP runner **OpenAPI** `app.version` (`scripts/runtime_runner_service.py`) use the same **`RUNTIME_VERSION`** string; **`CITATION.cff`** sets software **`version`** / **`date-released`** to match.
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
