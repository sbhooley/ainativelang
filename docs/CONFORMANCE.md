# AI Native Lang (AINL) 1.0 implementation conformance

This checklist confirms alignment of this workspace with **AINL_SPEC.md (AINL 1.0)**. AINL 1.0 is the normative spec (graph-first, core+modules, effect typing, namespacing). *AINL 1.0 corresponds to the stabilized subset of the former v2 draft; references to v2 in repo or code (e.g. compiler_v2.py) are historical.* It distinguishes **surface syntax + IR schema** from **canonical graph IR** and **runtime execution mode** so conformance is not overclaimed.
Timeline anchor: Foundational AI research and cross-platform experimentation by
the human founder began in **2024**. After partial loss of early artifacts, AINL
workstreams were rebuilt, retested, and formalized in overlapping phases through
**2025-2026**.

**Normative:** `AINL_SPEC.md` (Version 1.0). **Non-normative expansion:** `docs/language/AINL_CORE_AND_MODULES.md`. **Implementation status:** compiler emits canonical graph (nodes/edges/entry/exits) and legacy.steps; runtime **executes the graph by default** (graph-preferred mode); legacy step-list is fallback when no graph or when steps-only mode.

---

## Schema conformance vs semantic conformance

- **Schema conformance:** IR keys and storage layout match the spec (e.g. `labels[id].nodes`, `labels[id].edges`, `labels[id].legacy.steps`).
- **Semantic conformance:** Runtime and compiler behavior match spec meaning (graph semantics, effect typing, binding rules).

A conformant implementation must satisfy both. The tables below mark schema (IR shape) and semantic (behavior) separately where they diverge.

---

## IR mode (1.0 alignment)
**Canonical IR is the graph** (`labels[id].nodes` / `labels[id].edges`; here and below, `labels[id]` means `labels[label_key]` where label_key is the numeric id). **The current implementation** emits `nodes`/`edges`/`entry`/`exits` and **`legacy.steps`** per label. **Runtime executes the graph by default:** when a label has `nodes`, `edges`, and `entry`, the engine runs **graph traversal** (`_run_label_graph`: follow edges by port, execute one node at a time). Legacy step-list is used only as fallback (e.g. when `execution_mode` is `steps-only`, or when a label has no graph data).

**Gap closed:** The pipeline is **AINL text → canonical graph (emitted) + legacy.steps → runtime executes graph** (when graph is present; default `execution_mode` is `graph-preferred`). The invariant *canonical IR = nodes/edges* is now enforced in execution: the runtime walks nodes/edges and uses `node.data` as the step payload per node. Legacy.steps remain for backward compatibility and as fallback.

| Aspect | Schema | Semantic | Notes |
|--------|--------|----------|-------|
| Graph execution (default) | — | ✅ | Runtime runs **nodes/edges** when present (`_run_label_graph`); default mode `graph-preferred`. |
| Legacy step-list fallback | — | ✅ | When no graph or `steps-only` mode, runtime runs `legacy.steps` (or `steps`). |
| Legacy step-list storage | ✅ | — | Compiler emits **`labels[id].legacy.steps`** only; no bare `steps`. Runtime reads `legacy.steps` with fallback to `steps` for backward compat. |
| Compiler emits `labels[id].nodes/edges` | ✅ | — | **Implemented.** `_steps_to_graph_all()` populates nodes, edges, entry, exits per label. |
| Deterministic `steps_to_graph()` | — | ✅ | **Implemented.** Same steps → same graph; canonical node ids n1, n2, … |
| Conformance claim | Full | Full | Schema and runtime behavior match AINL 1.0 for labels; remaining items are non-normative tooling/CLI conveniences. |

---

## §1 Design principles

| Principle | Status |
|-----------|--------|
| Non-human-readable by design | ✓ Dense ops and slots; no prose keywords. Oversight via artifacts (tests, diffs, reports), not AINL source. |
| AI-optimized | ✓ Single IR; multiple emitters; consistent slot patterns. |
| Single spec → many targets | ✓ One .lang → IR → React, FastAPI, Prisma, MT5, scraper, cron, server. |
| Explicit binding | ✓ E supports optional `->return_var`; `label_id` stored per endpoint. |
| Pluggable backends | ✓ Runtime uses `AdapterRegistry`; mock + base adapters in `adapters/`. |

