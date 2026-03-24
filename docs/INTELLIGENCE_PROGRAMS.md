# Intelligence programs (`intelligence/*.lang`)

AINL sources under `intelligence/` support **OpenClaw-style** automation: memory compaction, session signals, token-aware bootstrap context, and scheduled digests. They are **examples / operator programs** — not part of the core language spec. **ZeroClaw** users usually integrate via **`docs/ZEROCLAW_INTEGRATION.md`** (skill + **`ainl-mcp`**), not this monitor registry layout.

## Programs

| File | Role |
|------|------|
| `intelligence_digest.lang` | Scheduled web + TikTok snapshot, cache + memory + notify (see `openclaw/INTELLIGENCE_DIGEST.md`) |
| `memory_consolidation.lang` | Keyword-based promotion from `memory/*.md` into `MEMORY.md` (no LLM) |
| `proactive_session_summarizer.lang` | Summarize prior-day logs via OpenRouter; writes `MEMORY.md`; needs `OPENROUTER_API_KEY` + `http` allowlist |
| `token_aware_startup_context.lang` | Builds compact `.openclaw/bootstrap/session_context.md` from `MEMORY.md` under a token budget |
| `token_aware_startup_context2.lang` | Variant bootstrap writer (same general pattern) |
| `session_continuity_enhanced.lang` | Lists `session` memory keys, heartbeat + notify (monitoring posture) |
| `store_baseline.lang` | One-shot seed into `memory` (`intel` / baseline) |
| `test_split.lang` | Small harness for split/len-style checks |
| `infrastructure_watchdog.lang` | Service health checks + optional notify path (operator-tuned; pair with your gateway / bridge allowlists) |

## Local runner

`scripts/run_intelligence.py` compiles and runs selected programs with the OpenClaw monitor adapter registry (for hosts that mirror that layout):

```bash
# from repo root, with project on PYTHONPATH / editable install
python3 scripts/run_intelligence.py context
python3 scripts/run_intelligence.py summarizer --trace
python3 scripts/run_intelligence.py consolidation
python3 scripts/run_intelligence.py continuity
python3 scripts/run_intelligence.py all
```

Enable the same adapters and paths your production gateway uses (`fs`, `cache`, `http`, `memory`, `queue`, etc.); see `docs/INSTALL.md` and `docs/reference/ADAPTER_REGISTRY.md`.

## Host responsibilities

- **Cron / scheduler:** programs declare `S` schedules; the host must trigger runs.
- **Prompt injection:** token-aware output is only useful if the host loads `session_context.md` / `MEMORY.md` into the agent context.
- **Secrets:** summarizer and digest flows need env vars (e.g. `OPENROUTER_API_KEY`) where applicable.

## See also

- [`agent_reports/README.md`](../agent_reports/README.md) — operator field reports
- [`docs/RUNTIME_COMPILER_CONTRACT.md`](RUNTIME_COMPILER_CONTRACT.md)
- [`docs/OPENCLAW_ADAPTERS.md`](OPENCLAW_ADAPTERS.md)
