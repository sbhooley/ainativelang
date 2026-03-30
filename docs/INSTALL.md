# Install (Cross-OS)

See also:

- `DOCS_INDEX.md` for full navigation
- `RUNTIME_COMPILER_CONTRACT.md` for runtime/compiler semantics and strict literal policy
- `CONFORMANCE.md` for current implementation status

## Requirements

- Python 3.10+
- pip

## Linux / macOS

**Recommended (match CI: Python 3.10):** use a dedicated env at `.venv-py310` so local runs
and pre-commit use the same baseline as GitHub Actions. If you prefer a name without a leading dot,
use `VENV_DIR=venv-py310` and `source venv-py310/bin/activate` instead.

```bash
# macOS (Homebrew): brew install python@3.10
PYTHON_BIN=python3.10 VENV_DIR=.venv-py310 bash scripts/bootstrap.sh
source .venv-py310/bin/activate
ainl-validate examples/blog.lang --emit ir
```

Default bootstrap (uses whatever `python3` resolves to, must still be 3.10+):

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
ainl-validate examples/blog.lang --emit ir
```

Automation / agents: prefer **`./.venv-py310/bin/python`** or **`./.venv-ainl/bin/python`** (after bootstrap or sync below) for pytest,
scripts, and checks so results match the 3.10 CI matrix.

**CI + OpenClaw parity (two venv names, one install):** OpenClaw scripts and docs often use **`.venv-ainl`**; CI docs use **`.venv-py310`**. They should carry the same extras (**`dev`**, **`web`**, **`mcp`**) so either path runs tests and MCP tooling. After cloning or when dependencies drift, run:

```bash
PYTHON_BIN=python3.10 bash scripts/sync_dual_venvs.sh
# or: make sync-venvs
```

This creates or refreshes both directories with **`pip install -U -e ".[dev,web,mcp]"`**. Override extras with **`AINL_PIP_EXTRAS=...`** if needed. Single-venv bootstrap uses the same default extras: **`bash scripts/bootstrap.sh`** (see **`AINL_PIP_EXTRAS`** in **`scripts/bootstrap.sh`**).

If **`.venv-ainl`** was created with a non-3.10 interpreter (e.g. an older manual **`python3 -m venv`**), remove that directory once and re-run **`sync_dual_venvs.sh`** so both envs use **`PYTHON_BIN=python3.10`** and match the Actions matrix.

After upgrading the repo to a new **`pyproject.toml` / `RUNTIME_VERSION`** (see **`docs/CHANGELOG.md`**), reinstall editable installs with **`pip install -U -e .`** (or recreate the venv) so **`ainl`** / **`runtime`** imports match the tree and stale **`__pycache__`** does not shadow updated modules.

## Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
ainl-validate examples/blog.lang --emit ir
```

## Manual install

```bash
python -m pip install -e ".[dev,web,mcp]"
```

## No-root / sandbox install order (PEP 668 aware)

When `sudo` is unavailable or Python is externally managed, use this order:

