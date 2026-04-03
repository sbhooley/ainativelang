# Wishlist examples (1–8)

These graphs mirror the **agent orchestration wishlist**: caching, vector recall, parallel fan-out, subprocess validation, routed LLM calls, feedback memory, parallel HTTP, and code-context packing.

| # | File | Adapters (typical) | Notes |
|---|------|---------------------|--------|
| 1 | `01_cache_and_memory.ainl` | `cache`, `memory`, `core` | Host sets `AINL_CACHE_JSON`, `AINL_MEMORY_DB`. |
| 2 | `02_vector_semantic_search.ainl` | `vector_memory`, `core` | Keyword overlap scoring; optional embedding backends are separate. |
| 3 | `03_parallel_fanout.ainl` | `fanout`, `core` | Pure parallel calls via `fanout.ALL`. |
| 4 | `04_validate_with_ext.ainl` | `ext` | Requires `AINL_EXT_ALLOW_EXEC=1` and `--enable-adapter ext`. |
| 5 | `05_route_then_llm_mock.ainl` | `llm_query`, `core` | Mock: `AINL_LLM_QUERY_MOCK=true` + `--enable-adapter llm_query`. |
| 5b | `05b_unified_llm_offline_config.ainl` | `llm`, `core` | Unified **`llm`** + **`--config`** / `AINL_CONFIG`. CI uses **`fixtures/llm_offline.yaml`**. For real models, copy **`fixtures/llm_openrouter.example.yaml`** or **`llm_ollama.example.yaml`** (see **`docs/LLM_ADAPTER_USAGE.md`**). |
| 6 | `06_feedback_memory.ainl` | `memory`, `core` | `memory.GET` returns prior turn if you ran `01` or another PUT first. |
| 7 | `07_parallel_http.ainl` | `fanout`, `http` | Opcode `Set` for JSON (URLs with `:` break compact assignments). |
| 8 | `08_code_review_context.ainl` | `code_context`, `core` | Indexes `examples/wishlist` (includes `review_helper.py` for chunks). |

**Validate all (strict):**

```bash
for f in examples/wishlist/0*.ainl; do
  python -m cli.main validate "$f" --strict || exit 1
done
```

**Split:** orchestration lives here (AINL). **ArmaraOS** (or any host) supplies credentials, cwd, adapter allowlists, and when to run — see `armaraos/programs/wishlist-host-kit/README.md` (includes `frames/01.json`–`08.json`, `wishlist_host_smoke.ainl`, and `run_upstream_wishlist.sh`).
