# `apollo-x-bot/modules/promoter`

**Strict-safe `.ainl` includes** for **bridge JSON envelopes** used by [`ainl-x-promoter.ainl`](../ainl-x-promoter.ainl) and [`gateway_server.py`](../gateway_server.py). Static envelopes use shared [`../../modules/common/executor_bridge_request.ainl`](../../modules/common/executor_bridge_request.ainl) (`R core.ECHO` JSON text → `Call …/bridge_req/ENTRY`).

**LLM copy** (classify system, classify instruction, reply system) lives in **[`../prompts/`](../prompts/README.md)** as `.txt` files loaded by the gateway. The graph sends only **`tweets`** to `llm.classify`; it does not embed long prompt strings.

| File | Role |
|------|------|
| `req_search.ainl` | POST body for `x.search` |
| `req_process_tweet.ainl` | Envelope + `bridge.POST promoter.process_tweet` |
| `req_cursor.ainl` | `promoter.search_cursor_commit` |
| `req_daily.ainl` | `promoter.maybe_daily_post` |

**Docs:** [apollo-x-bot/README.md](../README.md).
