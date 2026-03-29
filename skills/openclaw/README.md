# AINL — OpenClaw skill

Deterministic compiled graphs for [OpenClaw](https://openclaw.ai/): **importer**, **CLI**, **`ainl-mcp`** merged into **`~/.openclaw/openclaw.json`**, and a **`~/.openclaw/bin/ainl-run`** compile-then-run wrapper after bootstrap. **Operator quickstart:** [`docs/QUICKSTART_OPENCLAW.md`](../../docs/QUICKSTART_OPENCLAW.md) (`ainl install openclaw`, `ainl status`, `ainl doctor --ainl`). **Rolling budget / storage:** [`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`](../../docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md) §c. <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP -->

**PyPI:** `ainativelang` **v1.3.1** (optional extras: `[mcp]`, `[solana]`).

OpenClaw is normally installed with **npm** and **`openclaw onboard`**. This skill adds the **Python** **`ainl`** toolchain and wires **MCP** + **`ainl-run`** for OpenClaw’s config layout.

**Not ZeroClaw:** there is no `zeroclaw skills install <git url>` here. Use **ClawHub** (when the skill is published there), **manual folder copy**, or a **standalone git repo** you clone yourself.

## Where skills live

- **User scope:** `~/.openclaw/skills/<skill-name>/` (typical)
- **Workspace scope:** `<your-openclaw-workspace>/skills/` — default workspace is often **`~/.openclaw/workspace`**

Copy this directory so you have `SKILL.md`, `install.sh`, and `README.md` next to each other.

## Standalone repo (optional)

To publish as a **repository root** (not nested under `skills/` in the monorepo), copy this folder to **[github.com/sbhooley/ainl-openclaw-skill](https://github.com/sbhooley/ainl-openclaw-skill)** (or any repo) with this layout:

```text
ainl-openclaw-skill/
├── SKILL.md
├── install.sh
└── README.md
```

Users clone or download the repo, then copy the folder into **`~/.openclaw/skills/ainl-openclaw-skill/`** (or add via **ClawHub** when listed). OpenClaw does **not** mirror ZeroClaw’s `skills install <url>` one-liner.

## Install and use

### Option A — ClawHub

If this skill appears on **ClawHub**, install it the way OpenClaw documents for registry skills (UI or CLI), then run the installer from the skill directory:

```bash
cd ~/.openclaw/skills/<skill-folder>
chmod +x install.sh
./install.sh
```

### Option B — Manual copy from monorepo

This folder lives under the main AINL repo as [`skills/openclaw/`](./):

```bash
cp -R /path/to/ainativelang/skills/openclaw ~/.openclaw/skills/ainl
cd ~/.openclaw/skills/ainl
chmod +x install.sh
./install.sh
```

### Option C — Manual (no skill folder)

```bash
pip install 'ainativelang[mcp]'
ainl install-mcp --host openclaw
```

### Flags

Pass **`ainl install-mcp`** flags (e.g. **`--dry-run`**, **`--verbose`**) through the script:

```bash
./install.sh --verbose
./install.sh --dry-run
```

### Skip global npm

If you already manage the OpenClaw CLI yourself:

```bash
OPENCLAW_SKIP_NPM=1 ./install.sh
```

## What gets set up

1. **Optional `npm install -g openclaw@latest`** — refreshes the OpenClaw CLI when **npm** is on PATH (skipped if **`OPENCLAW_SKIP_NPM=1`**).
2. **`pip install --upgrade 'ainativelang[mcp]'`** — compiler, importer extras, MCP dependencies.
3. **`ainl install-mcp --host openclaw`** — pip self-upgrade path, **`mcpServers.ainl`** in **`~/.openclaw/openclaw.json`**, and **`~/.openclaw/bin/ainl-run`**.

Add **`~/.openclaw/bin`** to **PATH** if you want to invoke **`ainl-run`** without a full path (the installer prints a hint).

## Typical commands

| Command | Description |
|--------|-------------|
| `ainl import …` | Import Markdown or ecosystem sources into `.ainl` |
| `ainl compile <file.ainl>` | Compile / validate |
| `ainl run <file.ainl>` | Run via CLI where the graph supports it |
| `ainl install openclaw [--workspace PATH] [--dry-run]` | Patch gateway `env.shellEnv`, bootstrap SQLite, register three gold-standard crons, restart gateway |
| `ainl status [--json]` | Markdown (or JSON) health: workspace, weekly budget (legacy **`weekly_remaining_v1`** row or **`memory_records`** fallback), crons, token usage, caps <!-- AINL-OPENCLAW-TOP5-DOCS-ROLLUP --> |
| `ainl doctor --ainl` | Validate OpenClaw + AINL integration (env, schema, crons, bootstrap flag) |
| `~/.openclaw/bin/ainl-run <file.ainl>` | After MCP bootstrap: shim entrypoint |

Quickstart: [`docs/QUICKSTART_OPENCLAW.md`](../../docs/QUICKSTART_OPENCLAW.md) (repo root).

## Try in OpenClaw

After a successful install:

> Import the morning briefing using AINL.

Point the importer at the right source (Markdown path or ecosystem subcommand).

## Files

| File | Role |
|------|------|
| `SKILL.md` | Skill manifest + `metadata.openclaw` + agent instructions |
| `install.sh` | Optional npm OpenClaw CLI + pip + `ainl install-mcp --host openclaw` |
| `README.md` | Human-facing install and use |

## Upstream

- [github.com/sbhooley/ainativelang](https://github.com/sbhooley/ainativelang)
- [openclaw.ai](https://openclaw.ai/) (official site and installer)
