# Token-Aware Startup Context

**Automatically generates a compact `session_context.md` for OpenClaw session bootstrapping, reducing token usage on every new session.**

## Overview

The `token_aware_startup_context` wrapper (AINL) reads your full `MEMORY.md`, filters for high-signal lines (decisions, preferences, todos, lessons, settings), and writes an optimized bootstrap file targeted to a configurable token budget (default: 200–2000 tokens, typically ~500).

This reduces session bootstrap tokens from ~3,200 (full MEMORY.md) to well under 1,000, preventing context max-outs during high-frequency usage. It is part of the AINL v1.2.8 enhancements for OpenClaw.

## Deployment Status

✅ **Deployed** on this system (2026-03-26).
- Wrapper: `AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl`
- Cron job: `Token-Aware Startup Context` (runs every 15 minutes)
- Runner: `openclaw/bridge/run_wrapper_ainl.py`
- Session key: `agent:default:ainl-advocate`

The file `.openclaw/bootstrap/session_context.md` is automatically regenerated; do not edit manually.

## Installation (from scratch)

1. Copy the wrapper:
   ```bash
   cp AI_Native_Lang/intelligence/token_aware_startup_context.lang AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl
   ```

2. Register the wrapper in `openclaw/bridge/run_wrapper_ainl.py`:
   ```python
   "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",
   ```

3. Configure environment (optional):
   - `AINL_STARTUP_CONTEXT_TOKEN_MIN` (default 200)
   - `AINL_STARTUP_CONTEXT_TOKEN_MAX` (default 2000)
   - `AINL_STARTUP_USE_EMBEDDINGS` (default 0) — enable if `embedding_memory` is indexed

4. Add cron job:
   ```bash
   openclaw cron add \
     --name "Token-Aware Startup Context" \
     --cron "*/15 * * * *" \
     --session-key "agent:default:ainl-advocate" \
     --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py token-aware-startup" \
     --description "Generates optimized session_context.md for faster boot"
   ```

5. Test:
   ```bash
   python3 openclaw/bridge/run_wrapper_ainl.py token-aware-startup --dry-run
   ```

## How It Works

- Uses the `openclaw_monitor_registry()` adapters (fs, memory, cache, embedding_memory).
- Reads `MEMORY.md` from the workspace root.
- Selects high-value lines using heuristics and (optionally) embedding similarity.
- Respects a token budget derived from the daily token budget or explicit limits.
- Writes to `.openclaw/bootstrap/session_context.md`.
- Logs generation metrics to AINL memory and monitor cache.

## Verification

- Check file modification time updates each run.
- Compare token counts: the generated file should be a few hundred lines (~200–500 tokens).
- Observe `/status` in new sessions: bootstrap token usage should be significantly lower.

## Related Documentation

- Full integration guide: [`docs/ainl_openclaw_unified_integration.md`](../../ainl_openclaw_unified_integration.md)
- Token budget bridge: `BRIDGE_TOKEN_BUDGET_ALERT.md` (same directory)

## Notes

- The wrapper runs under the same registry as other AINL-OpenClaw bridge wrappers.
- `OPENCLAW_FS_ROOT` is set automatically by the registry to your OpenClaw workspace.
- If using embeddings, ensure `embedding_memory` is populated and set `EMBEDDING_MODE`.
- The cron schedule can be adjusted; every 15 minutes keeps context fresh without excessive load.
