# AI Native Lang (AINL) — Formal Spec & Design Principles

**Version: 1.0** — Grammar and IR are stable for training and tooling. Backward-compatible extensions only. *AINL 1.0 is the stabilized subset of the graph-first design (formerly v2 draft).*
Timeline anchor: Foundational AI research and cross-platform experimentation by
the human founder began in **2024**. After partial loss of early artifacts, AINL
workstreams were rebuilt, retested, and formalized in overlapping phases through
**2025-2026**.

**AI Native Lang (AINL) is an agent-native production language.** It is an **AI-to-AI intermediate programming language**: a compact, deterministic, executable IR that happens to have a surface syntax. It is **not intended to be authored or reviewed by humans**. Humans interact with the system in natural language; AI agents compile those intents into AINL, which serves as a compact, deterministic, verifiable intermediate program representation. **Human oversight is performed through emitted artifacts** (tests, semantic diffs, policy reports, and target-code output), not through direct inspection of AINL source.

**Design axiom:** Natural language is the **human interface**. AINL is the **agent interface**. Emitters and runtimes are the **machine interface**. Pipeline: **Human NL → Agent planning → AINL → IR(graph) → execution/emission.** AINL’s requirements are parseability, low entropy, determinism, trainability, and verifiability—not human readability.

**Definition:** AINL is a **deterministic, effect-typed, agent-generated graph IR** with declarative metadata layers and pluggable emitters. It is explicitly optimized for LLM generation and verification. **Invariant:** Canonical IR = nodes/edges; everything else is serialization. This invariant must be preserved to avoid conceptual drift (e.g. step semantics diverging from graph semantics, or aliases diverging across implementations).

---

## 0. Core vs. modules (the One Rule)

**Core = execution. Declarations = structural metadata. Modules = domain metadata.**

- **Core** is the only executable semantics: S, D, E, L, R, J, If, Err, Retry, Call, Set, Filt, Sort, Inc. These ops define control flow, adapters, and label graphs; runtimes execute them.
- **Declarations** are structural metadata (UI, routes, config, bindings). They never affect execution. Ops: U, T, Rt, Lay, Fm, Tbl, Ev, A, Q, Sc, Cr, P, C, Pol, Txn. In IR they are stored under **`core.decl`**; emitters consume them. Runtimes that do not implement a declaration simply preserve it in IR.
- **Modules** are domain metadata (`ops`, `fe`, `arch`, `test`, etc.). Namespaced ops are distinct from core (e.g. **Retry** vs **fe.FetchRetry**). Runtimes may ignore module ops they don’t implement; all ops must be preserved in IR for emitters. **Normalization:** For backward compatibility, unprefixed ops that are known module ops may be accepted at parse time but **must be normalized to canonical `module.op` form in emitted IR** (e.g. `Env` → `ops.Env`), so IR does not diverge across implementations.
- **Canonical IR:** Label meaning is defined by **nodes/edges**. A step-list is an **optional, non-canonical** serialization (`legacy.steps`) and must round-trip to the same graph. Core (executable) nodes have **effect: pure | io** (R = io; Set/Filt/Sort/If = pure; Call computed from callee subgraph).
- **Full grammar and validation:** [language/AINL_CORE_AND_MODULES.md](language/AINL_CORE_AND_MODULES.md) — namespaced grammar, canonical IR, effect typing, validation ruleset, optional bytecode (AINL-BC).

---

## 1. Design Principles

