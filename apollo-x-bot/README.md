# ainl-x-promoter

Strict AINL graph for an X/Twitter **awareness + promotion** workflow for [AINL](https://github.com/sbhooley/ainativelang). Source: `ainl-x-promoter.ainl`.

**Public usage (short):** Run `gateway_server.py` on localhost, point `ainl run` at this graph with `--enable-adapter bridge` and `--enable-adapter memory`, register every executor key below (including `kv.get` / `kv.set`), set `PROMOTER_STATE_PATH` and `AINL_MEMORY_DB` to writable SQLite files, add X + LLM credentials to the gateway environment, and schedule label `_poll` on your cadence. Start with `PROMOTER_DRY_RUN=1` until you trust classify + gate behavior. See **Making this bot public** for security and env details.

## What this demonstrates (AINL vs the gateway)

This is intentionally a **reference integration**, not a contest to delete Python.

- **In AINL (the program people read):** declared cadence (`S core cron`), **retries** around each loop iteration (`Call retry/ENTRY` at `L_each`), **unified bridge bodies** via **[`modules/common/executor_request_builder.ainl`](../modules/common/executor_request_builder.ainl)** (`include … as exreq` + `Call exreq/ENTRY ->req`), **dataflow** (`X` get/put), **policy knobs** (`core.env` + `core.FILTER_HIGH_SCORE`), **loop orchestration**, and **explicit ordering** — including **committing the X search cursor only after** the tweet loop finishes so incremental search stays safe if a run stops mid-loop. **LLM copy** is edited in **[`prompts/*.txt`](prompts/README.md)** (loaded by the gateway), not embedded in the graph. **v2 classify path (default):** `x.search` → `llm.classify` (envelope / raw) → `llm_safe_json_parse` → `llm.merge_classify_rows` when the model returns only `raw_text` → `FILTER_HIGH_SCORE` → loop. **Per tweet:** [`heuristic_keyword_score.ainl`](../modules/common/heuristic_keyword_score.ainl) builds `tweets=[tweet]` + `keywords=[…]`, calls **`promoter.heuristic_scores`**, reads **`items[0].score`**, and passes it as optional **`heuristic_score`** on the **`promoter.gate_eval`** JSON body (**observability only**; **gate_eval** **controls** proceed/skip from SQLite caps/cooldown/dedupe — **`heuristic_score`** is ignored for that decision). Then **`promoter.process_tweet`** or a local skip dict. **`L_after_loop`:** **`kv.get`** snapshot for audit, then **`promoter.search_cursor_commit`** (authoritative cursor KV write inside the gateway — the graph does not mirror with **`kv.set`**). **[`record_decision.ainl`](../modules/common/record_decision.ainl)** with **`record_rd_scope`** **`promoter`**: classify; **`gate_eval`** on proceed (`L_do_process`); **`gate_skip`** on skip (`L72`, detail = **`gate_b`**); **`process_tweet`**; cursor snapshot/commit/daily. Legacy v1 is **commented at the bottom** of `ainl-x-promoter.ainl`.
- **In the gateway (adapters):** secrets, OAuth 1.0a signing, HTTP to X and to the LLM, SQLite, dry-run / heuristic fallbacks, and the **strict-mode-friendly** single `bridge.POST` per tweet that bundles cap/cooldown/draft/post/audit.

That split matches how production systems separate **orchestration** from **platform SDKs**. The graph is the artifact that shows AINL’s strengths; the gateway is the smallest trusted surface that must speak X’s wire protocol.

**Cost note:** Incremental search (`since_id`, stored in SQLite), **deferred cursor commit** from the graph, **reply dedupe** by tweet id, and a tunable classify floor (`PROMOTER_CLASSIFY_MIN_SCORE`, wired in the graph via `core.env`) reduce **X read volume per poll**, **LLM tokens**, and **duplicate reply work** without removing features.

## Validate

```bash
python3 -m cli.main check --strict apollo-x-bot/ainl-x-promoter.ainl
# or: ainl check --strict apollo-x-bot/ainl-x-promoter.ainl
```

**Strict checklist (after graph changes):**

1. `python3 -m cli.main check apollo-x-bot/ainl-x-promoter.ainl --strict`
2. `python3 -m pytest tests/test_common_llm_modules_strict.py tests/test_apollo_x_gateway.py -q`
3. Dry-run poll: `PROMOTER_DRY_RUN=1 ./apollo-x-bot/run-with-gateway.sh` (or gateway up + `./apollo-x-bot/openclaw-poll.sh`)
4. Production-shaped poll: `PROMOTER_DRY_RUN=0` with real keys, same bridge + memory flags as the scripts

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
| `llm.classify` | `POST /v1/llm.classify` | **Default (no `messages`):** merged scored tweet list from server-built prompts + `tweets[]`. **Envelope mode** only when the body includes a **non-empty** `messages` array (OpenAI-style chat); then the response is `{ v, kind, raw_text, error, items }`. A bare `classify_response=raw` without `messages` does **not** force envelope mode (avoids spurious `envelope_missing_messages` on partial requests). |
| `llm.json_array_extract` | `POST /v1/llm.json_array_extract` | Parse first JSON array from a string (`text` or `payload.text`); `{ ok, array, reason?, error? }` — used by `modules/llm/llm_safe_json_parse.ainl`. |
| `llm.merge_classify_rows` | `POST /v1/llm.merge_classify_rows` | Merge `score_rows` / `parsed` onto `tweets` (same rules as legacy classify); returns `{ items }`. |
| `promoter.text_contains_any` | `POST /v1/promoter.text_contains_any` | Case-insensitive substring hits: `haystack` + `phrases[]` → `{ hit_count, any }`. |
| `promoter.heuristic_scores` | `POST /v1/promoter.heuristic_scores` | Keyword heuristic batch: body `tweets[]` + optional `keywords[]` (else gateway defaults); returns `{ items }` with per-tweet `score` / `why` (used by `heuristic_keyword_score.ainl` in `L_each` and by classify fallback in `L_poll`). |
| `promoter.classify_prompts` | `POST /v1/promoter.classify_prompts` | File-backed `{ system, instruction }` for classify (same sources as gateway). |
| `promoter.gate_eval` | `POST /v1/promoter.gate_eval` | SQLite-backed `{ tweet_id, user_id, heuristic_score? }` → `{ proceed, reason, dry_run, daily_count, daily_cap }` (mirrors `process_tweet` skip logic). Extra fields such as `heuristic_score` are ignored for the decision. |
| `promoter.process_tweet` | `POST /v1/promoter.process_tweet` | Cooldowns, draft reply, post reply; reply **system** from [`prompts/reply_system.txt`](prompts/README.md) unless `reply_system_prompt` is set in JSON |
| `promoter.discover_tweet_authors` | `POST /v1/promoter.discover_tweet_authors` | Body `tweets[]` (same shape as `x.search`); scores authors from search results and may follow (when not dry-run). **Default path** from AINL via [`modules/common/promoter_discover_from_tweets.ainl`](../modules/common/promoter_discover_from_tweets.ainl) after `x.search` when `PROMOTER_DISCOVERY_ENABLED=1`, `PROMOTER_DISCOVERY_FROM_SEARCH=1`, and `PROMOTER_DRY_RUN=0`. |
| `promoter.discovery_candidates_from_tweets` | `POST /v1/promoter.discovery_candidates_from_tweets` | Track A step 1: body `tweets[]` → `{ users: [...] }` (dedupe, cap, X user lookup). Empty + `skipped` when preflight fails (e.g. dry-run). |
| `promoter.discovery_score_users` | `POST /v1/promoter.discovery_score_users` | Track A step 2: body `users[]` → `{ items: [{..., score}] }` (heuristic + discovery LLM). |
| `promoter.discovery_apply_one` | `POST /v1/promoter.discovery_apply_one` | Track A optional: single user + `score` in payload (monitor/follow/audit). |
| `promoter.discovery_apply_batch` | `POST /v1/promoter.discovery_apply_batch` | Track A step 4: body `items[]` (scored rows, same shape as score output after `FILTER_HIGH_SCORE` in AINL); applies monitor/follow in one gateway pass with shared caches. |
| `promoter.search_cursor_commit` | `POST /v1/promoter.search_cursor_commit` | Promote pending search `newest_id` → `since_id` after loop + daily (see graph `L_after_loop`) |
| `llm.chat` | `POST /v1/llm.chat` | OpenAI-style `messages[]` + optional `temperature` + `usage_context`; used by **`modules/llm/promoter_daily_post_payload.ainl`** for daily post copy (strict graph). |
| `promoter.daily_snippets` | `POST /v1/promoter.daily_snippets` | `{ snippets }` — repo text for the daily prompt (same env as `PROMOTER_DAILY_SNIPPET_FILES`). |
| `promoter.daily_post_prompts` | `POST /v1/promoter.daily_post_prompts` | `{ system, user_suffix }` from `daily_post_system.txt` + `daily_post_user_suffix.txt`. |
| `promoter.maybe_daily_post` | `POST /v1/promoter.maybe_daily_post` | Up to **`PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY`** (default 15) original posts per UTC day, spaced by **`PROMOTER_ORIGINAL_POST_MIN_INTERVAL_SEC`** (default 3600s = 1h). Body `payload` may include **`text`** (draft from graph); otherwise **`topic` + `link`** produce a static line. |
| `kv.get` | `POST /v1/kv.get` | Read promoter SQLite KV: body `{ "key": "<name>" }` (or executor-bridge `payload` with same keys) → `{ ok, value }` (`value` is JSON `null` when missing). |
| `kv.set` | `POST /v1/kv.set` | Write/delete KV: `{ "key", "value" }` — string values stored; `value: null` deletes the key. Same SQLite file as search cursor / dedupe (`PROMOTER_STATE_PATH`). |

### Human monitoring (read-only GET + token audit)

The gateway logs **every successful chat/completion** that returns a `usage` object as **`audit` rows** with `action = llm.usage` and JSON detail: `context` (e.g. `llm.classify_legacy`, `process_tweet_reply_draft`), `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`. Providers that omit `usage` produce no row (nothing to estimate). **Dollar cost** is not computed (model pricing varies); sum tokens and apply your provider’s rates.

| Path | Role |
|------|------|
| `GET /` or `GET /v1/promoter.dashboard` | Single-page **HTML** monitor: **Chart.js** graphs, **scoring & reply outcomes** (filtered audit: discovery, skips, dry-run, posts), full **audit** tail, **AINL memory decisions** (`gate_eval`, classify counts, etc.) with verdict/reason/JSON detail. Auto-refresh 10s and shows a visible **Last refresh** indicator. |
| `GET /v1/promoter.stats` | JSON snapshot: paths, today’s reply count, dedupe size, `audit` action counts (24h / 7d), LLM token sums (24h), plus **`charts`** (hourly series, `daily_replies`, pie data). Tune `PROMOTER_DASHBOARD_CHART_HOURS` / `PROMOTER_DASHBOARD_CHART_DAYS`. |
| `GET /v1/promoter.audit_tail?limit=80` | JSON: newest `audit` rows with parsed `detail` objects. Each row includes **`verdict`**, **`verdict_label`**, **`reason`** (derived from `detail`). Use **`focus=scoring`** to restrict to reply/discovery outcomes: `discovery_from_search`, `process_tweet_*`. |
| `GET /v1/promoter.memory_tail?limit=40` | JSON: newest `memory_records` for `ops` / `promoter.decision` (same DB as `--memory-db`). Rows include **`verdict`**, **`reason`**, **`user_id`**, full **`detail`** (gate body, classify metadata, etc.). |

Disable with **`PROMOTER_DASHBOARD_ENABLED=0`** if the process is exposed beyond localhost (no auth on these routes).

**SQLite views** (on `PROMOTER_STATE_PATH`, created automatically at gateway startup): **`v_audit_timeline`** (flattened `tweet_id`, `user_id`, `reason`, LLM fields from `detail_json`) and **`v_llm_usage`** (only `llm.usage` rows). Example: `SELECT * FROM v_llm_usage ORDER BY id DESC LIMIT 20;`

**Strict modules (repo `modules/`):** `common/executor_request_builder.ainl` (all bridge JSON envelopes in this graph), `llm/llm_classify_request_builder.ainl`, `llm/llm_safe_json_parse.ainl`, `common/heuristic_keyword_score.ainl` (wraps **`promoter.heuristic_scores`** for one tweet + keyword list), `common/promoter_discover_from_tweets.ainl` (default single-bridge discovery → **`promoter.discover_tweet_authors`**; Track A uses **`promoter.discovery_*`** routes in **`ainl-x-promoter.ainl`** when `PROMOTER_DISCOVERY_AINL_STEPS=1`), `common/promoter_decision_gate.ainl`, `common/record_decision.ainl` (memory audit). **Track A** keeps the graph strict-safe (no `Loop` in the discovery branch): four linear bridge calls + `core.FILTER_HIGH_SCORE` for the min-score gate before **`promoter.discovery_apply_batch`**. **Heuristic note:** `L_each` copies the loop `tweet` into `hkw_tweet`, sets `heuristic_keywords_json`, calls **`heuristic_keyword_score/ENTRY`**, then **`X heur_score get heur_row score`** (via `items` → index `0`). That score is forwarded as **`heuristic_score`** on the gate payload only; classify batch fallback in `L_poll` still uses **`promoter.heuristic_scores`** directly when merge is unavailable.

### `record_decision` (memory audit)

[`modules/common/record_decision.ainl`](../modules/common/record_decision.ainl) writes structured rows via the **`memory` adapter** (`namespace` `ops`, kind `promoter.decision`). The graph sets `record_rd_action`, `record_rd_detail_json`, optional `record_rd_tweet_id` / `record_rd_score`, **`R core.echo "promoter" ->record_rd_scope`**, then `Call rd/ENTRY`. Requires **`--enable-adapter memory`** and `AINL_MEMORY_DB` or `--memory-db` (see scripts). Example frame pattern:

```text
R core.echo "cursor_commit" ->record_rd_action
R core.stringify some_detail_frame ->record_rd_detail_json
Set record_rd_tweet_id null
Set record_rd_score null
R core.echo "promoter" ->record_rd_scope
Call rd/ENTRY ->_
```

**R step style:** in strict lowering, use **`->outvar` with no space** after `->` on `R core.*` / `R bridge.POST` lines so the compiler binds the output variable correctly.

**`core.contains`:** pure substring check `needle in haystack` (empty needle → true) — usable from `R core.contains` in strict graphs without the gateway.

### Environment (gateway)

**Twitter / X names:** In the developer portal, **API Key** under *Consumer Keys* is the **consumer key** — use it as `X_API_KEY` or `X_CONSUMER_KEY`. The **API Key Secret** (consumer secret) is `X_API_SECRET` or `X_CONSUMER_SECRET`. Those are the pair created with the app (you can regenerate them; old ones stop working).

You can put variables in **`apollo-x-bot/.env`** (`KEY=value` per line). The gateway loads that file automatically; `run-with-gateway.sh` and `openclaw-poll.sh` also `source` it so `ainl run` sees the same values. The repo root `.gitignore` already ignores `.env`. Production can instead use `~/.openclaw/apollo-x-promoter.env` via `APOLLO_PROMOTER_ENV` (see `OPENCLAW_DEPLOY.md`).

**Troubleshooting:** If debug shows `X_BEARER_TOKEN` missing but `.env` has it, fix an empty export in your shell (`export X_BEARER_TOKEN=`) or rely on the gateway: non-empty values in `.env` **overwrite** the environment when the process starts. Use `PROMOTER_GATEWAY_DEBUG=1` and check the `startup:` lines for `dotenv_path` / `exists` / `bearer_set`. Delete `data/promoter_state.sqlite` (or change `PROMOTER_STATE_PATH`) to reset **already_posted_today**, **search cursor**, **replied-tweet dedupe**, and related keys during dev.

**Reply / post caps:** If the dashboard or audit shows **`daily_cap`** / **`daily_reply_cap`** while `replies counted` equals **10**, your process almost certainly has **`PROMOTER_MAX_REPLIES_PER_DAY=10`** in the environment (older configs and `AINL_INFRASTRUCTURE_DIAGNOSTIC.md` used 10). The gateway **defaults to 20** in code only when the variable is unset. Set **`PROMOTER_MAX_REPLIES_PER_DAY=20`** in `apollo-x-bot/.env` (or your service env) and restart. Confirm with **`GET /v1/promoter.stats`** → **`max_replies_per_day`**, or read stderr on startup: `caps: PROMOTER_MAX_REPLIES_PER_DAY=…`.

**AINL bridge HTTP timeout:** `cli.main run` defaults to **`--http-timeout-s 5`**, which is often too short for batched `llm.classify` (OpenRouter / slow models). **`openclaw-poll.sh`** and **`run-with-gateway.sh`** pass **`--http-timeout-s 120`** (override with **`AINL_HTTP_TIMEOUT_S`**). If you invoke `ainl run` yourself, set **`--http-timeout-s`** to at least the gateway/LLM latency you expect (executor payloads in this graph already use `timeout_s` up to **120**).

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
| `AINL_MEMORY_DB` | SQLite file for `record_decision` / `memory.put` (default in scripts: `apollo-x-bot/data/promoter_memory.sqlite`; else CLI default `~/.openclaw/ainl_memory.sqlite3`). |
| `PROMOTER_DRY_RUN` | Set to `1` to skip X writes and use heuristic scoring when no LLM key is set. |
| `PROMOTER_MAX_REPLIES_PER_DAY` | Default **`20`** (reply/comment cap per UTC day). |
| `PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY` | Max standalone promotional posts per UTC day (default **`15`**). |
| `PROMOTER_ORIGINAL_POST_MIN_INTERVAL_SEC` | Minimum seconds between original posts (default **`3600`** = 1h) so polls spread posts across the day. |
| `PROMOTER_DAILY_POST_TEMPERATURE` | Sampling temperature for **`llm.chat`** when `usage_context=daily_original_post` (graph default **`0.9`**; gateway default if temperature omitted). |
| `PROMOTER_DAILY_SKIP_LLM` | If **`1`**, **`ainl-x-promoter.ainl`** skips **`llm.chat`** and sends only topic+link to **`maybe_daily_post`** (static body). |
| `PROMOTER_PERSONA_PROFILE` | Personality profile for generated post/reply tone. `default` (current behavior) or `fity`. |
| `PROMOTER_CODEBASE_ROOT` | Root directory for snippet files (default: repo root, parent of `apollo-x-bot`). |
| `PROMOTER_DAILY_SNIPPET_FILES` | Comma-separated paths under codebase root (default `README.md,HOW_AINL_SAVES_MONEY.md,apollo-x-bot/README.md`). |
| `PROMOTER_DAILY_SNIPPET_MAX_CHARS` | Max characters of snippets sent to the LLM (default **`12000`**). |
| `PROMOTER_USER_COOLDOWN_HOURS` | Default `48` (per user_id). |
| `PROMOTER_CLASSIFY_MIN_SCORE` | Integer floor for `core.FILTER_HIGH_SCORE` in the graph (set in shell/env; graph default via `core.env` is `5`). Raise (e.g. `8`) to cut LLM reply volume; must match what you want the classify prompt to treat as “high intent.” |
| `PROMOTER_SEARCH_USE_SINCE_ID` | Default `1`: use stored `since_id` on X recent search and defer advancing until `promoter.search_cursor_commit` runs. Set `0` to always request a fresh page (higher overlap / cost). Ignored when `PROMOTER_DRY_RUN=1`. |
| `PROMOTER_SEARCH_MAX_RESULTS` | Default `10` (allowed range `10`–`100` per X recent search). |
| `PROMOTER_DEDUPE_REPLIED_TWEETS` | Default `1`: skip draft LLM + post for tweet IDs already consumed (reply or dry-run). Set `0` only for debugging. |
| `PROMOTER_PROMPTS_DIR` | Directory containing `classify_system.txt`, `classify_instruction.txt`, `reply_system.txt`, `daily_post_system.txt`, `daily_post_user_suffix.txt` (default: `apollo-x-bot/prompts` next to `gateway_server.py`). |
| `PROMOTER_DAILY_TOPIC` / `PROMOTER_DAILY_LINK` | Optional defaults for the daily-post chain in **`promoter_daily_post_payload.ainl`** (same defaults as the previous hard-coded JSON in the graph). |
| `PROMOTER_GATEWAY_HOST` | Default `127.0.0.1`. |
| `PROMOTER_GATEWAY_PORT` | Default `17302`. |
| `PROMOTER_GATEWAY_DEBUG` | Set to `1` to print `[apollo-x-gateway] …` lines on **stderr** (tweet counts, `n_score_ge_8`, skip reasons). |
| `PROMOTER_DASHBOARD_ENABLED` | Default **on** (`1`): serve GET dashboard + JSON stats. Set **`0`** to disable when the gateway is reachable beyond localhost. |
| `PROMOTER_MONITOR_ENABLED` | Growth pack: `1` enables optional **`monitor-poll.sh`** / `follow_manager.ainl` (default `0`). |
| `PROMOTER_DISCOVERY_ENABLED` | Default **`1`**: score authors from **`x.search`** and **`x.search_users`** (when `merge_monitored`); add to **`monitored_accounts`** and optionally follow. Set **`0`** to disable. |
| `PROMOTER_DISCOVERY_FROM_SEARCH` | Default **`1`**: after each **`x.search`**, score up to **`PROMOTER_DISCOVERY_MAX_AUTHORS_PER_SEARCH`** unique authors not already monitored (heuristic + optional LLM). |
| `PROMOTER_DISCOVERY_AINL_STEPS` | Default **`0`**: use one bridge call **`promoter.discover_tweet_authors`**. Set **`1`** so **`ainl-x-promoter.ainl`** runs Track A ( **`promoter.discovery_*`** candidates → score → filter → **`promoter.discovery_apply_batch`**). Requires the same bridge registrations as the default path. |
| `PROMOTER_DISCOVERY_AUTO_FOLLOW` | Default **`1`**: follow scored authors **not** already in the OAuth following cache (cached via **`GET /2/users/me/following`**). |
| `PROMOTER_DISCOVERY_AUTO_MONITOR` | Default **`1`**: add scored authors to **`monitored_accounts`** (for likes / tracking). |
| `PROMOTER_DISCOVERY_MAX_AUTHORS_PER_SEARCH` | Default **`15`** (cap per poll). |
| `PROMOTER_FOLLOWING_CACHE_TTL_SEC` | Default **`3600`**: seconds between full following-list refreshes. |
| `PROMOTER_LIKE_ENABLED` | Growth pack: `1` allows **`x.like`** and auto-like after **`process_tweet`** when the author is in **`monitored_accounts`** (default `0`). |
| `PROMOTER_THREAD_ENABLED` | Growth pack: `1` enables **`promoter.thread_continue`** (default `0`). |
| `PROMOTER_AWARENESS_BOOST` | Growth pack: `1` adds an extra GitHub CTA line to **`promoter.maybe_daily_post`** text (default `0`). |
| `PROMOTER_DISCOVERY_MIN_SCORE` | Integer **1–10** floor for discovery merge (default `7`). |

Bind the gateway to **localhost** or protect it behind a reverse proxy; the executor bridge has no built-in auth.

### Persona profiles

Set `PROMOTER_PERSONA_PROFILE` in `.env` (or host env) to change style at runtime:

- `default`: existing Apollo style.
- `fity`: ultra-short, punchy, slightly imperfect voice with playful edge; aggressively AINL/graph-focused (no vague agent fluff); uses light emoji sparingly; ends with casual engagement questions; avoids using "Captain/Captains".

## Optional Apollo-X Growth Pack (v1.3)

**Additive only:** `ainl-x-promoter.ainl` and existing routes are unchanged. **Discovery** (score/follow/monitor from search) defaults **on**; other growth flags stay **off** unless set. Optional graphs live under [`modules/apollo/`](modules/apollo/).

| Key | Path | Role |
|-----|------|------|
| `x.follow` | `POST /v1/x.follow` | OAuth user follows `target_user_id`; optional `add_to_monitored` (default true on success). Respects **`PROMOTER_DRY_RUN`**. |
| `x.search_users` | `POST /v1/x.search_users` | Recent search for `query`, author lookup, heuristic + optional LLM scores (`prompts/discovery_user_instruction.txt`). With discovery **on** and body **`merge_monitored`: true**, merges users ≥ **`PROMOTER_DISCOVERY_MIN_SCORE`** into KV/table **`monitored_accounts`**. |
| `x.like` | `POST /v1/x.like` | Like a tweet (OAuth user). Dry-run audits only. |
| `x.get_conversation` | `POST /v1/x.get_conversation` | Recent search for `conversation_id:`; if `conversation_id` omitted, uses first id from KV **`active_threads`**. |
| `promoter.thread_continue` | `POST /v1/promoter.thread_continue` | **`PROMOTER_THREAD_ENABLED=1`**: draft via **`reply_system.txt`** + post reply to **`reply_to_tweet_id`**; tracks **`conversation_id`** in KV **`active_threads`**. |
| `promoter.awareness_boost` | `POST /v1/promoter.awareness_boost` | Returns CTA lines (for optional cron / audit); daily merge still happens in gateway when **`PROMOTER_AWARENESS_BOOST=1`**. |

**State:** KV keys **`monitored_accounts`** and **`active_threads`** hold JSON string arrays (user ids / conversation ids). SQLite tables **`monitored_accounts`** and **`active_threads`** mirror membership for tooling. One-time: `python3 scripts/apollo_migrate_state.py` (idempotent).

**Poll scripts (optional):** `monitor-poll.sh` (`_monitor_list`), `discover-poll.sh` (`_discover`), `thread-poll.sh` (`_thread_continue`). **`like_handler.ainl`** (`_like_batch`) is run manually with the same `--bridge-endpoint` list as those scripts. Example:

```bash
python3 -m cli.main check --strict apollo-x-bot/modules/apollo/follow_manager.ainl
PROMOTER_DRY_RUN=1 PROMOTER_MONITOR_ENABLED=1 ./apollo-x-bot/monitor-poll.sh
```

**Safe rollout:** Keep **`PROMOTER_DRY_RUN=1`**, enable one flag at a time, watch gateway stderr with **`PROMOTER_GATEWAY_DEBUG=1`**, then flip dry-run off.

## Making this bot public

- **Forking / layout:** Clone [sbhooley/ainativelang](https://github.com/sbhooley/ainativelang) (or fork and clone your fork). Use the **`apollo-x-bot/`** tree as-is beside the repo root, or copy that directory into your deployment layout while keeping paths consistent for `include "../modules/..."` in `ainl-x-promoter.ainl`. Create **`apollo-x-bot/.env`** (gitignored) with **`X_*`** and **`OPENAI_*` / `LLM_*`** keys, or use **`APOLLO_PROMOTER_ENV`** pointing at a file outside git (see `OPENCLAW_DEPLOY.md`). Adjust **`PROMOTER_PROMPTS_DIR`** if you customize `apollo-x-bot/prompts/`.
- **Required env (gateway + runner):** `X_BEARER_TOKEN`; `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` for posting; `OPENAI_API_KEY` or `LLM_API_KEY`; `PROMOTER_STATE_PATH`; `AINL_MEMORY_DB` (or `--memory-db`); optional `OPENAI_BASE_URL`, `LLM_MODEL`, and **`PROMOTER_*`** tuning vars from the environment table above.
- **Dry-run:** **`PROMOTER_DRY_RUN=1`** — gateway uses **sample tweets**, **no live X writes**, and classify may use **heuristic fallback** when no LLM key is set. Gate **reasons** and cursor **timing** match production except for real X posts.
- **Security:** Run the gateway on **127.0.0.1** (default) or behind **TLS + auth**. **`kv.set`** can **corrupt** cursor/dedupe state; unauthenticated access to the bridge is effectively **full control** of the bot.
- **Backup:** Copy **`PROMOTER_STATE_PATH`** (SQLite: cursor, dedupe, cooldowns) and **`AINL_MEMORY_DB`** (`record_decision` audit rows) on a schedule you trust.
- **Strict graphs:** Never put a **space** after **`->`** on **`R core.*`** / **`R bridge.POST`** lines — use **`->outvar`** or lowering mis-binds operands (see [`modules/common/executor_request_builder.ainl`](../modules/common/executor_request_builder.ainl) header).
- **Secret check (pre-publish):** From repo root:  
  `git grep -iE 'token|key|secret|bearer|oauth' -- apollo-x-bot/`  
  Review every hit: **documentation of env var names** is fine; **literal secrets** must not appear.

## Why one bridge call per tweet

Strict compilation requires **Loop** body labels (`L_each`) to contain **exactly one terminal `J`** and to **end** with that `J`. Branching inside the loop body breaks that contract. The graph therefore runs **search → LLM classify → filter → Loop** in `L_poll`, and uses a **single** `bridge.POST` to `promoter.process_tweet` per item. The gateway implements daily caps, cooldowns, drafting, posting, and audit.

After the loop, **`L_after_loop`** runs **`promoter.search_cursor_commit`** then **`Call pdpp/ENTRY`** (builds **`llm.chat`** + `maybe_daily`) then **`promoter.maybe_daily_post`** so incremental search advances only after a **complete** poll (crash-safe). Daily LLM orchestration lives in **`modules/llm/promoter_daily_post_payload.ainl`** (strict), not in Python.

## Run (gateway + AINL)

**1. Start the gateway** (from repo root):

```bash
export PROMOTER_DRY_RUN=1   # optional: safe local test
python3 apollo-x-bot/gateway_server.py
```

**2. Run the graph** (separate terminal) with one `--bridge-endpoint` per key:

```bash
BASE=http://127.0.0.1:17302
python3 -m cli.main run apollo-x-bot/ainl-x-promoter.ainl --strict --label _poll \
  --enable-adapter bridge \
  --enable-adapter memory \
  --memory-db "${AINL_MEMORY_DB:-./apollo-x-bot/data/promoter_memory.sqlite}" \
  --bridge-endpoint x.search=${BASE}/v1/x.search \
  --bridge-endpoint llm.classify=${BASE}/v1/llm.classify \
  --bridge-endpoint llm.json_array_extract=${BASE}/v1/llm.json_array_extract \
  --bridge-endpoint llm.merge_classify_rows=${BASE}/v1/llm.merge_classify_rows \
  --bridge-endpoint promoter.text_contains_any=${BASE}/v1/promoter.text_contains_any \
  --bridge-endpoint promoter.heuristic_scores=${BASE}/v1/promoter.heuristic_scores \
  --bridge-endpoint promoter.classify_prompts=${BASE}/v1/promoter.classify_prompts \
  --bridge-endpoint llm.chat=${BASE}/v1/llm.chat \
  --bridge-endpoint promoter.daily_post_prompts=${BASE}/v1/promoter.daily_post_prompts \
  --bridge-endpoint promoter.daily_snippets=${BASE}/v1/promoter.daily_snippets \
  --bridge-endpoint promoter.gate_eval=${BASE}/v1/promoter.gate_eval \
  --bridge-endpoint promoter.process_tweet=${BASE}/v1/promoter.process_tweet \
  --bridge-endpoint promoter.discover_tweet_authors=${BASE}/v1/promoter.discover_tweet_authors \
  --bridge-endpoint promoter.discovery_candidates_from_tweets=${BASE}/v1/promoter.discovery_candidates_from_tweets \
  --bridge-endpoint promoter.discovery_score_users=${BASE}/v1/promoter.discovery_score_users \
  --bridge-endpoint promoter.discovery_apply_one=${BASE}/v1/promoter.discovery_apply_one \
  --bridge-endpoint promoter.discovery_apply_batch=${BASE}/v1/promoter.discovery_apply_batch \
  --bridge-endpoint promoter.search_cursor_commit=${BASE}/v1/promoter.search_cursor_commit \
  --bridge-endpoint promoter.maybe_daily_post=${BASE}/v1/promoter.maybe_daily_post \
  --bridge-endpoint kv.get=${BASE}/v1/kv.get \
  --bridge-endpoint kv.set=${BASE}/v1/kv.set
```

Registering **all** keys above matches `tests/test_apollo_x_gateway.py` and the current graph (`kv.get` is required for `L_after_loop`; `kv.set` is registered for symmetry / future use).

**Convenience script** (starts gateway + runs the graph; defaults `PROMOTER_DRY_RUN=1`):

```bash
./apollo-x-bot/run-with-gateway.sh
```

Use `PYTHON=/path/to/venv/bin/python` if you rely on a virtualenv.

## Cron / OpenClaw

- IR declares `S core cron "*/45 * * * *"` as metadata; your scheduler must **invoke** the runner on label `_poll` (e.g. every 45 minutes).
- **OpenClaw-managed schedules:** use **`openclaw cron add`** with a message that runs `apollo-x-bot/openclaw-poll.sh` (gateway must already be supervised). Full steps: **`OPENCLAW_DEPLOY.md`**.
- Example (system cron):  
  `*/45 * * * * cd /path/to/AI_Native_Lang && /path/to/venv/bin/python -m cli.main run apollo-x-bot/ainl-x-promoter.ainl --strict --label _poll --enable-adapter bridge --enable-adapter memory --memory-db "$AINL_MEMORY_DB" …`  
  Include the same **`--bridge-endpoint`** list as `openclaw-poll.sh`. Ensure the gateway is already running (systemd, Docker, or a long-lived supervisor).

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
- **[`modules/common/executor_request_builder.ainl`](../modules/common/executor_request_builder.ainl)** — shared `run_id` / `step_id` / `executor` / `payload` / `timeout_s` envelope for every `bridge.POST` in this graph (`exreq`).
- `modules/common/retry.ainl` — opens each `L_each` iteration before heuristic + gate + process.
- `modules/common/record_decision.ainl` — memory audit after classify; `gate_eval` on proceed (`L_do_process`); `gate_skip` on skip (`L72`); `process_tweet` (`L_do_process`); cursor KV snapshot, cursor commit, daily.
- `modules/common/timeout.ainl` — available for future deadline wrapping (`Call timeout/ENTRY`); not used in this graph.
- `modules/llm/llm_classify_request_builder.ainl`, `modules/llm/llm_safe_json_parse.ainl` — v2 classify request + safe JSON array parse.

## Future extensions (post-stability)

- **Prompts:** explore sandboxed `fs.read` for prompt files instead of gateway-only loads.
- **Batch merge:** if `llm.merge_classify_rows` round-trips become painful in graphs, propose `core.merge_llm_scores_batch` with full tests (pure merge, no I/O).
