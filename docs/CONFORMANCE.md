# AINL 1.0 implementation conformance

This checklist confirms alignment of this workspace with **docs/AINL_SPEC.md (AINL 1.0)**. AINL 1.0 is the normative spec (graph-first, core+modules, effect typing, namespacing). *AINL 1.0 corresponds to the stabilized subset of the former v2 draft; references to v2 in repo or code (e.g. compiler_v2.py) are historical.* It distinguishes **surface syntax + IR schema** from **canonical graph IR** and **runtime execution mode** so conformance is not overclaimed.

**Normative:** docs/AINL_SPEC.md (Version 1.0). **Non-normative expansion:** AINL_CORE_AND_MODULES.md. **Implementation status:** compiler emits canonical graph (nodes/edges/entry/exits) and legacy.steps; runtime executes legacy step-list (graph execution planned).

---

## Schema conformance vs semantic conformance

- **Schema conformance:** IR keys and storage layout match the spec (e.g. `labels[id].nodes`, `labels[id].edges`, `labels[id].legacy.steps`).
- **Semantic conformance:** Runtime and compiler behavior match spec meaning (graph semantics, effect typing, binding rules).

A conformant implementation must satisfy both. The tables below mark schema (IR shape) and semantic (behavior) separately where they diverge.

---

## IR mode (1.0 alignment)
**Canonical IR is the graph** (`labels[id].nodes` / `labels[id].edges`; here and below, `labels[id]` means `labels[label_key]` where label_key is the numeric id). **The current implementation** emits `nodes`/`edges`/`entry`/`exits` and **`legacy.steps`** per label; runtime executes the legacy serialization (reads `legacy.steps` with fallback to `steps` for old IR). **Graph execution will replace step execution** when runtime runs nodes/edges directly.

**The only remaining real gap:** Right now the pipeline is **AINL text → canonical graph (emitted) + legacy.steps → runtime executes steps**. The spec demands **AINL text → canonical graph → runtime executes graph**. Until the runtime executes nodes/edges directly, the invariant (canonical IR = nodes/edges) is aspirational. Once the runtime executes the graph directly, AINL becomes fully coherent.

| Aspect | Schema | Semantic | Notes |
|--------|--------|----------|-------|
| Legacy step-list exists and is executed | — | ✅ | Runtime runs step-list (via `legacy.steps` or `steps`). |
| Legacy step-list storage | ✅ | — | Compiler emits **`labels[id].legacy.steps`** only; no bare `steps`. Runtime reads `legacy.steps` with fallback to `steps` for backward compat. |
| Compiler emits `labels[id].nodes/edges` | ✅ | — | **Implemented.** `_steps_to_graph_all()` populates nodes, edges, entry, exits per label. |
| Deterministic `steps_to_graph()` | — | ✅ | **Implemented.** Same steps → same graph; canonical node ids n1, n2, … |
| Conformance claim | Partial | Partial | Schema conformant for labels (legacy.steps, nodes/edges). Graph execution not yet; strict validation partial. |

When runtimes execute the graph directly (instead of legacy.steps), this doc will be updated to state full 1.0 conformance.

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
| Err | [@node_id] ->Lhandler | ✓ (step-list) | Bare form only (attach to previous node). **@node_id** parsing **Not yet**. |
| Retry | [@node_id] count [backoff_ms] | ✓ (step-list) | Bare form only. **@node_id** **Not yet**. |
| Call | Lid [->out] | ✓ | ->out stored when present; runtime uses _call_result. |
| Set / Filt / Sort | (see spec) | ✓ | Block and inline. |
| Inc | path | ✓ | Merge included .lang into IR. |
| U, T, Rt, Lay, Fm, Tbl, Ev, A, Q, Sc, Cr, P, C | (original + FE) | ✓ | As in table below. |
| **Module-prefixed** | `ops.Env`, `fe.Tok`, `rag.Src`, … | Partial | rag ops supported via `rag.*` forms; legacy aliases `Rag*` also accepted for backward compatibility. `ops.Env` / `fe.Tok` as single token **Not yet** (unprefixed Env, Tok, … accepted). |

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
| labels | label_id → { **nodes**, **edges**, **entry**, **exits**, **legacy**: { **steps** } } | **Schema ✅** Compiler emits `nodes`, `edges`, `entry`, `exits`, and `legacy.steps` only (no bare `steps`). **Semantic ✅** Runtime runs legacy.steps. |
| crons | [ { label, expr } ] | ✓ Same. |
| stats | (lines, ops) | ✓ Returned by compile(). |