| Principle | Meaning |
|-----------|--------|
| **Non-human-readable by design** | AINL is not intended for manual authoring or manual review. Humans review *reports*, *diff summaries*, *tests*, and *runtime behavior*—not AINL text. This justifies aggressive compression and strict slot patterns. Syntax is optimized for parseability, low entropy, and determinism. |
| **AI-optimized** | Dense, consistent slot patterns; minimal redundancy; single source of truth (one spec → many targets). AINL reduces token entropy and structural, control-flow, effect, and binding ambiguity—so small models (e.g. 3B) can operate reliably in this constrained semantic space; larger models (e.g. 7B) do agentic programming with lower token and reasoning cost than when using Python/TS/Java directly. |
| **Single spec → many targets** | One AINL program compiles to an **IR** (intermediate representation). Emitters produce React/TS, FastAPI/Python, Prisma, MT5, scrapers, cron stubs, web servers, and (by extension) system scripts, game plugins, .NET, Java, etc. No need for the model to “speak” each target language; it speaks AINL and the compiler emits the rest. |
| **Explicit binding** | Path ↔ label ↔ return is explicit where possible (e.g. `E /products G ->L1 ->products`), so both agents and runtime can resolve behavior without inferring from multiple ops. |
| **Pluggable backends** | Data (R), payment (P), scrape (Sc), and API calls are executed via **adapters**. The language describes *what*; the adapter implements *how* in the host environment (Prisma, Stripe, httpx, etc.). |

**Human oversight.** The unit of oversight is not AINL source. In production, humans verify **artifacts**: executable tests and pass/fail, generated diffs in target languages when needed, policy checks (RBAC, PII, security), traces and audits, and conformance reports. **Compilation and execution must emit human-auditable artifacts.**

### 1.1 Production requirements (correctness and safety from tooling)

Since agents generate AINL, correctness and safety come from **tooling and verification**, not human review. The spec commits to:

- **Determinism:** Canonical graph semantics, deterministic steps→graph, canonical node IDs, strict slot arity.
- **Verifiability:** Strict-mode validation; static checks (reference validity, single-exit J, Call return rules); effect typing for replay/caching guarantees.
- **Traceability:** Compiler/runtime should support semantic diff (IR/graph level), behavioral diff (tests/endpoints affected), and adapter-contract diff (R calls changed). Humans answer “why did behavior change?” via these artifacts.
- **Safety boundaries:** Allowlists on adapters/verbs/targets, rate limits and auth policies (modules), sandboxed runtime permissions, audit trails for io edges.

**Architectural risks to avoid:** (1) Adding too many module ops too fast. (2) Letting aliases diverge across implementations. (3) Allowing step execution semantics to drift from graph semantics. Protecting the invariant—**canonical IR = nodes/edges**—keeps AINL coherent.

### 1.2 What we need to do next (operational safety)

Operational-safety milestones are now implemented and enforced across compiler/runtime/test contracts:

1. **Canonical graph emission** — implemented (`nodes`/`edges` + deterministic lowering/round-trip behavior).
2. **Runtime graph traversal** — implemented (graph-first execution policy with compatibility `steps-only` mode).
3. **Strict validation** — implemented (`--strict` guarantees in §3.5).
4. **Semantic graph diff** — implemented in graph tooling.
5. **Oversight reporting** — implemented via oversight/tooling surfaces.

The invariant (canonical IR = nodes/edges) is now operational, not aspirational.

---

## 2. Formal Grammar

### 2.1 Lexical and line structure

- **Line**: optional leading/trailing whitespace; **comment** or **statement**; newline.
- **Comment**: `#` to end of line (ignored).
- **Statement**: **OP** **slots**.
- **OP (core):** Either (a) a short core token (`S`, `D`, `E`, `R`, `J`, `U`, `T`, `Q`, `Sc`, `Cr`, `P`, `C`, `Rt`, `Lay`, `Fm`, `Tbl`, `Ev`, plus `A` and structural/declaration ops), or (b) a reserved identifier for core control/dataflow: `If`, `Err`, `Retry`, `Call`, `Set`, `Filt`, `Sort`, `Inc`. Labels use `L` + id + `:`.
- **Label block parsing:** `L`&lt;number&gt;`:` begins a label block. Within a label block, each subsequent non-empty non-comment line **must** begin with a label-step op token (`R|J|If|Err|Retry|Call|Set|X|Loop|ForEach|While|Filt|Sort|CacheGet|CacheSet|QueuePut|Tx|Enf`). Any other op within a label block is invalid. The block continues until the next `L`&lt;number&gt;`:` or EOF. Inline form is allowed: after the colon on the same line, a sequence of label-step statements may appear. This makes compiler behavior deterministic.
- **OP (module):** Module-prefixed ops use an identifier form: `module "." MODULE_OP` where `module` and `MODULE_OP` are identifiers (`[A-Za-z][A-Za-z0-9_]*`); dot only in the prefix (e.g. `ops.Env`, `fe.Tok`, `rag.Src`). This preserves dense short core ops while allowing descriptive module ops.
- **Statement grammar:** `statement := core_stmt | module_stmt`; `core_stmt := CORE_OP slots`; `module_stmt := module "." MODULE_OP slots`.
- **slots**: Zero or more **slot** tokens. Slots are separated by whitespace **except inside double-quoted strings**, which form a single token and may contain spaces. A **slot** is thus: a path, identifier, literal (including a quoted string), or composite like `f:T`, `->x` (arrow_var), `->L1` (arrow_lbl), `A[User]`.
- **Strings**: Double quotes only; no multiline. Escaping: `\"` and `\\`. A quoted string is one token even when it contains spaces. Conformance: tokenizer must recognize quoted strings as single tokens.
- **Identifiers**: Alphanumeric and underscore (dot allowed e.g. in fe tokens like `color.primary`). **Path**: `/`-prefixed (e.g. `/api/products`). **Enum literal**: `E[Id1,Id2,...]` — comma-separated ids inside brackets.

