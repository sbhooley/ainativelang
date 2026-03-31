---
> ArmaraOS is an independent open-source project and is not affiliated with any entities using similar names (e.g., Amaros AI or others).
> It is a customized fork and extension of OpenFang by RightNow-AI (https://github.com/RightNow-AI/openfang), licensed under Apache-2.0 OR MIT.
> It includes and integrates AINativeLang (https://github.com/sbhooley/ainativelang) for deterministic AI workflows.
> Modifications Copyright (c) 2026 sbhooley. Original OpenFang and AINativeLang works retain their respective licenses.
---

# Migrating from OpenClaw to ArmaraOS

This guide helps you move your existing OpenClaw setup to ArmaraOS.

## Why Migrate?

- **ArmaraOS** offers stronger security (WASM sandbox, Merkle trails, taint tracking)
- Native MCP support with a simpler TOML configuration
- 16 security systems out of the box
- Tauri sidecar support for desktop apps
- Modern Rust-based architecture

## What Migrates

- AINL workflows (`.ainl` files) are portable
- Memory data (SQLite) can be copied
- Cron jobs (need to be re-added via `armaraos cron add`)
- MCP configuration (converted automatically)

## Migration Steps

### 1. Backup Your Data

```bash
# Backup OpenClaw workspace
cp -r ~/.openclaw ~/.openclaw.backup
```

### 2. Install ArmaraOS and AINL Integration

```bash
# Install ArmaraOS (see ArmaraOS docs)
# Then install AINL for ArmaraOS:
ainl install armaraos
```

### 3. Copy Workspace Data

```bash
# Copy AINL database and cache
cp -r ~/.openclaw/workspace/.ainl ~/.armaraos/workspace/
```

### 4. Migrate MCP Configuration

The `ainl install armaraos` command already registered AINL as an MCP server in `~/.armaraos/config.toml`. Verify:

```toml
[[mcp_servers]]
name = "ainl"
command = "ainl-mcp"
args = []
```

### 5. Re-add Cron Jobs

OpenClaw cron jobs are stored in ArmaraOS's own cron system. Re-add them:

```bash
# List OpenClaw cron jobs
openclaw cron list  # or check ~/.openclaw/cron/

# Re-add to ArmaraOS
armaraos cron add /path/to/job.ainl --cron "0 9 * * *"
```

You can also use the AINL wrapper:

```bash
ainl cron add my_job.ainl --host armaraos --cron "0 9 * * *"
```

### 6. Verify Workspace

If you have custom workspace settings (non-standard location), update `OPENFANG_WORKSPACE` accordingly.

### 7. Update Scripts

Any scripts that reference `openclaw` or `~/.openclaw` should be updated to use `armaraos`:

- Change `openclaw` CLI calls to `armaraos`
- Change `~/.openclaw/bin/ainl-run` to `~/.armaraos/bin/ainl-run`
- Update paths for logs, data, etc.

### 8. Test

Run a few hands to ensure they work:

```bash
armaraos hand run ainl-test-hand --input '{}'
ainl status --host armaraos
```

Check that token tracking and memory are functioning.

## Automated Migration

We provide a semi-automated migration tool:

```bash
ainl migrate openclaw-to-armaraos
```

This will:
- Copy `~/.openclaw/config.toml` to `~/.armaraos/config.toml` (if exists)
- Copy `~/.openclaw/workspace` to `~/.armaraos/workspace`
- Print instructions for re-adding cron jobs and verifying MCP

It does **not** modify your OpenClaw installation; you can roll back if needed.

## Differences to Be Aware Of

| Feature | OpenClaw | ArmaraOS |
|---------|----------|----------|
| Config format | JSON (`openclaw.json`) | TOML (`config.toml`) |
| Cron storage | SQLite + file-based | ArmaraOS native cron |
| Security model | Sandboxed processes | WASM sandbox + Merkle trails |
| Sidecar | Tauri support | Tauri support + subprocess |
| MCP server | `ainl-mcp` with JSON config | `ainl-mcp` with TOML array |
| Workspace path | `~/.openclaw/workspace` | `~/.armaraos/workspace` |

## Rollback

If you need to revert:

```bash
# Restore OpenClaw config and data
rm -rf ~/.armaraos
cp -r ~/.openclaw.backup ~/.openclaw

# Reinstall OpenClaw AINL integration
ainl install openclaw
```

## Post-Migration Checklist

- [ ] `ainl status --host armaraos` reports OK
- [ ] `armaraos hand list` shows your hands
- [ ] Cron jobs are re-added and running
- [ ] Memory persistence works (check `armaraos memory list`)
- [ ] Token audit trail is generating (`/var/log/armaraos/token_audit.jsonl`)
- [ ] MCP tools are available in ArmaraOS

## Support

If you encounter issues, consult:
- [ArmaraOS GitHub Issues](https://github.com/RightNow-AI/armaraos/issues)
- [AINL ArmaraOS docs](../README.md)
- [AINL Discord](https://discord.gg/ainl)

Happy migrating!
