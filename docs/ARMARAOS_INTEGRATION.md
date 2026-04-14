# ArmaraOS integration

ArmaraOS is an **optional** host runtime for AINL workflows. AINL supports ArmaraOS at the same “host pack” level as OpenClaw (bootstrap + status + cron + bridge utilities), while preserving OpenClaw / ZeroClaw / Hermes Agent behavior unchanged.

## What you get

- **MCP support**: `ainl-mcp` registered into the host’s `config.toml` so ArmaraOS can call AINL tools over stdio (**today:** `~/.openfang/config.toml` in the upstream fork; **after rebrand:** `~/.armaraos/config.toml`).
- **Run wrapper**: a host-local `ainl-run` shim (installed under `~/.armaraos/bin/`) that forwards to `ainl run` (you may also mirror it under `~/.openfang/bin/` during the transition).
- **Emit to Hand package**: `ainl emit --target armaraos` produces a directory with `HAND.toml`, compiled IR JSON (`<stem>.ainl.json`), `security.json`, and `README.md`. Each artifact declares a **`schema_version`** string (currently **`1`**) aligned with the **openfang-hands** loader and **`openfang hand validate`** so freshly emitted packs do not warn on a missing manifest version.
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

- `HAND.toml` — `[hand]` manifest including **`name`**, **`version`** (semver string), **`entrypoint`** (the `<stem>.ainl.json` filename), **`ainl_ir_version`** (from the compiled IR), **`schema_version`** (hand manifest contract; **`1`** today, immediately after **`ainl_ir_version`**), plus metadata fields such as **`id`**, **`description`**, **`author`**.
- `<stem>.ainl.json` — canonical compiled IR JSON with a top-level **`schema_version`** field (**`1`**) added by the emitter. The in-memory IR dict passed into **`emit_armaraos`** is **not** mutated; only the on-disk copy includes **`schema_version`**.
- `security.json` — WASM / sandbox policy hints; the first key is **`schema_version`** (**`1`**, same contract family as **`HAND.toml`**), then **`version`**, **`sandbox`**, **`wasm_config`**, etc. Also includes **`capability_declarations.adapters`**, a sorted list of adapter roots inferred from the graph (from `ir["avm_policy_fragment"]["allowed_adapters"]`; empty when the program has no adapter-using steps).
- `README.md` — short human-oriented summary referencing the stem and calling out **`schema_version`** on each emitted file.

Emitter source of truth: **`armaraos/emitter/armaraos.py`** — constants **`HAND_SCHEMA_VERSION`** and **`AINL_IR_SCHEMA_VERSION`** (both the literal **`1`** as a string today); keep these in sync when **ArmaraOS** / **openfang-hands** bumps its expected versions.