### 2.2 BNF-style grammar (ops and slots)

```
program       := (comment | statement)*
statement     := core_stmt | module_stmt

core_stmt     := S_s | D_s | E_s | L_s | Inc_s
              | U_s | T_s | Q_s | Sc_s | Cr_s | P_s | C_s | A_s
              | Rt_s | Lay_s | Fm_s | Tbl_s | Ev_s

label_step    := R_s | J_s | If_s | Err_s | Retry_s | Call_s | Set_s | X_s | Filt_s | Sort_s | Loop_s | While_s | ForEach_s | CacheGet_s | CacheSet_s | QueuePut_s | Tx_s | Enf_s
L_s           := "L" number ":" (label_step)*
at_node_id    := "@n" number

If_s          := "If" cond arrow_lbl [ arrow_lbl ]
Err_s         := "Err" [ at_node_id ] arrow_lbl
Retry_s       := "Retry" [ at_node_id ] number [number]
Call_s        := "Call" label_id [ arrow_var ]
Set_s         := "Set" var ref
Filt_s        := "Filt" var ref field cmp value
Sort_s        := "Sort" var ref field ["asc"|"desc"]
Inc_s         := "Inc" path

A_s           := "A" kind header_name [extra]
Pol_s         := "Pol" policy_name (constraint)*
Txn_s         := "Txn" txn_name [adapter] [mode]
S_s           := "S" name mode [path]
D_s           := "D" type_name (field ":" type)+
E_s           := "E" path method arrow_lbl [ arrow_var ]
R_s           := "R" ident target (r_arg)* arrow_var
target        := ident | path
r_arg         := path | ident | number | string | enum
arrow_var     := "->" id       // single token, e.g. ->out
arrow_lbl     := "->L" number  // single token, e.g. ->L1
J_s           := "J" var
U_s           := "U" ui_name [prop]*
T_s           := "T" (var | var ":" type)
Q_s           := "Q" name max_size [retry]
Sc_s          := "Sc" name url (bind_token)*
bind_token    := ident "=" id  // single token, e.g. selector=field
Cr_s          := "Cr" label_id cron_expr+
P_s           := "P" name amount currency [desc]
C_s           := "C" name key ttl [default]
Rt_s          := "Rt" path ui_name
Lay_s         := "Lay" shell_name slot_name+
Fm_s          := "Fm" form_name type_name field*
Tbl_s         := "Tbl" table_name type_name column*
Ev_s          := "Ev" component_name event target
CacheGet_s    := "CacheGet" cache_name key [arrow_var] [fallback]
CacheSet_s    := "CacheSet" cache_name key value [ttl]
QueuePut_s    := "QueuePut" queue_name value [arrow_var]
Tx_s          := "Tx" ("begin"|"commit"|"rollback") txn_name
Enf_s         := "Enf" policy_name

module_stmt   := module "." MODULE_OP slots
path          := "/" segment*
method        := "G" | "P" | "U" | "D" | "L"
label_id      := "L" number
number        := [0-9]+
type          := "I"|"S"|"B"|"F"|"D"|"J" | "A[" type "]" | "E[" (id ",")* id "]"
id            := [A-Za-z_][A-Za-z0-9_]*
```

