# AINL + Hermes Agent Skills Pack

This folder is the **Hermes Agent** companion skill pack for **AINL**.

**PyPI:** `ainativelang` **v1.5.1** (optional extras: `[mcp]`, `[solana]`).

**Gold standard integration:**

- **AINL** compiles AI-authored workflows into **deterministic graphs** (canonical IR).
- **Hermes Agent** runs a **closed learning loop** (skill evolution) on top of stable tool surfaces.
- A small **bidirectional bridge** lets you feed AINL execution/audit tapes into Hermes memory, and export Hermes-evolved behavior back into `.ainl` for **strict validation**.

## Quick usage

1. Install and register AINL MCP for Hermes:

```bash
ainl install-mcp --host hermes
```

2. Then say in Hermes:

> Import the morning briefing using AINL

Hermes should discover the **AINL MCP server** and the installed **AINL skill pack** under `~/.hermes/skills/`.

## What this pack installs

- A Hermes skill folder under `~/.hermes/skills/ainl/` containing:
  - `SKILL.md` — Hermes-facing skill instructions and install hints
  - `example_ainl_to_hermes_skill.ainl` — small deterministic example workflow
  - `ainl_hermes_bridge.py` — utility bridge (AINL trajectories ↔ Hermes memory / evolved skill export)

## Install

From this directory:

```bash
chmod +x install.sh
./install.sh
```

You can pass `ainl install-mcp` flags through:

```bash
./install.sh --dry-run
./install.sh --verbose
```

## Files

| File | Role |
|------|------|
| `SKILL.md` | Skill manifest + Hermes-facing agent instructions |
| `install.sh` | Idempotent installer for `~/.hermes/skills/ainl/` (and optional MCP bootstrap) |
| `ainl_hermes_bridge.py` | Bridge helper for trajectories and export |
| `example_ainl_to_hermes_skill.ainl` | Minimal strict-safe workflow sample |

## Upstream

- AINL: [github.com/sbhooley/ainativelang](https://github.com/sbhooley/ainativelang)
- Hermes Agent: [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

