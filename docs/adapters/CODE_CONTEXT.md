# Code context adapter (`code_context`)

`code_context` is an optional AINL runtime adapter for **tiered codebase context**: index a local tree into a JSON file, then query signatures, summaries (TF–IDF), or full source on demand. The design is inspired by [BradyD2003/ctxzip](https://github.com/BradyD2003/ctxzip); full credit to **Brady Drexler** for the original idea. This repository ships a **clean re-implementation** for AINL’s adapter system (not a fork of upstream code).

## Enablement

- **CLI**: `ainl run … --enable-adapter code_context`
- **Store**: default `.ainl_code_context.json` in the current working directory; override with **`AINL_CODE_CONTEXT_STORE`**.

If the adapter is not enabled, `code_context` calls fail at runtime like other opt-in adapters.

## How this helps coding agents

Run **`INDEX`** once per workspace so chunks live in persistent JSON; in the agent loop, use **`QUERY_CONTEXT`** at **Tier 1** for token-efficient signatures plus doc/summary, and escalate to **Tier 2** or **`GET_FULL_SOURCE`** only when a specific implementation is needed. **`STATS`** gives quick visibility into index size and freshness without pulling code into the prompt. The tiered flow mirrors how humans skim a repo before reading files in depth.

## Tiers

| Tier | Behavior |
|------|----------|
| **0** | Compact list of all chunk signatures (directory-style). |
| **1** | Top chunks by TF–IDF over indexed text: signature + first-line doc/summary (no external embeddings). |
| **2** | Same ranked chunks as Tier 1, plus full source bodies; or fetch one chunk with **`GET_FULL_SOURCE`**. |

Chunking covers **Python** (`ast`) and **basic JS/TS** (heuristics).

## Verbs (`R code_context.<VERB> …`)

Preferred **dotted** form (matches other memory-style adapters):

```ainl
R code_context.INDEX "/path/to/repo" ->ok
R code_context.QUERY_CONTEXT "search terms" 1 50 ->text
R code_context.GET_FULL_SOURCE "chunk_id" ->src
R code_context.STATS "_" ->stats
```

**`STATS`** has no logical parameters; use a placeholder token such as `"_"` after the dotted verb so strict-mode `R` lines parse (the adapter ignores it). Alternatively, **split** form works with no placeholder: `R code_context STATS ->stats` (same as other zero-arg reads, e.g. `R ptc_runner health ->h`).

| Verb | Arguments | Returns |
|------|-----------|---------|
| `INDEX` | `path` (directory) | `{ "ok": true, "chunks": <n> }` |
| `QUERY_CONTEXT` | `query`, optional `max_tier` (0–2), optional `limit` | string (tiered text) |
| `GET_FULL_SOURCE` | `chunk_id` | string |
| `STATS` | (none) | `{ "chunks", "indexed_root", "store_path", "updated_at" }` |

## Direct Python helpers

The module exposes `index_repository`, `query_context`, and `get_full_source` for scripts and tests (same defaults as the adapter). See `adapters/code_context.py`.

## Example graph

Runnable demo: [`../../examples/code_context_demo.ainl`](../../examples/code_context_demo.ainl).

## See also

- README: hybrid adapters section (quick narrative + AINL snippet).
- [`../reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) — adapter inventory.