**Lexical / slot productions (grammar closure):** `slot` := path | ident | number | string | enum | at_node_id. **`arrow_var`** is a single token `->` + id (e.g. `->out`). **`arrow_lbl`** is a single token `->L` + number (e.g. `->L1`). **`bind_token`** is a single token containing one `=` (e.g. `selector=field`). These and the cond forms below are **token classes** used only in the productions that require them; they are not part of the generic slot union. `ident` := id | dotted_id. `dotted_id` := id ("." id)*. `segment` := token-level (non-space, non-slash; exact charset left to tokenizer). `prop` := slot. `selector` := slot. `cron_expr` := slot+.

**Token classes (used in grammar):** `number` := [0-9]+. `node_id` := canonical form `n` number (e.g. n1); implementations may accept other id tokens but **must generate** only `n` number in `steps_to_graph()`. **Strict:** `at_node_id` (and thus `@node_id` in step-list) must be canonical: `@n` number (e.g. @n3). Parsers may accept non-canonical node ids in graph inputs for interoperability, but **must normalize** all node ids in IR to canonical `n`&lt;number&gt;. Node ids are thus always canonical `n`&lt;number&gt; in IR and in surface `@n`&lt;number&gt; references. `ref`, `var`, `name`, `field`, `mode`, `kind`, `header_name`, `type_name`, `ui_name`, and similar slot positions are **identifier tokens**; `cond` := ident | qmark_ident | eq_ident_value. **qmark_ident** is a single token: id followed by `?` (e.g. `ready?`). **eq_ident_value** is a single token: id `=` value_atom (e.g. `status=ok`, `count=0`); value_atom is ident, number, or quoted string. Equality cond is intentionally limited to ident | number | string in v1.0 (no enums/paths) to keep tokenizer and validation simple. (Three semantic forms: variable, presence, equality.) Other slot positions use `id` or dotted `id.id` where noted unless the production specifies otherwise. `cmp` := one of = != < <= > >= in contains (validators may extend). `value` := slot (excluding `at_node_id`, `arrow_var`, and `arrow_lbl`). **`@node_id`** is a **single slot token** (e.g. @n3). **`arrow_var`** / **`arrow_lbl`** are single tokens (`->out`, `->L1`); validators require exactly one trailing arrow_var for R in strict mode. Label id is **numeric** (e.g. L1, L2).

### 2.3 Slot rules by op