---

## §2 Formal grammar

### 2.1 Lexical and line structure

| Rule | Implementation |
|------|----------------|
| Comment `#` to EOL (only outside quotes) | ✓ `tokenize_line()` strips `#` and rest of line when not inside double-quoted string. |
| Statement = OP + slots | ✓ `parse_line()` splits on whitespace; first token = op, rest = slots. |
| OP; L id : for labels | ✓ Ops parsed; labels via `op.startswith("L") and op.endswith(":")`. |
| Strings: double quotes only; escape `\"` `\\` | ✓ `tokenize_line()` treats quoted strings as single tokens; escapes supported. |
| Identifiers / path / enum | ✓ Identifiers: alnum + underscore; dot allowed for fe tokens (e.g. `color.primary`); paths `/`-prefixed; enums as `E[Id,...]`. |

### 2.2–2.3 Ops and slot rules

| Op | Spec | Compiler | Notes |
|----|------|----------|--------|
| S | name mode [path] | ✓ | |
| D | type_name (field:type)+ | ✓ | Parser accepts zero fields (non-conformant); compiler warns; **strict mode should fail**. |
| E | path method ->label_id [->return_var] | ✓ | `label_id` and `return_var` stored in eps. |
| L | L id : (slot)* | ✓ | Label blocks + inline steps parsed: R, J, If, Err, Retry, Call, Set, Filt, Sort. |
| R | adapter.verb target [args...] -><out> | ✓ | Parsed as slots; adapter/entity/path and ->out. |
| J | var | ✓ | |
| If | cond ->Lthen [->Lelse] | ✓ | Block and inline. |
| Err | [@node_id] ->Lhandler | ✓ (step-list) | Bare form (attach to previous node) and **@node_id** (err edge from that node). |
| Retry | [@node_id] count [backoff_ms] | ✓ (step-list) | Bare form and **@node_id** (retry edge from that node). |
| Call | Lid [->out] | ✓ | ->out stored when present; runtime uses _call_result. |
| Set / Filt / Sort | (see spec) | ✓ | Block and inline. |
| Inc | path | ✓ | Merge included .lang into IR. |
| U, T, Rt, Lay, Fm, Tbl, Ev, A, Q, Sc, Cr, P, C | (original + FE) | ✓ | As in table below. |
| **Module-prefixed** | `ops.Env`, `fe.Tok`, `rag.Src`, … | ✓ | Prefixed forms parsed as single tokens (no split on `.`); unprefixed Env, Tok, etc. normalize to `ops.Env`, `fe.Tok` in IR. rag.* and legacy `Rag*` accepted. |

| U | ui_name [prop]* | ✓ | |
| T | var or var:type | ✓ | Attaches to current U. |
| Q | name [max_size] [retry] | ✓ | |
| Sc | name url (selector=field)* | ✓ | |
| Cr | label_id cron_expr+ | ✓ | expr = " ".join(slots[1:]). |
| P | name amount currency [desc] | ✓ | **Spec:** P is declaration only (non-executable). Implementation: P never added to label steps; runtime skips P. Payment in labels = `R pay.*`. |
| C | name key ttl [default] | ✓ | |
| Rt, Lay, Fm, Tbl, Ev | (FE) | ✓ | fe.routes, layouts, forms, tables, events. |
| A | kind header_name | ✓ | services.auth. |
| Env, Sec, M, Tr, Deploy, EnvT, Flag, Lim | (ops) | ✓ | config, observability, deploy, limits. |
| Role, Allow, Aud, Adm | (RBAC/audit) | ✓ | roles, allow, audit, admin. |
| Ver, Compat, Tst, Mock, Desc, Rel, Idx, Svc, Contract, API, Dep, SLA, Run | (top-level / arch) | ✓ | ver, compat, tests, desc, types.*.relations/indexes, runbooks, etc. |
| Tok, Brk, Sp, Comp, Copy, Theme, i18n, A11y, Off, Help, Wiz, FRetry | (fe) | ✓ | fe.tokens, … , fe.retry. |
| `rag.Src` … `rag.Pipe` (and Rag*) | (rag) | ✓ | rag ops via `rag.*`; legacy `Rag*` accepted. ir["rag"]. |

