# AI Native Lang (AINL) 1.0 — Grammar & Ops Reference

**Version: 1.0** — Stable for conformance tests and model training. *Formerly referred to as v2 draft; AINL 1.0 is the normative name.*

**Formal grammar and conformance:** see [AINL_SPEC.md](../AINL_SPEC.md) and [CONFORMANCE.md](../CONFORMANCE.md).
**Compiler/runtime decoding contract:** see [RUNTIME_COMPILER_CONTRACT.md](../RUNTIME_COMPILER_CONTRACT.md).

**Ownership split (for contributors):**
- Grammar law and prefix transition helpers live in `compiler_v2.py`.
- Formal orchestration/admissibility lives in `compiler_grammar.py`.
- Non-authoritative candidate priors live in `grammar_priors.py`.
- Compatibility composition APIs live in `grammar_constraint.py`.

## Syntax

- **Format**: One op per line. `OP slot1 slot2 ...` (space-delimited).
- **Comments**: `#` to end of line, only when not inside a double-quoted string.
- **Labels**: `L<id>:` starts a block. Following **executable step ops** belong to that label until next `L<id>:` or EOF. Only executable step ops are allowed inside a label: `R J If Err Retry Call Set Filt Sort`. Inline form `L1: R ... J var` is allowed on the same line. **P is declaration-only** (not a step); payment in labels uses `R pay.*`.
- **Lexical:** Strings = double quotes only; no multiline; escape `\"` and `\\`. Identifiers = alphanumeric + underscore (dot allowed e.g. in fe tokens). Path = `/`-prefixed. Enum = `E[Id1,Id2,...]`.
- **Strict literal policy:** In strict mode, bare identifier-like tokens in read positions are interpreted as variable references. If intent is a string literal, quote it explicitly (e.g. `Set out "ok"` not `Set out ok`).

---

## Original 10 Ops (Stats)

| Op | Name       | Slots (typical)              | Purpose                          | IR key        |
|----|------------|------------------------------|----------------------------------|---------------|
| **S** | Service   | `name mode [path]`            | Declare backend/front service    | `services`    |
| **D** | Data      | `TypeName f1:T1 f2:T2 ...`   | Entity/type with fields          | `types`       |
| **E** | Endpoint  | `path METHOD ->Lbl`          | HTTP endpoint → label            | `services[srv].eps` |
| **L** | Label     | `L1:` (op) `slot1 slot2`     | Block target for E; holds R/J    | `labels`      |
| **R** | Request   | `src.Op Entity * ->out`      | Data op: db.F, api.G, etc.       | per-label     |
| **J** | JSON      | `var`                        | Return JSON from var              | per-label     |
| **U** | UI        | `Name [Component props...]`  | Screen/component                | `services.fe.ui` |
| **T** | State     | `var:T` or `var:A[Type]`     | UI state (attaches to current U) | `ui.states`   |
| *(reserved)* | | | | |
| *(reserved)* | | | | |

**Stats (original)**: 8 primary ops (S, D, E, L, R, J, U, T). Two slots reserved for future (e.g. auth, middleware).

---

## Proposed 5 New Ops

| Op | Name    | Slots (typical)           | Purpose                    | IR key              |
|----|---------|---------------------------|----------------------------|----------------------|
| **Q** | Queue  | `name maxSize [retry]`    | Queue def (e.g. Bull/Redis)| `services.queue.defs` |
| **Sc** | Scrape | `name url sel1=field1 …` | Scraper: URL + CSS selectors → fields | `services.scrape.defs` |
| **Cr** | Cron   | `label cron_expr`         | Cron: run label at schedule | `labels.cron` or `crons` |
| **P** | Pay    | `name amount currency [desc]` | Stripe payment intent   | `services.pay.defs`  |
| **C** | Cache  | `name key ttl [default]`  | Redis cache get/set        | `services.cache.defs` |

---

## Op Details

### S (Service)
- `S core web /api` → backend `core`, mode `web`, path `/api`
- `S fe web /` → frontend service
- **`S hybrid`** (deployment hint, not a network service): `S hybrid langgraph`, `S hybrid temporal`, or `S hybrid langgraph temporal` — records targets under IR **`services.hybrid.emit`** (de-duped), sets **`emit_capabilities.needs_langgraph`** / **`needs_temporal`**, and can add **`langgraph`** / **`temporal`** to **`required_emit_targets.minimal_emit`** for benchmarks/planners. Strict mode: only **`langgraph`** and **`temporal`** are valid target tokens. Normative spec: **[`docs/AINL_SPEC.md`](../AINL_SPEC.md) §2.3.1**.

### D (Data / Type)
- Field types: `I` int, `S` string, `E[Ad,Us]` enum, `A[User]` array of type.

### E (Endpoint) — explicit path → label → return
- `E /users G ->L1` → GET `/users` runs label L1 (return var inferred from J in L1).
- **Explicit return:** `E /products G ->L1 ->products` → GET `/products`, run L1, return var `products`. If `E` specifies `->return_var`, it **must match** the label's terminal `J` var; else validation fails. If omitted, infer from terminal `J`.
- `E /order P ->L2` → POST `/order` runs L2.
- Stored in IR: `method`, `tgt`, `label_id`, `return_var` (optional).

