# Installing AINL for OpenFang

This guide covers installing AINL and configuring it to work with OpenFang.

## Prerequisites

- Python 3.10 or higher
- Rust toolchain (for OpenFang)
- OpenFang CLI (`openfang`) installed and on PATH
- Git

## One-Command Install

The easiest way is:

```bash
ainl install openfang
```

This performs the full bootstrap:

1. Installs/upgrades `ainativelang[mcp]` via pip
2. Registers AINL as an MCP server in `~/.openfang/config.toml`
3. Installs the `ainl-run` wrapper script to `~/.openfang/bin/`
4. Adds `~/.openfang/bin` to your `PATH` in `~/.bashrc`/`~/.zshrc`
5. Validates the installation
6. Prints a success tip

### Options

```bash
ainl install openfang --workspace /custom/path  # Use custom workspace
ainl install openfang --dry-run                # Print actions without doing them
ainl install openfang --verbose                # Show detailed logs
```

## Manual Steps

If you prefer to install manually:

### 1. Install AINL

```bash
pip install ainativelang[mcp]
```

### 2. MCP Registration

Add to `~/.openfang/config.toml`:

```toml
[[mcp_servers]]
name = "ainl"
command = "ainl-mcp"
args = []
```

### 3. Install ainl-run Wrapper

```bash
mkdir -p ~/.openfang/bin
cat > ~/.openfang/bin/ainl-run << 'EOF'
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
chmod +x ~/.openfang/bin/ainl-run
```

Add to PATH in `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.openfang/bin:$PATH"
```

### 4. Verify

```bash
ainl status --host openfang
```

Should show:
- OpenFang installation detected
- AINL MCP registered
- Schema initialized

## Emitting AINL Hands

Once installed, you can compile AINL files to OpenFang Hand packages:

```bash
ainl emit --target openfang -o my_hand/ my_workflow.ainl
```

This produces:
- `HAND.toml` - manifest
- `my_workflow.ainl.json` - compiled IR
- `security.json` - security policy
- `README.md` - usage notes

Copy the `my_hand/` directory to your OpenFang hands location or reference it directly.

## Uninstall

To remove AINL integration:

1. Remove `ainl` package: `pip uninstall ainativelang`
2. Remove `~/.openfang/bin/ainl-run`
3. Edit `~/.openfang/config.toml` and remove the `[[mcp_servers]]` entry named `ainl`
4. Remove the `PATH` line from your shell rc file

## Troubleshooting

- **`openfang: command not found`**: Ensure OpenFang is installed and on PATH
- **MCP registration fails**: Check that `~/.openfang/config.toml` is writable
- **`ainl-mcp: command not found`**: Ensure `ainativelang[mcp]` is installed
- **Permission denied on ainl-run**: Run `chmod +x ~/.openfang/bin/ainl-run`

For more help, see the main [AINL documentation](../README.md) or [OpenFang docs](https://github.com/RightNow-AI/openfang).
