# AI Native Lang (AINL): Core + Modules — Thesis-Aligned Spec

**Status:** This document is the thesis-aligned expansion of [AINL_SPEC.md](AINL_SPEC.md). It must not introduce new normative rules that contradict the formal spec; the formal spec (§§0–5 of AINL_SPEC.md) is normative.

**Design rule (the One Rule):**

> **Core = execution. Declarations = structural metadata. Modules = domain metadata.**

- **Core** is the only executable semantics; runtimes execute core ops. **Declarations** (U, T, Rt, …) are structural metadata stored as `core.decl`; they never affect execution. **Modules** are domain metadata; runtimes may ignore module ops they don’t implement, but all ops must be preserved in IR for emitters.
- **No unqualified op name may have multiple semantics.** Namespaced ops are distinct (e.g. `Retry` vs `fe.FetchRetry`). Use distinct names across domains to avoid trainability drift.
- IR is **graph-first**: canonical meaning is defined by nodes/edges; `legacy.steps` is an allowed compatibility encoding only.
- Token cost stays low because meaning is structural, not prose.

---

## 1. Namespaced grammar

Statements are **unprefixed** (legacy/core) or **module-prefixed**. Prefix is optional for backward compatibility; when present it disambiguates and enables validation. The prefix `core.` is allowed but optional; tooling may normalize unprefixed core ops to module `core` and core declarations to `core.decl`.

```
statement   := [ module "." ] op_slots
module      := "core" | "ops" | "fe" | "arch" | "test" | "rag"
op_slots    := OP slots
```

**Examples:** `If cond ->Lthen ->Lelse` | `ops.Env DATABASE_URL required` | `fe.Tok color.primary #333` | `fe.FetchRetry 3 1000` (client fetch retry; surface form `FRetry` allowed for brevity).

---

## 2. AINL-Core

### 2.1 Core (execution) vs declarations (structural metadata)

- **Core** = the ops that define execution: S, D, E, L, R, J, If, Err, Retry, Call, Set, Filt, Sort, Inc. These are the only ops that affect runtime behavior.
- **Declarations** = structural metadata (UI, routes, config, bindings). Ops: U, T, Rt, Lay, Fm, Tbl, Ev, A, Q, Sc, Cr, P, C. They are unprefixed for brevity but stored as **`core.decl`** in IR; they never affect execution and are consumed by emitters.

### 2.2 Executable ops and slots

| Op | Slots | Effect | IR (graph node) |
|----|-------|--------|------------------|
| **R** | adapter.verb target [args...] -><out> | io | Request (adapter call); see §2.4 |
| **J** | var | pure | Return |
| **If** | cond ->Lthen [->Lelse] | pure | Branch |
| **Err** | [@node_id] ->Lhandler | — | Edge from node’s `error` port to handler; step-list: bare = immediately preceding node |
| **Retry** | [@node_id] count [backoff_ms] | — | Wrapper around (io) node; step-list: bare = immediately preceding executable node |
| **Call** | Lid [->out] | io if callee has io else pure | Subgraph invocation; result in ctx[out]; if ->out omitted, callee must have exactly one J |
| **Set** | name ref | pure | Assign |
| **Filt** | name ref field cmp value | pure | Filter array |
| **Sort** | name ref field [asc\|desc] | pure | Sort array |
| **Inc** | path | — | Compile-time merge |

**Effect typing:** Every core node has `effect: "pure" | "io"`. **R** (adapter call) = `io`. **Set**, **Filt**, **Sort**, **If** = `pure`. P, Sc are declarations (metadata) in the normative spec; if a runtime treats them as label steps, they behave as io. **Call:** `Call.effect = "io"` if the callee’s reachable subgraph from the callee entry contains any io node; else `"pure"`. **Effect typing at the graph level** unlocks: pure-node parallelization, subgraph caching, deterministic replay, differential testing, and semantic diffing at effect boundaries. Most AI orchestration frameworks do not have this.

S, D, E, L define structure (services, types, endpoints, labels); execution is over label graphs only.

**Label blocks:** `L<id>:` begins a label. Subsequent **executable step ops** (`R J If Err Retry Call Set Filt Sort`) belong to that label until the next `L<id>:` or EOF. Non-executable ops inside a label are invalid. Inline form: `L1: R db.F User * ->us J us` is allowed (same line); only executable step ops may appear in the block or inline.

### 2.4 R (Request) — canonical form

