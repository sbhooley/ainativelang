# Intelligence Digest Program — Technical Documentation

## Overview

The Intelligence Digest is an automateddaily reporting system that combines real‑time web search and internal TikTok analytics into a single markdown summary. It runs via the OpenClaw AINL (AI Native Language) engine, stores results in the CRM database (`IntelligenceReport` table), and optionally sends notifications over Telegram.

**Key features**

- Direct `web search` via Perplexity Sonar (OpenRouter).
- TikTok recent activity count from the CRM database.
- Robust JSON parsing with fallback extraction.
- Simple deployment via cron (default: 08:00, 12:00, 18:00 UTC).
- Outputs to DB and Telegram; additionally written to `/tmp/intelligence_report_latest.txt`.

## Architecture

```
scripts/run_intelligence_digest.py    ← Runner (Python)
AI_Native_Lang/intelligence/intelligence_digest.lang   ← AINL program
AI_Native_Lang/adapters/openclaw_integration.py       ← WebAdapter, TiktokAdapter
CRM (Prisma)                ← IntelligenceReport table
.env                        ← Configuration (OPENROUTER_API_KEY, SOCIAL_MONITOR_QUERY)
```

### Runner

- Loads `.env` to pick up `OPENROUTER_API_KEY` and `SOCIAL_MONITOR_QUERY`.
- Registers adapters via `openclaw_monitor_registry()`.
- Explicitly allows `web` and `tiktok` adapters.
- Compiles the AINL program with `AICodeCompiler`.
- Executes label `0` with `trace=True`.
- Extracts outputs from trace events:
  - `ts` from `R core now`
  - `mentions` from `R web search "<query>"`
  - `tiktok_recent` from `R tiktok recent 24`
- Builds a markdown report body.
- Stores the report via `log_intelligence_report`.
- Attempts Telegram delivery via `R queue Put` (using default OpenClaw messaging target).

### AINL Program

A minimal single‑label program:

```
L0: R core now ->ts
R web search "..." ->mentions
R tiktok recent 24 ->tiktok_recent
Ret null
```

- `R core now` produces an ISO timestamp.
- `R web search "<query>"` returns a list of dicts `{id, title, text}`.
- `R tiktok recent 24` returns an integer count of videos created in the last 24 hours.

### WebAdapter

- Group: `web`, target: `search`.
- Requires `OPENROUTER_API_KEY`.
- Calls `https://openrouter.ai/api/v1/chat/completions` with model `perplexity/sonar`.
- System prompt instructs pure JSON array output (`[{id, title, text}, ...]`).
- Fallback parsing: strips markdown code fences; if JSON parse fails, extracts the first `[...]` substring.
- Normalizes keys: `id` (URL), `title` (headline), `text` (snippet).
- Timeout: 60s; returns a list.

### TiktokAdapter

- Group: `tiktok`, target: `recent`.
- Argument: integer `hours` (e.g., `24`).
- Queries the CRM database (`TiktokVideo` table) for records with `createdAt` within the past `hours`.
- Returns an integer count.

## Configuration

All configuration lives in `.env` at the workspace root:

```bash
# Required
OPENROUTER_API_KEY=sk-orv1-...    # Your OpenRouter API key

# Query used for web search (10‑site focused)
SOCIAL_MONITOR_QUERY='("U.S. Iran war" OR "Strait of Hormuz" OR "oil prices" OR "ICE" OR "Palantir" OR "Anthropic" OR "Federal Reserve" OR "immigration enforcement" OR "surveillance AI") site:reuters.com OR site:apnews.com OR site:bbc.com OR site:iea.org OR site:federalreserve.gov OR site:dhs.gov OR site:ice.gov OR site:palantir.com OR site:anthropic.com OR site:defense.gov OR site:aljazeera.com OR site:dw.com OR site:fr24news.com'
```

Existing keys (Google Places, Cloudflare) are unrelated but retained.

## Running Manually

```bash
cd /Users/clawdbot/.openclaw/workspace
python3 scripts/run_intelligence_digest.py
```

The script logs to stdout and the OpenClaw log system. On success, it prints “==== END REPORT ====” and logs `INFO: Logged intelligence report: Intelligence Digest (ok)`.

