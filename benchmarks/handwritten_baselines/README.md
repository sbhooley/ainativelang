# Handwritten baselines

Reference implementations used to compare **AINL compile/runtime** against idiomatic **async Python** and **LangGraph** (optional third-party package).

Each workflow lives in its own subfolder:

| Folder | Inspired by |
|--------|-------------|
| [`token_budget_monitor/`](token_budget_monitor/) | [`openclaw/bridge/wrappers/token_budget_alert.ainl`](../../openclaw/bridge/wrappers/token_budget_alert.ainl) |
| [`basic_scraper/`](basic_scraper/) | [`examples/scraper/basic_scraper.ainl`](../../examples/scraper/basic_scraper.ainl) |
| [`retry_timeout_wrapper/`](retry_timeout_wrapper/) | [`examples/retry_error_resilience.ainl`](../../examples/retry_error_resilience.ainl) + [`modules/common/timeout.ainl`](../../modules/common/timeout.ainl) |
| [`competitive/langgraph/`](competitive/langgraph/) | LangGraph authoring baselines vs [`enterprise_monitor.ainl`](../../examples/benchmark/enterprise_monitor.ainl) and [`support_ticket_router.ainl`](../../examples/workflows/support_ticket_router.ainl) — see `scripts/benchmark_competitor_baselines.py` |

Files per workflow:

- `pure_async_python.py` — stdlib + small deps (`aiohttp` where noted).
- `langgraph_version.py` — graph-shaped equivalent (`pip install langgraph`).
- `README.md` — mapping to AINL and equivalence notes.

Keep additions conservative and reproducible; prefer **mocked I/O** for deterministic benchmarks.