Regression coverage: **`tests/test_emit_armaraos_handpack.py`** (artifact set + manifest / IR / security **`schema_version`** + no in-place IR mutation + README checks).

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
| Rust → Python graph snapshot (SQLite export JSON) | `AINL_GRAPH_MEMORY_ARMARAOS_EXPORT` | **Daemon (Rust):** must be a **directory** if set; runtime writes **`{dir}/{agent_id}_graph_export.json`** per agent after persona evolution. If **unset**, Rust writes **`…/agents/<id>/ainl_graph_memory_export.json`** next to **`ainl_memory.db`**. **Python (`GraphStore`):** same env can be a **directory** (needs **`ARMARAOS_AGENT_ID`**) or a **single `.json` file** (legacy / CLI export). If export env is **unset** but **`ARMARAOS_AGENT_ID`** is set, Python loads the default **`…/agents/<id>/ainl_graph_memory_export.json`** when present. See **`docs/adapters/AINL_GRAPH_MEMORY.md`** and **armaraos** **`docs/graph-memory.md`**. |
| Graph memory **inbox** (Python → Rust ingest) | `ARMARAOS_AGENT_ID` | Required for **`AinlMemorySyncWriter`** / bridge **`_sync`** pushes; with **`ARMARAOS_HOME`** (or **`OPENFANG_HOME`**, or default **`~/.armaraos`**) and existing **`agents/`** dir, appends to **`agents/<id>/ainl_graph_memory_inbox.json`**. Also used with **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** when that value names a **directory** (per-agent snapshot filename). See **`armaraos/docs/graph-memory-sync.md`**. |
| ArmaraOS data root (inbox + paths) | `ARMARAOS_HOME` | Optional; aliases **`OPENFANG_HOME`**. |
| Bundle file for scheduled `ainl run` (host sets on child) | `AINL_BUNDLE_PATH` | Absolute path to `~/.armaraos/agents/<agent_id>/bundle.ainlbundle` when that file exists; **`AINLGraphMemoryBridge.boot`** pre-seeds **`bundle.persona`** via **`persona.update`** and **`bundle.memory`** (non-persona graph nodes: episodic, semantic, procedural, patch) into the JSON **`GraphStore`** when ids are not already present (see **`docs/adapters/AINL_GRAPH_MEMORY.md`**). |
| Agent id for bundle + export subprocesses | `AINL_AGENT_ID` | Set with **`AINL_BUNDLE_PATH`** by ArmaraOS cron (**`Kernel::cron_run_job`**). |
| Agent id for Python graph-memory inbox (`AinlMemorySyncWriter`) | `ARMARAOS_AGENT_ID` | UUID string; with **`ARMARAOS_HOME`** / default **`~/.armaraos`**, resolves **`…/agents/<id>/ainl_graph_memory_inbox.json`** for append + daemon drain (see **`docs/adapters/AINL_GRAPH_MEMORY.md`**). |
| Bundle export helper only | `AINL_EXPORT_AGENT_ID` | Internal: set by **`export_ainl_bundle_after_ainl_run_best_effort`** in **armaraos** `openfang-runtime` when rewriting the bundle after a successful **`ainl`**. |

## AINL graph memory (bridge + runtime)

The **`ainl_graph_memory`** adapter stores typed **nodes** and **edges** in a JSON file (default under `~/.armaraos/`). The ArmaraOS bridge runner (`armaraos/bridge/runner.py`) builds a shared monitor registry via **`adapters.armaraos_integration.build_armaraos_monitor_registry`**, registers host adapters (`armaraos_memory`, `github`, …), then **`boot_armaraos_graph_memory`** so **`AINLGraphMemoryBridge.boot()`** runs once. The returned **`AdapterRegistry`** is wrapped with **`_GraphToolInboxAdapterRegistry`** so non-core adapter calls become **`on_tool_execution`** graph nodes and optional **`ainl_graph_memory_inbox.json`** appends when **`ARMARAOS_AGENT_ID`** + **`agents/`** are present (**`armaraos/docs/graph-memory-sync.md`**). After each successful wrapper run it records a delegation node via **`on_delegation`**.