**Canonical pattern:** `R <adapter>.<verb> <target> [args...] -><out>`

- **adapter** = `db | api | pay | cache | scrape | rag | …` (resolved at runtime; declared in IR for validation).
- **verb** = adapter-defined (e.g. `F`, `G`, `P`, `D` for db/api); each adapter.verb has a **fixed arity** for args (declared for validation). Prefer fixed arity per adapter.verb for small-model reliability; otherwise models may hallucinate arg shapes. Key-value slots (`k=v`) are an allowed alternative for variable arity.
- **target** = entity (type name) or path (e.g. `/external`).
- **args** = adapter-specific; fixed slot count per verb or key-value list.
- **->out** = context key for the result.

Examples: `R db.F User * ->us` | `R api.G /external ->res` | `R rag.Ret ret1 query 5 ->chunks`.

### 2.5 Lexical and quoting

- **Strings:** Double quotes only; no multiline. Escaping: `\"` and `\\`. Conformance tests must accept only this form. **Tokenization:** Slots are separated by whitespace **except inside double-quoted strings**, which are a single token and may contain spaces.
- **Identifiers:** Alphanumeric and underscore; no spaces. Names like `OrderTable`, `color.primary` (dot allowed in fe tokens). Path tokens: `/`-prefixed, e.g. `/api/products`. Enum literals: `E[Ad,Us]` — comma-separated ids inside brackets.
- **Strict disambiguation:** In strict mode, bare identifier-like tokens in read positions are interpreted as variable references; if literal intent is required, quote the value.

### 2.6 Core declarations (non-executable)

| Op | Purpose | IR |
|----|---------|-----|
| U, T, Rt, Lay, Fm, Tbl, Ev | UI/route bindings | fe.ui, fe.routes, fe.layouts, fe.forms, fe.tables, fe.events |
| A | Auth | services.auth |
| Q, Sc, Cr, P, C | Queue, Scrape, Cron, Pay, Cache | adapter/config metadata |

Variables: use **Set**, **Filt**, **Sort** only (no overloading). Client fetch retry: **fe.FetchRetry** (surface `FRetry`); not the same op as core **Retry**. **Aliases** (e.g. `FRetry` for `fe.FetchRetry`, `RagSrc` for `rag.Src`): must **normalize during parsing** into the canonical op names so that IR does not diverge across implementations.

---

## 3. Canonical IR and serialization

### 3.1 Canonical meaning is the graph

- **Canonical meaning** of a label is defined by **nodes** and **edges**.  
- **`labels[id].nodes`** and **`labels[id].edges`** are the canonical representation (in IR and in this doc, `labels[id]` means `labels[label_key]` where label_key is the numeric id).  
- **`labels[id].legacy.steps`** is a **non-canonical compatibility encoding** that must round-trip to the same graph. Emitters and runtimes that consume step-lists must treat them as a serialization of that graph. **graph_to_steps()** is required only for graphs that are representable in step-list form (a reducible subset). For general graphs, `legacy.steps` may be absent; `nodes`/`edges` remains canonical.

So: *“Canonical meaning is defined by nodes/edges; step-list is an allowed compatibility encoding.”* **Invariant:** Canonical IR = nodes/edges; everything else is serialization. Current implementation emits canonical graph and executes graph by default (`graph-preferred`), with `legacy.steps` retained for compatibility and explicit `steps-only` mode. No emitter should define label semantics from steps alone in a way that diverges from the graph.

### 3.2 Labels as graphs

- A **label** is a directed graph of **nodes** and **edges**. Per spec §3.2: each label must have **exactly one entry node**, **at least one exit J**, and in strict mode **no unreachable nodes** and **no duplicate or non-canonical node IDs**.
- Each node has: `id`, `op`, `effect` (pure | io), and op-specific payload.
- **If:** node with cond, then_node_id, else_node_id; edges to then/else.
- **Err:** edge from a node's `error` port to the handler label's entry. **Canonical (graph):** `Err @node_id ->Lhandler`. Step-list form without `@node_id` = attach to immediately preceding executable node.
- **Retry:** wrapper node around one inner node; `count`, `backoff_ms`. **Canonical (graph):** `Retry @node_id count [backoff_ms]`. Step-list without `@node_id` = wrap immediately preceding executable node.
- **Call:** subgraph-invocation node; edge to callee entry, return edge from callee J to caller next.
- **R, J, Set, Filt, Sort:** single nodes with one outgoing edge (J = exit).

