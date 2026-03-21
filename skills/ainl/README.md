# AINL — ZeroClaw skill

Deterministic compiled graphs for [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw): **importer**, **CLI**, **`ainl-mcp`**, and a **`zeroclaw ainl run`**-friendly shim after bootstrap.

## Standalone repo (`sbhooley/ainl-zeroclaw-skill`)

Publish this folder as the **repository root** (not nested under `skills/`):

```text
ainl-zeroclaw-skill/
├── SKILL.md
├── install.sh
└── README.md
```

Then: `zeroclaw skills install https://github.com/sbhooley/ainl-zeroclaw-skill`.

## Install and use

### Option A — `zeroclaw skills install` (standalone repo)

When this directory is the root of **`sbhooley/ainl-zeroclaw-skill`** (or any git URL ZeroClaw accepts):

```bash
zeroclaw skills install https://github.com/sbhooley/ainl-zeroclaw-skill
```

ZeroClaw will fetch the skill; run the skill’s installer from the checked-out path, or rely on the skill manifest’s **`install`** field pointing at `./install.sh`.

Then:

```bash
./install.sh
```

Or pass flags through to the CLI (once your `ainl` supports them):

```bash
./install.sh --verbose
./install.sh --dry-run
```

### Option B — Monorepo copy

This folder also lives under the main AINL repo as [`skills/ainl/`](./):

```bash
cd /path/to/ainativelang/skills/ainl
chmod +x install.sh
./install.sh
```

### Option C — Manual (no skill checkout)

```bash
pip install 'ainl-lang[mcp]'
ainl install-zeroclaw
```

## What gets set up

1. **`pip install --upgrade 'ainl-lang[mcp]'`** — compiler, importer extras, MCP dependencies.  
2. **`ainl install-zeroclaw`** — self-upgrade path, MCP registration for ZeroClaw-style hosts, and **`~/.zeroclaw/bin/ainl-run`** so **`zeroclaw ainl run <file.ainl>`** can delegate to a compile/run wrapper.

## Typical commands

| Command | Description |
|--------|-------------|
| `ainl import …` | Import Markdown or ecosystem sources into `.ainl` |
| `ainl compile <file.ainl>` | Compile / validate |
| `ainl run <file.ainl>` | Run via CLI where the graph supports it |
| `zeroclaw ainl run <file.ainl>` | After `install-zeroclaw`: shim entrypoint |

## Try in ZeroClaw

After a successful install:

> Import the morning briefing using AINL.

Point the importer at the right source (Markdown path or ecosystem subcommand).

## Files

| File | Role |
|------|------|
| `SKILL.md` | Skill manifest + agent instructions (YAML frontmatter) |
| `install.sh` | `pip install` + `ainl install-zeroclaw` |
| `README.md` | Human-facing install and use |

## Upstream

- [github.com/sbhooley/ainativelang](https://github.com/sbhooley/ainativelang)