### R (Request) — canonical form
- **Pattern:** `R <adapter>.<verb> <target> [args...] -><out>`. adapter = db | api | pay | cache | scrape | rag | …; verb = adapter-defined (fixed arity per adapter.verb preferred). target = entity or path; args = adapter-specific; ->out = result context key.
- `R db.F User * ->us` → DB Find User, all fields → var `us`
- `R api.G /external ->res` → API GET `/external` → var `res`
- `R rag.Ret ret1 query 5 ->chunks` → rag retriever `ret1`, query var `query`, top_k 5 → `chunks`

### J (JSON return)
- `J us` → return JSON from variable `us` (in same label as R).
- In strict mode, returning unbound bare identifier-like tokens is a defined-before-use error; quote literals when literal intent is required upstream.

### T (State)
- `T us:A[User]` → state `us` of type array of User (attaches to current U).

### Q (Queue)
- `Q orders 100 3` → queue `orders`, max 100, retry 3.

### Sc (Scrape)
- `Sc products https://shop.com list=.item title=h2` → scrape `products`, URL + selectors.

### Cr (Cron)
- `Cr L1 */5 * * * *` → every 5 min run label L1.

### P (Pay) — declaration only
- `P checkout 1999 usd "Order"` → payment definition (non-executable). In labels use `R pay.Charge checkout ... ->receipt` (or adapter verb) for payment execution.

### A (Auth)
- `A jwt Authorization` → API auth: kind `jwt`, header `Authorization`; emitted server uses Depends to require header (401 if missing). Stored in `services["auth"]` with `kind`, `arg` (header name), optional `extra`.
- `A apikey X-API-Key` → API-key auth; same middleware, validate key per backend.

### C (Cache)
- `C sess sessionId 3600` → cache `sess`, key `sessionId`, TTL 3600s.

---

## Front-end spec (routes, layout, forms, tables, events)

| Op  | Name   | Slots (typical)        | Purpose                          | IR key           |
|-----|--------|-------------------------|----------------------------------|------------------|
| **Rt** | Route  | `path UIName`           | Which path renders which UI      | `fe.routes`      |
| **Lay** | Layout | `ShellName slot1 slot2`  | Layout shell with named slots    | `fe.layouts`     |
| **Fm** | Form   | `FormName TypeName f1 f2` | Form for type, fields list     | `fe.forms`       |
| **Tbl** | Table  | `TableName TypeName c1 c2` | Table columns for type       | `fe.tables`      |
| **Ev** | Event  | `Component event target` | Bind event to label or path   | `fe.events`      |

### Rt (Route)
- `Rt / Dashboard` → path `/` renders UI `Dashboard`.
- `Rt /orders OrderTable` → `/orders` renders `OrderTable`.

### Lay (Layout)
- `Lay Shell Sidebar Main` → layout `Shell` has slots `Sidebar`, `Main` (emitted as wrapper with outlet).

### Fm (Form)
- `Fm OrderForm Order id uid total status` → form for type `Order`, fields listed.

### Tbl (Table)
- `Tbl OrderTable Order id uid total status` → table with columns for type `Order`.

### Ev (Event)
- `Ev CheckoutBtn click L3` → when `CheckoutBtn` gets `click`, run label L3 (e.g. POST).
- `Ev CheckoutBtn click /checkout` → on click, POST `/checkout`.

---

## Extensions (Core + modules)

- **Core (label steps):** If cond ->Lthen [->Lelse], Err [@node_id] ->Lhandler (step-list: bare = previous node), Retry [@node_id] count [backoff_ms] (step-list: bare = previous node), Call Lid [->out] (if ->out omitted, callee must have exactly one J), Set name ref, Filt name ref field cmp value, Sort name ref field [asc|desc]. Inc path (include .lang).
- **Ops (metadata):** Env name [required|optional] [default], Sec name ref, M name counter|histogram, Tr on|off, Deploy strategy, EnvT staging|prod, Flag name [default], Lim path rpm | Lim tenant rpm.
- **RBAC / audit / admin:** Role name, Allow role path method | Allow role UI, Aud event retention_days, Adm UIName [entities...].
- **Versioning / testing:** Ver 1.0, Compat break|add, Tst L1, Mock adapter key value.
- **Desc / data:** Desc path "text" | Desc TypeName "text", Rel Type1 hasMany|belongsTo Type2 [fk], Idx Type field...
- **Arch:** Svc name [path_prefix], Contract path method [response_type], API rest|graphql [version_prefix], Dep path at version, SLA path p99_ms availability, Run name step...
- **Fe (metadata):** Tok name value, Brk name value, Sp name value, Comp Name slots..., Copy key text, Theme dark|light, i18n key text, A11y UI label, Off path [ttl], Help UI content_key, Wiz UI step..., fe.FetchRetry (surface FRetry) count backoff_ms.

- **Rag (module):** rag.Src name type path | rag.Chunk name source strategy size [overlap] | rag.Embed name model [dim] | rag.Store name type | rag.Idx name source chunk embed store | rag.Ret name idx top_k [filter] | rag.Aug name tpl chunks_var query_var out | rag.Gen name model prompt_var [out] | rag.Pipe name ret aug gen. Build RAG piece-by-piece or one pipeline. Surface forms RagSrc, RagChunk, … allowed.

See [AINL_CORE_AND_MODULES.md](AINL_CORE_AND_MODULES.md) for namespaced grammar and IR.

---

## Totals

- **Ops**: 10 original + 5 (Q,Sc,Cr,P,C) + 5 front-end (Rt,Lay,Fm,Tbl,Ev) + A + extensions above.
- **Stats**: `lines`, `ops` in IR.
