# Email Monitor Wrapper

**See also:** [`openclaw/bridge/run_wrapper_ainl.py`](../../openclaw/bridge/run_wrapper_ainl.py) (registry) · [`docs/ainl_openclaw_unified_integration.md`](../../ainl_openclaw_unified_integration.md) (integration hub)

---

## Overview

The **email monitor** is a lightweight OpenClaw bridge workflow (`openclaw/bridge/wrappers/email_monitor.ainl`, runner name **`email-monitor`**).

By default, the wrapper is **disabled** in `openclaw/bridge/run_wrapper_ainl.py` because it depends on the optional `openclaw mail` plugin. Enable it only if your OpenClaw install has that plugin configured.

When enabled, in production it:

- Fetches unread emails via the `email` adapter (OpenClaw’s `mail check`).
- If any unread messages are found, sends a single consolidated Telegram notification showing the count and the subject of the most recent email.
- Runs on a configurable schedule (default: every 15 minutes).

This wrapper replaces the legacy Python `email_monitor.py` script, demonstrating a simple cron job conversion to AINL-native graph execution.

## How it works

1. **Schedule:** The wrapper declares `S core cron "*/15 * * * *"` inside the source. Production timing is whatever you configure in OpenClaw (`openclaw cron add`); keep it aligned with the source.

2. **Invocation:**

   ```bash
   python3 openclaw/bridge/run_wrapper_ainl.py email-monitor [--dry-run]
   ```

3. **Workflow:**
   - Calls `R email G` to get unread messages (returns JSON with a `messages` array).
   - Extracts the count and the first message’s `subject`.
   - Builds a notification: `📧 You have X unread email(s).\nLatest: <subject>`.
   - Sends via `R queue Put ["notify", message]` (OpenClaw Telegram delivery).

   In dry-run mode, `queue Put` is skipped, but the rest executes.

## Installation (from scratch)

1. **Ensure the wrapper is present** in `AI_Native_Lang/openclaw/bridge/wrappers/email_monitor.ainl` (bundled).

2. **Enable and register the wrapper** in `openclaw/bridge/run_wrapper_ainl.py` by adding or uncommenting the following entry in `WRAPPERS`:
   ```python
   "email-monitor": _BRIDGE_DIR / "wrappers" / "email_monitor.ainl",
   ```

3. **Add a cron job** (or replace existing Python-based email monitor):
   ```bash
   openclaw cron add \
     --name "Email Monitor — Immediate alerts" \
     --cron "*/15 * * * *" \
     --session-key "agent:default:ainl-advocate" \
     --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py email-monitor" \
     --description "AINL email monitor wrapper"
   ```

   Adjust `--session-key` to match your agent’s session if different.

4. **Test:**
   ```bash
   python3 openclaw/bridge/run_wrapper_ainl.py email-monitor --dry-run
   ```

   The dry-run will print the JSON output; inspect the `out` value for the chosen branch.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENCLAW_TARGET` or `OPENCLAW_NOTIFY_CHANNEL` | Destination for Telegram notifications (chat ID or channel). Required for live delivery. |
| `AINL_DRY_RUN` | Set to `1` to skip side effects; also pass `--dry-run`. |

## Example output

Live Telegram notification:

```
📧 You have 3 unread email(s).
Latest: Re: Project update – please review
```

## Troubleshooting

| Issue | What to do |
|-------|------------|
| **No Telegram** | Confirm `OPENCLAW_TARGET` or `OPENCLAW_NOTIFY_CHANNEL` is set and that the OpenClaw message plugin is configured for Telegram. |
| **Adapter errors** | Ensure `openclaw mail check` works from the command line. The `email` adapter mirrors `openclaw mail check --unread --json`. |
| **Cron not running** | Verify the cron job status with `openclaw cron list` and `openclaw cron runs <id>`. |
| **Dry-run shows success but live fails** | Check agent session key and permissions; ensure the bridge runner has access to `email` and `queue` adapters (registry allowlist). |

## Development notes

- The wrapper uses only core AINL ops and the `email`/`queue` adapters, making it a minimal conversion example.
- To extend (e.g., add importance filtering, digest mode), edit `email_monitor.ainl`. The source is heavily commented.
- This pattern can be replicated for other simple poll-and-notify cron jobs.
