# WASM examples (deterministic compute)

These examples show how to move deterministic parsing/scoring/aggregation out of LLM prompts and into **WASM** via `R wasm.CALL`.

## Requirements

- Install `wasmtime` (optional dependency used by the runtime WASM adapter).
- Ensure the runtime has a module mapping for `metrics` / `health` (the OpenClaw registry auto-registers demo modules from `demo/wasm/*.wat` when `wasmtime` is available).

## Run (demo)

The simplest demo program is the legacy `.lang` example:

```bash
python3 scripts/run_intelligence.py --dry-run context
python3 scripts/run_intelligence.py --dry-run summarizer
```

For a WASM-specific demo, see:

- `demo/demo_wasm.lang` (uses `R wasm.CALL metrics add ...` and `metrics lead_score ...`)

This folder exists as a landing page for future `.ainl`-native WASM examples (strict-valid) without changing runtime semantics.

