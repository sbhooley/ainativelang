# Adapters

Use this section to understand how AINL reaches external systems and how capabilities, effects, and host bindings are modeled.

## Key docs

- [`../reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) — adapter inventory and contracts
- [`../integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](../integrations/EXTERNAL_EXECUTOR_BRIDGE.md) — JSON body contract for `http.Post` / `bridge.Post` to external workers; [`../../schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json), [`../../modules/common/executor_bridge_request.ainl`](../../modules/common/executor_bridge_request.ainl)
- [`OPENCLAW_ADAPTERS.md`](OPENCLAW_ADAPTERS.md) — OpenClaw integration guide (adapter verbs / bridge); **OpenClaw MCP skill:** [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) · **ZeroClaw** MCP skill: [`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)
- [`../operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md) — bridge token budget, weekly trends, daily markdown **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`**, cron, sentinel, env vars
- [`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md) — memory contract and state surfaces
- [`AINL_GRAPH_MEMORY.md`](AINL_GRAPH_MEMORY.md) — **`ainl_graph_memory`** (JSON graph store, ArmaraOS bridge), IR ops **`MemoryRecall`** / **`MemorySearch`**, **`EdgeType`** (structural + epistemic edges), **`persona.update`** → bridge **`persona_update`**, optional graph viz server; demos **`demo/procedural_roundtrip_demo.py`**, **`demo/ainl_graph_memory_demo.py`** · tests **`tests/test_semantic_edges.py`**
- [`MEMORY_CONTRACT.md`](MEMORY_CONTRACT.md) §3.7 — SQLite **`ainl_memory_patterns`**, **`memory.store_pattern`** / **`recall_pattern`**, runtime **`memory.merge`** / **`MemoryMerge`** (live IR re-injection) · **`tests/test_memory_merge.py`**
- [`MEMORY_CONTRACT_V1_1_RFC.md`](MEMORY_CONTRACT_V1_1_RFC.md) — additive v1.1 proposal for deterministic query metadata and filters
- **Opt-in access metadata on memory rows** (bump `last_accessed` / `access_count` on read, list, or write): source module [`../../modules/common/access_aware_memory.ainl`](../../modules/common/access_aware_memory.ainl), index [`../../modules/common/README.md`](../../modules/common/README.md); graph-safe list path: **`LACCESS_LIST_SAFE`**
- **Local Hyperspace-oriented adapters** (JSON files under cwd; no extra deps): **`vector_memory`** — keyword overlap search / upsert ([`../../adapters/vector_memory.py`](../../adapters/vector_memory.py)); **`tool_registry`** — list / get / register / discover ([`../../adapters/tool_registry.py`](../../adapters/tool_registry.py)). Enable with `ainl run --enable-adapter vector_memory --enable-adapter tool_registry`. Env: `AINL_VECTOR_MEMORY_PATH`, `AINL_TOOL_REGISTRY_PATH`. Catalog: [`../reference/ADAPTER_REGISTRY.md`](../reference/ADAPTER_REGISTRY.md) §9. Used by the **`--emit hyperspace`** agent ([`../emitters/README.md`](../emitters/README.md)).
- **Tiered code context (optional)**: **`code_context`** — index a repo to JSON; TF–IDF tiers (`INDEX`, `QUERY_CONTEXT`, `GET_FULL_SOURCE`, `STATS`); import graph (`GET_DEPENDENCIES`), impact + PageRank (`GET_IMPACT`), greedy token budget (`COMPRESS_CONTEXT`). [`CODE_CONTEXT.md`](CODE_CONTEXT.md), [`../../examples/code_context_demo.ainl`](../../examples/code_context_demo.ainl), **`--enable-adapter code_context`** on **`ainl run`**, `AINL_CODE_CONTEXT_STORE`.

## Related sections

- Runtime behavior: [`../runtime/README.md`](../runtime/README.md)
- Advanced/operator-only docs: [`../advanced/README.md`](../advanced/README.md)
- Operations and monitors: [`../operations/README.md`](../operations/README.md)
