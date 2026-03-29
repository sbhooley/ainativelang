#!/usr/bin/env bash
# setup_ainl_integration.sh — AINL v1.3.1 OpenClaw integration setup
#
# This script is a thin convenience wrapper around `ainl install openclaw`.
# For most users, running `ainl install openclaw --workspace PATH` directly is
# the recommended path (it handles env.shellEnv, SQLite, crons, and prints a
# health table). This script adds --with-cron and --dry-run flags for
# environments that prefer a single shell entry point.
#
# Usage:
#   ./setup_ainl_integration.sh [--workspace PATH] [--dry-run] [--with-cron] [--verbose]
#
# Options:
#   --workspace PATH   OpenClaw workspace root (default: ~/.openclaw/workspace)
#   --dry-run          Print what would happen; make no changes
#   --with-cron        Also register gold-standard cron jobs (same as ainl install openclaw default)
#   --verbose          Pass --verbose to ainl install openclaw
#
# Requires: ainl CLI on PATH (pip install 'ainativelang[mcp]')
# Docs: docs/QUICKSTART_OPENCLAW.md
# NOTE: openclaw gateway config.patch is no longer used — env.shellEnv keys
#       are merged directly into openclaw.json (gateway config.patch rejects
#       AINL-specific keys via schema validation).

set -euo pipefail

AINL_BIN="${AINL_BIN:-ainl}"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
DRY_RUN=0
VERBOSE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)  WORKSPACE="$2"; shift 2 ;;
    --workspace=*) WORKSPACE="${1#*=}"; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --with-cron)  shift ;;   # cron registration is default in ainl install openclaw; accepted for compatibility
    --verbose|-v) VERBOSE=1; shift ;;
    -h|--help)
      grep '^#' "$0" | head -25 | sed 's/^# \{0,2\}//'
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "== AINL v1.3.1 OpenClaw Integration Setup =="
echo ""

if ! command -v "$AINL_BIN" &>/dev/null; then
  echo "ERROR: 'ainl' not found on PATH." >&2
  echo "Install: pip install 'ainativelang[mcp]'" >&2
  exit 1
fi

AINL_VER=$("$AINL_BIN" --version 2>/dev/null | head -1 || echo "unknown")
echo "ainl: $AINL_VER"
echo "workspace: $WORKSPACE"
echo ""

# Build ainl install openclaw args
ARGS=("install" "openclaw" "--workspace" "$WORKSPACE")
[[ $DRY_RUN -eq 1 ]] && ARGS+=("--dry-run")
[[ $VERBOSE -eq 1 ]] && ARGS+=("--verbose")

if [[ $DRY_RUN -eq 1 ]]; then
  echo "-- DRY RUN (no changes will be made) --"
  echo ""
fi

echo "Running: $AINL_BIN ${ARGS[*]}"
echo ""
"$AINL_BIN" "${ARGS[@]}"
EXIT=$?

echo ""
if [[ $EXIT -eq 0 && $DRY_RUN -eq 0 ]]; then
  echo "== Setup complete =="
  echo ""
  echo "Next steps:"
  echo "  ainl status                    # unified health view"
  echo "  ainl doctor --ainl             # integration diagnostics"
  echo "  openclaw cron list             # verify cron jobs"
  echo "  ainl status --json             # machine-readable output"
  echo ""
  echo "Docs: docs/QUICKSTART_OPENCLAW.md"
elif [[ $DRY_RUN -eq 1 ]]; then
  echo "== Dry run complete. Re-run without --dry-run to apply. =="
fi

exit $EXIT