| Op | Required slots | Optional / rest | Notes |
|----|----------------|-----------------|------|
| **S** | name, mode | path | path = service base path (e.g. `/api`). **Exception:** **`S hybrid …`** — see §2.3.1. |
| **D** | type_name | field:type … | type_name = entity; field:type = key:shorthand |
| **E** | path, method | ->label_id, ->return_var | **Strict:** Endpoint label must have exactly one exit `J`. If `E` includes `->return_var`, it must match that `J` var. If omitted, infer from that `J`. |
| **L** | (op = L number :) | inline executable steps | Label id is numeric (L1, L2). Executable ops within a label block: `R J If Err Retry Call Set X Loop While ForEach Filt Sort CacheGet CacheSet QueuePut Tx Enf`. |
| **R** | adapter.verb target [args...] -><out> | | Canonical: adapter.verb (e.g. db.F, api.G, rag.Ret); target = entity or path. **Strict:** Exactly one trailing `arrow_var` (single token, e.g. `->out`) and it must be last; R slot arity validated by adapter.verb definition (fixed-arity or k=v list). Parsers accept arbitrary slots; validators enforce the pattern. |
| **J** | var | | resolve `var` from the execution frame and return it as the label result. `var` may be a frame variable name or a quoted string literal. |
| **X** | dst fn [args…] | | compact inline compute: evaluate `fn(args…)` and store the result in frame variable `dst`. `fn` is one of `add sub mul div idiv len get put push obj arr eq ne lt lte gt gte and or not concat join ite if` or a `core.*`-prefixed alias (e.g. `core.add`). S-expression paren form `X dst (fn arg…)` is also accepted; the compiler strips parens before emitting IR. |
| **Loop** | ref item ->Lbody ->Lafter | | iterate over list `ref`, binding each element to `item`; jump to `Lbody` per iteration, then `Lafter` when done. Alias: `ForEach`. |
| **While** | cond ->Lbody ->Lafter | limit= | loop while `cond` is truthy; enforce optional `limit=N` iteration cap. |
| **U** | ui_name | props… | props = component or data binding names |
| **T** | var or var:type | | attach state to current U |
| **Q** | name | max_size, retry | |
| **Sc** | name, url | selector=field … | |
| **Cr** | label_id | cron_expr (space-separated) | |
| **P** | name, amount, currency | desc | **Declaration only** (non-executable). For payment inside a label, use **R pay.*** (e.g. `R pay.Charge ... ->receipt`). P is metadata for emitters/adapters; runtime never executes P as a step. |
| **C** | name, key, ttl | default | |
| **A** | kind, header_name | extra | Auth: kind = jwt|apikey; header_name = e.g. Authorization, X-API-Key; stored in services.auth; emitted server adds Depends for protected routes. |
| **Rt** | path, ui_name | | path → which UI to render |
| **Lay** | shell_name | slot_name … | layout wrapper slots |
| **Fm** | form_name, type_name | field … | |
| **Tbl** | table_name, type_name | column … | |
| **Ev** | component, event, target | | target = path (e.g. /checkout) or label |

### 2.3.1 **S hybrid** (deployment hint / emit planning)

A top-level line of the form:

```text
S hybrid <target> [<target> …]
```

where each **`<target>`** is one of **`langgraph`**, **`temporal`**, is a **compiler-recognized deployment hint** (not a network service). It does **not** use the usual **`S name mode [path]`** shape.

- **Semantics:** each valid target is recorded under **`services.hybrid.emit`** (order-free; duplicates removed; first-seen order preserved).
- **IR effects:** the compiler sets **`emit_capabilities.needs_langgraph`** / **`needs_temporal`** accordingly and may include **`langgraph`** / **`temporal`** in **`required_emit_targets.minimal_emit`** so benchmarks and emission planners treat hybrid wrapper emitters as required when you opt in. **`full_multitarget`** mode still includes hybrid wrappers regardless.
- **Strict mode:** unknown target tokens are errors (allowed tokens: **`langgraph`**, **`temporal`**).

### 2.3.2 Canonical op registry contract (compiler validation)

To keep parsing/validation deterministic across implementations, compilers should maintain a canonical op registry entry per op:

- `scope`: where an op is valid
  - `top`: declaration/top-level only
  - `label`: label-step only
  - `any`: valid at top-level and in label blocks
- `min_slots`: minimum required slot count (arity floor)

Recommended compile behavior (strict and non-strict):

- If `len(slots) < min_slots`: preserve line in `meta` with `reason: "arity"`; in strict mode also add a compiler error.
- If a `label`-scope op appears at top-level: preserve line in `meta` with `reason: "scope"`; in strict mode also add a compiler error.
- Alias normalization (e.g. `Env` -> `ops.Env`) should occur before registry lookup.

This registry-backed validation is the source of truth for arity/scope checks and avoids hard-coded per-op drift.

### 2.3.3 Registry reference table (op -> scope, min_slots)

This table mirrors the compiler registry and is intended as a machine-readable human reference.

