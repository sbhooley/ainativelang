# Active roadmap: adapter semantics, run path, and registration (Phase 2+)

This document is the **working checklist** for continuing the closed *Strict AINL Authoring* plan in three tracks:

1. **Adapter semantics** — syntax-valid graphs can still be wrong for real adapter/API contracts.  
2. **Validate → compile → run path** — make the **preferred proof chain** explicit in MCP, prompts, and optional evals.  
3. **Adapter registration vs source editing** — when the host is missing adapters, **configuration** is the default repair, not deleting behavior from source.

**Repos involved:** primarily `AI_Native_Lang` (MCP + compiler), `armaraos` (prompts, agent loop, digest), optionally `ainl-inference-server` (deterministic evals / guidance text).

**Progress (2026-04-25 / 2026-04-26, PR slice):** MCP `compile_ok` now inserts `ainl_capabilities` immediately after `ainl_run` when `required_adapters` is non-empty; `repair_recipe` for adapter/verb failures adds an explicit “do not strip adapter lines to get ok:true” step; new tests in `tests/test_mcp_server.py` cover validate→compile ordering, `http`/`fs` contracts, and FS `required_adapters` alignment. **`strict_valid_pointers`** on `ainl_adapter_contract` for **http** and **fs**. **Validate/compile/run** JSON responses include boolean **`strict`** and optional **`strict_mode_note`**. **`docs/adapters/CONTRACT_AND_COMPILER.md`**, `schema_version` on adapter contracts, and **`contract_alignment`** on successful validate/compile. **ArmaraOS** surfaces `contract_alignment` in system prompt via `mcp_ainl_contract_alignment_hint`; `ainl_mcp_soft_failure_message` and **loop guard** cover adapter-registration failures; **ainl-inference-server** planner chains validate→compile→run deterministically and evals enforce compile-before-run.

---

## Track 1 — Adapter semantics (contract layer)

**Outcome:** Agents can tell **“compiler ok”** apart from **“adapter/API shape ok”**, with discoverable contracts and tests on at least one vertical.

### 1.1 Schema and data sources

- [x] **Versioned `adapter_contract` + alignment:** `schema_version` on MCP/get_started payloads; validate/compile may emit `contract_alignment` — see `docs/adapters/CONTRACT_AND_COMPILER.md` and `tooling/ainl_get_started.py`.
- [x] **Document the contract** — `docs/adapters/CONTRACT_AND_COMPILER.md` (compiler vs contract, single source of truth).
- [ ] **Single source of truth rule (ongoing):** new verbs should land in the manifest/contract path used by `ainl_capabilities` / `strict_summary`, not only in free-form AGENTS text.

### 1.2 MCP: `ainl_adapter_contract` and `ainl://adapter-contracts`

- [x] **Audit (first vertical http + fs):** contracts are defined in `tooling/ainl_get_started.py` (`ADAPTER_CONTRACTS`); `ainl://adapter-contracts` bundle remains the JSON aggregate — no schema drift in this PR.
- [x] For **http** and **fs**: automated checks that contracts expose `verbs` (e.g. `GET`, `write`) and pitfalls (GET URL / param anti-patterns) — see `TestAdapterContractMcp` in `tests/test_mcp_server.py`.
- [x] For each of **http** and **fs**: `tooling/ainl_get_started.py` adds **`strict_valid_pointers`** to `adapter_contract` (http: `examples/http_get_minimal.ainl` when in `strict-valid` profile; fs: `path: null` + note — no `fs.*` graph is in the current CI `strict-valid` set).
- [x] **Validation path (lightweight):** validate/compile may append `warnings` and `contract_alignment` (http/fs audit; severity warning) from MCP; see `CONTRACT_AND_COMPILER.md` and `tests/test_mcp_server.py` (`TestContractAlignment`).
- [x] **Tests in `tests/test_mcp_server.py`:** `TestAdapterContractMcp` + existing capabilities / strict_summary tests; full **negative** arity test still optional.

### 1.3 ArmaraOS / prompts

- [x] **Session contract-alignment text:** `format_contract_alignment_note` + `on_mcp_ainl_tool_result` + `mcp_ainl_contract_alignment_hint` in `build_ainl_mcp_tools_section` (capabilities digest still surfaces `strict_summary`; graph persistence for contract rows TBD).
- [x] **prompt_builder:** already states compiler vs runnable and points at `mcp_resources` / `ainl://adapter-contracts` (no change required in this slice).

**Acceptance (Track 1):** For **http** + **fs**, an agent (or test harness) can follow **contract + strict example** to author a call shape that matches runtime; a deliberately wrong return-field assumption is **caught** by tests or a clear compiler/MCP message — not a silent success story.

---

## Track 2 — Validate → compile → run (proof chain)

**Outcome:** The product consistently **prefers** strict validate, then compile (IR / `frame_hints`), then run with adapters — in **defaults**, **recommended_next_tools**, and **prompt copy**, not only in prose docs.

