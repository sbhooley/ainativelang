# Apollo X Promoter Production Restart Checklist

Use this checklist after pulling updates or rebooting the host.

## 1) Confirm environment

- `PROMOTER_GATEWAY_PORT=17302`
- `PROMOTER_GATEWAY_URL=http://127.0.0.1:17302`
- `PROMOTER_STATE_PATH` points to `apollo-x-bot/data/promoter_state.sqlite`
- `AINL_MEMORY_DB` points to `apollo-x-bot/data/promoter_memory.sqlite`

## 2) Restart gateway

From `apollo-x-bot/`:

```bash
PROMOTER_GATEWAY_PORT=17302 python3 gateway_server.py
```

Expected startup lines include:

- `apollo-x gateway on http://127.0.0.1:17302/v1/...`
- `apollo-x monitor  http://127.0.0.1:17302/v1/promoter.dashboard`

## 3) Endpoint smoke checks

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:17302/v1/promoter.dashboard
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:17302/v1/promoter.stats", timeout=10) as r:
    s = json.load(r)
print("stats_ok", bool(s))
print("last_poll_success_ts", (s.get("run_health") or {}).get("last_poll_success_ts"))
print("daily_fallback_active", (s.get("policy_state") or {}).get("daily_fallback_active"))
print("llm_calls_avoided", (s.get("cost_avoidance_last_24h") or {}).get("llm_calls_avoided"))
print("original_posts_today", s.get("original_posts_today"), "/", s.get("original_posts_cap"))
PY
```

## 4) Dry-run poll checks

```bash
PROMOTER_DRY_RUN=1 ./openclaw-poll.sh
PROMOTER_DRY_RUN=1 ./thread-poll.sh
```

Expected: both commands return `{'ok': True, ...}`.

## 5) Quick run-health review

In dashboard (`/v1/promoter.dashboard`) verify:

- `Run health` card updates after polls
- `Policy state` reflects active/expired flags correctly
- `Cost avoidance (24h)` shows non-zero values when fallback/skip policies are active

## 6) Poll schedule (OpenClaw or OS cron)

The promoter does not run by itself: something must invoke `apollo-x-bot/openclaw-poll.sh` on a cadence (e.g. every 45 minutes). After restart:

- **OpenClaw:** confirm the job exists (`openclaw cron` / your host’s UI) and the message still `cd`’s to this repo and runs `bash apollo-x-bot/openclaw-poll.sh`. See **`OPENCLAW_DEPLOY.md`** for the exact `openclaw cron add` example.
- **OS cron:** `crontab -l` should contain a line that runs the same script; fix missing jobs if `GET /v1/promoter.stats` → `run_health` shows stale `last_poll_success_utc`.
