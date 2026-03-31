# Migrating from OpenClaw to OpenFang

This guide helps you move your existing OpenClaw setup to OpenFang.

## Why Migrate?

- **OpenFang** offers stronger security (WASM sandbox, Merkle trails, taint tracking)
- Native MCP support with a simpler TOML configuration
- 16 security systems out of the box
- Tauri sidecar support for desktop apps
- Modern Rust-based architecture

## What Migrates

- AINL workflows (`.ainl` files) are portable
- Memory data (SQLite) can be copied
- Cron jobs (need to be re-added via `openfang cron add`)
- MCP configuration (converted automatically)

## Migration Steps

### 1. Backup Your Data

```bash
# Backup OpenClaw workspace
cp -r ~/.openclaw ~/.openclaw.backup
```

### 2. Install OpenFang and AINL Integration

```bash
# Install OpenFang (see OpenFang docs)
# Then install AINL for OpenFang:
ainl install openfang
```

### 3. Copy Workspace Data

```bash
# Copy AINL database and cache
cp -r ~/.openclaw/workspace/.ainl ~/.openfang/workspace/
```

### 4. Migrate MCP Configuration

The `ainl install openfang` command already registered AINL as an MCP server in `~/.openfang/config.toml`. Verify:

```toml
[[mcp_servers]]
name = "ainl"
command = "ainl-mcp"
args = []
```

### 5. Re-add Cron Jobs

OpenClaw cron jobs are stored in OpenFang's own cron system. Re-add them:

```bash
# List OpenClaw cron jobs
openclaw cron list  # or check ~/.openclaw/cron/

# Re-add to OpenFang
openfang cron add /path/to/job.ainl --cron "0 9 * * *"
```

You can also use the AINL wrapper:

```bash
ainl cron add my_job.ainl --host openfang --cron "0 9 * * *"
```

### 6. Verify Workspace

If you have custom workspace settings (non-standard location), update `OPENFANG_WORKSPACE` accordingly.

### 7. Update Scripts

Any scripts that reference `openclaw` or `~/.openclaw` should be updated to use `openfang`:

- Change `openclaw` CLI calls to `openfang`
- Change `~/.openclaw/bin/ainl-run` to `~/.openfang/bin/ainl-run`
- Update paths for logs, data, etc.

### 8. Test

Run a few hands to ensure they work:

```bash
openfang hand run ainl-test-hand --input '{}'
ainl status --host openfang
```

Check that token tracking and memory are functioning.

## Automated Migration

We provide a semi-automated migration tool:

```bash
ainl migrate openclaw-to-openfang
```

This will:
- Copy `~/.openclaw/config.toml` to `~/.openfang/config.toml` (if exists)
- Copy `~/.openclaw/workspace` to `~/.openfang/workspace`
- Print instructions for re-adding cron jobs and verifying MCP

It does **not** modify your OpenClaw installation; you can roll back if needed.

## Differences to Be Aware Of

| Feature | OpenClaw | OpenFang |
|---------|----------|----------|
| Config format | JSON (`openclaw.json`) | TOML (`config.toml`) |
| Cron storage | SQLite + file-based | OpenFang native cron |
| Security model | Sandboxed processes | WASM sandbox + Merkle trails |
| Sidecar | Tauri support | Tauri support + subprocess |
| MCP server | `ainl-mcp` with JSON config | `ainl-mcp` with TOML array |
| Workspace path | `~/.openclaw/workspace` | `~/.openfang/workspace` |

## Rollback

If you need to revert:

```bash
# Restore OpenClaw config and data
rm -rf ~/.openfang
cp -r ~/.openclaw.backup ~/.openclaw

# Reinstall OpenClaw AINL integration
ainl install openclaw
```

## Post-Migration Checklist

- [ ] `ainl status --host openfang` reports OK
- [ ] `openfang hand list` shows your hands
- [ ] Cron jobs are re-added and running
- [ ] Memory persistence works (check `openfang memory list`)
- [ ] Token audit trail is generating (`/var/log/openfang/token_audit.jsonl`)
- [ ] MCP tools are available in OpenFang

## Support

If you encounter issues, consult:
- [OpenFang GitHub Issues](https://github.com/RightNow-AI/openfang/issues)
- [AINL OpenFang docs](../README.md)
- [AINL Discord](https://discord.gg/ainl)

Happy migrating!