**Scheduled `ainl run` (kernel cron):** when the host runs **`ainl run`** for a job, it may set **`AINL_BUNDLE_PATH`** / **`AINL_AGENT_ID`** so **`boot()`** can merge **`bundle.persona`** and **`bundle.memory`** from **`bundle.ainlbundle`** into the live JSON store before the graph executes, and a post-run step rebuilds that bundle from the bridge ( **`AINLBundleBuilder`** snapshots **`export_graph()`** + **`persona_load`** ). See **armaraos** [`docs/scheduled-ainl.md`](https://github.com/sbhooley/armaraos/blob/main/docs/scheduled-ainl.md).

**Dashboard chat (Rust `ainl-memory`):** the daemon’s agent loop uses per-agent SQLite **`~/.armaraos/agents/<id>/ainl_memory.db`** to append recent **persona** traits (strength ≥ **0.1**, last **90** days) to the **system prompt** as **`[Persona traits active: …]`** (separate from the JSON file above). The same loop optionally refreshes a **per-agent JSON export** for **ainativelang** **`GraphStore`** (shared export directory or default file next to the DB — **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** / **`armaraos_graph_memory_export_json_path`**). See **armaraos** [`docs/graph-memory.md`](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md) and **`docs/adapters/AINL_GRAPH_MEMORY.md`**.

**Python inbox (write-back):** when **`ARMARAOS_AGENT_ID`** is set, **`armaraos/bridge/ainl_memory_sync.py`** (**`AinlMemorySyncWriter`**) can append **`MemoryNode`** rows to **`…/agents/<id>/ainl_graph_memory_inbox.json`**. The daemon drains that file into **`ainl_memory.db`** each agent turn; envelope fields **`schema_version`**, **`source_features`**, and optional **`requires_ainl_tagger`** in **`source_features`** align Rust ingest with compile-time features. Schema + CI: **`armaraos/bridge/ainl_graph_memory_inbox_schema_v1.json`**, **`.github/workflows/cross-repo-armaraos-bridge.yml`**.

**Debugging Python vs daemon capabilities:** **`GET /api/status`** on the ArmaraOS API includes **`openfang_runtime_ainl`**: booleans **`ainl_extractor`**, **`ainl_tagger`**, **`ainl_persona_evolution`**, **`ainl_runtime_engine`** (which **`openfang-runtime`** Cargo features this binary was built with). Use that when inbox rows are skipped or **ainl-runtime** paths behave differently than on another machine.

AINL’s **`RuntimeEngine`** also supports IR ops **`MemoryRecall`** and **`MemorySearch`**, which dispatch the same adapter (for graphs compiled with those steps or nodes). Full contract, `R` examples, optional **FastAPI + D3** graph browser, and tests: **`docs/adapters/AINL_GRAPH_MEMORY.md`**.

### Monitor registry API (`adapters/armaraos_integration.py`)

Use this module when embedding the same adapter surface as **`armaraos/bridge/runner.py`** (scheduled wrappers, local tools, tests):

| Symbol | Role |
|--------|------|
| **`build_armaraos_monitor_registry(..., boot_graph_memory=False)`** | Creates **`AdapterRegistry`**, **`allow`** + **`register`** for **`ainl_graph_memory`**, **`bridge`**, **`cron_drift_check`**. Pass **`boot_graph_memory=True`** only for monitor-only processes that do not register extra adapters before graph **`boot`**. |
| **`boot_armaraos_graph_memory(reg, agent_id=...)`** | **`reg.get("ainl_graph_memory")`** → **`AINLGraphMemoryBridge.boot()`**; returns the bridge instance. Call **after** any extra **`register`** calls (runner pattern). |
| **`armaraos_monitor_registry()`** | Convenience: same as **`build_armaraos_monitor_registry(boot_graph_memory=False)`**. |
| **`ARMARAOS_MONITOR_PRESEEDED_ADAPTERS`** (`adapters/armaraos_defaults.py`) | Single source of truth for the pre-seeded adapter **names**. |

**Runtime:** **`AdapterRegistry.get(name)`** (`runtime/adapters/base.py`) returns the registered **`RuntimeAdapter`** or **`None`** (does not enforce the capability allowlist — use **`call`** for gated dispatch). **`RuntimeEngine`** uses **`get`** when it needs the graph-memory **`GraphStore`** for patch finalize / reinstall / fitness.

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
- **Graph memory inbox (Python write-back):** `armaraos/docs/graph-memory-sync.md`
- Host hub: `docs/getting_started/HOST_MCP_INTEGRATIONS.md`
- ArmaraOS config reference: `armaraos/docs/CONFIG.md`
- ArmaraOS install notes: `armaraos/docs/INSTALL.md`
- ArmaraOS migration: `armaraos/docs/MIGRATION.md`