### 3.2 Label execution

**Runtime currently executes the legacy step-list serialization** (steps only); it does not yet execute the canonical nodes/edges graph. Graph execution will replace step execution when canonical IR is available. Control-flow ops (If, Err, Retry, Call) are compiled to steps and executed in step order; effect typing is not yet applied at runtime.

| Rule | Implementation |
|------|----------------|
| Entry: path → label_id from eps | ✓ Emitted server calls `_engine.run(ep["label_id"])`. |
| Run label steps | ✓ Engine runs `_get_steps(label)` (reads `legacy.steps`, fallback `steps`) in order (legacy mode). |
| R: adapter by src (db/api); store under out | ✓ `ExecutionEngine` uses adapters; result in ctx[out]. |
| J: return context[var] | ✓ Engine returns on J; server wraps as `{"data": result}`. |
| If / Err / Retry / Call / Set / Filt / Sort | ✓ Executed as step-list (branch, error handler, retry, subroutine, assign, filter, sort). |
| P (if present) | ✓ **Conformant.** P is never executable; runtime skips P. Use R pay.* in labels for payment. |

### 3.3 Path → label → return

| Rule | Implementation |
|------|----------------|
| E stores return_var when given | ✓ Parsed and stored in eps. |
| E return_var must match label's terminal J (else validation error) | **Not implemented.** Required in `--strict`. |
| Call Lid [->out]; if ->out omitted callee must have exactly one J | **Not implemented.** Runtime stores callee result in _call_result; explicit ->out and single-J validation required in `--strict`. |
| label_id normalized (L1 → 1) | ✓ In compiler and runtime. |
| Emitters use return_var / infer from J | ✓ _path_to_var() prefers return_var; React fetch wiring uses it. |

---

## §3.4 Core + Modules (1.0)

**Normalization rule (normative):** Unprefixed ops that are known module ops may be accepted for backward compatibility but **must be normalized to canonical `module.op` form in emitted IR**. This prevents divergent IR across implementations.

| Rule | Implementation |
|------|----------------|
| Module-prefixed statements (e.g. `ops.Env`, `fe.Tok`, `rag.Src`) | **Partial.** rag ops supported via `rag.*` forms; legacy aliases `Rag*` also accepted. Unprefixed Env, Tok, … ✓; prefixed `ops.Env` / `fe.Tok` as single token **Not yet**. IR must store canonical prefixed form (see normalization rule). |
| Module–op consistency validation | **Not yet.** Compiler does not reject unknown module.op in strict. |
| Core-only in labels enforced | **Not yet.** Only executable steps appear in label body in practice; no strict check. |
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
| Parser: single line → (OP, slots[]) | ✓ parse_line() returns (OP, slots[]) via whitespace tokenization (**strict tokenizer not yet implemented for quoted strings**). |
| Compiler: program → IR per §3.1 | ✓ compile() returns services, types, labels, crons, stats; labels use nodes, edges, entry, exits, legacy.steps. |
| Runtime: load IR + adapters; run(label_id) | ✓ ExecutionEngine.run() over legacy steps. |
| Emitters: path→label_id→return_var and fe.* | ✓ All emitters use IR; React uses routes, layouts, events, path_to_var. |
| Canonical IR (nodes/edges) or steps→graph | ✓ Compiler emits nodes/edges/entry/exits; deterministic `steps_to_graph()`. Runtime still executes steps (graph execution planned). |

---

## Known divergences from 1.0 conformance

- **Err @node_id** and **Retry @node_id** are not parsed; bare forms only (attach to immediately preceding node).
- **module.op** tokenization is not supported as single token; module ops accepted unprefixed; IR stores canonical prefixed form (normalization implemented).
- **Strict validations** are not fully enforced: E return_var vs terminal J, Call single-J, module–op consistency, core-only in labels. Strict mode partial.

---

## What we need to do next

