# AGENTS.md — Ground Truth for AI Agents

> Read this FIRST before doing anything in this repository.

## What This Repo Is

Python compiler + runtime for AINL (AI Native Language), version 1.4.1.
AINL compiles `.ainl` source files into an IR (intermediate representation)
graph, then executes that graph via adapters (database, HTTP, LLM, Solana, etc).

## Repository Layout

```
compiler_v2.py          — The compiler (5300 lines). Parses .ainl → IR dict.
compiler_diagnostics.py — Error/warning types used by compiler.
runtime/engine.py       — The runtime engine (2150 lines). Executes IR graphs.
runtime/adapters/       — Runtime adapter base classes and builtins.
cli/main.py             — CLI entry point (2700 lines). All `ainl` commands.
adapters/               — 54 adapter modules (solana, postgres, redis, LLM, etc).
scripts/                — Standalone scripts (emit_langgraph, emit_temporal, etc).
tooling/                — Graph analysis, normalization, effect analysis tools.
examples/               — 154 .ainl example files. USE THESE as syntax reference.
tests/                  — ~1000 test files, 300K lines. Run with pytest.
docs/                   — Documentation (some accurate, some aspirational — see below).
```

## Commands That Work

```bash
ainl run <file>                          # Compile and execute
ainl validate <file> [--strict]          # Validate (alias for check)
ainl validate <file> --json-output       # Full IR JSON output
ainl compile <file>                      # Compile to IR JSON
ainl emit <file> --target <t> [-o path]  # Emit to target platform
ainl serve [--host H] [--port P]         # HTTP server (REST API)
ainl check <file> [--strict]             # Same as validate
ainl visualize <file> --output -         # Mermaid diagram
ainl inspect <file>                      # Canonical IR dump
ainl init <name>                         # Create new project
ainl doctor                              # Environment diagnostics
ainl-validate <file> --emit <target>     # Separate script, more emit targets
```

### Emit Targets (ainl emit --target)

```
ir, langgraph, temporal, hermes-skill, hermes,
solana-client, blockchain-client, server, python-api,
react, openapi, prisma, sql, docker, k8s, cron
```

### ainl serve Endpoints

```
GET  /health     — Health check
POST /validate   — Validate source (JSON: {source, strict?})
POST /compile    — Compile to IR (JSON: {source, strict?})
POST /run        — Compile and execute (JSON: {source, strict?, frame?})
```

## AINL Syntax — Two Formats

AINL supports TWO equivalent syntaxes. Both compile to the same IR.

### Compact Syntax (Recommended for new code)

Human-friendly, Python-like. See `examples/compact/` for examples.

```ainl
# examples/compact/hello_compact.ainl
adder:
  result = core.ADD 2 3
  out result
```

```ainl
# Branching, inputs, adapter calls
classifier:
  in: level message
  severity = llm.classify level message
  if severity == "CRITICAL":
    result = http.POST ${SLACK_WEBHOOK} {text: message}
    out {action: "slack"}
  out {action: "logged"}
```

Compact syntax rules:
```
name:                             Graph header (becomes S + labels)
name @cron "schedule":            Cron job
name @api "/path":                API endpoint
in: field1 field2                 Input fields (X field ctx.field)
var = adapter.op args             Adapter call (R adapter.op args ->var)
adapter.op args                   Bare call (R adapter.op args ->_)
var = expr                        Assignment (Set var expr)
if cond:                          Branch (==, !=, >, <, >=, or bare var)
  indented body                   Then-block
out expr                          Return value (Set _out expr + J _out)
err "message"                     Raise error
call label                        Call another section
config key:type                   Config declaration (D Config)
state key:type                    State declaration (D State)
# comment                         Comments preserved
```

### Opcode Syntax (Low-level, power users)

The original 1-char opcode format. See `examples/hello.ainl`.

### Opcodes

```
S <scope> <adapter> <path>        — Header: declares program surface
D <kind> <name> <fields>          — Declaration (Config, State, etc)
L<n>:                             — Label (graph node)
X <var> <expr>                    — Assign literal or expression
R <adapter>.<op> <args> -><var>   — Request: call adapter, bind result
J <var>                           — Join: return value, finish this node
Set <var> <expr>                  — Set variable
If (<expr>) -><then> -><else>    — Conditional branch to labels
While (<cond>) -><body>           — Loop
Call <label>                      — Call another label
Err <msg>                         — Raise error
```

### Minimal Example

```ainl
S app core noop

L1:
  R core.ADD 2 3 ->sum
  J sum
```

### Real-World Example (Monitoring)

```ainl
S app core noop

L_start:
  R solana.GET_BALANCE "11111111111111111111111111111111" ->bal
  X lamports get bal lamports
  X min_lp 500000000
  X below (core.gt min_lp lamports)
  If below ->L_alert ->L_ok

L_alert:
  Set status "below_budget"
  J status

L_ok:
  Set status "ok"
  J status
```

## Available Adapters

```
core       — Built-in ops (ADD, SUB, MUL, NOW, GET, etc)
solana     — Solana RPC (GET_BALANCE, TRANSFER, etc) — 1447 lines
postgres   — PostgreSQL queries
mysql      — MySQL queries
redis      — Redis get/set/pub/sub
dynamodb   — AWS DynamoDB
supabase   — Supabase client
airtable   — Airtable API
http       — HTTP requests
memory     — Key-value memory store
cache      — Cache get/set
queue      — Message queue put/get
llm/*      — LLM adapters (openrouter, ollama, anthropic, cohere)
```

## How To Test

```bash
source .venv-ainl/bin/activate
python -m pytest tests/ -x -q -k "not test_profiles_cover"
# Expected: ~400 passed
```

## ⚠️ NOTE: Tutorial Syntax Variants

The files in `docs/learning/intermediate/` contain TWO syntax styles:

1. **Compact syntax** (works now) — Python-like, uses the preprocessor:
   ```ainl
   classifier:
     in: level
     if level == "high":
       out "critical"
     out "info"
   ```

2. **Graph block syntax** (DESIGN PREVIEW — does NOT compile):
   ```
   graph AlertClassifier {
     node classify: LLM("severity-classifier") { ... }
   }
   ```
   This `graph { node ... }` syntax is aspirational. It does NOT compile.
   Look for `⚠️ DESIGN PREVIEW` markers in those docs.

**Use compact syntax for new code.** Always validate: `ainl validate <file> --strict`

## Do NOT

- Modify files outside this repository (especially ~/.openclaw/)
- Invent new AINL syntax — use compact or opcode format only
- Use `graph { node ... }` block syntax (it does NOT compile)
- Skip running `ainl validate --strict` before committing .ainl files
- Use `X var value` for assignments — use `Set var value` instead (X has runtime quirks)

## Related Repositories

- `sbhooley/ainativelangweb` — Marketing website (Next.js)
- `sbhooley/ainativelangcloud` — Cloud platform plans (private)
