#!/usr/bin/env bash
# AINL Auto-Tuner runner for OpenClaw
# Part of the official AINL integration suite.

set -euo pipefail

# Resolve workspace
WS="${OPENCLAW_WORKSPACE:-${WORKSPACE:-$HOME/.openclaw/workspace}}"
cd "$WS/AI_Native_Lang" || exit 1

# Optional: source environment if present
if [ -f "tooling/openclaw_workspace_env.example.sh" ]; then
  . tooling/openclaw_workspace_env.example.sh
fi

# Run the AINL program via the intelligence runner
# This uses the ainl CLI and the OpenClaw bridge to execute the program
python3 scripts/run_intelligence.py auto_tune_ainl_caps "$@"