Per spec §1.2, in order:

1. ~~**Implement canonical graph emission**~~ — **Done.** Compiler emits `nodes`/`edges`/`entry`/`exits` and `legacy.steps`; deterministic `steps_to_graph()`.
2. **Replace runtime execution with graph traversal** — Runtime executes the graph (nodes/edges), not the step-list; steps become optional/cache only.
3. **Implement strict validation fully** — `--strict` per spec §3.5 (canonical graph, single exit J, Call return, no undeclared refs, no unknown module.op, adapter arity, no unreachable/duplicate/non-canonical nodes).
4. **Implement semantic graph diff** — IR-level semantic diff (machine + human views) for traceability.
5. **Emit oversight report per compile/run** — Human-auditable report (summary, deltas, tests) on every compile and run.

Until (2) is done, the invariant (canonical IR = nodes/edges) is emitted but not yet executed; once the runtime executes the graph, AINL becomes fully coherent.

---

## Roadmap: gaps to reach full 1.0 conformance

The table below expands the five items above with implementation notes.

| Gap | To reach full 1.0 | Notes |
|-----|------------------|-------|
| Canonical graph IR | ~~Emit `nodes`/`edges` or implement `steps_to_graph()`~~ | **Done** |
| Node targeting | Parse `Err @id` / `Retry @id` | Required |
| Namespacing | Parse `module.op` tokenization | Required |
| Strict validation | Implement `--strict` per spec §3.5 (canonical graph, single exit J, Call return, no undeclared refs, no unknown module.op, adapter arity, no unreachable/duplicate/non-canonical nodes) | Required |
| Round-trip | Ensure steps ⇄ graph equivalence | Required |
| Semantic diff | IR-level semantic diff (machine + human views) | For traceability |
| Adapter contracts | Enforce arity + allowlists at validation time | Safety boundaries |
| Oversight report | Emit human-auditable report on every compile/run (summary, deltas, tests) | Human verification |

---

## Summary

This workspace is **conformant with AINL 1.0** for surface syntax, IR schema (labels use `nodes`, `edges`, `entry`, `exits`, `legacy.steps`), lossless unknown-op preservation in `meta`, P declaration-only, and deterministic graph emission. Remaining gaps: runtime still executes legacy.steps (graph execution not yet), strict validation partial, `module.op` single-token parsing and Err/Retry @node_id not implemented.

**Current runtime execution** uses **`_get_steps(label)`** (reads `labels[id].legacy.steps`, fallback to `labels[id].steps`). The **canonical IR** (`labels[id].nodes` / `labels[id].edges`) **is emitted** by the compiler; **graph execution will replace step execution** when implemented.

Module-prefixed metadata ops (`ops.*`, `fe.*`, `arch.*`, `test.*`, `rag.*`) are preserved in IR for emitters (rag.* and unprefixed forms fully; `ops.Env` / `fe.Tok` as prefixed tokens planned). **Strict validation mode** (slot arity, module–op consistency, E return_var vs J, Call ->out, core-only label bodies) is **not implemented**; the doc specifies the entrypoints below.

---

## Conformance and strict-mode entrypoints (specified)

To keep the conformance doc durable and testable:

| Command | Purpose |
|---------|--------|
| `python -m ainl compile --strict spec.lang` | Run all validations (E/J, Call ->out, slot arity, module–op, core-only in labels); fail or warn on non-conformant input. **Not yet implemented**; entrypoint specified here. |
| `python -m ainl test conformance/` | Execute conformance tests that validate behavior against this doc (e.g. from `docs/CONFORMANCE.md` or a `conformance/` test suite). **Not yet implemented**; entrypoint specified here. |

Current entrypoint: compile via `compiler_v2.py` (e.g. `python compiler_v2.py` or `run_tests_and_emit.py`); runtime via `runtime.ExecutionEngine` and emitted server.

---

## Minimal conformance test matrix (intended)

These tests define “conformance in spirit”; implement as automated suite when possible.

| Area | Test | Purpose |
|------|------|---------|
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
| Schema | Legacy step-list under `labels[id].legacy.steps` when emitted | IR shape |
| Schema | P never as executable step; R pay.* for payment in labels | One Rule |
