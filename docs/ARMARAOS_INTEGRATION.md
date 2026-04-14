# ArmaraOS integration

ArmaraOS is an **optional** host runtime for AINL workflows. AINL supports ArmaraOS at the same “host pack” level as OpenClaw (bootstrap + status + cron + bridge utilities), while preserving OpenClaw / ZeroClaw / Hermes Agent behavior unchanged.

## What you get

- **MCP support**: `ainl-mcp` registered into the host’s `config.toml` so ArmaraOS can call AINL tools over stdio (**today:** `~/.openfang/config.toml` in the upstream fork; **after rebrand:** `~/.armaraos/config.toml`).
- **Run wrapper**: a host-local `ainl-run` shim (installed under `~/.armaraos/bin/`) that forwards to `ainl run` (you may also mirror it under `~/.openfang/bin/` during the transition).
- **Emit to Hand package**: `ainl emit --target armaraos` produces a directory with `HAND.toml`, compiled IR JSON (`<stem>.ainl.json`), `security.json`, and `README.md`.
- **Status + schema bootstrap**: `ainl status --host armaraos` validates the local AINL memory DB schema and reports what’s installed.
- **Cron helper**: `ainl cron add ... --host armaraos` shells out to `armaraos cron add` when the ArmaraOS CLI is present.

ArmaraOS CLI is **not required** for AINL to install or run; ArmaraOS-only features (cron listing/adding) are best-effort when the `armaraos` binary is on PATH.

## Library layout on disk (daemon / desktop)

When ArmaraOS runs, graphs under `~/.armaraos/ainl-library/` may include:

| Path | Origin |
|------|--------|
| `armaraos-programs/` | First-party graphs **materialized** from the ArmaraOS build (health checks, learning-frame samples, stubs). |
| `demo/`, `examples/`, `intelligence/` | Mirrored from the public [ainativelang](https://github.com/sbhooley/ainativelang) repo when desktop sync runs (or equivalent). |

Paths in tutorials (e.g. `examples/compact/hello_compact.ainl`) match the **mirror** after sync. Paths documented in ArmaraOS as `armaraos-programs/...` refer to the **embedded** tree. See ArmaraOS `docs/ootb-ainl.md`.

## Quickstart (MCP bootstrap)

```bash
pip install 'ainativelang[mcp]'
ainl install armaraos
```

Verify:

```bash
ainl status --host armaraos
```

## Emit a Hand package

```bash
ainl emit my_flow.ainl --target armaraos -o ./my_flow_armaraos_hand
```

Expected outputs:

- `HAND.toml` — `[hand]` manifest including **`name`**, **`version`** (semver string), **`entrypoint`** (the `<stem>.ainl.json` filename), **`ainl_ir_version`** (from the compiled IR), plus metadata fields such as **`id`**, **`description`**, **`author`**.
- `<stem>.ainl.json` — canonical compiled IR JSON.
- `security.json` — WASM / sandbox policy hints plus **`capability_declarations.adapters`**, a sorted list of adapter roots inferred from the graph (from `ir["avm_policy_fragment"]["allowed_adapters"]`; empty when the program has no adapter-using steps).
- `README.md` — short human-oriented summary referencing the stem.

Regression coverage: **`tests/test_emit_armaraos_handpack.py`** (artifact set + manifest / security / README checks).

## Env vars (canonical + aliases)

AINL prefers `ARMARAOS_*` for ArmaraOS integration, with `AINL_*` and legacy `OPENFANG_*` aliases supported for compatibility.

| Purpose | Canonical | Aliases |
|---------|-----------|---------|
| Workspace root | `ARMARAOS_WORKSPACE` | `OPENFANG_WORKSPACE` |
| AINL SQLite DB path | `ARMARAOS_MEMORY_DB` | `AINL_MEMORY_DB`, `OPENFANG_MEMORY_DB` |
| Token audit JSONL | `ARMARAOS_TOKEN_AUDIT` | `OPENFANG_TOKEN_AUDIT` |
| Prefer session context injection | `ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT` | `OPENFANG_BOOTSTRAP_PREFER_SESSION_CONTEXT` |
| IR cache directory | `AINL_IR_CACHE_DIR` | (none) |
| Monitor cache JSON | `MONITOR_CACHE_JSON` | (none) |
| FS sandbox root | `AINL_FS_ROOT` | (none) |
| JSON graph memory file | `AINL_GRAPH_MEMORY_PATH` | (default `~/.armaraos/ainl_graph_memory.json`) |
| Bundle file for scheduled `ainl run` (host sets on child) | `AINL_BUNDLE_PATH` | Absolute path to `~/.armaraos/agents/<agent_id>/bundle.ainlbundle` when that file exists; **`AINLGraphMemoryBridge.boot`** pre-seeds **persona** nodes from the bundle (see **`docs/adapters/AINL_GRAPH_MEMORY.md`**). |
| Agent id for bundle + export subprocesses | `AINL_AGENT_ID` | Set with **`AINL_BUNDLE_PATH`** by ArmaraOS cron (**`Kernel::cron_run_job`**). |
| Bundle export helper only | `AINL_EXPORT_AGENT_ID` | Internal: set by **`export_ainl_bundle_after_ainl_run_best_effort`** in **armaraos** `openfang-runtime` when rewriting the bundle after a successful **`ainl`**. |

## AINL graph memory (bridge + runtime)

The **`ainl_graph_memory`** adapter stores typed **nodes** and **edges** in a JSON file (default under `~/.armaraos/`). The ArmaraOS bridge runner (`armaraos/bridge/runner.py`) builds a shared monitor registry via **`adapters.armaraos_integration.build_armaraos_monitor_registry`** (pre-allows and pre-registers **`ainl_graph_memory`**, **`bridge`**, **`cron_drift_check`**), registers host adapters (`armaraos_memory`, `github`, …), then calls **`boot_armaraos_graph_memory`** so **`AINLGraphMemoryBridge.boot()`** runs once after wiring. After each successful wrapper run it records a delegation node via **`on_delegation`**.

**Scheduled `ainl run` (kernel cron):** when the host runs **`ainl run`** for a job, it may set **`AINL_BUNDLE_PATH`** / **`AINL_AGENT_ID`** so **`boot()`** can merge **persona** rows from **`bundle.ainlbundle`** into the live JSON store before the graph executes, and a post-run step rebuilds that bundle from the bridge. See **armaraos** [`docs/scheduled-ainl.md`](https://github.com/sbhooley/armaraos/blob/main/docs/scheduled-ainl.md).

**Dashboard chat (Rust `ainl-memory`):** the daemon’s agent loop uses per-agent SQLite **`~/.armaraos/agents/<id>/ainl_memory.db`** to append recent **persona** traits (strength ≥ **0.1**, last **90** days) to the **system prompt** as **`[Persona traits active: …]`** (separate from the JSON file above). See **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) and **`docs/adapters/AINL_GRAPH_MEMORY.md`**.

AINL’s **`RuntimeEngine`** also supports IR ops **`MemoryRecall`** and **`MemorySearch`**, which dispatch the same adapter (for graphs compiled with those steps or nodes). Full contract, `R` examples, optional **FastAPI + D3** graph browser, and tests: **`docs/adapters/AINL_GRAPH_MEMORY.md`**.

## PostHog (ArmaraOS desktop only)

The **ainativelang** compiler repo does **not** include a PostHog API key (do not commit `phc_…` values). The ArmaraOS **desktop** app optionally sends **at most one** anonymous install event per machine via PostHog; **tagged release** CI on **sbhooley/armaraos** bakes in the key from **`ARMARAOS_POSTHOG_KEY`** or **`AINL_POSTHOG_KEY`** (if the first is unset). Use the **same** PostHog project key as **`NEXT_PUBLIC_POSTHOG_KEY`** on **ainativelangweb** (production env / Vercel) so web and desktop share one project.

**See also:** **armaraos** [`docs/release-desktop.md`](https://github.com/sbhooley/armaraos/blob/main/docs/release-desktop.md), [`docs/production-checklist.md`](https://github.com/sbhooley/armaraos/blob/main/docs/production-checklist.md) (optional secrets), [`docs/desktop.md`](https://github.com/sbhooley/armaraos/blob/main/docs/desktop.md) (product analytics section), root `README.md`.

## Troubleshooting

- **`ainl status --host armaraos` reports schema errors**: the command bootstraps required tables automatically. If the DB path is unexpected, set `ARMARAOS_MEMORY_DB` (or `AINL_MEMORY_DB`) explicitly and re-run status.
- **Cron helpers don’t work**: ensure the external `armaraos` CLI is installed and on PATH. AINL will skip cron checks when it is missing.

## Config schema note (upstream fork)

The current upstream fork’s MCP config schema expects a `[[mcp_servers]]` entry with a nested transport table:

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

## See also

- **Graph memory adapter + engine ops:** `docs/adapters/AINL_GRAPH_MEMORY.md`
- Host hub: `docs/getting_started/HOST_MCP_INTEGRATIONS.md`
- ArmaraOS config reference: `armaraos/docs/CONFIG.md`
- ArmaraOS install notes: `armaraos/docs/INSTALL.md`
- ArmaraOS migration: `armaraos/docs/MIGRATION.md`

