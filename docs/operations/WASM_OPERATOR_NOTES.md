# WASM operator notes (`R wasm`)

**Goal:** Run **deterministic** work (parse, aggregate, scoring) in WASM so it does not consume LLM tokens.

## Registration

`adapters/openclaw_integration.py` registers `WasmAdapter` when `wasmtime` is available and demo modules exist under `demo/wasm/` (`metrics`, `health` — `.wasm` or `.wat`).

Custom deployments: extend the same pattern — map **logical names** to absolute paths via env or code, then call `R wasm CALL ...` from AINL (see runtime `WasmAdapter` contract).

## Safe rollout

1. Identify a **hot path** that is pure/deterministic (same inputs → same outputs).  
2. Add or reuse a **small** module; unit-test the WASM boundary.  
3. Route **one** label or monitor to WASM; keep the Python fallback until parity is proven.  
4. Expand only after benchmarks show real savings.

This is **not** a substitute for gateway caps or embedding retrieval — it removes LLM calls only where logic is already non-LLM.
