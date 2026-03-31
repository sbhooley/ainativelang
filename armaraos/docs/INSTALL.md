---
> ArmaraOS is an independent open-source project and is not affiliated with any entities using similar names (e.g., Amaros AI or others).
> It is a customized fork and extension of OpenFang by RightNow-AI (https://github.com/RightNow-AI/openfang), licensed under Apache-2.0 OR MIT.
> It includes and integrates AINativeLang (https://github.com/sbhooley/ainativelang) for deterministic AI workflows.
> Modifications Copyright (c) 2026 sbhooley. Original OpenFang and AINativeLang works retain their respective licenses.
---

# Installing AINL for ArmaraOS

This guide covers installing AINL and configuring it to work with ArmaraOS.

## Prerequisites

- Python 3.10 or higher
- Rust toolchain (for ArmaraOS)
- ArmaraOS CLI (`armaraos`) installed and on PATH (**optional** — only required for ArmaraOS-specific operations like cron management and running hands)
- Git

## One-Command Install

The easiest way is:

```bash
ainl install armaraos
```

This performs the full bootstrap:

1. Installs/upgrades `ainativelang[mcp]` via pip
2. Registers AINL as an MCP server in `config.toml` (during transition: `~/.openfang/config.toml` and/or `~/.armaraos/config.toml`)
3. Installs the `ainl-run` wrapper script to `~/.armaraos/bin/`
4. Adds `~/.armaraos/bin` to your `PATH` in `~/.bashrc`/`~/.zshrc`
5. Validates the installation
6. Prints a success tip

### Options

```bash
ainl install armaraos --workspace /custom/path  # Use custom workspace
ainl install armaraos --dry-run                # Print actions without doing them
ainl install armaraos --verbose                # Show detailed logs
```

## Manual Steps

If you prefer to install manually:

### 1. Install AINL

```bash
pip install ainativelang[mcp]
```

### 2. MCP Registration

Add to your host config (`~/.openfang/config.toml` today; `~/.armaraos/config.toml` after rebrand):

```toml
[[mcp_servers]]
name = "ainl"
timeout_secs = 30
env = []

[mcp_servers.transport]
type = "stdio"
command = "ainl-mcp"
args = []
```

### 3. Install ainl-run Wrapper

```bash
mkdir -p ~/.armaraos/bin
cat > ~/.armaraos/bin/ainl-run << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: ainl-run <file.ainl> [extra ainl run args...]" >&2
  exit 1
fi
FILE="$1"
shift
ainl compile "$FILE" && exec ainl run "$FILE" "$@"
EOF
chmod +x ~/.armaraos/bin/ainl-run
```

Add to PATH in `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.armaraos/bin:$PATH"
```

### 4. Verify

```bash
ainl status --host armaraos
```

Should show:
- ArmaraOS installation detected
- AINL MCP registered
- Schema initialized

## Emitting AINL Hands

Once installed, you can compile AINL files to ArmaraOS Hand packages:

```bash
ainl emit --target armaraos -o my_hand/ my_workflow.ainl
```

This produces:
- `HAND.toml` - manifest
- `my_workflow.ainl.json` - compiled IR
- `security.json` - security policy
- `README.md` - usage notes

Copy the `my_hand/` directory to your ArmaraOS hands location or reference it directly.

## Uninstall

To remove AINL integration:

1. Remove `ainl` package: `pip uninstall ainativelang`
2. Remove `~/.armaraos/bin/ainl-run`
3. Edit `~/.armaraos/config.toml` and remove the `[[mcp_servers]]` entry named `ainl`
4. Remove the `PATH` line from your shell rc file

## Troubleshooting

- **`armaraos: command not found`**: Ensure ArmaraOS is installed and on PATH
- **MCP registration fails**: Check that `~/.armaraos/config.toml` is writable
- **`ainl-mcp: command not found`**: Ensure `ainativelang[mcp]` is installed
- **Permission denied on ainl-run**: Run `chmod +x ~/.armaraos/bin/ainl-run`

For more help, see the main [AINL documentation](../README.md) or [ArmaraOS docs](https://github.com/RightNow-AI/armaraos).
