# MCP Research Contract (Hyperagent Pack)

This document defines additive MCP tool contracts intended for self-improving research loops.

## Stability note (v1.5.0 release line)

The following fields are considered stable in the v1.2.7+ research pack surface (current **`RUNTIME_VERSION`** **1.5.0**):

- `ainl_validate(...).diagnostics[].llm_repair_hint`
- `ainl_ir_diff(...).diff.changed_nodes[]` as a list of `{label_id, node_id, changes}`
- `ainl_fitness_report(...).metrics.fitness_score`
- `ainl_fitness_report(...).metrics.fitness_components.weights`
- `ainl_compile(...).frame_hints[]` as a list of `{name, type, source}` — added v1.4.3 (present only when `ok: true`)

Future versions may add fields but should not remove or rename these without a versioned migration note.

## Tools

- `ainl_validate(code, strict=True)`
  - Returns: `ok`, `errors`, `warnings`, `diagnostics[]`
  - Contract: each diagnostic includes `llm_repair_hint`.

- `ainl_compile(code, strict=True)`
  - Returns: `ok`, `ir`, `frame_hints[]`
  - `frame_hints` is a list of `{"name": str, "type": str, "source": "comment"|"inferred"}` entries describing variables the caller should supply via `frame` when calling `ainl_run`. Authoritative entries come from `# frame: name: type` (or `# frame: name`, which sets `type` to `"any"`) comment lines in source; additional heuristic entries are inferred from IR variables referenced but never assigned. Best-effort — may include false positives for inferred entries.
  - Workflow: call `ainl_compile` first to discover `frame_hints`, then construct the `frame` dict and call `ainl_run`.

- `ainl_ir_diff(file1, file2, strict=True)`
  - Returns: `ok`, `diff`
  - `diff` keys: `added_nodes`, `removed_nodes`, `changed_nodes`, `added_edges`, `removed_edges`, `rewired_edges`, `human_summary`.
  - Contract: `changed_nodes` includes payload-level `data` deltas when node op shape is unchanged but node data changed.

- `ainl_fitness_report(file, runs=5, strict=True)`
  - Returns: `ok`, `metrics`, `sample_runs`, `last_error`
  - `metrics` keys:
    - `latency_ms`, `step_count`, `adapter_calls`
    - `memory_deltas` (trace-derived frame-key proxy)
    - `operation_histogram`
    - `token_use_estimate`
    - `reliability_score`
    - `fitness_score` in `[0,1]`
    - `fitness_components` with explicit component values and `weights`

## Scoring stability guidance

- Treat `fitness_components.weights` as the live source of truth.
- Consumers should not hard-code weight constants without checking the payload.
- Rank by `fitness_score`; use component breakdown for tie-breaks and debugging.

## `ainl_run` execution contract (v1.4.3+; current package **1.5.0**)

### Variable shadowing in `R` arguments

String literals in `R` arg positions (e.g. `"records"`) are compiled without quotes and resolved against the live frame before being treated as literals. If a frame variable named `records` exists, `R core.GET data "records"` will pass the list, not the string. **Prevention:** use unique variable name prefixes per label scope.

### Per-workspace limit overrides

Place `ainl_mcp_limits.json` at `<fs.root>/ainl_mcp_limits.json` to adjust limits for that workspace without modifying global server config:

```json
{"max_steps": 500000, "max_time_ms": 900000, "max_adapter_calls": 50000}
```

The server default ceiling still wins via restrictive merge — this file can only tighten or match defaults, not exceed the server ceiling.

If `ainl_mcp_limits.json` is present but cannot be parsed as JSON, limits fall back to server defaults and a successful `ainl_run` may include `warnings` (string list) explaining that the file was ignored.

**`max_adapter_calls`:** A value of **`0`** is a real ceiling (no adapter calls). Positive integers cap total adapter dispatches (`R` lines, cache/queue helpers, etc.).

### Auto-registered `cache` adapter

When the `fs` adapter is enabled in `ainl_run` and no `cache` adapter is explicitly listed in `adapters.enable`, the MCP server will automatically register the `cache` adapter if any of these files exist:
- `<fs.root>/output/cache.json`
- `<fs.root>/cache.json`

This makes per-workspace caching zero-config for scripts that already have a cache file. Explicit `"cache"` in `adapters.enable` always takes precedence.

Before registration, a **non-empty** candidate file must contain valid JSON; otherwise `ainl_run` returns `{"ok": false, "error": "adapter_config_error", "details": "…"}`. An empty file (0 bytes) is skipped by the pre-check and handled by the adapter as an empty object store.

**Interaction with `RuntimeEngine`:** graphs that reference `cache` may still get a default file-backed `cache` adapter from the engine when no MCP-scoped adapter was registered — that default uses `AINL_CACHE_JSON` / `MONITOR_CACHE_JSON` / `~/.openclaw/ainl_cache.json`. To prove the workspace path in tests, isolate `HOME` and seed only `<fs.root>/…/cache.json`.

### `frame` declaration convention

Document expected frame variables in source using comment lines:

```ainl
# frame: search_body: dict
# frame: req_headers: dict
S app core noop
...
```

These are picked up by `ainl_compile` and returned in `frame_hints` so agents can auto-construct the `frame` argument before calling `ainl_run`.

## Authoring wizard, strict-valid family index, and contract alignment (v1.7.x)

The MCP server also ships:

- **`ainl_get_started`** — pass **`wizard_state_json`** to continue a wizard session; returns checkpoints and `wizard_state` for hosts that persist digests to graph memory.
- **`ainl_step_examples`** — strict-valid **snippets** and optional corpus paths by topic, without advancing wizard state; includes `schema_version` in the response.
- **`ainl://strict-valid-families`** — JSON mined into **`corpus/strict_valid_family_index.json`** (regenerate with **`tooling/corpus_mining.py`**).
- On successful **`ainl_validate`** / **`ainl_compile`**: **`contract_validation_status`** and **`contract_alignment`**, with **`mismatched_calls`** listing adapter/verb rows that do not match the get-started `ADAPTER_CONTRACTS` bundle (non-fatal warnings; see source for exact schema).

**Full reference:** **[`MCP_AINL_WIZARD_AND_CORPUS.md`](MCP_AINL_WIZARD_AND_CORPUS.md)**. **ArmaraOS** prompt and graph tags: **`armaraos/docs/mcp-a2a.md`**.
