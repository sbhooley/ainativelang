# Structured Tool API

AINL includes a simple structured tool interface for local agent loops:

- CLI: `ainl-tool-api`
- Schema: `tooling/ainl_tool_api.schema.json`

## Supported actions

- `compile` -> returns IR
- `validate` -> returns `ok`, `errors`, `meta`
- `emit` -> returns selected artifact (`ir|server|react|openapi|prisma|sql`)
- `explain_error` -> returns a short remediation hint

## Example

```bash
echo '{"action":"compile","code":"S core web /api"}' | ainl-tool-api
```

```bash
echo '{"action":"emit","target":"openapi","code":"S core web /api"}' | ainl-tool-api
```
