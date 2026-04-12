# Language

Use this section for the AINL language definition itself: spec, canonical core, grammar, and module structure.

## Key docs

- [`../AINL_SPEC.md`](../AINL_SPEC.md) — formal spec and design principles
- [`../AINL_CANONICAL_CORE.md`](../AINL_CANONICAL_CORE.md) — recommended public language lane
- [`AINL_CORE_AND_MODULES.md`](AINL_CORE_AND_MODULES.md) — core language and module structure; **§8** documents repo **strict `include` libraries** ([`modules/common/`](../../modules/common/README.md), [`modules/llm/`](../../modules/llm/README.md)) and **app-local** trees (e.g. gateway-adjacent `modules/<your-app>/`, `prompts/`, etc.)
- **AINL → HTTP executor bridge (JSON envelope):** [`../integrations/EXTERNAL_EXECUTOR_BRIDGE.md`](../integrations/EXTERNAL_EXECUTOR_BRIDGE.md) — recommended body shape, [`../../schemas/executor_bridge_request.schema.json`](../../schemas/executor_bridge_request.schema.json), Python validator `schemas/executor_bridge_validate.py`, reusable include [`../../modules/common/executor_bridge_request.ainl`](../../modules/common/executor_bridge_request.ainl) (`ainl_bridge_request_json` + `Call …/bridge_req/ENTRY`; use `R core.ECHO` for JSON **text** before parsing)
- [`AINL_EXTENSIONS.md`](AINL_EXTENSIONS.md) — extension lanes
- [`grammar.md`](grammar.md) — grammar quick reference

**Label header vs bare number:** Only `L1:` (letter **L** + digits + colon) starts a label block. A line like `1:` is **not** a label declaration; indented steps under it are stored on the compiler’s synthetic label `_anon`, not on label id `1`. If you call `RuntimeEngine.run(..., label="1")` (or any host that picks an entry label by id), use `L1:` in source so steps land under the real label `1` in IR.

## Related sections

- Getting started: [`../getting_started/README.md`](../getting_started/README.md)
- Architecture: [`../architecture/README.md`](../architecture/README.md)
- Runtime: [`../runtime/README.md`](../runtime/README.md)
