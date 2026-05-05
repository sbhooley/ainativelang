# Agent Install Simplification — Design

**Status:** Proposed
**Date:** 2026-05-05
**Author:** Terrence Schonleber (external contribution via PR)
**Tracking PR:** sbhooley/ainativelang (forthcoming)

## Problem

Today an AI agent (Claude Code, Cursor, Cline, Codex CLI/Desktop, Claude
Desktop, OpenClaw, Hermes, ArmaraOS, or any generic MCP host) that is asked
"install AINL into this project" cannot do so without human-supplied context.
The repo presents:

- A `README.md` "Start here — pick your path" matrix with five different
  install commands keyed to host
- An `AGENTS.md` with install information buried below 200+ lines of unrelated
  ground truth
- Four overlapping agent guides — `AI_AGENT_QUICKSTART_OPENCLAW.md`,
  `OPENCLAW_AI_AGENT.md`, `docs/AI_AGENT_CONTINUITY.md`,
  `docs/QUICKSTART_OPENCLAW.md` — each starting with a different reading list

An agent with no human pointing them at the right file picks one of the agent
guides at random, follows its 10-document reading list, and either gets stuck
on a prerequisite that doesn't apply or installs the wrong path for the host.

## Goal

Pointing any agent at this repo (`https://github.com/sbhooley/ainativelang`)
should be sufficient for the agent to install AINL into its own host stack
correctly — no human-supplied selection, no "pick your path" branching, no
multi-document reading list before the first command runs.

## Non-goals

- Auto-installing the Python package itself. The agent still needs `pipx` or
  `pip`; we provide the post-install glue, not a system-package bootstrap.
- Uninstall / migration tooling. Separate feature.
- Rewriting the 1,665-line README. We insert the new install section at the
  top and demote the existing host matrix to a "Per-host details (advanced)"
  subsection.
- Per-host MCP-server tuning beyond defaults. `setup` writes a working
  baseline; tuning stays a host-side concern.
- Fixing the `Notify ainativelangweb content sync` workflow's `Bad
  credentials` failure (separate repo-config issue).

## Design

### Single canonical entry point

A new top-level CLI subcommand, `ainl setup`, also reachable as
`python -m ainativelang setup`. The agent-facing command is:

```bash
pipx run ainativelang setup --auto
```

Fallback if `pipx` is unavailable:

```bash
python3 -m pip install --user 'ainativelang[mcp]' && python3 -m ainativelang setup --auto
```

What `setup` does, in order:

1. **Detect host(s)** by probing standard config paths and environment
   variables (matrix below). Multiple matches are normal; all are configured.
2. **Merge MCP server entry** named `ainl` (stdio launching `ainl-mcp`) into
   each detected host's config file. Atomic write via tempfile + rename;
   pre-write backup at `<file>.ainl-backup-<UTC-compact-timestamp>` (e.g. `…ainl-backup-20260505T141530Z`; no colons so the path stays Windows-safe).
3. **Run `ainl doctor`** and capture exit status. Any non-zero exit is
   surfaced in the summary but does not roll back the MCP config (the host
   may need a restart before doctor sees the new server).
4. **Print a summary**: hosts configured, files touched, doctor result, and
   exactly one next step (typically "restart your agent host").

Flags:

| Flag                | Meaning                                                                   |
|---------------------|---------------------------------------------------------------------------|
| `--auto` (default)  | Detect every host present and configure all of them                       |
| `--host <name>`     | Force a single host; bypass detection                                     |
| `--dry-run`         | Print the plan (files, diffs) without writing                             |
| `--print-config`    | Emit just the stdio JSON block for paste-into-host scenarios              |
| `--no-verify`       | Skip the trailing `ainl doctor` step                                      |
| `--quiet`           | Machine-readable JSON to stdout, human prose to stderr                    |

### Host detection matrix

Detection uses a "first signal wins" rule per host. A host is treated as
present if **any** of its signals match. Multiple hosts can be present
simultaneously and all are configured.

| Host                       | Detection signals                                                                                              | Config target                                                                                |
|----------------------------|----------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| Claude Code (project)      | `cwd` contains `.mcp.json`, **or** `cwd` contains `.claude/`                                                   | merge into `./.mcp.json`                                                                     |
| Claude Code (user)         | `~/.claude/` exists                                                                                            | merge into `~/.claude/mcp.json`                                                              |
| Cursor                     | `~/.cursor/mcp.json` exists, **or** any `CURSOR_*` env var set                                                 | merge into `~/.cursor/mcp.json`                                                              |
| Cline                      | `~/Library/Application Support/Cline/` (mac) or `~/.config/Cline/` (linux) or `%APPDATA%/Cline/` (win) exists  | merge into Cline's `cline_mcp_settings.json` at the appropriate location                     |
| Codex CLI                  | `~/.codex/` exists, **or** `codex` on `PATH`                                                                   | merge into `~/.codex/config.toml` `[[mcp_servers]]`                                          |
| Codex Desktop              | macOS: `~/Library/Application Support/Codex/config.json` exists; Windows: `%APPDATA%/Codex/config.json` exists | merge into that file                                                                         |
| Claude Desktop             | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%/Claude/...`     | merge into that file                                                                         |
| OpenClaw                   | `~/.openclaw/openclaw.json` exists                                                                             | delegate to existing `ainl install-mcp --host openclaw`                                      |
| Hermes                     | `~/.hermes/` exists                                                                                            | delegate to existing `ainl install-mcp --host hermes`                                        |
| ArmaraOS                   | `~/.armaraos/config.toml` exists                                                                               | delegate to existing `ainl install-mcp --host armaraos`                                      |
| Generic MCP (fallback)     | nothing detected                                                                                               | print stdio JSON block and the literal path/process pointer; exit 0                          |

