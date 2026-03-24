# Promoter LLM prompts (text files)

The gateway loads these **UTF-8** files at request time (no secrets here — only copy).

| File | Used by | Purpose |
|------|---------|---------|
| `classify_system.txt` | `POST /v1/llm.classify` | OpenAI `system` role: JSON-array-only replies. |
| `classify_instruction.txt` | `llm.classify` user message | Preamble instruction before the tweet batch JSON. |
| `reply_system.txt` | `POST /v1/promoter.process_tweet` | OpenAI `system` role for drafting replies. |
| `discovery_user_instruction.txt` | `POST /v1/x.search_users` (optional) | User-turn instructions for per-author relevance scores (fallback string in gateway if missing). |

**Override directory:** set `PROMOTER_PROMPTS_DIR` to an absolute path; otherwise `apollo-x-bot/prompts/` next to `gateway_server.py`.

**Overrides in JSON:** If the request body includes a non-empty `system` (classify) or `reply_system_prompt` (process_tweet), that value wins over the file.

The graph [`ainl-x-promoter.ainl`](../ainl-x-promoter.ainl) sends **only** `tweets` for classify; the gateway fills system + instruction from files by default.
