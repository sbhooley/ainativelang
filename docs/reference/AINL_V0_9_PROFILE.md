# AI Native Lang (AINL) v0.9 – Small‑Model Profile

This document defines a **tiny, stable subset of AINL 1.0** that is optimized for 3B–7B parameter models running offline or in constrained settings.

It is a **profile of the full spec** in `AINL_SPEC.md`. Everything here is backwards‑compatible with 1.0; it just narrows the surface area and semantics.

Related references:

- `RUNTIME_COMPILER_CONTRACT.md` (runtime/compiler ownership and compatibility)
- `reference/IR_SCHEMA.md` (machine-readable IR shape)
- `reference/GRAPH_SCHEMA.md` (canonical graph shape)
- `CONFORMANCE.md` (current shipped behavior)

---

## 1. Goals

- **Tiny grammar**: a minimal set of statements that cover 80% of automation tasks.
- **Deterministic semantics**: every construct has a single, obvious meaning.
- **Graph‑first**: programs are compiled and executed as graphs; step lists are legacy.
- **Agent‑friendly**: all validation errors and debug artifacts are structured and machine‑readable.

This profile is intended as the **default target** for small models learning AINL.

---

## 2. Core statement set (beginner profile)

The beginner profile allows only the following core statements:

- `S` – service header
- `E` – HTTP endpoint binding
- `L` – label block
- `R` – adapter call (I/O)
- `J` – return / jump to endpoint return value
- `If` – conditional branch between labels
- `Err` – error handler binding
- `Call` – invoke another label
- `Cr` – cron schedule

All other ops from the full spec (UI, tests, policies, FE modules, etc.) are **allowed** in advanced profiles, but small‑model training should start with this subset.

### 2.1 Canonical forms

Within this profile, the **canonical forms** for the most important ops are:

- Service:

  ```text
  S core web /api
  ```

- Endpoint:

  ```text
  E /users G ->L1 ->users
  ```

- Label:

  ```text
  L1:
    R db.F User * ->users
    J users
  ```

- Adapter call:

  ```text
  R adapter.verb Target arg1 arg2 ... ->out
  ```

- Branch:

  ```text
  If cond ->L_then ->L_else
  ```

- Error handler:

  ```text
  Err ->L_err
  ```

These forms are the ones used in **examples and corpus** so small models see a single pattern repeatedly.

---

## 3. Deterministic semantics

- **Graph canonicalization**: the compiler always emits canonical graphs (`labels[id].nodes/edges/entry/exits`) and a stable `graph_semantic_checksum`.
- **Runtime mode**: default `execution_mode` is `graph-preferred`; when a label has a graph, the runtime executes it.
- **Effects**:
  - `R` nodes are `effect_tier = "io-read" | "io-write" | "io"` depending on adapter.
  - `If`, `Call`, `Set`, `Sort`, etc. are pure unless they contain an `io` node in their subgraph.
- **Single exit**: each reachable label must terminate with exactly one `J` (strict mode).
- **Literal disambiguation (strict mode)**: bare identifier-like read tokens are treated as variables; quote string literals explicitly in read slots.

These semantics are enforced by `compiler_v2.py` and the runtime engine.

---

## 4. Validation & errors

The compiler and tooling guarantee:

- **Strict structural validation**:
  - Canonical graph invariants (entry, nodes, edges, exits).
  - No undefined label targets.
  - Single `J` at the end of reachable labels.
  - Adapter contracts (known `adapter.verb`, correct arity).
  - Defined‑before‑use for variables at graph level.
- **Machine‑readable result**:
  - IR always contains `errors: [str]`, `warnings: [str]`.
  - Tooling adds `graph_semantic_checksum` and per‑label/node hashes.
  - `tooling/oversight.runtime_debug_envelope` emits a **single debug object** per run with `error`, `trace_tail`, `focus`, and a compact graph slice.

Small models should be trained to:

1. Compile.
2. Inspect `errors` and `warnings`.
3. Optionally inspect the debug envelope.
4. Modify the program or emit a compact patch.

---

## 5. Adapters in this profile

For the v0.9 profile, recommended adapters are:

- `db.*` – database CRUD (read‑heavy to start).
- `http.*` – outbound HTTP requests (GET/POST).
- `queue.*` – simple enqueue operations.
- `cache.*` – cache get/set.

Each adapter is documented in `ADAPTER_REGISTRY.md` with:

- `name` and availability.
- Input slots and expected types.
- Output variables and typical shapes.
- Example `R` statements.

---

## 6. Examples and patterns

See:

- `examples/web/basic_web_api.ainl` – small JSON API.
- `examples/scraper/basic_scraper.ainl` – fetch, parse, store.
- `examples/cron/monitor_and_alert.ainl` – periodic check + alert.
- `docs/PATTERNS.md` – reusable graph/label patterns (retry, rate limiting, etc.).

All examples are written **only** in the v0.9 subset to keep training distribution clean.

---

## 7. Advanced profile (opt‑in)

The following features are **available but not part of v0.9 beginner profile**:

- UI declarations and FE modules (`U`, `T`, `Rt`, `Lay`, `Fm`, `Tbl`, `Ev`, `fe.*`).
- Policy and auth modules (`Pol`, `Enf`, `auth.*`).
- RAG and search modules (`rag.*`).
- WASM adapters and custom compute.

Small models should only opt into these once they reliably handle the v0.9 core.

