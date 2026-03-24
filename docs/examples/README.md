# Examples

Use this section to understand example support levels, recommended examples, and how to navigate example-heavy material without confusing canonical and compatibility lanes.

## Key docs

- **[`../ECOSYSTEM_OPENCLAW.md`](../ECOSYSTEM_OPENCLAW.md)** — Clawflows / Agency-Agents **`examples/ecosystem/`** (weekly auto-sync from upstream; OpenClaw- and ZeroClaw-oriented imports)
- **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** — **OpenClaw skill**, **`ainl install-openclaw`**, MCP importer tools, **`tiktoken cl100k_base`** / **viable subset** context
- **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)** — **ZeroClaw skill**, **`ainl install-zeroclaw`**, MCP importer tools, **`tiktoken cl100k_base`** / **viable subset** context
- [`../EXAMPLE_SUPPORT_MATRIX.md`](../EXAMPLE_SUPPORT_MATRIX.md) — support classification for examples
- **`examples/bad_include.ainl`** — intentionally broken include (strict / `ainl visualize` error demos); not in strict-valid profiles
- **`examples/hyperspace_demo.ainl`** — minimal graph using **`vector_memory`** / **`tool_registry`**; pair with `--emit hyperspace` (see [`../emitters/README.md`](../emitters/README.md)) and root `README.md` happy path
- **`examples/test_phase2_common_modules.ainl`** — smoke for `modules/common` **guard** / **session_budget** / **reflect** includes (optional committed sample: `examples/test_phase2_common_modules.trajectory.jsonl` when run with `--log-trajectory`)
- **Small compiler/runtime harnesses:** `examples/test_nested.ainl`, `test_mul.ainl`, `test_if_var.ainl`, `test_X_sub.ainl` — local development aids, not tiered “product” examples
- Visualize any example: `ainl visualize path/to/example.ainl --output diagram.md` (see root `README.md`, `docs/architecture/GRAPH_INTROSPECTION.md` §7)

## Related sections

- Getting started: [`../getting_started/README.md`](../getting_started/README.md)
- Operations examples: [`../operations/README.md`](../operations/README.md)
- Narrative proof and applied writeups: [`../case_studies/README.md`](../case_studies/README.md)