### 2.4 Type shorthand

| Type | Spec | Implementation |
|------|------|-----------------|
| I, S, B, F, D, J | ✓ | `TYPE_MAP` in compiler; normalize_type() for emission. |
| A[Type], E[V1,V2,…] | ✓ | Handled in normalize_type(); Prisma/React emission. |

---

## §3 Execution model

### 3.1 IR

| IR key | Spec | Implementation |
|--------|------|-----------------|
| services | name → { mode, path, eps, ui, … } | ✓ Same. `fe` is `services["fe"]` (routes, layouts, forms, tables, events, ui, states). |
| types | type_name → { fields } | ✓ Same. |
| labels | label_id → { **nodes**, **edges**, **entry**, **exits**, **legacy**: { **steps** } } | **Schema ✅** Compiler emits `nodes`, `edges`, `entry`, `exits`, and `legacy.steps` only (no bare `steps`). **Semantic ✅** Runtime runs **graph** (nodes/edges) when present; legacy.steps as fallback. |
| crons | [ { label, expr } ] | ✓ Same. |
| stats | (lines, ops) | ✓ Returned by compile(). |

### 3.2 Label execution

**Runtime executes the canonical graph** when a label has `nodes`/`edges`/`entry` (default `execution_mode` is `graph-preferred`). It walks the graph by node id and edge port; per-node execution uses `node.data` (step payload). Legacy step-list is used only when graph is absent or `execution_mode` is `steps-only`. Control-flow (If, Err, Retry, Call) is driven by graph edges (then/else, handler, next, etc.); trace events include `node_id` and `port_taken`.

| Rule | Implementation |
|------|----------------|
| Entry: path → label_id from eps | ✓ Emitted server calls `_engine.run(ep["label_id"])`. |
| Run label (graph) | ✓ When graph present: `_run_label_graph()` traverses nodes/edges by port; trace has node_id/port_taken. |
| Run label (legacy fallback) | ✓ When no graph or steps-only: Engine runs `_get_steps(label)` (reads `legacy.steps`, fallback `steps`) in order. |
| R: adapter/verb dispatch; store under out | ✓ `RuntimeEngine` executes canonical `adapter,target,args,out` (with compiler-owned normalization and compatibility fold for legacy `src/req_op/entity/fields`). |
| J: return context[var] | ✓ Engine returns on J; server wraps as `{"data": result}`. |
| If / Err / Retry / Call / Set / Filt / Sort | ✓ In graph mode: driven by edges (then/else, handler, next); in step mode: step-list order. |
| P (if present) | ✓ **Conformant.** P is never executable; runtime skips P. Use R pay.* in labels for payment. |

### 3.3 Path → label → return

| Rule | Implementation |
|------|----------------|
| E stores return_var when given | ✓ Parsed and stored in eps. |
| E return_var must match label's terminal J (else validation error) | ✓ **Implemented** in strict mode (compile-time error when mismatch). |
| Call Lid [->out]; if ->out omitted callee must have exactly one J | ✓ Runtime honors explicit `->out`; `_call_result` preserved for compatibility when omitted. Strict compiler validation enforces call-shape and endpoint return constraints. |
| label_id normalized (L1 → 1) | ✓ In compiler and runtime. |
| Emitters use return_var / infer from J | ✓ _path_to_var() prefers return_var; React fetch wiring uses it. |

---

## §3.4 Core + Modules (1.0)

**Normalization rule (normative):** Unprefixed ops that are known module ops may be accepted for backward compatibility but **must be normalized to canonical `module.op` form in emitted IR**. This prevents divergent IR across implementations.