**Step-list → graph (deterministic):** When building a graph from a step-list, node IDs are assigned in step order. **Canonical generated ids** are `n` followed by a number (e.g. `n1`, `n2`); implementations **must not generate** other id forms in `steps_to_graph()`. Node numbering in `steps_to_graph()` starts at `n1` for each label and increments by appearance order of executable nodes. In `steps_to_graph()`: **Retry** creates a wrapper node around the target node; **Err** adds an error edge from the target node to the handler label. "Immediately preceding executable node” means the **highest-numbered node created so far in the same label** (so Err/Retry in bare form attach to that node). This makes `steps_to_graph()` fully spec-able and deterministic.

**Execution / binding (stable for training):** (1) **Strict:** An endpoint label referenced by `E` must have exactly one exit `J`. If `E` specifies `->return_var`, it must match that `J` var; else validation fails. If omitted, infer from that `J`. (2) `Call Lid ->out` stores callee return in `ctx[out]`; if `->out` omitted, callee must have exactly one `J` else validation fails. (3) Graph targeting: `Err @node_id ->Lhandler` and `Retry @node_id count [backoff_ms]` are canonical; step-list bare forms target the immediately preceding executable node (see above).


### 3.3 Metadata namespaces (non-executable)

| Module | Ops | IR key | Consumed by |
|--------|-----|--------|-------------|
| **ops** | Env, Sec, M, Tr, Deploy, EnvT, Flag, Lim | config, observability, deploy, limits | Server emit, K8s, gateway |
| **fe** | Tok, Brk, Sp, Comp, Copy, Theme, i18n, A11y, Off, Help, Wiz, **fe.FetchRetry** | fe.tokens, … , fe.retry | React/Vue/Svelte, design system |
| **arch** | Svc, Contract, Rel, Idx, API, Dep, SLA, Adm, Desc, Run | services.boundaries, … , runbooks | OpenAPI, SQL, K8s, runbooks |
| **test** | Tst, Mock | tests | Test runner |
| top-level | Ver, Compat, Role, Allow, Aud | ver, compat, roles, allow, audit | All emitters, compat report |

**fe.FetchRetry** (surface `FRetry`): `fe.FetchRetry count backoff_ms` → `fe.retry: { count, backoff_ms }`. Distinct name from core **Retry**; no overloading.

---

## 3.4 RAG module (retrieval-augmented generation)

The **rag** module lets low-parameter models declare RAG pipelines **all together** (one pipeline) or **individually** (sources, chunking, embedding, index, retrieve, augment, generate). Each op is a fixed slot pattern; IR is declarative; emitters produce ingestion scripts, retrieval endpoints, or full RAG pipelines.

| Op | Slots | Purpose | IR |
|----|-------|---------|-----|
| **rag.Src** | name type path | Document source (file, url, db) | rag.sources |
| **rag.Chunk** | name source strategy size [overlap] | Chunking config | rag.chunking |
| **rag.Embed** | name model [dim] | Embedding model | rag.embeddings |
| **rag.Store** | name type | Vector store (pgvector, qdrant, memory) | rag.stores |
| **rag.Idx** | name source chunk embed store | Index: source + chunk + embed store | rag.indexes |
| **rag.Ret** | name idx top_k [filter] | Retriever: index, top_k, optional filter | rag.retrievers |
| **rag.Aug** | name tpl chunks_var query_var out | Augment: template, vars → prompt var | rag.augment |
| **rag.Gen** | name model prompt_var [out] | Generate: LLM model, prompt var → out | rag.generate |
| **rag.Pipe** | name ret aug gen | Pipeline: wire retriever + augment + gen | rag.pipelines |

- **Individually:** Emit “chunk only,” “embed only,” “retrieve only,” or “generate only” from the corresponding `rag.*` entry.
- **Together:** Emit one pipeline (e.g. Python or a label with R rag.Ret / R rag.Aug / R rag.Gen) from `rag.pipelines` or from a label that references rag steps. Core can invoke rag via **R rag.Ret** ret_name query_var top_k ->out (and similar) when a rag adapter is registered.

---

## 4. Normalized IR schema (summary)

