# WASM examples (deterministic compute)

These examples show how to move deterministic parsing/scoring/aggregation out of LLM prompts and into **WASM** via `R wasm.CALL`.

## Strict-valid examples

| File | Description |
|------|-------------|
| `wasm_add_minimal.ainl` | Minimal WASM call — add two numbers |
| `wasm_lead_score.ainl` | Lead scoring with branch on WASM result |
| `wasm_health_check.ainl` | Health check with threshold branch |

All pass `ainl validate --strict` and are registered in `tooling/artifact_profiles.json`.

## Requirements

- Install `wasmtime`: `pip install 'ainativelang[wasm]'`
- Ensure the runtime has a module mapping for `metrics` / `health` (the OpenClaw registry auto-registers demo modules from `demo/wasm/*.wat` when `wasmtime` is available).

## Run (demo)

```bash
# Validate a strict-valid example
ainl validate examples/wasm/wasm_add_minimal.ainl --strict

# Demo runner (legacy)
python3 scripts/run_intelligence.py --dry-run context
```

For a WASM-specific demo, see `demo/demo_wasm.lang`.

## Operator notes

See [`docs/operations/WASM_OPERATOR_NOTES.md`](../../docs/operations/WASM_OPERATOR_NOTES.md) for MCP config, runner config, and security guidance.
