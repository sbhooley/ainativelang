# Hermes Agent integration

**Hub (all MCP hosts):** [`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md) — **`ainl install-mcp --host hermes`** (same as **`ainl hermes-install`**).

**PyPI:** `ainativelang` **v1.5.0**.

AINL ships official Hermes Agent support via:

- **MCP bootstrap**: `ainl install-mcp --host hermes` (merges `ainl-mcp` into `~/.hermes/config.yaml`, installs `~/.hermes/bin/ainl-run`, prints PATH hints)
- **Skill pack**: [`skills/hermes/`](../skills/hermes/) (bridge helpers + install script)
- **Emitter**: `ainl compile --emit hermes-skill` (drop-in Hermes skill bundle)

Hermes discovers AINL skills automatically through its skills system (e.g. bundles under `~/.hermes/skills/`) and invokes the registered MCP tool **`ainl_run`** for deterministic execution.

Hermes brings the learning loop; AINL brings deterministic graph semantics. The result is a **self-improving agent** that still has a **strictly replayable** execution core.

---

## Architecture (compile → run → learn → validate)

Text flow:

1. **Author/import** a workflow as `.ainl`
2. **Compile** to canonical IR (strict mode): `ainl check --strict` / `ainl compile --strict`
3. **Emit** a Hermes skill bundle: `--emit hermes-skill`
4. **Hermes runs the skill** by calling the MCP tool **`ainl_run`** with the bundled AINL source
5. **AINL produces audit tapes** (trajectory JSONL) when enabled
6. **Bridge ingests tapes** into Hermes memory (Honcho) so the loop can learn from executions
7. **Hermes evolves** candidate improvements (new prompts, new steps, refined control flow)
8. **Export back to `.ainl`** and re-run `ainl check --strict` before promotion

Key contract:

- **Determinism** lives at the AINL runtime boundary: Hermes calls `ainl_run` rather than re-orchestrating the workflow in prose.
- **Learning** lives above the boundary: Hermes can propose edits, but AINL strict mode is the gate.

---

## Quickstart (recommended)

### 1) Install Hermes Agent (host)

Follow Hermes’ official install docs:

- Hermes repo: `https://github.com/NousResearch/hermes-agent`

Ensure `hermes` is on your `PATH` and that `~/.hermes/` exists after onboarding.

### 2) Install AINL MCP support for Hermes

Either:

```bash
pip install 'ainativelang[mcp]'
ainl install-mcp --host hermes
```

Or the shortcut:

```bash
pip install 'ainativelang[mcp]'
ainl hermes-install
```

What this wires:

- `~/.hermes/config.yaml` → adds a `mcp_servers.ainl` stdio entry pointing to `ainl-mcp`
- `~/.hermes/bin/ainl-run` → shim that compiles then runs a `.ainl` file
- A PATH hint to include `~/.hermes/bin`

**Optional adapter — `code_context`:** workflows that call **`R code_context.*`** (tiered repo index, dependencies, impact, **`COMPRESS_CONTEXT`**) must pass **`--enable-adapter code_context`** to **`ainl run`** or **`~/.hermes/bin/ainl-run`** (or any cron/wrapper that forwards args to **`ainl run`**). Installing MCP does **not** enable optional adapters. Guide: **`docs/adapters/CODE_CONTEXT.md`** · demo **`examples/code_context_demo.ainl`** · optional env **`AINL_CODE_CONTEXT_STORE`**.

### 3) Scaffold a Hermes-targeted worker

```bash
ainl init my-worker --target hermes
cd my-worker
```

### 4) Emit a Hermes skill bundle

The Hermes emitter writes a drop-in skill bundle directory with:

- `SKILL.md` (agentskills-style markdown + `ainl_run` payload)
- `workflow.ainl` (exact source)
- `ir.json` (canonical IR)

```bash
ainl compile main.ainl --strict --emit hermes-skill -o ~/.hermes/skills/ainl-imports/my-worker/
```

### 5) Use the skill in Hermes

Start Hermes:

```bash
hermes chat
```

Then ask:

> Import the morning briefing using AINL.

Or browse installed skills (depending on your Hermes build) and run the emitted bundle.

---

## Closed learning loop (audit tapes ↔ memory ↔ strict validation)

### A) AINL audit tapes → Hermes memory (Honcho)

AINL can write a trajectory JSONL “tape” for each run. When using `ainl-run`, enable it with:

```bash
export AINL_LOG_TRAJECTORY=1
```

Then ingest it into Hermes via the bridge helpers in the Hermes skill pack:

- `skills/hermes/ainl_hermes_bridge.py` (installed into `~/.hermes/skills/ainl/` by `skills/hermes/install.sh`)

### B) Hermes-evolved trajectories → `.ainl` export

Treat Hermes’ proposed changes as **candidates**:

1. Export/edit into `.ainl`
2. Gate with strict mode:

```bash
ainl check candidate.ainl --strict
```

If strict validation passes, re-emit the Hermes bundle and replace the skill directory under `~/.hermes/skills/ainl-imports/`.

---

## Migration path (OpenClaw → Hermes)

Hermes can migrate some OpenClaw-style workflows using its migration tooling (e.g. `hermes claw migrate`). After migration:

1. Convert the result into compiling `.ainl` (either by hand or with AINL import tools)
2. Validate with `ainl check --strict`
3. Emit a Hermes skill bundle using `--emit hermes-skill`

This layering keeps Hermes’ ergonomics while moving orchestration into AINL’s deterministic, auditable graph core.

---

## Troubleshooting

### `ainl doctor` (Hermes host status)

Run:

```bash
ainl doctor
```

You should see checks for Hermes MCP config presence under:

- `~/.hermes/config.yaml` (`mcp_servers.ainl`)

If the config is missing, rerun:

```bash
ainl install-mcp --host hermes
```

### Common issues

- **`hermes` not on PATH**: install Hermes and add its bin dir to PATH.
- **AINL tools not on PATH**: ensure your Python user base `bin/` is in PATH (doctor prints hints).
- **MCP server missing**: verify `~/.hermes/config.yaml` contains `mcp_servers:` and `ainl:`.

---

## Links

- Hermes Agent repo: `https://github.com/NousResearch/hermes-agent`
- AgentSkills format hub: `https://agentskills.io/`
- AINL Hermes skill pack: [`skills/hermes/`](../skills/hermes/)
- AINL host hub: [`docs/getting_started/HOST_MCP_INTEGRATIONS.md`](getting_started/HOST_MCP_INTEGRATIONS.md)

## LLM Adapter Setup

To enable cloud LLM providers, create an AINL config file following the guide in `docs/LLM_ADAPTER_USAGE.md`. Set your provider API keys via environment variables (e.g., `OPENROUTER_API_KEY`). Then pass the config path using `--config` or set `AINL_CONFIG`.

You can verify cost tracking and retry behavior by running a program and checking the SQLite DB under `intelligence/monitor/`.

