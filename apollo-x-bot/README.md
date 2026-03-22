# ainl-x-promoter

Strict AINL graph for an X/Twitter **awareness + promotion** workflow for [AINL](https://github.com/sbhooley/ainativelang). Source: `ainl-x-promoter.ainl`.

## What this demonstrates (AINL vs the gateway)

This is intentionally a **reference integration**, not a contest to delete Python.

- **In AINL (the program people read):** declared cadence (`S core cron`), **retries** around side effects (`Call retry/ENTRY`), **JSON-shaped requests** for each step, **dataflow** (`X` get/put), **policy knobs** (`core.env` + `core.FILTER_HIGH_SCORE`), **loop orchestration**, and **explicit ordering** — including **committing the X search cursor only after** the tweet loop finishes so incremental search stays safe if a run stops mid-loop. **LLM copy** is edited in **[`prompts/*.txt`](prompts/README.md)** (loaded by the gateway), not embedded in the graph. Bridge JSON shells: [`modules/promoter/`](modules/promoter/README.md).
- **In the gateway (adapters):** secrets, OAuth 1.0a signing, HTTP to X and to the LLM, SQLite, dry-run / heuristic fallbacks, and the **strict-mode-friendly** single `bridge.POST` per tweet that bundles cap/cooldown/draft/post/audit.

That split matches how production systems separate **orchestration** from **platform SDKs**. The graph is the artifact that shows AINL’s strengths; the gateway is the smallest trusted surface that must speak X’s wire protocol.

**Cost note:** Incremental search (`since_id`, stored in SQLite), **deferred cursor commit** from the graph, **reply dedupe** by tweet id, and a tunable classify floor (`PROMOTER_CLASSIFY_MIN_SCORE`, wired in the graph via `core.env`) reduce **X read volume per poll**, **LLM tokens**, and **duplicate reply work** without removing features.

## Validate

```bash
python3 -m cli.main check --strict apollo-x-bot/ainl-x-promoter.ainl
# or: ainl check --strict apollo-x-bot/ainl-x-promoter.ainl
```

## Visualize (Mermaid)

```bash
python3 -m cli.main visualize apollo-x-bot/ainl-x-promoter.ainl --output apollo-x-bot/promoter.mmd
```

## Production layout: HTTP gateway + `ExecutorBridgeAdapter`

The graph uses `R bridge.POST <executor_key> <json_body>` (see `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`). The runtime wraps HTTP responses as `{ ok, status_code, body, ... }`, so the graph extracts lists with `X … get search_resp body.tweets` and `X … get scored body`.

**Ship this repo’s gateway** (`gateway_server.py`): one process per host (or multiple instances behind a load balancer). Map **each executor key** to a URL path (below). Secrets stay in the gateway environment, not in the `.ainl` file.

### Executor keys → URL paths

| Key | Path | Role |
|-----|------|------|
| `x.search` | `POST /v1/x.search` | Recent search (or dry-run sample tweets); records pending `newest_id` for cursor commit |
| `llm.classify` | `POST /v1/llm.classify` | **Default:** merged scored tweet list (same as before). **Envelope mode** (opt-in): set `classify_response` / `response` to `raw`, `v2`, or `envelope`, or send a non-empty `messages` array — response is `{ v, kind, raw_text, error, items }` (`items` holds heuristic rows when dry-run and no LLM key). |
| `llm.json_array_extract` | `POST /v1/llm.json_array_extract` | Parse first JSON array from a string (`text` or `payload.text`); `{ ok, array, reason?, error? }` — used by `modules/llm/llm_safe_json_parse.ainl`. |
| `llm.merge_classify_rows` | `POST /v1/llm.merge_classify_rows` | Merge `score_rows` / `parsed` onto `tweets` (same rules as legacy classify); returns `{ items }`. |
| `promoter.text_contains_any` | `POST /v1/promoter.text_contains_any` | Case-insensitive substring hits: `haystack` + `phrases[]` → `{ hit_count, any }`. |
| `promoter.heuristic_scores` | `POST /v1/promoter.heuristic_scores` | Keyword heuristic batch (optional `keywords[]`; else gateway defaults); returns `{ items }`. |
| `promoter.classify_prompts` | `POST /v1/promoter.classify_prompts` | File-backed `{ system, instruction }` for classify (same sources as gateway). |
| `promoter.gate_eval` | `POST /v1/promoter.gate_eval` | SQLite-backed `{ tweet_id, user_id }` → `{ proceed, reason, dry_run, daily_count, daily_cap }` (mirrors `process_tweet` skip logic). |
| `promoter.process_tweet` | `POST /v1/promoter.process_tweet` | Cooldowns, draft reply, post reply; reply **system** from [`prompts/reply_system.txt`](prompts/README.md) unless `reply_system_prompt` is set in JSON |
| `promoter.search_cursor_commit` | `POST /v1/promoter.search_cursor_commit` | Promote pending search `newest_id` → `since_id` after loop + daily (see graph `L_after_loop`) |
| `promoter.maybe_daily_post` | `POST /v1/promoter.maybe_daily_post` | Optional one original post per day |

**Strict modules (repo `modules/`):** `llm/llm_classify_request_builder.ainl`, `llm/llm_safe_json_parse.ainl`, `common/heuristic_keyword_score.ainl`, `common/promoter_decision_gate.ainl` — optional v2 classify path; see commented block in `ainl-x-promoter.ainl`.

**`core.contains`:** pure substring check `needle in haystack` (empty needle → true) — usable from `R core.contains` in strict graphs without the gateway.

### Environment (gateway)

**Twitter / X names:** In the developer portal, **API Key** under *Consumer Keys* is the **consumer key** — use it as `X_API_KEY` or `X_CONSUMER_KEY`. The **API Key Secret** (consumer secret) is `X_API_SECRET` or `X_CONSUMER_SECRET`. Those are the pair created with the app (you can regenerate them; old ones stop working).

You can put variables in **`apollo-x-bot/.env`** (`KEY=value` per line). The gateway loads that file automatically; `run-with-gateway.sh` and `openclaw-poll.sh` also `source` it so `ainl run` sees the same values. The repo root `.gitignore` already ignores `.env`. Production can instead use `~/.openclaw/apollo-x-promoter.env` via `APOLLO_PROMOTER_ENV` (see `OPENCLAW_DEPLOY.md`).

**Troubleshooting:** If debug shows `X_BEARER_TOKEN` missing but `.env` has it, fix an empty export in your shell (`export X_BEARER_TOKEN=`) or rely on the gateway: non-empty values in `.env` **overwrite** the environment when the process starts. Use `PROMOTER_GATEWAY_DEBUG=1` and check the `startup:` lines for `dotenv_path` / `exists` / `bearer_set`. Delete `data/promoter_state.sqlite` (or change `PROMOTER_STATE_PATH`) to reset **already_posted_today**, **search cursor**, **replied-tweet dedupe**, and related keys during dev.

| Variable | Purpose |
|----------|---------|
| `X_BEARER_TOKEN` | Twitter API v2 Bearer token — **recent search** (GET). |
| `X_API_KEY` / `X_CONSUMER_KEY` | OAuth 1.0a consumer key. |
| `X_API_SECRET` / `X_CONSUMER_SECRET` | Consumer secret. |
| `X_ACCESS_TOKEN` | OAuth 1.0a user access token (portal: Keys and tokens). |
| `X_ACCESS_TOKEN_SECRET` | Access token secret. **Required with the above for posting** (create tweet / reply). Bearer-only POST is often rejected. |
| `OPENAI_API_KEY` or `LLM_API_KEY` | LLM for classification + reply drafting. |
| `OPENAI_BASE_URL` | Default `https://api.openai.com/v1` (OpenAI-compatible). |
| `LLM_MODEL` | Default `gpt-4o-mini`. |
| `PROMOTER_STATE_PATH` | SQLite file for cooldowns / daily counts (default: `apollo-x-bot/data/promoter_state.sqlite`). |
| `PROMOTER_DRY_RUN` | Set to `1` to skip X writes and use heuristic scoring when no LLM key is set. |
| `PROMOTER_MAX_REPLIES_PER_DAY` | Default `10`. |
| `PROMOTER_USER_COOLDOWN_HOURS` | Default `48` (per user_id). |
| `PROMOTER_CLASSIFY_MIN_SCORE` | Integer floor for `core.FILTER_HIGH_SCORE` in the graph (set in shell/env; graph default via `core.env` is `5`). Raise (e.g. `8`) to cut LLM reply volume; must match what you want the classify prompt to treat as “high intent.” |
| `PROMOTER_SEARCH_USE_SINCE_ID` | Default `1`: use stored `since_id` on X recent search and defer advancing until `promoter.search_cursor_commit` runs. Set `0` to always request a fresh page (higher overlap / cost). Ignored when `PROMOTER_DRY_RUN=1`. |
| `PROMOTER_SEARCH_MAX_RESULTS` | Default `10` (allowed range `10`–`100` per X recent search). |
| `PROMOTER_DEDUPE_REPLIED_TWEETS` | Default `1`: skip draft LLM + post for tweet IDs already consumed (reply or dry-run). Set `0` only for debugging. |
| `PROMOTER_PROMPTS_DIR` | Directory containing `classify_system.txt`, `classify_instruction.txt`, `reply_system.txt` (default: `apollo-x-bot/prompts` next to `gateway_server.py`). |
| `PROMOTER_GATEWAY_HOST` | Default `127.0.0.1`. |
| `PROMOTER_GATEWAY_PORT` | Default `17301`. |
| `PROMOTER_GATEWAY_DEBUG` | Set to `1` to print `[apollo-x-gateway] …` lines on **stderr** (tweet counts, `n_score_ge_8`, skip reasons). |

Bind the gateway to **localhost** or protect it behind a reverse proxy; the executor bridge has no built-in auth.

## Why one bridge call per tweet

Strict compilation requires **Loop** body labels (`L_each`) to contain **exactly one terminal `J`** and to **end** with that `J`. Branching inside the loop body breaks that contract. The graph therefore runs **search → LLM classify → filter → Loop** in `L_poll`, and uses a **single** `bridge.POST` to `promoter.process_tweet` per item. The gateway implements daily caps, cooldowns, drafting, posting, and audit.

After the loop, **`L_after_loop`** runs **`promoter.search_cursor_commit`** then **`promoter.maybe_daily_post`** so incremental search advances only after a **complete** poll (crash-safe).

## Run (gateway + AINL)

**1. Start the gateway** (from repo root):

```bash
export PROMOTER_DRY_RUN=1   # optional: safe local test
python3 apollo-x-bot/gateway_server.py
```

**2. Run the graph** (separate terminal) with one `--bridge-endpoint` per key:

```bash
BASE=http://127.0.0.1:17301
python3 -m cli.main run apollo-x-bot/ainl-x-promoter.ainl --strict --label _poll \
  --enable-adapter bridge \
  --bridge-endpoint x.search=${BASE}/v1/x.search \
  --bridge-endpoint llm.classify=${BASE}/v1/llm.classify \
  --bridge-endpoint llm.json_array_extract=${BASE}/v1/llm.json_array_extract \
  --bridge-endpoint llm.merge_classify_rows=${BASE}/v1/llm.merge_classify_rows \
  --bridge-endpoint promoter.text_contains_any=${BASE}/v1/promoter.text_contains_any \
  --bridge-endpoint promoter.heuristic_scores=${BASE}/v1/promoter.heuristic_scores \
  --bridge-endpoint promoter.classify_prompts=${BASE}/v1/promoter.classify_prompts \
  --bridge-endpoint promoter.gate_eval=${BASE}/v1/promoter.gate_eval \
  --bridge-endpoint promoter.process_tweet=${BASE}/v1/promoter.process_tweet \
  --bridge-endpoint promoter.search_cursor_commit=${BASE}/v1/promoter.search_cursor_commit \
  --bridge-endpoint promoter.maybe_daily_post=${BASE}/v1/promoter.maybe_daily_post
```

Legacy graphs that only call the original five keys still work if you omit the extra `--bridge-endpoint` lines; registering them all matches `tests/test_apollo_x_gateway.py` and v2-oriented includes.

**Convenience script** (starts gateway + runs the graph; defaults `PROMOTER_DRY_RUN=1`):

```bash
./apollo-x-bot/run-with-gateway.sh
```

Use `PYTHON=/path/to/venv/bin/python` if you rely on a virtualenv.

## Cron / OpenClaw

- IR declares `S core cron "*/45 * * * *"` as metadata; your scheduler must **invoke** the runner on label `_poll` (e.g. every 45 minutes).
- **OpenClaw-managed schedules:** use **`openclaw cron add`** with a message that runs `apollo-x-bot/openclaw-poll.sh` (gateway must already be supervised). Full steps: **`OPENCLAW_DEPLOY.md`**.
- Example (system cron):  
  `*/45 * * * * cd /path/to/AI_Native_Lang && /path/to/venv/bin/python -m cli.main run apollo-x-bot/ainl-x-promoter.ainl --strict --label _poll --enable-adapter bridge …`  
  Ensure the gateway is already running (systemd, Docker, or a long-lived supervisor).

## Tests

When this tree is paired with `tests/test_apollo_x_gateway.py` in the AINL repo, run:

```bash
python3 -m pytest tests/test_apollo_x_gateway.py -q
```

Full suite (from repo root, with dev venv if you use one):

```bash
python3 -m pytest -q
```

### Local manual poll (debug, alternate port)

`apollo-x-bot/.env` forces `PROMOTER_GATEWAY_PORT` and can collide with an already-running gateway. For an isolated run, point `PROMOTER_DOTENV` at an **empty** file and pick a free port:

```bash
touch /tmp/no-apollo-dotenv.env
export PROMOTER_DOTENV=/tmp/no-apollo-dotenv.env
export PROMOTER_GATEWAY_PORT=48999
export PROMOTER_GATEWAY_DEBUG=1
# dry-run sample tweet + heuristic classify:
export PROMOTER_DRY_RUN=1
python3 apollo-x-bot/gateway_server.py &
# then `cli.main run …` with `--bridge-endpoint` lines as above (use the same port in BASE=).
```

Non-dry smoke (no X/LLM keys): expect `x.search` warning, empty classify batch, `maybe_daily_post` may report `no_x_auth` — still exercises non-dry branches and stderr debug lines.

## Includes & prompts

- **`prompts/*.txt`** — LLM system + instruction copy for classify and reply drafting; see [`prompts/README.md`](prompts/README.md).
- `modules/common/retry.ainl` — wrapped around `promoter.process_tweet` in `L_each`.
- `modules/common/timeout.ainl` — available for future deadline wrapping (`Call timeout/ENTRY`); not used in this graph.
- **`modules/promoter/`** (under `apollo-x-bot/`): [`modules/promoter/README.md`](modules/promoter/README.md) — bridge JSON shells only (`req_search`, `req_process_tweet`, `req_cursor`, `req_daily`).

## Future extensions (post-stability)

- **Bridge `kv_get` / `kv_set`:** narrow executor backed by existing `PromoterState` KV (same SQLite file).
- **Audit:** migrate structured logging to a `record_decision.ainl` pattern using `access_aware_memory` where appropriate.
- **Prompts:** explore sandboxed `fs.read` for prompt files instead of gateway-only loads.
- **Batch merge:** if `llm.merge_classify_rows` round-trips become painful in graphs, propose `core.merge_llm_scores_batch` with full tests (pure merge, no I/O).
