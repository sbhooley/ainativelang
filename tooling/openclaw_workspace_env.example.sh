#!/usr/bin/env bash
# Pin AINL + OpenClaw paths to ONE workspace root (safe to parallelize with OpenClaw host work).
#
# Usage (from repo root or anywhere):
#   export OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace"   # optional override
#   . tooling/openclaw_workspace_env.example.sh
#   eval "$(ainl profile emit-shell openclaw-default)"
#
# Then run: python3 scripts/run_intelligence.py context --dry-run
#
# Anchor: OPENCLAW_WORKSPACE (defaults to ~/.openclaw/workspace).

export OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
export OPENCLAW_MEMORY_DIR="${OPENCLAW_MEMORY_DIR:-$OPENCLAW_WORKSPACE/memory}"
export OPENCLAW_DAILY_MEMORY_DIR="${OPENCLAW_DAILY_MEMORY_DIR:-$OPENCLAW_MEMORY_DIR}"
export AINL_FS_ROOT="${AINL_FS_ROOT:-$OPENCLAW_WORKSPACE}"

_ainl_local="$OPENCLAW_WORKSPACE/.ainl"
mkdir -p "$_ainl_local"
export AINL_MEMORY_DB="${AINL_MEMORY_DB:-$_ainl_local/ainl_memory.sqlite3}"
export MONITOR_CACHE_JSON="${MONITOR_CACHE_JSON:-$_ainl_local/monitor_state.json}"
export AINL_EMBEDDING_MEMORY_DB="${AINL_EMBEDDING_MEMORY_DB:-$_ainl_local/embedding_memory.sqlite3}"
export AINL_IR_CACHE_DIR="${AINL_IR_CACHE_DIR:-$HOME/.cache/ainl/ir}"

unset _ainl_local