| Rule | Implementation |
|------|----------------|
| Module-prefixed statements (e.g. `ops.Env`, `fe.Tok`, `rag.Src`) | ✓ | Prefixed forms parsed as single tokens (no split on `.`); unprefixed Env, Tok, etc. normalize to `ops.Env`, `fe.Tok` in IR. rag.* and legacy `Rag*` accepted. |
| Module–op consistency validation | ✓ | Strict mode rejects unknown module.op in known modules; unknown ops go to meta in non-strict mode. |
| Core-only in labels enforced | ✓ | Strict mode enforces that every label step op is in STEP_OPS; non-core ops are rejected. |
| **Metadata preservation (unknown ops)** | ✓ Spec: compiler is **lossless by default**. Unknown ops are appended to **`meta`** (op, slots, lineno). Strict: error if prefixed op has unknown module. Known module ops normalized to `module.op` and stored under config, fe, rag, etc. |

These constraints are treated as *conformance requirements* in `--strict`; non-strict mode may compile permissively.

---

## §4 Target matrix

| Target | Spec | Emitter / behavior |
|--------|------|--------------------|
| React/TS (browser) | S(fe), D, E, U, T, Rt, Lay, Fm, Tbl, Ev | ✓ emit_react_browser: hash router, layout, forms, tables, events, fetch. |
| FastAPI | S(core), E, L, R, J | ✓ emit_python_api (stub) or server with runtime + ir.json. |
| Web server | S(core), S(fe), E, L, R, J | ✓ emit_server: API (runtime + adapters) + static mount. |
| Prisma | D | ✓ emit_prisma_schema. |
| MT5 | D, (E/L) | ✓ emit_mt5. |
| Scraper | Sc | ✓ emit_python_scraper. |
| Cron | Cr | ✓ emit_cron_stub. |
| Queue / Pay / Cache | Q, P, C | Config in IR; adapter-driven at runtime. |
| System scripts / Minecraft / .NET / Java | (future) | Not implemented; spec marks as future. |

---

## §5 Conformance

| Requirement | Status |
|-------------|--------|
| Parser: single line → (OP, slots[]) | ✓ Lossless tokenizer/parser supports quoted strings and escaped characters; slot kinds are preserved for strict-literal analysis. |
| Compiler: program → IR per §3.1 | ✓ compile() returns services, types, labels, crons, stats; labels use nodes, edges, entry, exits, legacy.steps. |
| Runtime: load IR + adapters; run(label_id) | ✓ Canonical execution via `RuntimeEngine` (`runtime/engine.py`) with graph-preferred policy; `ExecutionEngine` is compatibility shim. |
| Emitters: path→label_id→return_var and fe.* | ✓ All emitters use IR; React uses routes, layouts, events, path_to_var. |
| Canonical IR (nodes/edges) or steps→graph | ✓ Compiler emits nodes/edges/entry/exits; deterministic `steps_to_graph()`. Runtime executes graph by default and step fallback by policy. |

---

## Known divergences from 1.0 conformance

- No known divergences for the 1.0 core + modules: parser, compiler, runtime, and strict validation behave per spec. Remaining items in the roadmap are non-normative tooling/CLI conveniences and future targets.

---

## What we need to do next

Per spec §1.2, in order:

1. ~~**Implement canonical graph emission**~~ — **Done.** Compiler emits `nodes`/`edges`/`entry`/`exits` and `legacy.steps`; deterministic `steps_to_graph()`.
2. ~~**Replace runtime execution with graph traversal**~~ — **Done.** Runtime executes the graph (nodes/edges) by default (`graph-preferred`); `_run_label_graph()` walks nodes/edges by port; legacy.steps are fallback only.
3. ~~**Implement strict validation fully**~~ — **Done.** Strict mode enforces canonical graph invariants, E/J binding, Call return rules, module-op consistency, core-only labels, adapter contracts, and dataflow.
4. ~~**Implement semantic graph diff**~~ — **Done.** `tooling.graph_diff` and `tooling.graph_safe_edit` provide machine + human IR diffs.
5. ~~**Emit oversight report per compile/run**~~ — **Done.** `tooling.oversight` exposes compile/runtime oversight reports; callers/CLIs can persist them per compile/run.

(2) is done: the invariant (canonical IR = nodes/edges) is both emitted and executed when graph is present; AINL execution is graph-coherent by default.

