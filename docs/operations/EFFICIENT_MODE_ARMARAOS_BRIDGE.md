# Efficient mode bridge: AINL CLI ↔ ArmaraOS

This note ties together **AI Native Lang (AINL)** tooling and **ArmaraOS** Ultra Cost-Efficient Mode so operators do not confuse three different layers.

## Three different things

| Layer | Where it runs | What it does |
|-------|----------------|--------------|
| **Input compression** | Rust (`openfang-runtime` / `prompt_compressor`) | Shortens the **user message** sent to the LLM before each agent turn. |
| **`--efficient-mode` / `AINL_EFFICIENT_MODE`** | Python CLI sets env only | **Signal** to the host (e.g. ArmaraOS kernel injecting manifest metadata). **No compression in Python.** |
| **`modules/efficient_styles.ainl`** | AINL graphs (optional) | Shapes **model output** (dense prose / JSON) via `llm_query` — complementary to input compression. |

## CLI: `ainl run --efficient-mode`

- Sets **`AINL_EFFICIENT_MODE`** when not already set (values such as `balanced`, `aggressive`, `off` — host-defined).
- Does **not** implement compression in the Python runtime.

## Module: `modules/efficient_styles.ainl`

- **`human_dense_response`** — natural, concise technical prose from prior node output.
- **`terse_structured`** — JSON-only internal steps.

Include with the usual AINL `include` prelude pattern (see file header comments). Replace `llm_query` with your deployment’s LLM adapter when not under ArmaraOS.

## ArmaraOS authoritative behavior

Ground truth for retention rules, UI locations, API fields (`compression_savings_pct`, `compressed_input`), and logs: **ArmaraOS** repository:

- `docs/prompt-compression-efficient-mode.md`
- Root `README.md` — Ultra Cost-Efficient Mode section

## Related

- `AGENTS.md` (AINL repo) — HTTP adapter, MCP `ainl_run`, and environment conventions.
