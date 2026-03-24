---
name: AINL
description: Deterministic compiled graphs for ZeroClaw (importer, runtime, MCP tools)
install: ./install.sh
install_alt: pip install 'ainl-lang[mcp]' && ainl install-mcp --host zeroclaw
commands:
  - ainl import <source> — convert Markdown / ecosystem packs into `.ainl` graphs
  - ainl compile <file.ainl> — compile and validate deterministic graph IR
  - ainl run <file.ainl> — run compiled workflow (when your graph uses the runtime path)
  - zeroclaw ainl run <file.ainl> — same via ZeroClaw shim after install (see install-mcp --host zeroclaw)
tags:
  - ainl
  - graphs
  - mcp
  - zeroclaw
---

# AINL for ZeroClaw

**AINL** is an AI-native language that compiles **deterministic graphs**. In ZeroClaw, use it to import workflows, compile them, run them, and expose **`ainl-mcp`** tools to the agent.

## Agent instructions

Follow this skill when the user is on **ZeroClaw** (or wants **deterministic `.ainl` graphs** with **import / compile / run / MCP**). Prefer **`./install.sh`** after `zeroclaw skills install …`, or the manual **`pip install 'ainl-lang[mcp]' && ainl install-mcp --host zeroclaw`** path (alias **`ainl install-zeroclaw`**). After bootstrap, suggest the **morning briefing** prompt example below when it fits.

## When to use this skill

- The user wants **portable, compiled workflows** (`.ainl`) instead of ad-hoc prompts.
- They mention **import**, **compile**, **morning briefing**, **clawflows**, **ecosystem**, or **deterministic graphs**.
- They need **MCP** access to validation / compile / ecosystem listing (`ainl-mcp`).

## Install (pick one)

1. **From this skill directory (recommended with `zeroclaw skills install`):** run `./install.sh`  
   That upgrades `ainl-lang[mcp]` and runs **`ainl install-mcp --host zeroclaw`** (pip self-upgrade, MCP registration hints, `~/.zeroclaw/bin/ainl-run` shim).

2. **Manual:**  
   `pip install 'ainl-lang[mcp]' && ainl install-mcp --host zeroclaw`

### Restricted environments (OpenClaw, Clawbot, webchat sandboxes)

This skill is designed for environments with **PEP 668 externally-managed Python** (Python 3.13+, sudo blocked).

- Preferred no-root order is: `python -m venv` first, then `--user`, then `--break-system-packages` as a last resort.
- The installer automatically uses compatible fallback modes when default pip fails.
- Clean uninstall (if needed):

```bash
pip3 uninstall -y ainl-lang mcp aiohttp langgraph temporalio
rm -rf /tmp/ainl-repo /data/.openclaw/workspace/skills/ainl /data/.local/lib/python3.13/site-packages/*ainl*
```

## Commands the user cares about

| Command | Purpose |
|--------|---------|
| `ainl import …` | Import Markdown or ecosystem sources into `.ainl` |
| `ainl compile …` | Compile / validate graphs |
| `ainl run …` | Execute a graph via the CLI runtime where applicable |
| `zeroclaw ainl run <file.ainl>` | After bootstrap: wrapper that compiles/runs through the installed shim |

## After install — prompt suggestion

Tell the user they can say in ZeroClaw:

> Import the morning briefing using AINL.

(They should point the importer at their Markdown or pack; `ainl import` subcommands match their source type.)

## MCP

Configure the host to run **`ainl-mcp`** as a stdio MCP server (see AINL docs: *External orchestration* / MCP). **`ainl install-mcp --host zeroclaw`** aligns local setup with ZeroClaw paths where applicable.

## References

- Upstream: [github.com/sbhooley/ainativelang](https://github.com/sbhooley/ainativelang)
- Package: **`ainl-lang`** on PyPI