The three hosts with existing `ainl install-mcp --host <name>` support
(OpenClaw, Hermes, ArmaraOS) are handled by delegation rather than
reimplementation — `setup` shells out to the existing subcommand. This keeps
host-specific quirks (TOML for ArmaraOS, JSON-merge semantics for OpenClaw)
in their authoritative place.

### Idempotent merge semantics

For every host configured directly (not delegated), the merge rule is:

1. Read the existing config file. If absent, start from `{}`.
2. Locate or create the MCP-servers container per the host's schema (e.g.
   `mcpServers` for Claude Desktop / Cursor / `.mcp.json`, `[[mcp_servers]]`
   array-of-tables for Codex CLI's TOML).
3. If a server entry named `ainl` already exists, **replace** it. Do not
   produce duplicate entries.
4. Write the new content to a tempfile in the same directory; `os.rename` to
   the target. Pre-write backup at
   `<original>.ainl-backup-<RFC3339-timestamp>`.

The MCP server entry is the same shape for JSON hosts (modulo each host's
top-level key naming):

```json
{
  "command": "/abs/path/to/ainl-mcp",
  "args": [],
  "env": {"AINL_MCP_AGENT_ID": "<host-tag>"}
}
```

The `command` is **always written as an absolute path** resolved via
`shutil.which("ainl-mcp")` at install time. GUI MCP hosts (Claude Desktop,
Cursor on macOS) do not see `~/.local/bin` from their launch environment, so
relying on `PATH` produces silent "server failed to start" failures. This
mirrors brainctl's working pattern (`/Users/.../venvs/brainctl/bin/brainctl-mcp`
in real Claude Desktop config) — verified on this developer's machine.

For Codex CLI (TOML), the equivalent shape is:

```toml
[mcp_servers.ainl]
command = "/abs/path/to/ainl-mcp"
cwd = "/Users/<user>"
enabled = true
```

Format observed in working Codex CLI config on this developer's machine; the
detection writer follows that exact shape. If the user has
configured a non-default exposure profile, `setup` reads
`AINL_MCP_EXPOSURE_PROFILE` from the environment and threads it into the
`env` block of the MCP entry so re-runs are idempotent for that operator
preference too.

### Machine-readable companion

A new file at repo root, `.agent-install.json`:

```json
{
  "schema_version": "1.0",
  "primary_command": "pipx run ainativelang setup --auto",
  "fallback_command": "python3 -m pip install --user 'ainativelang[mcp]' && python3 -m ainativelang setup --auto",
  "verify_command": "ainl doctor",
  "min_python": "3.10",
  "produces_mcp_server": "ainl-mcp",
  "supported_hosts": [
    "claude-code-project",
    "claude-code-user",
    "cursor",
    "cline",
    "codex-cli",
    "codex-desktop",
    "claude-desktop",
    "openclaw",
    "hermes",
    "armaraos",
    "generic-mcp"
  ],
  "notes_for_agents": "Run primary_command. If it fails because pipx is unavailable, run fallback_command. Then verify with verify_command. No further configuration is required — the setup command auto-detects host(s) and writes the right MCP config."
}
```

This is cheap insurance for any agent that prefers structured signals over
prose. The file is also linked from the `AGENTS.md` install block.

### README and AGENTS.md changes

Both files get an identical install block at the very top, above any other
content, formatted for both humans and agents:

```markdown
## For agents — install AINL (one step)

Run:

    pipx run ainativelang setup --auto

Fallback if `pipx` is unavailable:

    python3 -m pip install --user 'ainativelang[mcp]' && python3 -m ainativelang setup --auto

That's the entire install. The setup command auto-detects your host
(Claude Code, Cursor, Cline, Codex CLI/Desktop, Claude Desktop, OpenClaw,
Hermes, ArmaraOS, or any generic MCP host), merges the right MCP config,
and verifies with `ainl doctor`. Backups of any prior config are created
before write.

If your host isn't detected, run `ainl setup --print-config` to get the
stdio block to paste into your MCP config manually.

Machine-readable spec: [`.agent-install.json`](./.agent-install.json).
```

