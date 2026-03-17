## AINL v1.1.0 — First Public Release

**AINL is the open language for deterministic AI workflows.** It compiles structured workflows to canonical graph IR and executes them through a deterministic runtime with adapter-based side effects, policy-gated execution, and multi-target emission.

### Highlights

- **Python 3.10+** official baseline, with CI coverage on 3.10 and 3.11
- **Core test profile fully green** — 403 tests, 0 failures
- **MCP v1 server** — a thin, stdio-only MCP server (`ainl-mcp`) exposing workflow compilation, validation, execution, capability discovery, and security introspection for Gemini CLI, Claude Code, Codex, and other MCP-compatible hosts
- **HTTP runner service** — `POST /run` with policy-gated execution, `/capabilities` discovery, health/metrics endpoints
- **Security/operator surfaces** — adapter privilege tiers, named security profiles, policy validator with `forbidden_privilege_tiers`, security report tooling
- **Docs reorganized** — intent-based information architecture with section READMEs and a root navigation hub

### Start here

| Path | First step |
|------|-----------|
| **CLI only** | `ainl-validate examples/hello.ainl --strict` |
| **HTTP runner** | `ainl-runner-service` then `curl localhost:8770/capabilities` |
| **MCP host** | `pip install -e ".[mcp]" && ainl-mcp` |

### Links

- [Getting started](../getting_started/README.md)
- [Release notes](../RELEASE_NOTES.md)
- [External orchestration guide](../operations/EXTERNAL_ORCHESTRATION_GUIDE.md)
- [Security & threat model](../advanced/SAFE_USE_AND_THREAT_MODEL.md)
- [Conformance](../CONFORMANCE.md)
- [Contributing](../../CONTRIBUTING.md)

### Licensing

Apache 2.0 for core code. See `LICENSE`, `LICENSE.docs`, `MODEL_LICENSE.md`, and `COMMERCIAL.md` for full details.