```text
IR = {
  ver?, compat?
  services: { [name]: { mode, path, eps?, ui?, auth?, _boundaries?, _contracts?, ... } }
  types: { [name]: { fields, optional?, required?, relations?, indexes? } }
  labels: { [id]: {
      nodes: [ { id, op, effect?, ... } ]   // canonical
      edges: [ { from, to, port? } ]
      legacy?: { steps: [ ... ] }           // non-canonical; must round-trip to graph
    }
  }
  crons: [ { label, expr } ]
  config, observability, deploy, limits, roles, allow, audit, admin
  fe: { ui, routes, layouts, forms, tables, events, tokens?, ... , retry? }
  api, desc, runbooks, tests
  rag?: { sources, chunking, embeddings, stores, indexes, retrievers, augment, generate, pipelines }
}
```

**Rule:** Only `services`, `types`, `labels` (graph), and `crons` (and adapter config implied by Q, Sc, P, C) drive execution. All other keys are metadata for emitters.
Canonical runtime execution lives in `runtime/engine.py` (`RuntimeEngine`); compatibility API lives in `runtime/compat.py` (`ExecutionEngine`, re-exported by `runtime.py`).

---

## 5. Validation ruleset (for 3B and tooling)

1. **Module–op consistency** — Prefixed statement → op must belong to that module.
2. **No cross-domain overloading** — No same unqualified op name with different semantics in different modules; use distinct names (e.g. **Retry** vs **fe.FetchRetry**).
3. **Core-only in labels** — Inside a label body, only executable step ops: R, J, If, Err, Retry, Call, Set, Filt, Sort.
4. **Slot arity and shape** — Fixed slot pattern per op; extra or missing slots → invalid.
5. **Reference validity** — Target labels in If/Call/Err must exist; `ref` in Set/Filt/Sort must be defined earlier or by Call.
6. **Graph acyclicity (optional)** — Per-label subgraph acyclic except Retry wrapper; no cycles except via Call/Return.
7. **Metadata preservation** — Preserve every metadata op in IR; store under module key or `meta: [ { module, op, slots } ]`.

---

## 6. Surface syntax and bytecode

**The canonical IR graph is the source of truth.** AINL surface syntax is a **transport, cache, and debugging format**; agents may generate it for bootstrap or inspection, but the real program is the graph. As tooling matures, agents can manipulate graphs (or bytecode) directly; human tools render IR/BC into oversight reports and diffs, not AINL text.

**Target stack:** Surface syntax = training/bootstrap. Canonical graph JSON = runtime. AINL-BC = storage/interchange. Human oversight = semantic diff reports and emitted artifacts.

**AINL-BC** is a deterministic encoding of the canonical IR graph. It may become the **primary storage and interchange format** for agent-generated programs.

- **Scope:** Encoding of the canonical label graph (nodes, edges, effect), plus var table and metadata blobs (namespaced).
- **Property:** AINL-BC decodes to the same nodes/edges as the canonical IR; no new semantics.
- **Use:** Compact, parseable target for small models and tooling without re-parsing surface syntax; enables “AI-native bytecode” as the real storage format while AINL text remains the easiest format to bootstrap today.

A future note can define a concrete layout (op enum, var table, node table, edge table, metadata blobs).

---

## 7. Module op lists (quick reference)

- **core (executable):** S, D, E, L, R, J, If, Err, Retry, Call, Set, Filt, Sort, Inc  
- **core (declarations, non-executable):** U, T, Rt, Lay, Fm, Tbl, Ev, A, Q, Sc, Cr, P, C  
- **ops:** Env, Sec, M, Tr, Deploy, EnvT, Flag, Lim  
- **fe:** Tok, Brk, Sp, Comp, Copy, Theme, i18n, A11y, Off, Help, Wiz, fe.FetchRetry  
- **arch:** Svc, Contract, Rel, Idx, API, Dep, SLA, Adm, Desc, Run  
- **test:** Tst, Mock  
- **rag:** rag.Src, rag.Chunk, rag.Embed, rag.Store, rag.Idx, rag.Ret, rag.Aug, rag.Gen, rag.Pipe (within module rag, ops appear as rag.Src, rag.Chunk, …)  
- **top-level:** Ver, Compat, Role, Allow, Aud  

---

## 8. Backward compatibility

- Unprefixed core ops remain valid. **V** is deprecated in favor of **Set** / **Filt** / **Sort**. Surface aliases (e.g. `FRetry`, `RagSrc`) are **surface-only** and must normalize to canonical op names in IR.
- Step-list form remains an allowed serialization; compilers may emit both `legacy.steps` and `nodes`/`edges`. Semantics are defined by the graph.

This keeps the thesis intact: **core is small and executable; declarations and metadata are named, modular, and do not enlarge the reasoning surface for small models.**