---

## Roadmap: gaps to reach full 1.0 conformance

The table below expands the five items above with implementation notes.

| Gap | To reach full 1.0 | Notes |
|-----|------------------|-------|
| Canonical graph IR | ~~Emit `nodes`/`edges` or implement `steps_to_graph()`~~ | **Done** |
| Runtime graph execution | ~~Execute nodes/edges instead of step-list~~ | **Done** — default `graph-preferred`; `_run_label_graph()` |
| Node targeting | ~~Parse `Err @id` / `Retry @id`~~ | **Done** — slot + CST paths; err/retry edges from designated node. |
| Namespacing | ~~Parse `module.op` tokenization~~ | **Done** — prefixed `ops.Env`, `fe.Tok`, etc. are single tokens; unprefixed normalize in IR. |
| Strict validation | ~~Implement `--strict` per spec §3.5~~ | **Done** — strict mode covers canonical graph invariants, E/J return_var, single exit J, Call format, module.op consistency, core-only steps, adapter contracts, and dataflow. |
| Round-trip | ~~Ensure steps ⇄ graph equivalence~~ | **Done** on reducible graphs; property tests validate steps vs graph equivalence and side effects. |
| Semantic diff | ~~IR-level semantic diff (machine + human views)~~ | **Done** — `tooling.graph_diff`, `tooling.graph_safe_edit`, and `tooling.oversight` provide machine + human IR diffs. |
| Adapter contracts | ~~Enforce arity + allowlists at validation time~~ | **Done** — R adapter.verb is validated against `ADAPTER_EFFECT`; runtime adapter registries enforce allowlists per environment. |
| Oversight report | Emit human-auditable report on every compile/run (summary, deltas, tests) | Human verification |

---

## Summary

This workspace is **conformant with AINL 1.0** for surface syntax, IR schema (labels use `nodes`, `edges`, `entry`, `exits`, `legacy.steps`), lossless unknown-op preservation in `meta`, P declaration-only, deterministic graph emission, strict validation, and **graph execution**.

Language-surface optimization guardrails for future compression/benchmark work are documented in `docs/runtime/SAFE_OPTIMIZATION_POLICY.md`.

**Current runtime execution:** When a label has `nodes`/`edges`/`entry`, the engine runs **graph traversal** (`_run_label_graph`); legacy step-list is used only when graph is absent or `execution_mode` is `steps-only`.

Module-prefixed metadata ops (`ops.*`, `fe.*`, `arch.*`, `test.*`, `rag.*`) are preserved in IR for emitters (including prefixed canonical forms). **Strict validation mode** is **implemented** for: E return_var vs terminal J; endpoint/targeted labels exactly one J and terminal J; Call second slot format (->var if present); unknown module.op in known module; core-only label bodies (every step op in STEP_OPS); graph port validity, adapter contract (R adapter.verb), call effect inclusion, dataflow defined-before-use, and quoted-literal disambiguation in read positions.

---

## Conformance and strict-mode entrypoints (specified)

To keep the conformance doc durable and testable:

| Command | Purpose |
|---------|--------|
| `python -m ainl compile --strict spec.lang` | Run all validations (E/J, Call ->out, module–op, core-only, graph). **Implemented** via `AICodeCompiler(strict_mode=True)`; compile returns `errors` list CLI entrypoint `ainl` may differ. |
| `ainl-validate --strict spec.ainl` | Same strict checks via the validator CLI; **structured diagnostics** on stderr by default (optional **rich** via dev extras); **`--diagnostics-format=json`** or legacy **`--json-diagnostics`** for JSON-only stdout on failure. |
| `ainl visualize spec.ainl` / `ainl-visualize spec.ainl` | **Strict** compile; on success prints **Mermaid** for **`ir["labels"]`** (subgraph clusters per **`include`** alias; synthetic **`Call`** edges documented in output). On failure, same **structured diagnostics** family as validate. Read-only; does not change IR or runtime. |
| `python -m ainl test conformance/` | Execute conformance tests that validate behavior against this doc (e.g. from `docs/CONFORMANCE.md` or a `conformance/` test suite). **Not yet implemented**; entrypoint specified here. |