| Op | Scope | min_slots |
|----|-------|-----------|
| S | top | 2 |
| D | top | 1 |
| E | top | 3 |
| L: | top | 0 |
| U | top | 0 |
| T | top | 1 |
| Q | top | 1 |
| Sc | top | 2 |
| Cr | top | 2 |
| P | top | 3 |
| C | top | 3 |
| Rt | top | 2 |
| Bind | top | 3 |
| Lay | top | 2 |
| Fm | top | 2 |
| Tbl | top | 2 |
| Ev | top | 3 |
| A | top | 2 |
| Pol | top | 1 |
| Txn | top | 1 |
| Inc | top | 1 |
| Role | top | 1 |
| Allow | top | 2 |
| Aud | top | 2 |
| Adm | top | 1 |
| Ver | top | 1 |
| Compat | top | 1 |
| Tst | top | 1 |
| Mock | top | 3 |
| Desc | top | 2 |
| Rel | top | 4 |
| Idx | top | 2 |
| API | top | 1 |
| Dep | top | 2 |
| SLA | top | 3 |
| Run | top | 2 |
| Svc | top | 1 |
| Contract | top | 3 |
| R | any | 0 |
| J | any | 0 |
| X | label | 2 |
| Loop | label | 4 |
| While | label | 3 |
| If | label | 2 |
| Err | label | 1 |
| Retry | label | 0 |
| Call | label | 1 |
| Set | label | 2 |
| Filt | label | 5 |
| Sort | label | 3 |
| CacheGet | label | 2 |
| CacheSet | label | 3 |
| QueuePut | label | 2 |
| Tx | label | 2 |
| Enf | label | 1 |

### 2.4 Type shorthand

- **I** int, **S** string, **B** boolean, **F** float, **D** datetime, **J** json.
- **A[Type]** array of Type.
- **E[V1,V2,…]** enum (emitted as string or target enum).

---

## 3. Execution Model

**Canonical IR is the graph.** Label meaning is defined by **nodes** and **edges**. The step-list (`legacy.steps`) is a **legacy compatibility serialization**; canonical runtimes execute graph semantics by default, and any step execution mode must remain semantically equivalent to graph behavior (via compiler lowering contracts such as `steps_to_graph()`).

**Conformance:** The thesis demands **AINL text → canonical graph → runtime executes graph**. The reference implementation achieves this: when a label has `nodes`/`edges`/`entry`, the runtime executes the graph (node/edge traversal by port); legacy step-list is fallback only. The invariant *canonical IR = nodes/edges* is thus both emitted and executed; AINL is **fully coherent** for graph-capable runtimes.

### 3.1 IR (intermediate representation)

- **services**: map service name → { mode, path, eps, ui, … }. **eps** = path → { method, tgt, label_id, return_var }. The reserved pseudo-service **`hybrid`** holds **`{ "emit": ["langgraph", "temporal", …] }`** (subset) when the source contains **`S hybrid …`** lines; it drives **`emit_capabilities.needs_langgraph`** / **`needs_temporal`** and **`required_emit_targets.minimal_emit`** for tooling.
- **types**: map type_name → { fields: { key: type_shorthand } }.
- **labels**: map `label_key` → { **nodes**, **edges**, **legacy**?: { steps } }, where `label_key` is the numeric id (`1`, `2`, …). IR may also store the raw source token (e.g. `"L1"`) as metadata. In IR examples and prose, `labels[id]` means `labels[label_key]` where label_key is the numeric id. **nodes** and **edges** are canonical; **steps** are optional compatibility serialization that must round-trip to the same graph. Current implementation emits canonical graph and executes graph by default (`graph-preferred` runtime mode), with `legacy.steps` kept for compatibility and explicit `steps-only` operation. **Recommended schema (for tooling and diffs):** `labels[id].entry` = root node id (e.g. `"n1"`); `labels[id].exits` = list of `{ node, var }` for each J node; nodes as `[{ id, op, effect?, slots?, data? }]`, edges as `[{ from, to, port? }]`.
- **crons**: list of { label, expr }.
- **fe**: routes, layouts, forms, tables, events (and ui, states) for front-end emission.

**Lossless source boundary (recommended compiler contract):**

- `source`: `{ text: string, lines: string[] }` where `text` is the exact original source (byte-for-byte) and `lines = text.split("\n")`.
- `cst.lines`: one entry per source line, preserving blanks/comments:
  - `{ lineno, original_line, op_value, slot_values, tokens[] }`
  - `tokens[]`: `{ kind, raw, value, span }`, `kind ∈ {bare,string,ws,comment}`.
