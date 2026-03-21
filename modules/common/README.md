# `modules/common`

Shared **strict-safe** `.ainl` helpers (compile-time `include`).

Place **`include ".../foo.ainl"` lines before any top-level `S` / `E` line** in the host program so the compiler prelude merges module labels (otherwise `Call alias/...` targets are missing from IR).

- **`access_aware_memory.ainl`** — opt-in helpers for explicit recency/frequency tracking via `metadata.last_accessed` and `metadata.access_count`. Use **`LACCESS_READ`** and **`LACCESS_WRITE`** for single-record flows (graph-safe). For list results, prefer **`LACCESS_LIST_SAFE`** (While + index loop, graph-safe); **`LACCESS_LIST`** remains available but uses `ForEach`, which may not fully run nested touches in graph-preferred mode until the compiler emits it as a `Loop` (see the module header). Plain `memory.get` / `memory.list` / `memory.put` stay side-effect free.
- **`distill_pattern.ainl`** — optional pattern: short-TTL session capture → durable `long_term` facts with null TTL. Pairs well with access-aware helpers when you want to see which distilled rows are referenced often.
