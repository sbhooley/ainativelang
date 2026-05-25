# Emit targets — honesty index

This document mirrors the exact `--target` choices accepted by `ainl emit` in [`cli/main.py`](../cli/main.py). If a target is not listed here, it does not exist and must not be claimed.

## Shipped targets

| Target | Description |
|--------|-------------|
| `ir` | Raw IR JSON |
| `langgraph` | LangGraph Python workflow |
| `temporal` | Temporal workflow definition |
| `hermes-skill` | Hermes skill package |
| `hermes` | Hermes agent |
| `solana-client` | Standalone Solana RPC runner |
| `blockchain-client` | Generic blockchain client runner |
| `server` | HTTP server wrapper |
| `python-api` | Python API module |
| `react` | React component scaffold |
| `openapi` | OpenAPI spec |
| `prisma` | Prisma schema |
| `sql` | SQL DDL |
| `docker` | Dockerfile |
| `k8s` | Kubernetes manifests |
| `cron` | Cron job wrapper |
| `armaraos` | ArmaraOS / openfang-hands Hand package |

## Targets that do NOT exist

| Claimed target | Status | Notes |
|----------------|--------|-------|
| `wasm` | Never shipped | WASM adapter (`R wasm.CALL`) calls modules; no graph-to-WASM emitter |
| `native` / `bare-metal` | Never | AINL executes via Python RuntimeEngine; no native codegen |
| `browser` | Never | No browser-targeted emit |

## Keeping this in sync

This list must match the `choices` argument of the `--target` flag in `cli/main.py` (`cmd_emit` subparser). When adding a new emit target:

1. Add the choice string to the CLI parser.
2. Add a row to this table.
3. Update [`STATUS.yaml`](../STATUS.yaml) `marketing_claims_boundary.emit_targets`.
4. Run `python scripts/refresh_repo_stats.py`.