### 2.1 MCP response contract

- [x] **Validate success:** `recommended_next_tools[0] == "ainl_compile"` — `test_validate_ok_recommends_compile_first`.
- [x] **Compile success:** `recommended_next_tools[0] == "ainl_run"`, and when IR needs adapters, **`ainl_capabilities` is second** to support building `adapters=` — `test_compile_ok_inserts_ainl_capabilities_after_run_when_adapters_required`. `required_adapters` / `runtime_readiness` + `compiler_vs_runtime_note` remain on both validate and compile success paths.
- [x] **Non-strict / `strict:false`:** validate, compile, and all **`ainl_run`** returns add **`strict`** and, when `strict=false`, **`strict_mode_note`**. ArmaraOS mirrors if needed.

### 2.2 ArmaraOS agent loop and prompts

- [x] **prompt_builder** / granted workflow: golden path already documents **get_started → validate → compile → run** and `adapters=` / `frame_hints` in `prompt_builder.rs` (verify when editing).
- [ ] **Optional state:** if not already present, a **session-scoped** note of “last successful strict validate hash for this `code`” to align with `ainl_run` gate logic (see `ainl_run_requires_strict_validate_first` in `agent_loop.rs`) — only extend if it reduces spurious runs without piling state complexity.

### 2.3 Deterministic evals (optional repo)

- [x] **MCP-level** coverage for order expectations (faster than full infer eval) — `test_validate_ok_recommends_compile_first`, `test_compile_ok_inserts_ainl_capabilities_after_run_when_adapters_required`, `test_validate_and_compile_align_fs_required_adapters`.
- [x] In **`ainl-inference-server`:** `ainl_planner` deterministic `Run` / `WriteHello` / `build_open_ended_write_plan` chains are **read → validate → compile → run**; `ainl_tool_eval` asserts `compile` precedes `mcp_ainl_ainl_run` and updates expected tool lists + cache-hit expectations.

**Acceptance (Track 2):** A fresh trace through MCP for a file-backed workflow shows **validate → compile → run** in `recommended_next_tools` and in ArmaraOS digest text; non-strict runs are **labeled** in outputs.

---

## Track 3 — Adapter registration (config-first repair)

**Outcome:** `adapter not registered` / `runtime_readiness` gaps drive **adapters config + retry**, not **stripping** `fs`/`http`/etc. from the program. Validate/compile success does **not** imply run readiness.

### 3.1 MCP payloads

- [x] **On `ainl_run` failure:** existing tests `test_run_missing_adapter_returns_retry_payload` and `test_run_preflight_fails_before_engine_when_http_and_fs_unregistered` (keep as regression).
- [x] **On validate/compile success:** `test_validate_and_compile_align_fs_required_adapters` + existing `test_compile_reports_required_adapters`; multi-adapter ordering covered indirectly via `HTTP_FS_CODE` in compile tools test.
- [x] **Repair recipe (validate, adapter/verb failures):** explicit step to **not** strip adapter lines to get `ok: true` — `test_validate_unknown_verb_repair_recipe_discourages_stripping_adapters`. (`adapter_registration` run failures already had `next_step` / `suggested_adapters` — unchanged.)

### 3.2 ArmaraOS: prompts and `agent_loop`

- [x] **Adapter-registration supplement** in `mcp_ainl_session::ainl_mcp_soft_failure_message` (run: `error_kind: adapter_registration`, `adapter not registered` in `error`, next-step + tests).
- [x] **Loop guard:** `mcp_ainl_adapter_registration_outcome_escalates_faster` — adapter-registration `ainl_run` results use stricter (non-relaxed) `record_outcome` thresholds.

### 3.3 Regression tests (minimum)

- [x] **MCP / Python:** `test_run_missing_adapter_returns_retry_payload` and related — optional second run with `adapters` not added here (low priority; host-dependent).
- [x] **ArmaraOS (optional):** B1c/B1d style tests for mock-vs-real pending already exist in `openfang_runtime` (prior work); not duplicated in this slice.

**Acceptance (Track 3):** Docs + tests + MCP JSON agree: **“valid AINL” ≠ “runnable in this host”**; the default next step is **pass adapters**, not **delete behavior**.

---

## How to work this list

- **Order:** 3.1–3.3 often unblock user pain fastest; 2.1–2.2 improve funnel coherence; 1.x is the largest design surface — still start 1.2 with **http** + **fs** only.  
- **DoD per PR:** each PR should tick a **small** set of checkboxes, add **tests**, and update **one** user-facing doc line if behavior changes.  
- **When done:** mark sections complete in this file, or open GitHub issues and link them here; avoid reviving the old 100+ row micro-checklist in Cursor plan YAML.

**Owner suggestion:** `AI_Native_Lang` PRs for MCP/compiler tests; `armaraos` PRs for prompt/digest/loop; cross-repo changes should merge **MCP contract first** when possible so ArmaraOS can assume stable fields.
