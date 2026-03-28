# Code context adapter (`code_context`)

`code_context` is an optional AINL runtime adapter for **tiered codebase context**: index a local tree into a JSON file, then query signatures, summaries (TF–IDF), full source, **import-based dependencies**, **reverse impact** (who imports whom, plus a PageRank-style score), or **greedy token-budget packing** on demand.

Design lineage:

- **Tiered retrieval** is inspired by [BradyD2003/ctxzip](https://github.com/BradyD2003/ctxzip); full credit to **Brady Drexler** for the original idea. This repository ships a **clean re-implementation** for AINL’s adapter system (not a fork of upstream code).
- **Import graph, transitive importers (“impact”), PageRank-style importance, and knapsack-style compression under a token budget** borrow ideas from import-graph tooling in the [chrismicah/forgeindex](https://github.com/chrismicah/forgeindex) ecosystem. Credit to **Chris Micah** and the forgeindex project; the implementation here is **independent** (not a fork of forgeindex).

## How this helps coding agents

Skeleton views (**`GET_SKELETON`**) give a cheap, token-light map of symbols before full retrieval. **`COMPRESS_CONTEXT`** can use the same embedding pipeline as **`embedding_memory`** (when that adapter is importable and embedding succeeds) to rank chunks by cosine similarity before greedy packing—falling back to TF–IDF when not. Extended **`STATS`** exposes graph size and top PageRank mass so agents can reason about index shape and dependency centrality without running separate queries.

Future iterations could add more advanced skeletonization (e.g. control-flow or dependency-aware views) while staying inside the existing adapter.

Run **`INDEX`** once per workspace so chunks live in persistent JSON; in the agent loop, use **`QUERY_CONTEXT`** at **Tier 1** for token-efficient signatures plus doc/summary, and escalate to **Tier 2** or **`GET_FULL_SOURCE`** only when a specific implementation is needed. **`COMPRESS_CONTEXT`** ranks chunks the same way as **`QUERY_CONTEXT`** (TF–IDF) but **packs** signature + summary lines until a **token budget** (heuristic: ~4 characters per token) is exhausted—useful when you need a single bounded blob for the prompt.

Use **`GET_DEPENDENCIES`** / **`GET_IMPACT`** to see **chunk-level** edges derived from **`import` / `from`** (Python) and **`import` / `require`** (JS/TS), resolved to indexed files. **`GET_IMPACT`** returns direct importers, all transitive importers (reverse graph reachability), and a **global PageRank** score on the forward graph (chunk *A* → *B* if *A*’s chunk source resolves an import to *B*’s file’s canonical chunk). **`STATS`** gives quick visibility into index size and freshness without pulling code into the prompt.

## Enablement

- **CLI**: `ainl run … --enable-adapter code_context`
- **Store**: default `.ainl_code_context.json` in the current working directory; override with **`AINL_CODE_CONTEXT_STORE`**.

If the adapter is not enabled, `code_context` calls fail at runtime like other opt-in adapters.

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
R code_context.GET_SKELETON "_" ->skel
R code_context.GET_SKELETON "path/to/file.py" ->skel2
R code_context.GET_DEPENDENCIES "chunk_id" ->deps
R code_context.GET_IMPACT "chunk_id" ->impact
R code_context.COMPRESS_CONTEXT "search terms" 32000 ->packed
R code_context.STATS "_" ->stats
```

**`STATS`** has no logical parameters; use a placeholder token such as `"_"` after the dotted verb so strict-mode `R` lines parse (the adapter ignores it). Alternatively, **split** form works with no placeholder: `R code_context STATS ->stats` (same as other zero-arg reads, e.g. `R ptc_runner health ->h`).

| Verb | Arguments | Returns |
|------|-----------|---------|
| `INDEX` | `path` (directory) | `{ "ok": true, "chunks": <n> }` |
| `QUERY_CONTEXT` | `query`, optional `max_tier` (0–2), optional `limit` | string (tiered text) |
| `GET_FULL_SOURCE` | `chunk_id` | string |
| `GET_SKELETON` | optional path or one or more `chunk_id` (no filter → use `"_"` as a parse placeholder for “all”, capped at 100 chunks) | string (Tier 0–style lines: `path:line  signature`) |
| `GET_DEPENDENCIES` | `chunk_id` | list of chunk ids (forward deps, sorted) |
| `GET_IMPACT` | `chunk_id` | `{ "chunk_id", "direct_importers", "transitive_importers", "pagerank" }` |
| `COMPRESS_CONTEXT` | `query`, optional `max_tokens` (default 32000) | string (packed signatures + summaries); ranks by **embedding cosine** vs query when `embedding_memory` embed succeeds, else **TF–IDF** |
| `STATS` | (none) | `{ "chunks", "indexed_root", "store_path", "updated_at", "num_nodes", "num_edges", "top_pagerank" }` — `top_pagerank` is up to 5 `{ "chunk_id", "score" }` entries |

Chunk ids are stable strings of the form `kind:path:name@start_line:<hash>` (see `adapters/code_context.py`). Use **`QUERY_CONTEXT`** output or the JSON store to obtain ids.

## Direct Python helpers

The module exposes `index_repository`, `query_context`, `get_full_source`, `get_skeleton`, `get_dependencies`, `get_impact`, and `compress_context` for scripts and tests (same defaults as the adapter). See `adapters/code_context.py`.

## Example graph

Runnable demo: [`../../examples/code_context_demo.ainl`](../../examples/code_context_demo.ainl).

## See also

- README: hybrid adapters section (quick narrative + AINL snippet).
- [`../reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) — adapter inventory.
