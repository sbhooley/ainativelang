# AGENTS.md — Ground Truth for AI Agents

> Read this FIRST before doing anything in this repository.

## What This Repo Is

Python compiler + runtime for AINL (AI Native Language), version 1.7.1.
AINL compiles `.ainl` source files into an IR (intermediate representation)
graph, then executes that graph via adapters (database, HTTP, LLM, Solana, etc).

## Repository Layout

```
compiler_v2.py          — The compiler (5300 lines). Parses .ainl → IR dict.
compiler_diagnostics.py — Error/warning types used by compiler.
runtime/engine.py       — The runtime engine (2150 lines). Executes IR graphs.
runtime/adapters/       — Runtime adapter base classes and builtins.
cli/main.py             — CLI entry point (2700 lines). All `ainl` commands.
adapters/               — 54 adapter modules (solana, postgres, redis, LLM, etc); ArmaraOS monitor bootstrap: `armaraos_integration.py`, `armaraos_defaults.py` (`build_armaraos_monitor_registry`, `boot_armaraos_graph_memory`). See `docs/ARMARAOS_INTEGRATION.md`, `docs/adapters/AINL_GRAPH_MEMORY.md`.
armaraos/emitter/       — `armaraos.py`: `ainl emit --target armaraos` Hand pack (`HAND.toml`, IR JSON, `security.json`, README) with `schema_version` for openfang-hands validation.
scripts/                — Standalone scripts (emit_langgraph, emit_temporal, etc).
tooling/                — Graph analysis, normalization, effect analysis tools.
examples/               — 154+ .ainl example files. **Training contract:** only paths listed as `strict-valid` in `tooling/artifact_profiles.json` are CI-checked with `ainl validate --strict`. See `examples/README.md` and `docs/EXAMPLE_SUPPORT_MATRIX.md` before copying random files.
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
react, openapi, prisma, sql, docker, k8s, cron, armaraos
```

**`armaraos`:** emits an **openfang-hands** Hand directory (`HAND.toml`, `<stem>.ainl.json`, `security.json`, `README.md`) with **`schema_version`** on **`[hand]`**, the IR JSON, and **`security.json`** — see **`docs/ARMARAOS_INTEGRATION.md`** § *Emit a Hand package*.

### ainl serve Endpoints

```
GET  /health     — Health check
POST /validate   — Validate source (JSON: {source, strict?})
POST /compile    — Compile to IR (JSON: {source, strict?})
POST /run        — Compile and execute (JSON: {source, strict?, frame?})
```

### Production defaults (runner + mass-market UX)

- **Default runner grant** (`scripts/runtime_runner_service.py`): adapter cap is **unset** at the grant layer so IR-declared adapters (e.g. `web`, `http`) work out of the box; **resource limits** (`max_steps`, `max_time_ms`, …) remain the universal safety floor.
- **MCP server** (`scripts/ainl_mcp_server.py`): **`ainl_run`** only registers `core` by default. Any workflow using `http`, `fs`, `cache`, or `sqlite` **MUST** pass them via the `adapters` parameter — otherwise the run fails with "adapter not registered". Example for a workflow that does HTTP + file I/O + caching:
  ```json
  {
    "enable": ["http", "fs", "cache"],
    "http": { "allow_hosts": ["example.com", "api.otherdomain.gov"], "timeout_s": 15 },
    "fs":   { "root": "/absolute/path/to/workspace", "allow_extensions": [".json", ".csv"] },
    "cache":{ "path": "/absolute/path/to/workspace/cache.json" }
  }
  ```
  LLM adapters additionally require **`AINL_CONFIG`** or **`AINL_MCP_LLM_ENABLED=1`** (see `docs/LLM_ADAPTER_USAGE.md`).
