---
> ArmaraOS is an independent open-source project and is not affiliated with any entities using similar names (e.g., Amaros AI or others).
> It is a customized fork and extension of OpenFang by RightNow-AI (https://github.com/RightNow-AI/openfang), licensed under Apache-2.0 OR MIT.
> It includes and integrates AINativeLang (https://github.com/sbhooley/ainativelang) for deterministic AI workflows.
> Modifications Copyright (c) 2026 sbhooley. Original OpenFang and AINativeLang works retain their respective licenses.
---

# ArmaraOS Configuration Reference

This document describes configuration options for AINL when running under ArmaraOS.

## ArmaraOS Config Changes (`~/.armaraos/config.toml`)

AINL integration adds an MCP server entry. The minimal config is:

```toml
[[mcp_servers]]
name = "ainl"
command = "ainl-mcp"
args = []
```

### Optional Settings

| Setting      | Description                            | Default |
|--------------|----------------------------------------|---------|
| `name`       | MCP server identifier                  | `"ainl"`|
| `command`    | Command to launch AINL MCP server     | `"ainl-mcp"`|
| `args`       | Extra arguments for the command       | `[]`|

## AINL Environment Variables

When running as an ArmaraOS hand, these environment variables are used:

| Variable                     | Description | Default |
|------------------------------|-------------|---------|
| `ARMARAOS_WORKSPACE`         | ArmaraOS workspace root | `~/.armaraos/workspace` |
| `ARMARAOS_MEMORY_DB`         | Path to SQLite memory DB | `$ARMARAOS_WORKSPACE/.ainl/ainl_memory.sqlite3` |
| `ARMARAOS_TOKEN_AUDIT`       | Token usage audit log | `/var/log/armaraos/token_audit.jsonl` |
| `ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT` | Enable session context heuristics | `false` |
| `AINL_MEMORY_DB`             | Alias for ArmaraOS memory DB | (derived) |
| `AINL_IR_CACHE_DIR`          | Compiled IR cache | `$ARMARAOS_WORKSPACE/.ainl/ir_cache` |
| `MONITOR_CACHE_JSON`         | Metrics cache | `$ARMARAOS_WORKSPACE/.ainl/monitor_cache.json` |

Legacy aliases (supported for compatibility): `OPENFANG_WORKSPACE`, `OPENFANG_MEMORY_DB`, `OPENFANG_TOKEN_AUDIT`, `OPENFANG_BOOTSTRAP_PREFER_SESSION_CONTEXT`.

## HAND.toml Manifest Options

When emitting to ArmaraOS, the generated `HAND.toml` contains:

```toml
[hand]
id = "ainl-<stem>"
name = "<Stemmed Name>"
version = "1.0.0"
description = "AINL-generated hand"
author = "AINL User"
entrypoint = "<stem>.ainl.json"

[config]
max_concurrency = 5
default_timeout = 300
retry_policy = "exponential_backoff"
max_retries = 3

[security]
sandbox = "wasm"
max_memory_mb = 256
max_instructions = 10_000_000
allowed_imports = ["env.print", "env.log", "env.sleep", "env.random"]
taint_sources = []
merkle_audit = true

[[inputs]]
name = "input"
type = "object"

[[outputs]]
name = "result"
type = "object"

[[outputs]]
name = "metrics"
type = "object"

[resources]
cpu_millicores = 500
memory_mb = 256
ephemeral_storage_mb = 100

[metadata]
tags = ["ainl", "<stem>"]
```

You can customize these before running the hand.

## Security Policies

The `security.json` file controls the WASM sandbox:

```json
{
  "version": "1.0",
  "sandbox": "wasm",
  "wasm_config": {
    "max_memory_mb": 256,
    "max_instructions": 10000000,
    "allowed_imports": ["env.print", "env.log", "env.sleep", "env.random"],
    "blocked_syscalls": ["filesystem", "network", "process"],
    "fuel_limit": null
  },
  "taint": {
    "sources": [],
    "tracking_enabled": true
  },
  "merkle": {
    "hooks_enabled": true,
    "incremental": true
  },
  "allowed_networks": [],
  "max_execution_time_sec": 300
}
```

Adjust `allowed_imports` and `allowed_networks` as needed, but be aware that relaxing security reduces isolation.

## Channel Adapters

AINL tools can publish to ArmaraOS channels via the `armaraos_channel` tool spec. The adapter registers these channels automatically:

- `ainl_control` – control messages (QoS 2)
- `ainl_metrics` – metrics (QoS 1)
- `ainl_alerts` – alerts (QoS 2)
- `armaraos_events` – ArmaraOS events (QoS 0)

You can add custom channels by modifying `armaraos/adapters/channel.py`.

## Token Tracking & Merkle Audit

Token usage is recorded to `ARMARAOS_TOKEN_AUDIT` (default `/var/log/armaraos/token_audit.jsonl`). Each entry includes a Merkle proof for tamper detection.

To verify the audit trail integrity:

```bash
python -c "from armaraos.bridge.token_tracker import ArmaraOSTokenTracker; print(ArmaraOSTokenTracker().verify_merkle_chain())"
```

## Troubleshooting

### Schema Errors

If `ainl status --host armaraos` reports schema errors, run:

```bash
# The bootstrap should auto-create tables; if not:
python -c "from armaraos.bridge.schema_bootstrap import bootstrap_tables; bootstrap_tables(Path('~/.armaraos/.ainl/ainl_memory.sqlite3').expanduser())"
```

### MCP Not Connecting

Ensure `ainl-mcp` is on PATH and the `config.toml` entry is correct. Test:

```bash
ainl-mcp --help
```

Should show MCP server help.

### WASM Sandbox Errors

If your hand exceeds memory or instruction limits, adjust the `security` section in `HAND.toml` and re-emit.

For more help, consult the ArmaraOS docs or AINL repository.


## Tauri Sidecar Configuration

ArmaraOS desktop applications can embed AINL as a sidecar process. Add this to your `tauri.conf.json`:

```json
{
  "tauri": {
    "allowlist": { "all": false },
    "sidecar": {
      " ainl-sidecar": {
        "desc": "AINL bridge sidecar for ArmaraOS",
        "cmd": "ainl-run",
        "args": ["--bridge-endpoint", "armaraos", "--workspace", "$APPDATA/armaraos/workspace"]
      }
    }
  }
}
```

Then in your Rust code, you can invoke the sidecar:

```rust
// Example: Start AINL sidecar
let mut sidecar = tauri::async_runtime::spawn(async move {
    let mut child = tauri::api::process::Command::new("ainl-sidecar")
        .args(&["run", "my_workflow.ainl"])
        .spawn()
        .expect("failed to start ainl-sidecar");
    child.wait().await
});
```

The sidecar communicates via stdin/stdout using the ArmaraOS bridge protocol. See `armaraos/bridge/` for protocol details.

For packaged applications, ensure `ainl` and its dependencies are bundled or available on the system PATH. PyInstaller or similar can create a standalone executable.

