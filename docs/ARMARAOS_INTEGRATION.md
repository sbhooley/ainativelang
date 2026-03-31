# ArmaraOS integration

ArmaraOS is an **optional** host runtime for AINL workflows. AINL supports ArmaraOS at the same “host pack” level as OpenClaw (bootstrap + status + cron + bridge utilities), while preserving OpenClaw / ZeroClaw / Hermes Agent behavior unchanged.

## What you get

- **MCP support**: `ainl-mcp` registered into `~/.armaraos/config.toml` so ArmaraOS can call AINL tools over stdio.
- **Run wrapper**: a host-local `ainl-run` shim (installed under `~/.armaraos/bin/`) that forwards to `ainl run`.
- **Emit to Hand package**: `ainl emit --target armaraos` produces a directory with `HAND.toml`, compiled IR JSON, and a `security.json`.
- **Status + schema bootstrap**: `ainl status --host armaraos` validates the local AINL memory DB schema and reports what’s installed.
- **Cron helper**: `ainl cron add ... --host armaraos` shells out to `armaraos cron add` when the ArmaraOS CLI is present.

ArmaraOS CLI is **not required** for AINL to install or run; ArmaraOS-only features (cron listing/adding) are best-effort when the `armaraos` binary is on PATH.

## Quickstart (MCP bootstrap)

```bash
pip install 'ainativelang[mcp]'
ainl install armaraos
```

Verify:

```bash
ainl status --host armaraos
```

## Emit a Hand package

```bash
ainl emit my_flow.ainl --target armaraos -o ./my_flow_armaraos_hand
```

Expected outputs:

- `HAND.toml`
- `<stem>.ainl.json`
- `security.json`
- `README.md`

## Env vars (canonical + aliases)

AINL prefers `ARMARAOS_*` for ArmaraOS integration, with `AINL_*` and legacy `OPENFANG_*` aliases supported for compatibility.

| Purpose | Canonical | Aliases |
|---------|-----------|---------|
| Workspace root | `ARMARAOS_WORKSPACE` | `OPENFANG_WORKSPACE` |
| AINL SQLite DB path | `ARMARAOS_MEMORY_DB` | `AINL_MEMORY_DB`, `OPENFANG_MEMORY_DB` |
| Token audit JSONL | `ARMARAOS_TOKEN_AUDIT` | `OPENFANG_TOKEN_AUDIT` |
| Prefer session context injection | `ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT` | `OPENFANG_BOOTSTRAP_PREFER_SESSION_CONTEXT` |
| IR cache directory | `AINL_IR_CACHE_DIR` | (none) |
| Monitor cache JSON | `MONITOR_CACHE_JSON` | (none) |
| FS sandbox root | `AINL_FS_ROOT` | (none) |

## Troubleshooting

- **`ainl status --host armaraos` reports schema errors**: the command bootstraps required tables automatically. If the DB path is unexpected, set `ARMARAOS_MEMORY_DB` (or `AINL_MEMORY_DB`) explicitly and re-run status.
- **Cron helpers don’t work**: ensure the external `armaraos` CLI is installed and on PATH. AINL will skip cron checks when it is missing.

## See also

- Host hub: `docs/getting_started/HOST_MCP_INTEGRATIONS.md`
- ArmaraOS config reference: `armaraos/docs/CONFIG.md`
- ArmaraOS install notes: `armaraos/docs/INSTALL.md`
- ArmaraOS migration: `armaraos/docs/MIGRATION.md`

