# Getting Started

Use this section when the goal is to get from zero to a working understanding
of AINL as quickly as possible.

## Prerequisites

- Python 3.10+
- pip and virtual environment support

```bash
git clone https://github.com/sbhooley/ainativelang.git
cd ainativelang
python -m pip install -e ".[dev,web]"
```

For platform-specific details (Windows, Docker, pre-commit), see
[`../INSTALL.md`](../INSTALL.md).

## Strict vs non-strict (your choice)

By default, validation and `ainl run` use the **permissive** compiler policy. **`--strict`** on **`ainl-validate`** (or `AICodeCompiler(strict_mode=True)`) turns on **stricter** static checks for production-style graphs. Read **[`STRICT_AND_NON_STRICT.md`](STRICT_AND_NON_STRICT.md)** for when to use which, and how that relates to files under `demo/` and `examples/`.

## Choose your integration path

AINL can be used through three surfaces. All three share the same compiler
and runtime; they differ in how you connect.

### Path A — CLI only (fastest start)

```bash
# Validate an example
ainl-validate examples/hello.ainl --strict --emit ir

# Mermaid diagram (paste into https://mermaid.live)
ainl visualize examples/hello.ainl --output - > hello.mmd

# Direct image export (requires Playwright runtime)
ainl visualize examples/hello.ainl --png hello.png

# Run a tiny workflow
ainl run examples/hello.ainl --json

# Optional: per-step JSONL trace beside the source (see docs/trajectory.md)
ainl run examples/hello.ainl --log-trajectory --json

# Optional: generate runtime config hints for AVM/general sandboxes
ainl generate-sandbox-config examples/hello.ainl --target general
ainl generate-sandbox-config examples/hello.ainl --target avm

# Emit a standalone Hyperspace Python agent (embedded IR); run from repo root
python3 scripts/validate_ainl.py examples/hyperspace_demo.ainl --strict --emit hyperspace -o demo_agent.py
```

No server needed. Good for local development, scripting, and CI.

For the full deterministic conformance matrix (tokenizer, IR canonicalization,
strict validation, runtime parity, emitter stability), run:

```bash
make conformance
```

### Path B — HTTP runner (orchestrator integration)

```bash
ainl-runner-service          # starts on http://localhost:8770

curl http://localhost:8770/capabilities
curl -X POST http://localhost:8770/run \
  -H "Content-Type: application/json" \
  -d '{"code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x", "strict": true}'
```

Best for container deployments, sandbox controllers, and external orchestrators.

Full guide: [`../operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md)

### Path C — MCP host (AI coding agents)

```bash
pip install -e ".[mcp]"
ainl-mcp                     # starts stdio MCP server
```

Configure your MCP-compatible host (Gemini CLI, Claude Code, Codex, etc.) to
use the `ainl-mcp` stdio transport. The host can then call `ainl_validate`,
`ainl_compile`, `ainl_capabilities`, `ainl_security_report`, and `ainl_run`.

Unified hub (all MCP hosts): **[`HOST_MCP_INTEGRATIONS.md`](HOST_MCP_INTEGRATIONS.md)** (**`ainl install-mcp --host …`**). **OpenClaw:** **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** · **ZeroClaw:** **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)**.

MCP v1 runs with safe defaults (core-only adapters, conservative limits).

Full quickstart: section 9 of
[`../operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md)

## Canonical "hello world" workflow

The same tiny program works across all three paths:

```
S app api /api
L1:
R core.ADD 2 3 ->x
J x
```

This declares a service, defines one label, calls the core `ADD` adapter to
compute 2 + 3, and returns the result. It compiles to canonical graph IR and
executes deterministically.

## Core first, advanced later

Start with the core compiler/runtime and the paths above. Advanced surfaces
(agent coordination, memory migration, OpenClaw extensions — **`docs/OPENCLAW_INTEGRATION.md`** (skill + MCP) and **`openclaw/bridge/`** (cron/memory), ZeroClaw skill — **`docs/ZEROCLAW_INTEGRATION.md`**) are documented
under [`../advanced/`](../advanced/) and are intended for operators who
understand their deployment environment.

## Recommended reading path

1. [`../AUDIENCE_GUIDE.md`](../AUDIENCE_GUIDE.md) — who AINL is for
2. [`../AINL_SPEC.md`](../AINL_SPEC.md) — formal language spec
3. [`../AINL_CANONICAL_CORE.md`](../AINL_CANONICAL_CORE.md) — canonical scope
4. [`../EXAMPLE_SUPPORT_MATRIX.md`](../EXAMPLE_SUPPORT_MATRIX.md) — example classification
5. [`../CONFORMANCE.md`](../CONFORMANCE.md) — implementation conformance

## Related sections

- MCP host integrations (OpenClaw, ZeroClaw, …): [`HOST_MCP_INTEGRATIONS.md`](HOST_MCP_INTEGRATIONS.md)
- What AINL is: [`../overview/README.md`](../overview/README.md)
- Why the model exists: [`../fundamentals/README.md`](../fundamentals/README.md)
- Full reference map: [`../DOCS_INDEX.md`](../DOCS_INDEX.md)
- Release notes: [`../RELEASE_NOTES.md`](../RELEASE_NOTES.md)
