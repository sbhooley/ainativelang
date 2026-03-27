# Adapter Expansion & Self-Monitoring Design

> tweaks: reuse existing tool_registry.py & openclaw_integration.py; place monitor/ in intelligence/; feed cost tracking into existing .lang programs; documentation next to INT..._PROGRAMS.md and EXTERNAL_EXECUTOR_BRIDGE.md; prioritize openrouter+ollama; use existing test suite.

## 3. Adapter Expansion

### Architecture

```
adapters/
├── llm/
│   ├── base.py          # AbstractLLMAdapter
│   ├── openrouter.py    # OpenRouter via OpenAI client
│   ├── anthropic.py     # Anthropic Claude
│   ├── cohere.py        # Cohere Command
│   ├── ollama.py        # Local Ollama
│   └── openai.py        # Direct OpenAI (fallback)
├── tools/
│   ├── mcp/
│   │   ├── client.py    # MCP client wrapper (stdio/HTTP)
│   │   └── registry.py  # Tool discovery
│   ├── openclaw/
│   │   ├── gateway.py   # Existing OpenClaw gateway wrapper
│   │   └── tools.py     # OpenClaw tool definitions
│   └── http/
│       └── rest.py      # Generic REST tool
└── registry.py          # AdapterRegistry (auto-discovery, aliases)
```

### Implementation Steps (Weeks 1–2 priority)

1. **Abstract LLM Interface** (`adapters/llm/base.py`)
   - Methods: `complete(prompt, max_tokens, **kwargs)`, `estimate_cost(prompt_tokens, completion_tokens)`, `validate()`
   - Return: `LLMResponse(content, usage, model, provider)`

2. **Extend existing `adapters/tool_registry.py`**
   - Add `register_llm_adapter(provider, adapter_class)`
   - Maintain existing tool registry; keep backward compatibility

3. **OpenRouter Adapter** (`adapters/llm/openrouter.py`)
   - Reuse/adapt current OpenRouter integration (if present)
   - Set headers: `HTTP-Referer`, `X-Title` from config
   - Handle 402 → raise `InsufficientCreditsError`

4. **Ollama Adapter** (`adapters/llm/ollama.py`)
   - HTTP to `http://ollama:11434/api/generate`
   - Discover models via `/api/tags`
   - Map AINL model names (`ollama/mistral`) → Ollama name (`mistral`)

5. **Adapter Configuration**
   - Extend existing `.env` or YAML config:
   ```yaml
   llm:
     provider: openrouter
     model: openai/gpt-4o-mini
     max_tokens: 800
     fallback_providers: [ollama]
   adapters:
     openrouter:
       api_key: ${OPENROUTER_API_KEY}
       base_url: https://openrouter.ai/api/v1
       referer: https://myapp.example
       title: AINL SBIR Demo
     ollama:
       base_url: http://ollama:11434
   ```

6. **MCP Integration**
   - Create `adapters/tools/mcp/client.py` supporting stdio and HTTP
   - Use `mcporter`-style discovery to list tools
   - Each MCP tool becomes an AINL node type `mcp_call`

7. **OpenClaw Tools**
   - Extend `adapters/tools/openclaw/gateway.py` (reuse existing)
   - Expose OpenClaw tools as callable nodes: `openclaw_file_read`, `openclaw_web_search`
   - Ensure gateway URL from config; do not touch `~/.openclaw` install

### Deliverables

- Adapter test matrix: each provider + 3 models, 100 prompts → success >95%
- Cost estimation accuracy within ±5%
- Fallback demonstration (OpenRouter outage → Ollama)
- Adapter developer guide (placed in `docs/`)

## 4. Self-Monitoring & Cost Tracking

### Components

Place new package in `intelligence/monitor/`:

```
intelligence/
├── monitor/
│   ├── __init__.py
│   ├── collector.py       # Prometheus metrics exporter
│   ├── health.py          # Liveness/readiness endpoints
│   ├── cost_tracker.py    # Cost accumulation per run/node
│   ├── budget_policy.py   # Thresholds, alerts, throttling
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── telegram.py
│   │   ├── email.py
│   │   └── webhook.py
│   └── dashboard/
│       ├── __init__.py
│       ├── static/
│       │   └── index.html # Single-page dashboard
│       └── server.py      # Simple Flask/FastAPI to serve dashboard
├── ... existing intelligence modules ...
```

### Integration Points

- **LLM adapters** return `usage` → feed into `cost_tracker.add(provider, model, prompt_tokens, completion_tokens)`.
- **Existing `.lang` programs** that call LLMs should import and use `monitor.cost_tracker` rather than duplicating budget logic.
- **OpenClaw bridge** (external executor) should also log tool usage to `monitor.collector`.
- Reuse existing `self_monitor.py` scheduling to run daily price reconciliation and health checks.

### Metrics to Collect

- Workflow: `ainl_workflow_runs_total`, `ainl_workflow_success`, `ainl_workflow_duration_seconds`
- Node: `ainl_node_calls_total{node_type}`, `ainl_node_errors_total{node_type}`
- LLM: `ainl_llm_tokens_total{provider,model}`, `ainl_llm_cost_total{provider,model}`
- Tools: `ainl_tool_calls_total{tool_name}`
- System: process memory/CPU, adapter health (`up`/`down`)

### Cost Tracking

- Persist to SQLite DB: `~/.ainl/costs.db`
- Tables: `run_costs`, `budget`
- Daily cron job: fetch latest pricing from providers, update rates, reconcile month-to-date spending, send alerts if discrepancy >5%.

### Budget Control & Alerts

- Config: monthly limit (default $20), alert_threshold_pct (80%), throttle_threshold_pct (95%)
- On threshold exceed: send Telegram alert; if throttled, reduce `max_tokens` by half or pause new runs.
- Health endpoints: `/health/live`, `/health/ready` used by Docker healthcheck.

### Dashboard

- Serve static HTML at `/monitor/dashboard` (or embed in existing UI)
- Display: current month cost, remaining budget, last 10 runs, provider health, live charts (Chart.js).

### Deliverables

- Metrics collector exposing `/metrics` (Prometheus format)
- Cost tracker + budget policy + Telegram alerts
- Health endpoints + Docker healthcheck integration
- Dashboard prototype with auto-refresh
- Documentation: “Operational Guide for AINL Self-Monitoring”

## Implementation Timeline (8 weeks)

| Week | Tasks |
|------|-------|
| 1–2 | Abstract LLM adapter; OpenRouter + Ollama adapters; initial tests |
| 3 | Anthropic adapter; adapter registry & config loader |
| 4 | Cohere adapter; fallback chain |
| 5 | MCP client; OpenClaw tools integration |
| 6 | Cost tracker DB + budget policy; Telegram alerts |
| 7 | Health endpoints + Prometheus metrics |
| 8 | Dashboard; documentation; demo rehearsal |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Provider API differences | Normalize in adapter layer; map AINL `max_tokens` appropriately |
| Cost rate changes | Daily price fetch; keep 30-day history; alert on large swings |
| 402 errors mid-run | Catch; mark run `quota_exceeded`; throttle future runs |
| MCP server heterogeneity | Support both stdio and HTTP; require `type` in config |
| Dashboard performance | In-memory cache; aggregate by minute |

## Testing Strategy

- Reuse existing strict-mode and test suite
- Add conformance tests for each adapter (mock HTTP, simulate failures)
- Benchmark suite: run same workflow with different providers, assert token savings >50% vs naive baseline
- End-to-end test: simulate OpenRouter outage, verify fallback to Ollama and alerting

## Documentation Plan

- `docs/ADAPTER_DEVELOPER_GUIDE.md` – how to add new LLM or tool adapters
- `docs/MONITORING_OPERATIONS.md` – setup, alerts, dashboard usage, troubleshooting
- Extend `docs/INTELLIGENCE_PROGRAMS.md` and `docs/EXTERNAL_EXECUTOR_BRIDGE.md` with new cost tracking hooks

---

*Design written to workspace for reference before implementation.*