The existing `README.md` "Start here — pick your path" / per-host matrix
moves into a new subsection titled **"Per-host details (advanced)"**, kept
verbatim for users who want to see what `ainl setup` is doing under the
hood. No content is deleted from the README.

### Documentation consolidation (Phase 2)

In the same PR, consolidate the four overlapping agent guides under a new
`docs/agents/` directory with stub redirects at the original paths so
external links keep working:

| Original                                  | New canonical                            | Stub at original |
|-------------------------------------------|------------------------------------------|------------------|
| `AI_AGENT_QUICKSTART_OPENCLAW.md`         | `docs/agents/openclaw-quickstart.md`     | one-line pointer |
| `OPENCLAW_AI_AGENT.md`                    | `docs/agents/openclaw-overview.md`       | one-line pointer |
| `docs/AI_AGENT_CONTINUITY.md`             | `docs/agents/continuity.md`              | one-line pointer |
| `docs/QUICKSTART_OPENCLAW.md`             | `docs/agents/openclaw-operator.md`       | one-line pointer |

Stub format (one line of body):

```markdown
> This guide moved to [`docs/agents/<new-name>.md`](docs/agents/<new-name>.md).
```

A new `docs/agents/INDEX.md` lists the four guides with one-sentence
descriptors, cross-referenced from the install block in `AGENTS.md`.

`AGENTS.md` itself stays the ground-truth file; only its top changes
(install block prepended).

### Testing

Three layers:

1. **Unit tests** (`tests/test_agent_setup.py`):
   - Detection: each host's signals trigger detection; absence triggers
     non-detection. Mocked filesystem and env via `monkeypatch`.
   - Merge logic: idempotency (running twice produces identical content),
     backup creation, atomic rename, schema correctness for each host's
     config shape.
   - Flag handling: `--dry-run` writes nothing, `--print-config` writes
     nothing and emits well-formed JSON, `--host <name>` bypasses detection.

2. **Snapshot tests** (`tests/setup_fixtures/`):
   - For each host, a fixture HOME directory and the expected post-`setup`
     state. Snapshot diffs catch accidental schema drift.

3. **CI smoke test** (`scripts/run_test_profiles.py --profile core`
   inclusion):
   - Spin up a temp HOME with selected fixtures, run
     `python -m ainativelang setup --auto`, assert exit 0, assert each
     "host present" fixture caused the right file change. Runs on the
     existing Linux/macOS/Windows matrix so we catch path-separator and
     line-ending issues.

Pre-merge manual verification on macOS:

- Claude Code (real install)
- Cursor (real install)
- Claude Desktop (real install)
- One generic-MCP fallback case

## Risks and mitigations

| Risk                                                       | Mitigation                                                                                                                                  |
|------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `setup` corrupts a user's host config                      | Atomic rename, pre-write backup with timestamp, snapshot tests for each host's exact merge shape, `--dry-run` for preview                    |
| `pipx run ainativelang` fails to find `setup`              | Wire `setup` as an explicit `[project.scripts]` entry in `pyproject.toml`; CI smoke test exercises the `pipx run` path                       |
| Host detection produces a false positive (configures host that isn't really there) | Detection uses concrete file/env signals, not heuristics; the merge is idempotent and backed up so worst-case is a noop on a stale config   |
| Phase 2 doc moves break external links                     | Stub redirects at every old path; the stub points at the new location; existing links continue to resolve through one extra hop             |
| Codex CLI's exact MCP config format drifts                 | Detection signal is conservative (presence of `~/.codex/`); if the format isn't recognized at runtime, fall through to `--print-config` mode |
| Existing `ainl install-mcp --host <name>` paths break      | `setup` delegates to those subcommands rather than reimplementing them; their tests stay authoritative                                       |

## Implementation order

The plan that comes out of this spec will sequence the work as:

1. New `ainl setup` subcommand and `__main__.py` entry — implementation +
   unit tests + snapshot fixtures (Linux/macOS/Windows aware paths)
2. `pyproject.toml` `setup` console-script wiring + CI smoke test for
   `pipx run` path
3. `.agent-install.json`
4. `README.md` + `AGENTS.md` install-block prepend; demote existing matrix
5. `docs/agents/` consolidation + stub redirects + `docs/agents/INDEX.md`
6. Manual verification on real Claude Code / Cursor / Claude Desktop;
   final docs polish

## Out-of-scope follow-ups

- Surfacing the `setup` command as an MCP tool (`ainl_setup`) for hosts
  that prefer to invoke it through the running MCP connection
- A "downgrade / uninstall" companion that removes the `ainl` server entry
  cleanly
- Auto-detecting `pipx` vs `pip` and choosing the right bootstrap line
  rather than asking the agent to pick the fallback