Current entrypoint: compile via `compiler_v2.py` (e.g. `python compiler_v2.py` or `python scripts/run_tests_and_emit.py`); canonical runtime via `runtime.engine.RuntimeEngine` (compatibility wrapper `runtime.compat.ExecutionEngine` retained for historical imports).

For the full automated matrix (tokenizer round-trip, IR canonicalization, strict validation, runtime parity, emitter stability), run:

```bash
make conformance
```

Update snapshots when expected outputs intentionally change:

```bash
SNAPSHOT_UPDATE=1 make conformance
```

## Release artifact profile contract

Release artifacts are explicitly profiled so strict expectations are not inferred:

- Source of truth: `tooling/artifact_profiles.json`
- Classes:
  - `strict-valid`: must compile with strict mode
  - `non-strict-only`: must compile in non-strict mode and fail strict mode
  - `legacy-compat`: retained for compatibility/training context; not strict conformance targets

This avoids overclaiming strict conformance for compatibility examples (notably `examples/golden/*.ainl` and selected OpenClaw/corpus fixtures).

---

## Minimal conformance test matrix (intended)

These tests define “conformance in spirit”; implement as automated suite when possible.

| Area | Test | Purpose |
|------|------|---------|
| Memory continuity (automated) | `tests/conformance/test_full_matrix.py` category **`memory_continuity_runtime`** on `tests/data/conformance/session_budget_memory_trace.ainl` | Strict compile → run under **`MemoryAdapter` only**; snapshots result + sanitized trace (session-budget-style put/list/prune; not mixed into core/sqlite/fs **runtime parity** because those adapters do not emulate memory). Extra tokenizer coverage: **`demo/session_budget_enforcer.lang`**. |
| Tokenizer | Quoted strings, escapes `\"` `\\` | Single-token strings |
| Parsing | `module.op` forms (e.g. `ops.Env`, `rag.Src`) | Prefixed op recognition |
| Parsing | Unprefixed known module ops → normalize to `module.op` in IR | Normalization rule |
| Lowering | `steps_to_graph()` determinism (same steps → same graph) | Canonical graph |
| Strict | E return_var vs single J in endpoint label | Binding validation |
| Strict | Call ->out or callee single J | Call return rules |
| Strict | Unknown prefixed `module.op` rejected | Module consistency |
| Strict | Unknown ops preserved to `meta` (warn non-strict, error invalid in strict) | Lossless compiler |
| Graph validation | Reachability from entry, no unreachable nodes | §3.2 topology |
| Graph validation | No duplicate node IDs, canonical `n`&lt;number&gt; only | §3.5 |
| Runtime | Graph traversal parity with step execution on reducible graphs | Semantic equivalence |
| Strict dataflow | `Call ->out` + `Retry @nX` + downstream `J out` compiles clean in strict mode | Compiler-owned RW/dataflow correctness |
| Strict literals | Quoted-vs-bare matrix for `Set.ref`, `Filt.value`, `CacheGet.key/fallback`, `CacheSet.value`, `QueuePut.value` | Ambiguity elimination in strict mode |
| Schema | Legacy step-list under `labels[id].legacy.steps` when emitted | IR shape |
| Schema | P never as executable step; R pay.* for payment in labels | One Rule |

---

## Tooling / local environment (non-normative)

- **Python 3.10+** is required; `scripts/bootstrap.sh` enforces it. For parity with
  the GitHub Actions matrix, use `PYTHON_BIN=python3.10` and `VENV_DIR=.venv-py310`
  (see [INSTALL.md](INSTALL.md)). Pre-commit’s docs-contract hook prefers
  `./.venv-py310/bin/python` when present.

## CI conformance note (v1.2.6 line)

- The CI `core-pr` profile installs `fastapi`/`uvicorn` through the `dev` extra so runtime-runner service tests import consistently across Linux/macOS/Windows.
- Runtime benchmark comparisons are still produced on pull requests, while strict runtime regression failure gating is enforced on non-PR lanes (push/release) to reduce host-noise false negatives in PR checks.
