# Install AINL

This guide covers installing AINL on macOS, Linux, and Windows (WSL). Choose the method that works for you.

## Prerequisites

- **Python 3.10+** (check: `python3 --version`)
- **pip** (Python package installer)
- **Git** (for cloning examples)

## Quick Install (Recommended)

```bash
pip3 install ainl
```

Verify installation:

```bash
ainl --version
# Expected output: ainl 1.7.1
```

### Platform-Specific Notes

#### macOS

Using Homebrew:

```bash
brew install ainl
```

If you encounter permission errors, use `pip3 install --user ainl` and add `~/.local/bin` to your `PATH`.

#### Linux

You may need `python3-dev` and `build-essential`:

```bash
sudo apt-get install python3-dev build-essential  # Debian/Ubuntu
pip3 install ainl
```

#### Windows (WSL)

1. Install WSL2 with Ubuntu
2. Follow Linux instructions above
3. Access Windows files via `/mnt/c/` if needed

## Verify Your Setup

Create a simple test file `test.ainl`:

```ainl
graph Test {
  input: string
  node hello: emit("Hello, {{input}}!")
  output: hello.result
}
```

Validate and run:

```bash
ainl validate test.ainl
ainl run test.ainl --input "World"
# Output: {"result":"Hello, World!"}
```

If these commands work, you're ready for the [next tutorial](02-first-agent.md).

## Optional: Install Adapters

AINL supports multiple LLM providers. Install adapters as needed:

```bash
# OpenRouter adapter (recommended for cost savings)
pip3 install ainl-adapter-openrouter

# Ollama for local models
pip3 install ainl-adapter-ollama

# MCP for Claude Desktop integration
pip3 install ainl-adapter-mcp
```

Configure adapters in `~/.ainl/config.yaml`:

```yaml
adapters:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    default_model: openai/gpt-4o-mini
```

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