1. **Best:** isolated venv

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ainativelang[mcp]"
```

2. **Fallback:** user install (no root)

```bash
python -m pip install --user "ainativelang[mcp]"
```

3. **Last resort:** break-system-packages (only if your platform requires it)

```bash
python -m pip install --break-system-packages "ainativelang[mcp]"
```

For Python 3.13 sandbox hosts, you can use the tested MCP constraints file:

```bash
python -m pip install --constraint constraints/py313-mcp.txt "ainativelang[mcp]"
```

### Host/container responsibilities (outside AINL package scope)

AINL install/runtime checks assume the host (or container image) provides:

- a writable user home directory
- outbound package download access (or internal package mirror)
- a usable Python interpreter + `pip`
- shell startup/PATH behavior that can discover user script bins
- filesystem permissions allowing local config writes for MCP bootstrap paths

## Optional local guardrails (recommended)

Enable pre-commit hooks for fast local feedback before pushing:

```bash
pre-commit install
pre-commit run --all-files
```

This includes the AINL docs contract hook (`ainl-docs-contract`) so docs/runtime
contract drift is caught locally before CI.

## Full conformance suite

Run the full snapshot-driven matrix locally:

```bash
make conformance
```

Intentionally refresh snapshots:

```bash
SNAPSHOT_UPDATE=1 make conformance
```

## CLI tools installed

- `ainl-validate` - compile/validate/emit from `.lang`

**Strict vs non-strict:** validation is **permissive by default**; **`--strict`** is opt-in for stronger static checks. See **`docs/getting_started/STRICT_AND_NON_STRICT.md`**.

### `ainl-validate` strict diagnostics

- **`--strict`** (and **`--strict-reachability`**) collects **structured compiler diagnostics** (lineno, kind, spans, suggestions). On failure, a human report is printed to **stderr** (numbered issues, source snippet, underlines). Install **`pip install -e ".[dev]"`** for optional **rich**-formatted output; otherwise plain text with optional ANSI colors when stderr is a TTY.
- **`--diagnostics-format`** — `auto` (default), `plain`, `json`, or `rich`. On structured failure: `json` → stdout JSON only; `plain` → text on stderr; `rich` → styled output when **rich** is installed (otherwise plain). `auto` picks rich when rich+TTY and not `--no-color`.
- **`--json-diagnostics`** — legacy alias for `--diagnostics-format=json`.
- **`--no-color`** — force plain diagnostic output (disables rich styling).

Legacy behavior is unchanged: **`compile()` without `context`** still returns IR with string `errors` in non-strict mode; strict + `CompilerContext` raises `CompilationDiagnosticError` for the structured tooling path.
- `ainl-validator-web` - run FastAPI validator UI
- `ainl-generate-dataset` - synthetic dataset generator
- `ainl-compat-report` - IR compatibility report
- `ainl-tool-api` - structured tool API CLI
- `ainl-ollama-eval` - local Ollama eval harness
- `ainl-visualize` / `ainl visualize` — compile `.ainl` to **Mermaid** (subgraph clusters for `include` aliases; paste into [mermaid.live](https://mermaid.live)) and export images with `--png/--svg` (`--width`/`--height` supported). For image export, install Playwright browser runtime once: `playwright install chromium`. See root `README.md` (**Visualize your workflow**) and `docs/architecture/GRAPH_INTROSPECTION.md` §7.
- `ainl doctor` - environment diagnostics (imports, PATH, MCP config, install-mcp dry-run checks)

### Doctor command

```bash
ainl doctor
ainl doctor --json
ainl doctor --host openclaw
```

## Runtime adapter CLI examples

Use `ainl run` with `--enable-adapter` flags to bootstrap reference adapters without writing Python glue code.

### Trajectory logging

Optional **`--log-trajectory`** or **`AINL_LOG_TRAJECTORY=1`** appends one JSON line per executed step to **`<source-stem>.trajectory.jsonl`** beside the `.ainl` file. This is separate from the HTTP runner’s structured audit log. See **`docs/trajectory.md`**.

### Local `vector_memory` / `tool_registry`

For JSON-backed search/upsert and a local tool catalog (used by **`examples/hyperspace_demo.ainl`** and **`--emit hyperspace`**), enable:

```bash
ainl run app.ainl --json \
  --enable-adapter vector_memory \
  --enable-adapter tool_registry
```

Env overrides: **`AINL_VECTOR_MEMORY_PATH`**, **`AINL_TOOL_REGISTRY_PATH`**. Details: **`docs/adapters/README.md`**, **`docs/reference/ADAPTER_REGISTRY.md`** §9, **`docs/emitters/README.md`**.

### Local `code_context` (tiered repo index)

For ctxzip-style tiered codebase context (used by **`examples/code_context_demo.ainl`**), enable:

```bash
ainl run app.ainl --json \
  --enable-adapter code_context
```

Env override: **`AINL_CODE_CONTEXT_STORE`**. Details: **`docs/adapters/CODE_CONTEXT.md`**, **`docs/reference/ADAPTER_REGISTRY.md`** §9.

### HTTP adapter

```bash
ainl run app.ainl --json \
  --enable-adapter http \
  --http-allow-host api.example.com \
  --http-timeout-s 5
```

### SQLite adapter

```bash
ainl run app.ainl --json \
  --enable-adapter sqlite \
  --sqlite-db ./data/app.db \
  --sqlite-allow-write \
  --sqlite-allow-table users \
  --sqlite-allow-table orders
```

### Sandboxed FS adapter

```bash
ainl run app.ainl --json \
  --enable-adapter fs \
  --fs-root ./sandbox \
  --fs-max-read-bytes 2000000 \
  --fs-max-write-bytes 2000000 \
  --fs-allow-ext .txt \
  --fs-allow-ext .json
```

### Tools bridge adapter

```bash
ainl run app.ainl --json \
  --enable-adapter tools \
  --tools-allow echo \
  --tools-allow sum
```

### Deterministic record/replay

Record adapter calls:

```bash
ainl run app.ainl --json \
  --enable-adapter http \
  --record-adapters calls.json
```

Replay from recorded calls (no live side effects):

```bash
ainl run app.ainl --json \
  --replay-adapters calls.json
```
