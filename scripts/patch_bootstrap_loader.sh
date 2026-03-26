#!/usr/bin/env bash
# Patch OpenClaw host binary to support OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT
# This modifies the workspace loader to automatically use session_context.md when available.
# Idempotent: creates backups and can be re-run safely.

set -euo pipefail

# Determine OpenClaw installation root
OPENCLAW_BIN="${OPENCLAW_BIN:-$(which openclaw 2>/dev/null || echo "/opt/homebrew/bin/openclaw")}"
OPENCLAW_ROOT="$(dirname "$(dirname "$OPENCLAW_BIN")")"
echo "OpenClaw root: $OPENCLAW_ROOT"

# Find the workspace-*.js file (host loader)
LOADER_FILE="$(find "$OPENCLAW_ROOT" -name 'workspace-*.js' -type f | head -n1)"
if [[ -z "$LOADER_FILE" ]]; then
  echo "ERROR: Could not find workspace-*.js under $OPENCLAW_ROOT"
  exit 1
fi
echo "Found loader: $LOADER_FILE"

# Backup
BACKUP="${LOADER_FILE}.bak-$(date +%Y%m%d-%H%M%S)"
cp "$LOADER_FILE" "$BACKUP"
echo "Backup created: $BACKUP"

# Apply the patch: add env-conditional bootstrap loading
# Idempotent: skip if already present
if grep -q "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT" "$LOADER_FILE"; then
  echo "Patch appears already applied. Skipping."
  exit 0
fi

# Use sed to insert after the line defining bootstrapPath.
# Pattern (may need adjustment based on exact source version):
#   const bootstrapPath = path.join(workspaceDir, '.openclaw', 'bootstrap', 'session_context.md');
PATTERN='const bootstrapPath = path\.join(workspaceDir, '\''\.openclaw'\'', '\''bootstrap'\'', '\''session_context\.md'\'')'

if ! grep -qE "$PATTERN" "$LOADER_FILE"; then
  # Try alternative pattern (without path.join, or with different quoting)
  PATTERN_ALT='bootstrapPath.*session_context\.md'
  if grep -qE "$PATTERN_ALT" "$LOADER_FILE"; then
    PATTERN="$PATTERN_ALT"
  else
    echo "ERROR: Could not find bootstrapPath line in $LOADER_FILE"
    echo "The pattern may have changed; please patch manually."
    exit 1
  fi
fi

# Insert a block after the matching line using sed -i (macOS)
# The inserted lines:
#   // AINL v1.2.8: Prefer session_context.md when env flag is set
#   if (process.env.OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT === '1') {
#     try {
#       const ctx = fs.readFileSync(bootstrapPath, 'utf8');
#       if (ctx && ctx.trim().length > 0) {
#         console.log('[AINL] Loading session_context.md (OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1)');
#         return ctx;
#       }
#     } catch (e) {
#       // file missing or unreadable; fall back to normal bootstrap
#     }
#   }
sed -i '' -e "/$PATTERN/a\\
      // AINL v1.2.8: Prefer session_context.md when env flag is set\\
      if (process.env.OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT === '1') {\\
        try {\\
          const ctx = fs.readFileSync(bootstrapPath, 'utf8');\\
          if (ctx && ctx.trim().length > 0) {\\
            console.log('[AINL] Loading session_context.md (OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1)');\\
            return ctx;\\
          }\\
        } catch (e) {\\
          // file missing or unreadable; fall back to normal bootstrap\\
        }\\
      }
" "$LOADER_FILE"

echo "Patch applied."
echo "Patch complete. Verify with: openclaw doctor --non-interactive"
echo "Then restart gateway: openclaw gateway restart"
