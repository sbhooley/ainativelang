# Token-Aware Startup Context

**Automatically generates a compact `session_context.md` for OpenClaw session bootstrapping, reducing token usage on every new session.**

## Overview

The `token_aware_startup_context` wrapper (AINL) reads your full `MEMORY.md`, filters for high-signal lines (decisions, preferences, todos, lessons, settings), and writes an optimized bootstrap file targeted to a configurable token budget (tuned to **100-150** tokens, typically **~140**).

This reduces session bootstrap tokens from ~3,200 (full MEMORY.md) to ~150 tokens (>95% reduction), preventing context max-outs during high-frequency usage. It is part of the AINL v1.2.8+ enhancements for OpenClaw (shipped; current **v1.7.0** includes `ainl install openclaw` and `ainl status`).

## Deployment Status

✅ **Deployed** on this system (2026-03-26).
- Wrapper: `AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl`
- Cron job: `Token-Aware Startup Context` (runs every 15 minutes)
- Runner: `openclaw/bridge/run_wrapper_ainl.py`
- Session key: `agent:default:ainl-advocate`
- **Optimizations (v1.2.8–v1.7.0 cumulative):**
  - Token budget tightened: `MIN=100`, `MAX=150` (now `MAX=100` in config) → typical output **~115 tokens** (range 100–150)
  - Embedding selection currently disabled in wrapper runtime (`useEmb=false`) for stability; filesystem heuristics are used
  - Compaction tuned: `reserveTokens=30000` (from 50k) for more frequent pruning
  - Wrapper bugfix: replaced fragile `core.env.get` pattern with `R core env` + `Set` to avoid env-read instability
  - Line length threshold remains 60 chars; selection naturally yields 11–17 lines

The file `.openclaw/bootstrap/session_context.md` is automatically regenerated; do not edit manually.

## Installation (from scratch)

**Recommended:** Use the all-in-one setup script for easiest installation:

```bash
cd AI_Native_Lang/scripts
./setup_ainl_integration.sh --with-cron
```

This automates all steps below (config patch, wrapper registration, host patching, cron jobs, gateway restart). For manual installation or to understand each step, continue.

---

1. Copy the wrapper:
   ```bash
   cp AI_Native_Lang/intelligence/token_aware_startup_context.lang AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl
   ```

2. Register the wrapper in `openclaw/bridge/run_wrapper_ainl.py`:
   ```python
   "token-aware-startup": _BRIDGE_DIR / "wrappers" / "token_aware_startup_context.ainl",
   ```

3. **Set environment variable** (OpenClaw >= 2026.3.22):
   The gateway already supports `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` natively. Ensure it is set to `1`.
   This is done automatically by `setup_ainl_integration.sh` via `gateway config.patch`. For manual config:
   ```bash
   openclaw gateway config.patch '{"env":{"vars":{"OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT":"1"}}}'
   ```
   Then restart: `openclaw gateway restart`
   *For OpenClaw versions older than 2026.3.22, use the legacy patch script: `scripts/patch_bootstrap_loader.sh` (not recommended; upgrade instead).*

4. Configure environment (optional):
   - `AINL_STARTUP_CONTEXT_TOKEN_MIN` (default **100**)
   - `AINL_STARTUP_CONTEXT_TOKEN_MAX` (default **150**) – tuned for ~115-token output; lower to 100 for tighter context
   - `AINL_STARTUP_USE_EMBEDDINGS` / `AINL_EMBEDDING_MODE` are reserved for future embedding re-enable (currently ignored by wrapper runtime)

5. Add cron job:
   ```bash
   openclaw cron add \
     --name "Token-Aware Startup Context" \
     --cron "*/15 * * * *" \
     --session-key "agent:default:ainl-advocate" \
     --message "Run: cd /path/to/AI_Native_Lang && python3 openclaw/bridge/run_wrapper_ainl.py token-aware-startup" \
     --description "Generates optimized session_context.md for faster boot"
   ```
   Adjust the schedule as needed; every 15 min keeps context fresh without overloading.

6. Test:
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
- Compare token counts: the generated file should be ~100–150 tokens (~10–15 lines, ~400–500 bytes).
- Observe `/status` in new sessions: bootstrap token usage should be significantly lower (~115 tokens).

## Related Documentation

- Full integration guide: [`docs/ainl_openclaw_unified_integration.md`](../../ainl_openclaw_unified_integration.md)
- Token budget bridge: `BRIDGE_TOKEN_BUDGET_ALERT.md` (same directory)

## Notes

- The wrapper runs under the same registry as other AINL-OpenClaw bridge wrappers.
- `OPENCLAW_FS_ROOT` is set automatically by the registry to your OpenClaw workspace.
- Embedding-based selection is currently disabled in wrapper runtime; current behavior is filesystem-only heuristic selection.
- The cron schedule can be adjusted; every 15 minutes keeps context fresh without excessive load.
