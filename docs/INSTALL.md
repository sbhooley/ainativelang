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
and pre-commit use the same baseline as GitHub Actions.

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

Automation / agents: prefer **`./.venv-py310/bin/python`** (after bootstrap above) for pytest,
scripts, and checks so results match the 3.10 CI matrix.

## Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
ainl-validate examples/blog.lang --emit ir
```

## Manual install

```bash
python -m pip install -e ".[dev,web]"
```

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

## Runtime adapter CLI examples

Use `ainl run` with `--enable-adapter` flags to bootstrap reference adapters without writing Python glue code.

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