- **MCP authoring loop:** call **`ainl_get_started`** for unfamiliar goals; **`ainl_validate`** / **`ainl_compile`** use **`CompilerContext`** so diagnostics include native **`kind`**, **`suggested_fix`**, and related fields. Responses include **`recommended_next_tools`**, **`recommended_resources`**, and on failures **`repair_recipe`**. Pass **full source** in MCP **`code`** (string; legacy alias **`ainl`**). Compiler **`ok:true`** is not the same as a successful **`ainl_run`** on MCP hosts that omit **`adapters=`** — read **`required_adapters`** / **`runtime_readiness`**. Resources: **`ainl://strict-authoring-cheatsheet`** (strict syntax + pitfalls), **`ainl://strict-valid-examples`** (JSON index of **`strict-valid`** paths from **`tooling/artifact_profiles.json`**), **`ainl://adapter-contracts`** (JSON bundle of adapter semantics), **`ainl://authoring-cheatsheet`** (HTTP `R`-lines + integrations). **`ainl_capabilities`** returns **`strict_summary`**, per-adapter **`strict_contract`**, **`mcp_telemetry`**, and **`mcp_resources`**. Integration docs: **`ainl://integrations-hub`**, **`ainl://integrations-http-machine-payments`**, **`ainl://integrations-agentic-protocols-readiness`**, **`ainl://integrations-agtp`**, **`ainl://integrations-a2a`** (see **`docs/integrations/`**; exposure profiles in **`tooling/mcp_exposure_profiles.json`**). **Strict-valid payment-flow example:** **`ainl://examples-http-machine-payment-flow`** (`examples/http/http_machine_payment_flow_compact.ainl`); local round-trip: **`python scripts/run_http_machine_payment_roundtrip_demo.py`**.
- **Phase 2 (roadmap):** adapter **semantic** contracts (verb args, config, return shape, side effects) on top of syntax strictness — use **`ainl_adapter_contract`** and **`ainl://adapter-contracts`** today; richer per-adapter schemas and “contract verified” statuses are planned, not a substitute for **`ainl_run`** smoke checks when side effects matter.
- **ArmaraOS chat + `ainl://` resources:** The MCP wire and resource list come from this repo (`scripts/ainl_mcp_server.py`). In **OpenFang** / ArmaraOS embedded agents, the host also exposes built-in **`mcp_resource_read`**, which calls MCP client **`resources/read`** on the connected **`ainl`** server so the model can load **`ainl://…`** URIs from **`mcp_resources`** without a separate MCP client. See **`armaraos/docs/mcp-a2a.md`** (*Host mcp_resource_read* under MCP Client).
- **Impact-first / repo-intelligence alignment:** Set **`AINL_MCP_EXPOSURE_PROFILE=design_impact_first`** (see `tooling/mcp_exposure_profiles.json`) or **`AINL_MCP_IMPACT_FIRST=1`** to prefer the chain **validate → compile → `ainl_ir_diff` → run** in `recommended_next_tools`. Responses may include **`policy_contract`** (context freshness defaults to **`unknown`** in MCP-only hosts; see `tooling/ainl_policy_contract.json`). Resources: **`ainl://impact-checklist`**, **`ainl://adapter-risk-matrix`**, **`ainl://run-readiness`**, **`ainl://policy-contract`**. Vocabulary: **`docs/AINL_GRAPH_VOCABULARY.md`**, **`docs/CONTEXT_FRESHNESS.md`**.
- **`AINL_STRICT_MODE=1`** (when **`AINL_SECURITY_PROFILE`** is unset): merges profile **`consumer_secure_default`** (or **`AINL_STRICT_PROFILE`**) with that floor — named allowlist + `operator_sensitive` tier blocked; good for “strict” product mode without hand-maintaining env lists.
- **`AINL_SECURITY_PROFILE`**: if set, loads that profile **as the full grant** (same as before); use for org/enterprise lockdown.
- **`AINL_HOST_ADAPTER_ALLOWLIST`** / **`AINL_HOST_ADAPTER_DENYLIST`**: comma-separated; applied in the runtime after IR resolution (denylist wins last). CLI: `--host-adapter-allowlist` / `--host-adapter-denylist`.
- **`AINL_ALLOW_IR_DECLARED_ADAPTERS=1`**: when set, **`AINL_HOST_ADAPTER_ALLOWLIST` from the environment is ignored** so programs can use any adapter referenced in the IR (useful when a parent shell or IDE exports a narrow list). Does not override explicit CLI/kwargs; **`AINL_HOST_ADAPTER_DENYLIST`** and security profiles still apply.
- **Intelligence programs** (`**/intelligence/**`): **`ainl run`** with a source path whose components include **`intelligence`** sets **`AINL_ALLOW_IR_DECLARED_ADAPTERS=1`** when that variable is unset (before compile/run). `RuntimeEngine.from_code(..., source_path=...)` does the same for those paths (unless **`AINL_INTELLIGENCE_FORCE_HOST_POLICY=1`**) so `web` / `tiktok` / `queue` in IR are not stripped by a narrow **`AINL_HOST_ADAPTER_ALLOWLIST`**. Operators who need strict host intersection for intelligence files set **`AINL_INTELLIGENCE_FORCE_HOST_POLICY=1`**. The CLI also registers **`web`**, **`tiktok`**, and **`queue`** (OpenClaw integration) on every `ainl run`.
- **ArmaraOS desktop / scheduled `ainl run`**: the OpenFang kernel injects **`AINL_ALLOW_IR_DECLARED_ADAPTERS=1`** into each scheduled child by default; the desktop shell sets it for the process when still unset after **`~/.armaraos/.env`**. Per-agent opt-out: manifest **`ainl_allow_ir_declared_adapters`** → **`0`** / **`false`** / **`off`** / **`no`**. Optional **`bundle.ainlbundle`** + **`AINL_BUNDLE_PATH`** pre-seed / post-export for **`ainl_graph_memory`** on cron: **`armaraos/docs/scheduled-ainl.md`**. Python→SQLite **inbox** when **`ARMARAOS_AGENT_ID`** (+ **`agents/`**): **`armaraos/docs/graph-memory-sync.md`**. Chat **system prompt** persona hook uses Rust **`ainl_memory.db`**: **`armaraos/docs/graph-memory.md`**. Operator narrative + manifest widen copy-paste: **`docs/INTELLIGENCE_PROGRAMS.md`** § ArmaraOS scheduled `ainl run`, snippet **`armaraos/docs/snippets/agent-metadata-intelligence-cron.toml`**.
- **Capability blocks**: errors include a short **what to change** hint; runner **`GET /metrics`** exposes `adapter_capability_blocks_total` and `adapter_capability_blocks_by_adapter` for telemetry. **`GET /capabilities`** includes a `host_security_env` key describing these variables.
- **`ainl doctor`**: reports current **runtime security env** (profiles / strict / allowlist presence).

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
core       — Built-in ops (ADD, SUB, MUL, NOW, GET, LEN, MAP, FILTER, etc)
solana     — Solana RPC (GET_BALANCE, TRANSFER, etc) — 1447 lines
postgres   — PostgreSQL queries
mysql      — MySQL queries
redis      — Redis get/set/pub/sub
dynamodb   — AWS DynamoDB
supabase   — Supabase client
airtable   — Airtable API
http       — HTTP requests
web        — Web search/fetch (SEARCH, FETCH, SCRAPE, GET)
browser    — Real Chrome/Chromium control via the ArmaraOS daemon's CDP stack (`adapters/browser.py` proxies `R browser.*` → `POST /mcp` `tools/call`). Verbs: NAVIGATE, CLICK, TYPE, SCREENSHOT, READ_PAGE, SCROLL, WAIT, RUN_JS, BACK, CLOSE, SESSION_START, SESSION_STATUS. Modes (second arg to NAVIGATE / SESSION_START): `"headless"` (default), `"headed"` (visible window), `"attach"` (drive a user-launched Chrome on `--remote-debugging-port`). Env: `ARMARAOS_API_BASE`, `ARMARAOS_API_KEY`, `AINL_BROWSER_AGENT_ID`, `AINL_BROWSER_TIMEOUT_S`. Requires the ArmaraOS daemon (`openfang start`) — see **`armaraos/docs/browser-control.md`** and `examples/browser/browser_visit_minimal.ainl`.
tiktok     — TikTok data (RECENT, SEARCH, PROFILE, STATS, TRENDING)
memory     — Key-value SQLite store + procedural patterns (`store_pattern`/`recall_pattern`, table `ainl_memory_patterns`); IR label steps `memory.merge` / `MemoryMerge` re-inject stored `labels` as live IR (`docs/adapters/MEMORY_CONTRACT.md` §3.7; tests/test_memory_merge.py)
ainl_graph_memory — ArmaraOS bridge JSON graph (file-backed nodes/edges; IR ops MemoryRecall/MemorySearch; EdgeType epistemic edges; persona.update → persona_update; **`boot()`** reads **`AINL_BUNDLE_PATH`** for scheduled **`ainl run`**; **`ainl_memory_sync`** → **`ainl_graph_memory_inbox.json`** when **`ARMARAOS_AGENT_ID`**); Rust auto-refresh writes per-agent **`{agent}_graph_export.json`** under **`AINL_GRAPH_MEMORY_ARMARAOS_EXPORT`** (directory) or **`…/agents/<id>/ainl_graph_memory_export.json`** when unset — Python resolves directory vs **`.json`** file + auto-fallback (`docs/adapters/AINL_GRAPH_MEMORY.md`); see also armaraos/docs/graph-memory-sync.md (hub) + armaraos/docs/graph-memory.md (daemon drain + env **`AINL_EXTRACTOR_ENABLED`** / **`AINL_TAGGER_ENABLED`** / **`AINL_PERSONA_EVOLUTION`** in **armaraos** `crates/openfang-runtime/README.md`); demos demo/procedural_roundtrip_demo.py, demo/ainl_graph_memory_demo.py; tests test_semantic_edges.py, test_armaraos_graph_snapshot_import.py, armaraos/bridge/tests/test_ainl_memory_sync.py
cache      — Cache get/set
queue      — Message queue put/get (use R queue Put "name" val ->_)
svc        — Service control (STATUS, RESTART, CADDY, NGINX, HEALTH)
crm        — CRM ops (QUERY, UPDATE)
llm/*      — LLM adapters (openrouter, ollama, anthropic, cohere)
```

## How To Test

```bash
source .venv-ainl/bin/activate
python -m pytest tests/ -x -q -k "not test_profiles_cover"
# Expected: ~1000 passed, 6 skipped (ArmaraOS CLI / langgraph / temporalio not installed)
```

Focused suites (optional): **`tests/test_compact_opcode_ir_parity.py`** (compact ↔ opcode IR), **`tests/test_memory_search_op.py`** (**`MemorySearch`** + **`GraphStore`**), **`tests/test_memory_merge.py`** (**`memory.merge`** + SQLite patterns), **`tests/test_semantic_edges.py`** (**`EdgeType`** / **`persona.update`** compile + graph store), **`tests/test_core_builtins_v143.py`** (v1.4.3 **`core.*`**). Shared fixture **`offline_llm_provider_config`** lives in **`tests/conftest.py`** (no network).

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

## Queue adapter syntax

The queue adapter uses the standard `R adapter.op` form — **not** the legacy `QueuePut` shorthand:

```ainl
# Correct
R queue Put "channel_name" payload ->_

# Wrong — QueuePut is not a valid opcode
QueuePut channel_name payload
```

## HTTP adapter (`http.*`) — read before writing `R http.*`

Ground truth implementation: `runtime/adapters/http.py` (`SimpleHttpAdapter`).

**Machine payments & agentic commerce (HTTP):** Native `payment_profile` parsing covers **HTTP 402** dialects used by **x402** and **MPP** (structured `payment_required` envelope + `http_payment` header merges). **AP2** (intent/authorization), **ACP** (*Agentic Commerce Protocol* checkout — not IBM ACP messaging), and **AGTP** (IETF agent transfer drafts) are mapped in `docs/integrations/HTTP_MACHINE_PAYMENTS.md`: use **generic `http` JSON/REST** where the wire is not x402/MPP 402 headers, or non-HTTP adapters for non-HTTP transports. **Practitioner readiness (what works end-to-end today vs gaps):** `docs/integrations/AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md`. **AGTP (not plain `http`):** `docs/integrations/AGTP.md`. CLI: `--http-payment-profile`; MCP/runner: `adapters.http.payment_profile`; monitor registry env: `AINL_HTTP_PAYMENT_PROFILE`.

**GET positional arguments (no named `params=` / `timeout=` on the `R` line):**

1. URL string (required). Put query parameters **in the URL** (e.g. `https://host/path?ParcelNumber=123&TaxYearId=uuid`).
2. Optional **headers** dict — second positional argument.
3. Optional **timeout** in seconds — third positional argument (a number).

```ainl
# URL only (default timeout from adapter config)
R http.GET "https://example.com/api?x=1" ->res

# URL + empty headers + 15s timeout
R http.GET "https://example.com/api?x=1" {} 15 ->res
```

**Do not** write `R http.GET url params = {...} timeout = 15 ->res`. The runtime parses extra tokens after the URL and will mis-parse `=` (e.g. `could not convert string to float: '='`).

**`core.GET` arg order is object-first:** `R core.GET obj "key" ->val` — NOT `R core.GET "key" obj`. The first positional arg to `core.GET` is always the container (dict or list), the second is the key/index string.

**`core.*` runtime coverage — verified working verbs (builtins.py v1.4.3+; package **1.7.1**):**
`ADD`, `SUB`, `MUL`, `DIV`, `IDIV`, `MIN`, `MAX`, `CLAMP`, `CONCAT`, `SPLIT`, `JOIN`, `LOWER`, `UPPER`, `REPLACE`, `CONTAINS`, `STARTSWITH`, `ENDSWITH`, `TRIM`, `STRIP`, `LSTRIP`, `RSTRIP`, `GET`, `PARSE`, `STRINGIFY`, `MERGE`, `LEN`, `NOW`, `ISO`, `ISO_TS`, `ECHO`, `ID`, `ENV`, `SUBSTR`, `SLEEP`, `FILTER_HIGH_SCORE`, `EQ`, `NEQ`, `GT`, `LT`, `GTE`, `LTE`, `KEYS`, `VALUES`, `STR`, `INT`, `FLOAT`, `BOOL`.

**Still NOT implemented at runtime** (pass `--strict` validation but throw "unsupported core builtin target"): `type`, `unique`, `reduce`, `map`, `filter`, `format`, `range`, `sort`, `reverse`, `flatten`, `omit`, `pick`, `zip`, `abs`, `ceil`, `floor`, `round`, `pow`, `mod`, `and`, `or`, `not`, `noop`, `hash`, `uuid`.

**Type coercion shortcuts (new):** Use `R core.STR val ->s` instead of `R core.CONCAT "" val ->s`. Use `R core.EQ a b ->ok` instead of `R core.CONTAINS str_a str_b ->ok` workarounds. Use `R core.TRIM html_text ->clean` instead of cascading `REPLACE` chains.

**Recursive loops hit Python's recursion limit.** Each `Call L_label` in AINL creates a Python stack frame. 73 records × ~5 frames/record = 365 frames — hits Python's default limit (~300-500). AINL is not suited for iterating over datasets > ~20 records via tail recursion. For larger datasets, use `shell_exec` to run a Python script.

**CRITICAL: Inline dict literals on `R` lines are never evaluated as dicts.** `R http.POST url {"key": "val"} ->resp` tokenizes `{"key": "val"}` as raw strings — the adapter receives `["{", "key", ":", "val", "}"]` and fails with `could not convert string to float: ':'`. Same for `R core.MERGE rec {"extra": val}` — the inline dict is silently skipped. The ONLY correct patterns are:
- Pass dicts via `frame` in `ainl_run` (e.g. `frame: {"body": {...}}`) and reference by name: `R http.POST url body ->resp`
- Build result JSON via `core.CONCAT` + `core.STRINGIFY` + `core.PARSE`
- Use `core.MERGE` only with two variables that are already resolved dicts (not inline literals)

**`web` vs `http`:** `http` is the plain HTTP client. `web` is OpenClaw-oriented search/fetch and is not a substitute for documented `http.Get` / `http.Post` when you need a normal request to a fixed host.

**`ainl_compile` returns `frame_hints`:** The `ainl_compile` MCP tool returns a `frame_hints` list alongside the IR on success (on compile failure the error bundle matches `ainl_validate` and does not include `frame_hints`). Each entry is `{"name": "...", "type": "...", "source": "comment"|"inferred"}` describing variables the caller should supply in the `frame` parameter of `ainl_run`. Authoritative hints come from `# frame: name: type` comment lines (anywhere in the source file); `# frame: name` without a second `:` is accepted and yields `type: "any"`. Inferred hints are derived from variables referenced in `R`/`X`/`Set` steps but never assigned in the IR (best-effort; may include false positives).

**Variable shadowing in `R` args (critical):** String literals in `R` argument positions (e.g. `"records"`) have their quotes stripped at compile time and resolved against the live frame before being used as literals. If a frame variable named `records` exists, `R core.GET data "records"` will pass the list, not the string `"records"`. Prevention: **use unique variable name prefixes in every label** (e.g. `lien_*` in first loop, `out_*` in second loop).

**Per-workspace `ainl_mcp_limits.json`:** Place a JSON file at `<fs.root>/ainl_mcp_limits.json` to raise or tighten limits for a specific workspace without editing global server defaults. Format: `{"max_steps": 500000, "max_time_ms": 900000, "max_adapter_calls": 50000}`. Values merge with per-call `limits` and then with the MCP server ceiling (most restrictive wins). If the file exists but is not valid JSON, limits fall back to defaults and a successful `ainl_run` may include `warnings` describing the parse failure.

**`max_adapter_calls` semantics:** Integer ceilings include **zero**: `max_adapter_calls: 0` means no adapter calls are allowed (the first `R` / cache / queue / etc. dispatch fails with a structured `RUNTIME_MAX_ADAPTER_CALLS` error). This is independent of `max_steps` / `max_time_ms`, where non-positive values in grants are treated as unset for legacy reasons.

**Auto-registered cache (MCP):** When the `fs` adapter is enabled in `ainl_run`, `cache` is not listed in `adapters.enable`, and `output/cache.json` or `cache.json` exists under `fs.root`, the MCP server registers `LocalFileCacheAdapter` with that path. The file must be valid JSON if it is non-empty; otherwise `ainl_run` returns `ok: false` with `error: "adapter_config_error"` and a `details` string (empty files are treated as `{}` once the adapter loads). **Note:** `RuntimeEngine` may still register a default file-backed `cache` adapter when the IR references `cache` and no adapter was supplied — that path uses `AINL_CACHE_JSON` / `MONITOR_CACHE_JSON` / `~/.openclaw/ainl_cache.json` unless the MCP server already registered `cache` for the workspace file.

**MCP `ainl_run` adapter requirement:** `http`, `fs`, `cache`, and `sqlite` are **not** registered by default in MCP runs — you will get "adapter not registered" / "http adapter not found" errors unless you pass the `adapters` argument. Always include it when your workflow uses those adapters:
```json
{
  "enable": ["http", "fs", "cache"],
  "http":  { "allow_hosts": ["ohwarren.fidlar.com", "auditor.warrencountyohio.gov"], "timeout_s": 15, "payment_profile": "none" },
  "fs":    { "root": "/Users/clawdbot/.armaraos/workspaces/Lien Scraper", "allow_extensions": [".json", ".csv"] },
  "cache": { "path": "/Users/clawdbot/.armaraos/workspaces/Lien Scraper/cache.json" }
}
```
ArmaraOS scheduled `ainl run` (CLI) auto-injects `AINL_ALLOW_IR_DECLARED_ADAPTERS=1` so adapters declared in the IR work without the `adapters` arg; this **only** applies to the CLI runner, **not** MCP `ainl_run`.

**Strict mode:** Use adapter verbs that exist on the contract (see `ainl capabilities` / diagnostics). Prefer forms that pass `ainl validate <file> --strict`.

**There is no `regex_find` adapter in this repository.** Do not emit `R regex_find ...` (it will not resolve to a real adapter). For pattern extraction use **`core`** string ops that exist in capabilities (e.g. `SUBSTR`, `CONTAINS`, `SPLIT`, `REPLACE`) or handle regex **outside** AINL (e.g. Python). If you see `regex_find` in a random snippet, treat it as invalid unless a project adds a custom adapter.

**Opcode graphs:** Multi-line `{ ... }` blocks inside `L_` labels (e.g. inside `core.REDUCE` callbacks) are easy to get wrong; a stray `}` can end the label and produce **auto-closed label** errors. When in doubt, use **compact** syntax from `examples/compact/` or keep graphs small and run **`ainl validate <file> --strict`** until clean.

**Canonical example file:** `examples/http_get_minimal.ainl`.

## App Store filtering (`demo/`)

Files under `demo/` are **development demos** — many use experimental syntax and do not pass `--strict`. They are excluded from the ArmaraOS App Store via a `demo/.ainl-library-skip` marker file. The ArmaraOS `ainl-library` walker skips any directory tree that contains this file. Do not remove it. To make a demo file discoverable in the App Store, move it to `examples/` and ensure `ainl validate <file> --strict` passes.

## Do NOT

- Modify files outside this repository (especially ~/.openclaw/)
- Invent new AINL syntax — use compact or opcode format only
- Use `graph { node ... }` block syntax (it does NOT compile)
- Skip running `ainl validate --strict` before committing .ainl files
- Use `X var value` for assignments — use `Set var value` instead (X has runtime quirks)
- Use `QueuePut` — use `R queue Put "channel" payload ->_` instead
- Place `include` directives after the `S` header line — includes must appear before `S` (prelude only)
- Put `params =` / `timeout =` as fake named arguments on `R http.GET` / `R http.POST` lines — use positional args and URL query strings (see **HTTP adapter** above)
- Claim or use a **`regex_find`** adapter — it is not part of this repo; use real `core` ops or external code

## OpenClaw workspace handoff (ClawHub skills → AINL)

Validated example that marks the ingestion slot for promoted digest text: `examples/compact/openclaw_learning_handoff.ainl`.  
Workspace-level contract (load order, `.learnings/`, export script): see `INTEGRATION.md` in the OpenClaw workspace root (sibling layout when this repo lives under `~/.openclaw/workspace/`).

## Related Repositories

- `sbhooley/ainativelangweb` — Marketing website (Next.js); **ArmaraOS** desktop installers on `/` and `/download` (manifest under `/downloads/armaraos/latest.json` when release CI syncs from **armaraos**)
- `sbhooley/armaraos` — ArmaraOS / OpenFang agent OS (Rust); desktop app + embedded dashboard; docs for Home folder API and `[dashboard]` home-editing allowlists; **Ultra Cost-Efficient Mode** (input prompt compression): **`armaraos/docs/prompt-compression-efficient-mode.md`**. **PostHog (desktop):** release CI bakes **`ARMARAOS_POSTHOG_KEY`** or org **`AINL_POSTHOG_KEY`** (same `phc_…` as **`NEXT_PUBLIC_POSTHOG_KEY`** on ainativelangweb). This repo does not ship that key. **AINL bridge:** **`docs/operations/EFFICIENT_MODE_ARMARAOS_BRIDGE.md`** (`--efficient-mode` / `modules/efficient_styles.ainl` vs Rust compression).
- `sbhooley/ainativelangcloud` — Cloud platform plans (private)
