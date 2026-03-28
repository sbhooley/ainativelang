# AINL Agent Guide Index

This index helps AI agents (OpenClaw, ZeroClaw, Hermes‑Agent, Claude Code, OpenAI, etc.) quickly find the relevant documentation for using AINL with cloud LLM adapters.

## Quick Reference

| Agent / Use‑Case | Primary Entry | Key Docs |
|------------------|---------------|----------|
| Standalone CLI (`python -m cli.main run`) | `--config` + YAML config | `docs/LLM_ADAPTER_USAGE.md`<br>`config.example.yaml` |
| Hermes‑Agent / OpenClaw skill (MCP) | `scripts/ainl_mcp_server.py` | `scripts/ainl_mcp_server.py` (run with `AINL_CONFIG`)<br>`docs/HERMES_INTEGRATION.md` |
| ZeroClaw agent | `--config` passed to ZeroClaw runner | `docs/ZEROCLAW_INTEGRATION.md` |
| OpenClaw agent | `--config` passed to OpenClaw runner | `docs/OPENCLAW_INTEGRATION.md` |
| Generic AI agent exploration | `docs/AINL_SPEC.md` + `docs/PATTERNS.md` | `docs/LLM_ADAPTER_USAGE.md` for LLM specifics |

## Feature Coverage

- **LLM adapter registration** – `docs/LLM_ADAPTER_USAGE.md`
- **Configuration** – `config.example.yaml` (env‑var expansion supported)
- **Circuit breaker & fallback** – `docs/LLM_ADAPTER_USAGE.md#circuit-breaker-fallback`
- **Cost tracking & validator** – `intelligence/monitor/cost_tracker.py` + `services/cost_validator.py`
- **Observability / Metrics** – `intelligence/monitor/collector.py`<br>Prometheus endpoint: `/api/metrics` (dashboard server)
- **Health checks** – `intelligence/monitor/health.py`<br>Endpoints: `/health/live`, `/health/ready`
- **Alerts** – `intelligence/monitor/alerts/telegram.py`, `email.py`, `webhook.py`
- **MCP server grant & auto‑registration** – `scripts/ainl_mcp_server.py::_load_mcp_server_grant()`

## Common Setup Patterns

### For CLI Runners

1. Create `config.yaml` based on `config.example.yaml`.
2. Export provider API keys (e.g., `OPENROUTER_API_KEY`).
3. Run:  
   ```bash
   python -m cli.main run --config config.yaml examples/hello.ainl
   ```

### For MCP‑based Agents (Hermes, OpenClaw skill)

1. Ensure `AINL_CONFIG` points to your YAML file.
2. Optionally set `AINL_MCP_LLM_ENABLED=1` (not required if `AINL_CONFIG` is set).
3. Start the MCP server:  
   ```bash
   python scripts/ainl_mcp_server.py
   ```
4. The server will automatically register the `llm` composite adapter and the individual LLM provider adapters.

### For Monitoring

- Enable observability JSONL: `export AINL_OBSERVABILITY=1` and optionally `AINL_OBSERVABILITY_JSONL=/path/metrics.jsonl`.
- Start the dashboard: `python scripts/serve_dashboard.py` (listens on `0.0.0.0:8080`).
- Scrape metrics at `http://localhost:8080/api/metrics`.
- Health endpoints: `http://localhost:8080/health/live`, `/health/ready`.

---

If a doc is missing or out‑of‑date, please file an issue or update it—AINL is maintained alongside the SBIR Phase I grant proposal.
