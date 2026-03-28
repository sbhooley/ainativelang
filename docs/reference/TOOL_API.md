# Structured Tool API

AINL includes a simple structured tool interface for local agent loops:

- CLI: `ainl-tool-api`
- Schema: `tooling/ainl_tool_api.schema.json`

Related docs:

- `../DOCS_INDEX.md` (entrypoint map)
- `../RUNTIME_COMPILER_CONTRACT.md` (execution/strict contract)
- `IR_SCHEMA.md` and `GRAPH_SCHEMA.md` (payload semantics)
- `../CONFORMANCE.md` (validation expectations)

## Supported actions

- `compile` -> returns IR
- `validate` -> returns `ok`, `errors`, `meta`
- `emit` -> returns selected artifact (`ir|server|react|openapi|prisma|sql`)
- `explain_error` -> returns a short remediation hint
- `plan_delta` -> compares `base_ir` vs new program/IR and returns additive/replace actions
- `patch_apply` -> safe patch merge (fail on conflict unless `allow_replace=true`)
- `policy_check` -> validates auth/role/policy/contracts invariants
- `compat_check` -> checks endpoint/type compatibility against `base_ir`
- `viability` -> strict compile + gates + runtime boot/health/endpoint checks
- `feedback` -> converts gate failures into normalized retry hints

## Example

```bash
echo '{"action":"compile","code":"S core web /api"}' | ainl-tool-api
```

```bash
echo '{"action":"emit","target":"openapi","code":"S core web /api"}' | ainl-tool-api
```

```bash
echo '{"action":"plan_delta","base_ir":{},"code":"S core web /api"}' | ainl-tool-api
```

```bash
echo '{"action":"patch_apply","base_ir":{},"patch_code":"S core web /api","allow_replace":false}' | ainl-tool-api
```

## CLI runtime options

When running AINL programs via `python -m cli.main run`, you can control adapter loading and configuration:

| Flag / Env | Description |
|------------|-------------|
| `--config PATH` | YAML configuration file. Enables LLM adapter registration and other adapter settings. |
| `AINL_CONFIG` | Env var alternative to `--config`. |
| `--enable-adapter NAMESPACE.ADAPTER` | Enable a specific adapter without a config file (rare). Multiple flags allowed. |
| `AINL_ENABLED_ADAPTERS` | Comma-separated adapter names to enable. |

Example:

```bash
export OPENROUTER_API_KEY="sk-or-..."
python -m cli.main run --config config.yaml examples/hello.ainl
```

See `LLM_ADAPTER_USAGE.md` for the config schema and environment variable details.