- `span` indexing: `line` is **1-based**; `col_start`/`col_end` are **0-based** (`[start,end)`).
- `meta` for unknown/rejected lines should use stable shape:
  - `{ lineno, op_value, slot_values, raw_line, tokens, reason? }`.
  - Backward-compatible readers may also accept legacy alias `slots_values`.
- `emit_source_exact(ir)` should return `ir.source.text` directly (no reconstruction).

### 3.2 Label graph semantics (deterministic topology)

For deterministic graph execution, each label’s graph must satisfy:

- **Exactly one entry node** — the first executable node (the single root from which all other executable nodes are reachable). In step-list form, this is the first step; in `steps_to_graph()`, it is the node with no incoming edge from within the label.
- **At least one exit J node** — every execution path must be able to reach a `J` (return) node. Labels referenced by `E` (endpoints) must have **exactly one** exit `J` in strict mode.
- **No unreachable nodes (strict mode)** — every node must be reachable from the entry and (for non-exit nodes) must have a path to some exit. Strict validation rejects labels with unreachable nodes.
- **No duplicate node IDs** — within a label, node ids are unique.
- **Canonical node IDs** — `n`&lt;number&gt; only; no non-canonical ids in canonical IR.

These rules prevent nondeterministic or ambiguous graph topologies.

### 3.3 Label execution (runtime)

- **Entry**: HTTP request hits endpoint **path** with **method**; server looks up **path** in **eps**, gets **label_id**.
- **Run:** A conforming runtime executes the label’s **canonical graph** (`nodes`/`edges`). **Legacy mode:** If only `legacy.steps` is present, the runtime executes the legacy serialization (or first applies `steps_to_graph()` and executes the graph). Semantics are defined by the graph; (Reference implementation runs the graph when nodes/edges are present.)
- **Node semantics:** **R** resolves adapter (db, api, …), stores result in context under **out**; **J** returns context[**var**] as response body (typically `{ "data": result }`). **Call** nodes have **effect** computed from the callee’s reachable subgraph **from the callee entry** (io if any reachable io node, else pure). **If**, **Err**, **Retry**, **Set**, **Filt**, **Sort** execute per graph edges. (Payments are metadata in v1.0; use R pay.* for label payment calls where supported.)
- **Adapters**: Pluggable (DB, API, Pay, Scrape). Default = mock; production = Prisma, Stripe, httpx, etc.

### 3.4 Path → label → return (explicit binding)

- **E path method ->label_id ->return_var** stores **return_var** in IR for that path. **Strict:** The endpoint label must have **exactly one exit J**. If `E` specifies `->return_var`, it must match that `J`’s var; otherwise validation fails. If omitted, infer from that single `J`. (Labels with multiple J exits require an explicit return mapping in a future extension or are invalid in strict mode.)
- **label_id** is `L`&lt;number&gt; in surface syntax (e.g. `L1`). IR may store both `raw: "L1"` and `num: 1` for fast indexing; labels are always referenced with the `L` prefix in source.
- **Call:** `Call Lid ->out` stores the callee's return in `ctx[out]`. If `->out` is omitted, the callee must have exactly one `J` exit; otherwise validation fails.
- **Err / Retry (graph):** Canonical forms are `Err @node_id ->Lhandler` and `Retry @node_id count [backoff_ms]`. In step-list form without `@node_id`, they attach to the **immediately preceding executable node**—i.e. the highest-numbered node created so far in the same label during deterministic lowering (`steps_to_graph()`).

### 3.5 Strict mode guarantees (safety engine)

Strict mode is the compiler’s enforcement layer. A conforming `--strict` validation **must** enforce:

| Guarantee | Meaning |
|----------|--------|
| Canonical graph emission | Emit `nodes`/`edges`; step-list optional and must round-trip. |
| Single exit J for endpoint labels | Any label referenced by `E` has exactly one `J` node. |
| Call return validation | `Call` with `->out` or callee with single J; return binding consistent. |
| No undeclared references | All label_ids, node_ids, and vars resolve. |
| Quoted literal disambiguation in read positions | Bare identifier-like tokens in read positions are treated as variable refs; string literals must be quoted to avoid ambiguity. |
| No unknown module.op | Every prefixed op is from a known module. |
| Adapter.verb arity validation | R slots match adapter definition (fixed-arity or k=v list). |
| No unreachable nodes | Every node reachable from entry and (if non-exit) can reach an exit. |
| No duplicate node IDs | Unique `n`&lt;number&gt; per label. |
| No non-canonical node IDs | Only `n`&lt;number&gt; in IR. |

