---
name: AINL
description: Deterministic compiled graphs for Hermes Agent (importer, runtime, MCP tools, learning-loop bridge)
install: ./install.sh
install_alt: pip install 'ainativelang[mcp]' && ainl install-mcp --host hermes
commands:
  - ainl import <source> — convert Markdown / ecosystem packs into `.ainl` graphs
  - ainl compile <file.ainl> — compile and validate deterministic graph IR
  - ainl run <file.ainl> — run compiled workflow (when your graph uses the runtime path)
  - ~/.hermes/bin/ainl-run <file.ainl> — compile-then-run wrapper after install-mcp --host hermes (add ~/.hermes/bin to PATH)
tags:
  - ainl
  - graphs
  - mcp
  - hermes
metadata:
  hermes:
    kind: skill
    upstream: https://github.com/sbhooley/ainativelang
    package_pypi: ainativelang
    mcp_server_key: ainl
    config_file: ~/.hermes/config.yaml
    skills_dir: ~/.hermes/skills
    onboarding_note: >-
      Hermes Agent reads MCP config from ~/.hermes/config.yaml (mcp_servers). This pack installs a local AINL skill folder and
      expects ainl-mcp to be registered as a stdio MCP server.
---

# AINL for Hermes Agent

**AINL** is an AI-native language that compiles **deterministic graphs**. In Hermes Agent, use it to import workflows, compile them, run them, and expose **`ainl-mcp`** tools to the agent for safe, repeatable execution.

**PyPI:** `ainativelang` **v1.3.3** (optional extras: `[mcp]`, `[solana]`).

## Agent instructions

Follow this skill when the user is on **Hermes Agent** (or wants a **closed learning loop** on top of **deterministic `.ainl` graphs**). Prefer **`./install.sh`** from a checked-out skill folder, or the manual path:

`pip install 'ainativelang[mcp]' && ainl install-mcp --host hermes`

After bootstrap, suggest the prompt below when it fits.

## When to use this skill

- The user wants **portable, compiled workflows** (`.ainl`) instead of ad-hoc prompt loops.
- They mention **import**, **compile**, **skills**, **learning loop**, or **MCP**.
- They want Hermes to evolve behavior while keeping a strict, checkable graph source of truth.

## Install (pick one)

1. **From this skill directory:** run `./install.sh`  
   That upgrades `ainl[mcp]` (if needed), installs a skill folder to `~/.hermes/skills/ainl/`, and wires MCP via `ainl install-mcp --host hermes`.

2. **Manual:**  
   `pip install 'ainativelang[mcp]' && ainl install-mcp --host hermes`

## After install — prompt suggestion

Tell the user they can say in Hermes:

> Import the morning briefing using AINL.

## MCP

Hermes reads MCP config from `~/.hermes/config.yaml` under `mcp_servers`. The host should run **`ainl-mcp`** as a stdio MCP server. `ainl install-mcp --host hermes` merges that entry when missing.

## Bridge (optional)

This pack includes `ainl_hermes_bridge.py` as a lightweight utility for:

- writing AINL trajectory/audit tapes into Hermes-friendly local memory files
- exporting Hermes-evolved behaviors back into `.ainl` (so you can re-run `ainl check --strict`)

