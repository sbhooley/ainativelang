# Install AINL

This guide covers installing AINL on macOS, Linux, and Windows (WSL). Choose the method that works for you.

## Prerequisites

- **Python 3.10+** (check: `python3 --version`)
- **pip** (Python package installer)
- **Git** (for cloning examples)

## Quick Install (Recommended)

The PyPI package is **`ainativelang`** (the CLI it installs is `ainl`):

```bash
pipx install 'ainativelang[mcp]'
```

Fallback if `pipx` is unavailable:

```bash
python3 -m pip install --user 'ainativelang[mcp]'
```

Verify installation:

```bash
ainl --version
# Expected output: ainl 1.8.0
```

### Platform-Specific Notes

#### macOS

Install `pipx` first if needed (`brew install pipx`), then use the Quick Install above.

If you encounter permission errors with pip, use `python3 -m pip install --user ainativelang` and add `~/.local/bin` to your `PATH`.

#### Linux

You may need `python3-dev` and `build-essential`:

```bash
sudo apt-get install python3-dev build-essential  # Debian/Ubuntu
python3 -m pip install --user 'ainativelang[mcp]'
```

#### Windows (WSL)

1. Install WSL2 with Ubuntu
2. Follow Linux instructions above
3. Access Windows files via `/mnt/c/` if needed

## Verify Your Setup

Create a simple test file `test.ainl` (compact syntax — see `examples/compact/` for more):

```ainl
adder:
  result = core.ADD 2 3
  out result
```

Validate and run:

```bash
ainl validate test.ainl --strict
ainl run test.ainl
# Output: 5
```

If these commands work, you're ready for the [next tutorial](02-first-agent.md).

## Optional: LLM Adapters and MCP

All adapters (including `llm/openrouter`, `llm/ollama`, `llm/anthropic`, `llm/cohere`)
ship inside the `ainativelang` package — there is nothing extra to install for them.

For MCP host integration (Claude Desktop, Cursor, etc.), install with the `[mcp]`
extra as shown above, then run:

```bash
ainl setup --auto
```

LLM provider credentials are configured via environment variables / `AINL_CONFIG` —
see `docs/LLM_ADAPTER_USAGE.md` in the repository for details.

## Next Steps

✅ Installation complete → **[Build Your First Agent](02-first-agent.md)**

---

**Problems?** Check [Troubleshooting](#troubleshooting) or [Open an issue](https://github.com/sbhooley/ainativelang/issues).

## Troubleshooting

### `command not found: ainl`

The `ainl` binary isn't in your `PATH`.

- **pip user install**: Add `~/.local/bin` to `PATH` (Linux/macOS) or `%APPDATA%\Python\Scripts` (Windows)
- **Homebrew**: Usually `/usr/local/bin` or `/opt/homebrew/bin`

### `ERROR: Could not find a version`

Python/pip version may be too old. Upgrade:

```bash
pip3 install --upgrade pip setuptools wheel
```

### Adapter import errors

Make sure you installed the adapter package:

```bash
pip3 list | grep ainl-adapter
```

If missing, install the needed adapter (see above).

### Permission denied on macOS/Linux

Use `pip3 install --user ainl` instead of system-wide install, or use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ainl
```

This is the recommended approach for development.