Without strict mode, AINL becomes soft; implementations should treat it as the default for production.

**Compiler behavior (two orthogonal flags):** **`--emit-graph`** (default true): emit canonical `nodes`/`edges`; if step-list is present it must round-trip. **`--strict`** (validation policy): enforce all §3.5 guarantees. Runtime policy controls execution mode (`graph-preferred`, `graph-only`, `steps-only`) without changing strict compile guarantees.

---

## 4. Target Matrix

**Expanded roadmap (real-world / production):** see [docs/runtime/TARGETS_ROADMAP.md](runtime/TARGETS_ROADMAP.md).

| Target | Ops / IR used | Emitter output |
|--------|----------------|----------------|
| **React/TS (browser)** | S(fe), D, E, U, T, Rt, Lay, Fm, Tbl, Ev, path→var | JSX with hash router, layout, forms, tables, event handlers, fetch(api_base+path) |
| **FastAPI (Python)** | S(core), E, L, R, J | Route handlers; or runtime + ir.json + adapters |
| **Web server** | S(core), S(fe), E, L, R, J | Single server: API (runtime + adapters) + static mount |
| **OpenAPI 3.0** | E, D | openapi.json (paths + schemas) for docs, codegen, gateways |
| **Docker + Compose** | S, E, D | Dockerfile + docker-compose.yml for one-command deploy |
| **Prisma** | D | schema.prisma (models from types) |
| **MT5** | D, (E/L) | .mq5 stub (OnInit/OnTick, types as comments) |
| **Scraper (Python)** | Sc | requests + BeautifulSoup or Scrapy stub |
| **Cron** | Cr | Python stubs (APScheduler/Celery Beat style) |
| **Queue** | Q | (Config only; backend-specific emission optional) |
| **Pay** | P | (Adapter-driven; Stripe etc. in runtime) |
| **Cache** | C | (Adapter-driven; Redis etc. in runtime) |
| **System scripts** | (future) Cr, R, E-like | Emit shell or small Python runner |
| **Minecraft / game** | (future) S, E, U-like | Emit plugin/event hooks for target API |
| **.NET / Java / Go / Node** | Same IR | New emitters + adapters (see roadmap) |

---

## 5. Conformance and Training

**Normative:** This document (§§0–5) is the formal spec. [AINL_CORE_AND_MODULES.md](AINL_CORE_AND_MODULES.md) is the thesis-aligned expansion and must not introduce normative rules that contradict this spec.

**Canonical IR is the source of truth.** The IR graph (nodes/edges) is the real program representation. AINL surface syntax is a **transport, cache, and debugging format**; agents may manipulate graphs directly. AINL-BC (see Core doc) is the deterministic bytecode encoding of the graph and may become the primary storage format; human-facing tools render IR/BC into reports and diffs.

- **Parsing**: A conforming parser takes a single line and returns (OP, slots[]). A conforming compiler parses all lines and produces the IR above.
- **Lossless compiler:** The compiler must preserve all ops in IR (no dropping). Unknown ops go to a `meta` bucket. **Non-strict:** preserve unknown ops into `meta`, warn. **Strict:** preserve into `meta`, error on invalid (e.g. unknown prefixed `module.op`). This is baseline behavior, not strict-only; traceability and emitters depend on it.
- **Execution**: A conforming runtime loads IR + adapters and, for a given label_id, executes the label graph (or legacy.steps via steps_to_graph()) as in §3.2.
- **Emission**: Emitters read IR and produce target code; they must respect path→label_id→return_var and fe.routes/layouts/forms/tables/events when present.

This spec is the single source of truth for “valid AINL” and “meaning of an AINL program.” It can be used to train or fine-tune small models (e.g. 3B) on AINL-only parsing/generation, with emission to one or more targets as a separate step.
