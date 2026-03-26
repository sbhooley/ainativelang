# PTC Runner Adapter (`ptc_runner`)

`ptc_runner` is an optional AINL runtime adapter for executing PTC-Lisp snippets
through an external PTC Runner service.

This integration is additive and opt-in:

- enable with `--enable-adapter ptc_runner`, or
- set `AINL_ENABLE_PTC=true`.

If neither is set, calls are blocked by design.

## Syntax

Preferred split form (lowercase verb):

```ainl
R ptc_runner run "(+ 1 2)" "{total :float}" 5 ->out
```

Dotted strict-friendly form:

```ainl
R ptc_runner.RUN "(+ 1 2)" "{total :float}" 5 ->out
```

Arguments:

1. `lisp` (required): PTC-Lisp source string
2. `signature` (optional): expected output signature string
3. `subagent_budget` (optional): integer execution budget

## Environment

- `AINL_ENABLE_PTC=true` enables adapter registration without CLI flag.
- `AINL_PTC_RUNNER_URL` sets the HTTP endpoint used for execution.
- `AINL_PTC_RUNNER_MOCK=1` enables deterministic mock mode for testing.
- `AINL_PTC_RUNNER_CMD` optional subprocess fallback command (stdin JSON, stdout JSON).

## Security + gating

- Adapter is disabled unless explicitly enabled (`--enable-adapter ptc_runner` or `AINL_ENABLE_PTC=true`).
- Host allowlist restrictions from `--http-allow-host` are respected.
- Calls fail fast when endpoint/config is missing.
- `_`-prefixed context keys are filtered before request serialization (context firewall).

## Result envelope

`ptc_runner` returns a normalized envelope:

```json
{
  "ok": true,
  "runtime": "ptc_runner",
  "status_code": 200,
  "result": {},
  "traces": []
}
```

`traces` is passed through when provided by the runner, so trajectory/intelligence
systems can capture the same execution breadcrumbs.

## Reliability add-ons (Phase 2)

- Optional signature annotation in AINL source comments:
  - `# signature: {total :float}`
- Signature linting appears via `scripts/validate_ainl.py` diagnostics.
- Runtime validation + bounded retry (max 3) are provided by:
  - `intelligence/signature_enforcer.py`

## PTC runner startup notes

AINL calls an existing PTC service endpoint via `AINL_PTC_RUNNER_URL` (HTTP).
If your deployment does not expose HTTP directly, use `AINL_PTC_RUNNER_CMD`
subprocess fallback.

Typical service startup (adjust to your `ptc_runner` install):

```bash
# Example only; use your checked-out ptc_runner launch command.
mix run --no-halt
```

or containerized:

```bash
docker run --rm -p 4000:4000 <your-ptc-runner-image>
```

## Example run

```bash
AINL_ENABLE_PTC=true \
AINL_PTC_RUNNER_URL=http://localhost:4000/run \
python3 -m cli.main run examples/test_adapters_full.ainl \
  --strict \
  --enable-adapter ptc_runner \
  --http-allow-host localhost
```

## Canonical End-to-End Example

This example is copy-paste oriented and keeps everything opt-in:

- uses a subagent-isolation envelope pattern (`namespace`, `budget`, `payload`)
- runs `ptc_runner` with signature metadata
- demonstrates `_` context firewall keys
- validates with `signature_enforcer`
- exports trajectory to PTC-compatible JSONL

### 1) AINL workflow (`examples/ptc_integration_example.ainl`)

```ainl
L1:
  Set subagent_namespace "ptc/orders"
  Set subagent_budget 3
  Set subagent_payload "{\"task\":\"orders\"}"
  X subagent_envelope (obj "namespace" subagent_namespace)
  X subagent_envelope (put subagent_envelope "budget" subagent_budget)
  X subagent_envelope (put subagent_envelope "payload" subagent_payload)

  # Context firewall demo: _internal_token is retained in runtime frame but filtered before outbound adapter serialization.
  Set _internal_token "debug-only-secret"

  R ptc_runner run "(->> (tool/get_orders {:status \"pending\"}) (filter #(> (:amount %) 100)) (sum-by :amount))" "{total :float}" 3 ->ptc_out # signature: {total :float}
  J ptc_out
```

### 2) Run in mock mode (strict + trajectory)

```bash
AINL_PTC_RUNNER_MOCK=1 \
python3 <<'PY'
from pathlib import Path
from runtime.engine import RuntimeEngine
from runtime.adapters.base import AdapterRegistry
from adapters.ptc_runner import PtcRunnerAdapter

code = Path("examples/ptc_integration_example.ainl").read_text()
reg = AdapterRegistry(allowed=["core", "ptc_runner"])
reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))

eng = RuntimeEngine.from_code(
    code,
    strict=True,
    adapters=reg,
    source_path=str(Path("examples/ptc_integration_example.ainl").resolve()),
    trajectory_log_path="/tmp/ainl_ptc_example.jsonl",
)
print(eng.run_label("1"))
PY
```

Expected result shape:

- live runner: `{"ok": true, "result": {"total": <float>}, ...}`
- mock mode (`AINL_PTC_RUNNER_MOCK=1`): deterministic envelope with echoed Lisp payload in `result.value`

### 3) Validate signature metadata and enforce runtime signature checks

```bash
# metadata inspection
python3 intelligence/signature_enforcer.py examples/ptc_integration_example.ainl

# runtime retry helper (bounded max 3 attempts)
AINL_PTC_RUNNER_MOCK=1 \
python3 <<'PY'
from adapters.ptc_runner import PtcRunnerAdapter
from intelligence.signature_enforcer import run_with_signature_retry

print(
    run_with_signature_retry(
        adapter=PtcRunnerAdapter(enabled=True),
        lisp="(->> (tool/get_orders {:status \"pending\"}) (filter #(> (:amount %) 100)) (sum-by :amount))",
        signature="{total :float}",
        max_attempts=3,
    )
)
PY
```

### 4) Export trajectory to PTC-compatible JSONL

```bash
PYTHONPATH=. python3 scripts/ainl_trace_viewer.py /tmp/ainl_ptc_example.jsonl --ptc-export /tmp/ptc_trace.jsonl
```

Notes:

- The adapter uses PTC Runner HTTP (`AINL_PTC_RUNNER_URL`) when configured, or subprocess fallback (`AINL_PTC_RUNNER_CMD`).
- Signature metadata is comment-based (`# signature: ...`) and intentionally does not require parser/grammar changes.
- `modules/common/subagent_isolated.ainl` and `modules/common/parallel.ainl` remain available as reusable helpers; the canonical CLI-safe flow above inlines the same subagent envelope shape.
- `--enable-adapter ptc_runner` registers the adapter in CLI runs, while capability policy allowlists are enforced separately by the runtime surface in use.
