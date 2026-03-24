# `modules/common`

Shared **strict-safe** `.ainl` helpers (compile-time `include`).

**Sibling libraries (repo root `modules/`):**

- **[`modules/llm/`](../llm/README.md)** — reusable LLM / chat-completion snippets (e.g. JSON-only system line). Long product-specific prompt text usually lives as **`.txt` files** beside your gateway and is loaded at runtime (not in `modules/`).
- **`modules/openclaw/`** — OpenClaw-oriented cron sketches (see file headers).

**App-local includes** that only make sense next to one integration (e.g. bridge `req_*` shells + main graph + `gateway_server.py`) live in that app’s tree, not under `modules/common/`.

Place **`include ".../foo.ainl"` lines before any top-level `S` / `E` line** in the host program so the compiler prelude merges module labels (otherwise `Call alias/...` targets are missing from IR).

**Spec / layout:** [docs/language/AINL_CORE_AND_MODULES.md](../../docs/language/AINL_CORE_AND_MODULES.md) §8 (repository include libraries).

- **`access_aware_memory.ainl`** — opt-in helpers for explicit recency/frequency tracking via `metadata.last_accessed` and `metadata.access_count`. Use **`LACCESS_READ`** and **`LACCESS_WRITE`** for single-record flows (graph-safe). For list results, prefer **`LACCESS_LIST_SAFE`** (While + index loop, graph-safe); **`LACCESS_LIST`** remains available but uses `ForEach`, which may not fully run nested touches in graph-preferred mode until the compiler emits it as a `Loop` (see the module header). Plain `memory.get` / `memory.list` / `memory.put` stay side-effect free.
- **`distill_pattern.ainl`** — optional pattern: short-TTL session capture → durable `long_term` facts with null TTL. Pairs well with access-aware helpers when you want to see which distilled rows are referenced often.
- **`executor_bridge_request.ainl`** — `R core.PARSE` on the JSON **string** in frame slot **`ainl_bridge_request_json`** (set with `R core.ECHO "<json>" ->ainl_bridge_request_json` or any step that yields a string). Shared bridge envelope pattern; see [EXTERNAL_EXECUTOR_BRIDGE.md](../../docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md) and [`schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json).
- **`guard.ainl`** — token/time ceilings plus `guard_condition_ok`; optional `guard_skip` and violation `memory.put` audit. Bind frame slots then `Call guard/ENTRY ->out`. Returns `"guard_ok"` / `"guard_violation"`; failure label **`LEXIT_GUARD_VIOLATION`**. Uses `R core.mul` + `R core.clamp` before `If` so standalone `--strict` matches include checks.
- **`session_budget.ainl`** — `R core.ADD` / `SUB`+`clamp` against caps; optional success-row `memory.put`. **`LEXIT_BUDGET_EXCEEDED`** / **`LEXIT_OK`**; helper label **`LBUDGET_RESET`** (echo placeholder). Optional logging gated the same way as guard flags.
- **`reflect.ainl`** — abort / nonempty-trajectory / fail-pattern gates; suggestion via `R core.PARSE` on a constant JSON string into **`reflect_adjustment`**. Set **`reflect_traj_nonempty`** to 0/1 (parent derives from text; avoids `core.len` in strict). **`LEXIT_REFLECT_ABORT`**, optional **`LREFLECT_AUDIT`** for a static memory row.
