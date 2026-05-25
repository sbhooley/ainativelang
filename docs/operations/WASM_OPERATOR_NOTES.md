# WASM operator notes (`R wasm`)

**Goal:** Run **deterministic** work (parse, aggregate, scoring) in WASM so it does not consume LLM tokens.

**Scope:** The WASM adapter calls pre-compiled `.wasm`/`.wat` module exports. It does **not** compile AINL graphs to WASM. See [`STATUS.yaml`](../../STATUS.yaml) `marketing_claims_boundary` for the distinction.

## Installation

```bash
pip install 'ainativelang[wasm]'
# or
pip install wasmtime
```

`ainl doctor` reports wasmtime availability when the package is installed.

## Registration

`adapters/openclaw_integration.py` registers `WasmAdapter` when `wasmtime` is available and demo modules exist under `demo/wasm/` (`metrics`, `health` — `.wasm` or `.wat`).

Custom deployments: extend the same pattern — map **logical names** to absolute paths via env or code, then call `R wasm.CALL ...` from AINL (see runtime `WasmAdapter` contract).

## MCP `ainl_run` configuration

```json
{
  "enable": ["wasm"],
  "wasm": {
    "modules": {
      "metrics": "/path/to/metrics.wasm",
      "health": "/path/to/health.wasm"
    }
  }
}
```

## Runner (`scripts/runtime_runner_service.py`)

```json
{
  "adapters": {
    "wasm": {
      "modules": {
        "metrics": "/opt/ainl/wasm/metrics.wasm"
      }
    }
  }
}
```

## Syntax

```ainl
# Compact syntax
result = wasm.CALL "metrics.add" 2 3

# Opcode syntax
R wasm.CALL metrics.add 2 3 ->result
```

The first argument to `CALL` is `<module>.<export>`. Additional arguments are positional and passed to the WASM function.

## Strict-valid examples

- [`examples/wasm/wasm_add_minimal.ainl`](../../examples/wasm/wasm_add_minimal.ainl) — minimal add call
- [`examples/wasm/wasm_lead_score.ainl`](../../examples/wasm/wasm_lead_score.ainl) — scoring with branch
- [`examples/wasm/wasm_health_check.ainl`](../../examples/wasm/wasm_health_check.ainl) — health check with branch

All registered in [`tooling/artifact_profiles.json`](../../tooling/artifact_profiles.json) under `strict-valid`.

## Security

- Module allowlist: `WasmAdapter(modules=..., allowed_modules=...)` restricts which modules can be invoked.
- WASI imports are not supported (sandboxed compute only).
- See [`docs/SECURITY_REVIEW.md`](../SECURITY_REVIEW.md) and [`docs/operations/SANDBOX_EXECUTION_PROFILE.md`](SANDBOX_EXECUTION_PROFILE.md) for the broader security model.

## Safe rollout

1. Identify a **hot path** that is pure/deterministic (same inputs → same outputs).
2. Add or reuse a **small** module; unit-test the WASM boundary.
3. Route **one** label or monitor to WASM; keep the Python fallback until parity is proven.
4. Expand only after benchmarks show real savings.

This is **not** a substitute for gateway caps or embedding retrieval — it removes LLM calls only where logic is already non-LLM.

## What this is NOT

- **Not** whole-graph WASM compilation (no `ainl emit --target wasm`)
- **Not** browser-targeted WASM (no DOM/web API access)
- **Not** on-chain smart contract execution

These are explicitly listed as `never_shipped` or `never` in `STATUS.yaml`.
