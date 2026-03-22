# Apollo X promoter — OpenClaw production deployment

OpenClaw does **not** replace the HTTP gateway: the graph uses `ExecutorBridgeAdapter` (`R bridge.POST …`), which requires a **long-lived** `gateway_server.py` (or equivalent) reachable at the URLs you pass to `--bridge-endpoint`. OpenClaw’s built-in **`openclaw/bridge/run_wrapper_ainl.py`** path registers **`BridgeTokenBudgetAdapter`** for token-budget wrappers — it does **not** wire generic `bridge.POST` executor keys. So production here is:

1. **Supervise the gateway** (systemd, launchd, Docker, or a host process manager).
2. **Schedule polls** with **OpenClaw cron** (or OS cron) using `apollo-x-bot/openclaw-poll.sh` (or an equivalent `python -m cli.main run …` line).

Optional: keep using **`ainl install-mcp --host openclaw`** so the agent can compile/run other AINL via MCP — orthogonal to the promoter poll.

---

## 1. Install toolchain on the host

```bash
pip install 'ainl-lang[mcp]'
# Optional: MCP + ~/.openclaw/openclaw.json + ~/.openclaw/bin/ainl-run
ainl install-mcp --host openclaw
```

Point `PYTHON` / `PATH` at the same venv OpenClaw cron will use.

---

## 2. Secrets and gateway URL

Create a file **outside git**, e.g. `~/.openclaw/apollo-x-promoter.env`:

```bash
export PYTHON=/path/to/venv/bin/python
export PROMOTER_GATEWAY_URL=http://127.0.0.1:17301
export PROMOTER_DRY_RUN=0
# Search (app): Bearer is enough for GET /2/tweets/search/recent
export X_BEARER_TOKEN=...
# Posting (user context): Twitter requires OAuth 1.0a — get Access Token & Secret from the
# developer portal (Keys and tokens) after enabling OAuth 1.0a for your app.
export X_API_KEY=...           # a.k.a. Consumer Key / API Key
export X_API_SECRET=...        # Consumer Secret
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...
export OPENAI_API_KEY=...
export PROMOTER_STATE_PATH="$HOME/.openclaw/workspace/apollo-x-bot/promoter_state.sqlite"
```

Aliases: `X_CONSUMER_KEY` / `X_CONSUMER_SECRET` work the same as `X_API_KEY` / `X_API_SECRET`. Posting tries OAuth 1.0a first; Bearer-only POST often returns 403 from X.

Then:

```bash
export APOLLO_PROMOTER_ENV="$HOME/.openclaw/apollo-x-promoter.env"
```

`openclaw-poll.sh` sources `APOLLO_PROMOTER_ENV` if set and the file exists.

---

## 3. Run the gateway under supervision

The gateway must be up **before** each poll. Example (adjust paths):

```bash
cd /path/to/AI_Native_Lang
set -a && source ~/.openclaw/apollo-x-promoter.env && set +a
export PROMOTER_GATEWAY_HOST=127.0.0.1
export PROMOTER_GATEWAY_PORT=17301
exec python3 apollo-x-bot/gateway_server.py
```

Wire this into **systemd** / **launchd** / **Docker** with `Restart=always` (or equivalent). Bind to **127.0.0.1** unless you put TLS + auth in front.

---

## 4. OpenClaw cron — manage the schedule

Use the same pattern as `openclaw/bridge/README.md`: one job that runs the poll script, stable session key, schedule aligned with `S core cron "*/45 * * * *"` in the graph (or your chosen cadence).

Set **`AINL_WORKSPACE`** (or use absolute paths in the message):

```bash
export AINL_WORKSPACE=/path/to/AI_Native_Lang
export APOLLO_PROMOTER_ENV="$HOME/.openclaw/apollo-x-promoter.env"
```

```bash
openclaw cron add \
  --name apollo-x-promoter-poll \
  --cron "*/45 * * * *" \
  --session-key "agent:default:ainl-advocate" \
  --message 'cd $AINL_WORKSPACE && APOLLO_PROMOTER_ENV='"$HOME"'/.openclaw/apollo-x-promoter.env bash apollo-x-bot/openclaw-poll.sh'
```

Notes:

- Adjust `--session-key` and flags to match your installed `openclaw cron add --help`.
- If `$VAR` expansion in `--message` is unreliable, use a **single line with absolute paths** (no env expansion in the stored payload).
- Validate with **`--dry-run`** on the gateway (`PROMOTER_DRY_RUN=1`) before enabling live X.

---

## 5. Drift checks (optional)

`tooling/cron_registry.json` documents jobs whose **payload** contains `run_wrapper_ainl.py`. The promoter uses **`openclaw-poll.sh`** instead — if you want `openclaw/bridge/cron_drift_check.py` to track this job, add a matching row to **your** registry copy and set `openclaw_match.payload_contains` to a **substring of your actual cron message** (e.g. `openclaw-poll.sh`).

---

## 6. What OpenClaw “manages” vs what the host manages

| Piece | Who manages |
|-------|-------------|
| **When** the poll runs | OpenClaw cron (or OS cron) |
| **Gateway process** | systemd / Docker / launchd (always on) |
| **Secrets** | Host env / `apollo-x-promoter.env` (not in repo) |
| **SQLite state** | `PROMOTER_STATE_PATH` on disk |
| **AINL graph** | `apollo-x-bot/ainl-x-promoter.ainl` in `AI_Native_Lang` |

---

## See also

- `docs/OPENCLAW_INTEGRATION.md` — MCP skill and `~/.openclaw/openclaw.json`
- `openclaw/bridge/README.md` — OpenClaw cron patterns and `AINL_WORKSPACE`
- `docs/CRON_ORCHESTRATION.md` — multi-scheduler governance