## Cron Scheduling

OpenClaw cron jobs can be used to run the digest automatically. Current schedule (UTC):

- `0 8,12,18 * * *`  → daily at 08:00, 12:00, 18:00.

To list OpenClaw cron jobs:

```bash
openclaw cron list
```

To add/edit a job, use the OpenClaw operator UI or edit the cron store. The payload should be `agentTurn` pointing to the main session and executing `scripts/run_intelligence_digest.py`.

## Outputs

1. **Database record** – `IntelligenceReport` columns:
   - `jobName`: “Intelligence Digest”
   - `createdAt`: timestamp (UTC)
   - `status`: `ok` | `error` | `starting`
   - `result_json`: JSON object with keys `ts`, `mentions`, `tiktok_recent`
   - `error_text`: populated if status is `error`
   - `deliveryStatus`: `delivered` or `null`
   - `telegram_message_id`: if delivered via Telegram.

2. **Telegram message** – sent to the OpenClaw default target (usually your user ID or a channel). The message contains a concise summary and a link to the CRM report.

3. **Local file** – `/tmp/intelligence_report_latest.txt` (overwritten each run) contains the full markdown body.

## CRM Integration

- Backend endpoint: `GET /api/intelligence-reports` (list) and `GET /api/intelligence-reports/:id` (detail).
- Frontend page: `/crm/intelligence_report.html` (viewable via Caddy reverse proxy at `:8787/crm/intelligence_report.html?id=<id>`).
- The “Reports” dropdown in `/crm/reports.html` includes an “Intelligence reports” option.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `WebAdapter: OPENROUTER_API_KEY not set` | `.env` missing key or runner not loading `.env` | Ensure `OPENROUTER_API_KEY` is present; runner loads `.env` before importing adapters. |
| `web search JSON parse error` | OpenRouter response not pure JSON | Adapter strips code fences and falls back to array extraction; if repeated, inspect logs for raw content. |
| `Adapter error: Access denied (adapter 'web')` | Adapter not allowed | Runner calls `engine.adapters.allow('web')`. If still failing, check adapter registration in `openclaw_monitor_registry`. |
| `telegram send failed` | Target chat not reachable | Verify OpenClaw messaging configuration (`openclaw message send --target <id> test`). |
| Report `status: starting` never changes | Runner crashed before `log_intelligence_report` | Check runner logs for exceptions; ensure `cap=web` and `openclaw_integration.py` imports succeed. |
| `mentions` array empty | Query returns no matches | Adjust `SOCIAL_MONITOR_QUERY` to be less restrictive or test with a generic query. |

## File Reference

- `AI_Native_Lang/adapters/openclaw_integration.py:240` → `WebAdapter` implementation.
- `scripts/run_intelligence_digest.py` → main runner (compilation, execution, logging).
- `AI_Native_Lang/intelligence/intelligence_digest.lang` → AINL source program.
- `crm/src/routes.ts` → API endpoints for intelligence reports.
- `crm/src/public/intelligence_report.html` → frontend detail view.

## Customization

- **Query**: Edit `SOCIAL_MONITOR_QUERY` in `.env`. Supports OR/AND and site restrictions.
- **Model**: Change `perplexity/sonar` to another OpenRouter model in `WebAdapter` if desired (respect rate limits).
- **Schedule**: Adjust cron times via `openclaw cron update …`.
- **Telegram target**: Set `OPENCLAW_TARGET` environment variable; otherwise uses OpenClaw default.

## Future Enhancements

- Add per‑adapter metrics (latency, success rate) to the runner.
- Include article titles in the markdown report (currently only snippet).
- Add retry/backoff for OpenRouter 429 responses.
- Replace the `queue` delivery with a direct `message send` call for more reliable Telegram targeting.

---

## See also

- **`docs/INTELLIGENCE_PROGRAMS.md`** — full map of `intelligence/*.lang` (digest, consolidation, summarizer, bootstrap context, continuity).
- **`agent_reports/README.md`** — indexed OpenClaw agent field reports.

---

Last updated: 2026‑03‑19
Maintained by: Steven / Apollo
