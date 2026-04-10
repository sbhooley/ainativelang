# Upstream Issue: Make OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT a native config option

**Project:** OpenClaw
**Component:** Gateway / Session Bootstrapping
**Suggested label:** enhancement, configuration

---

## Problem

OpenClaw now supports `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` natively in newer builds. However, teams on older builds still report confusion because historical setup guides required a manual host patch and those instructions are still copy-pasted in some environments.

Without native support (older builds), the system falls back to loading full `MEMORY.md` on every session, causing frequent context max-outs for larger workspaces.

Manual patching is:
- **Error-prone**: users must locate the correct file and apply exact code changes.
- **Non-persistent**: `openclaw upgrade` overwrites the host binary, wiping the patch.
- **Poor discoverability**: the required step is easy to miss in installation docs, leading to failed setups.

For smooth adoption of AINL-based token optimizations, this behavior should be native (now true on current builds) and documented as version-gated for older installs.

---

## Proposed Solution

Add native support for `OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` (or a similarly named config key) in OpenClaw’s gateway configuration. When enabled (e.g., `"bootstrap": { "preferSessionContext": true }` or via env var), the gateway automatically loads `.openclaw/bootstrap/session_context.md` if it exists and is non-empty, bypassing the full `MEMORY.md` load.

This would:
- Eliminate the need for the host binary patch script.
- Make AINL token optimizations truly turnkey.
- Persist across upgrades (as part of user config).
- Reduce support friction.

---

## Implementation Sketch

In the gateway’s session initialization code (likely the workspace loader), there is already a hook to generate `session_context.md` via AINL. Add a simple conditional:

```js
// Existing: const bootstrapPath = path.join(workspaceDir, '.openclaw', 'bootstrap', 'session_context.md');
// After reading the main MEMORY.md or before building context:
if (process.env.OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT === '1') {
  try {
    const ctx = fs.readFileSync(bootstrapPath, 'utf8');
    if (ctx && ctx.trim().length > 0) {
      console.log('[AINL] Using session_context.md (OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT=1)');
      return ctx; // or inject into context builder
    }
  } catch (e) {
    // no session_context.md; continue with normal bootstrap
  }
}
```

Alternatively, read from `openclaw.json` config (e.g., `config.get('bootstrap.preferSessionContext')`) instead of an env var for clarity.

---

## Context for Maintainers

- AINL **v1.2.8+** includes a wrapper `token_aware_startup_context.ainl` that generates the compact context file on a schedule (e.g., every 15 minutes); **current PyPI: v1.5.0**.
- The wrapper and bridge integration are documented in `AI_Native_Lang/docs/openclaw/TOKEN_AWARE_STARTUP_CONTEXT.md`.
- Current recommendation: use native support on recent OpenClaw builds and avoid patch scripts unless running an older version.
- Making this native removes a significant barrier to adoption and aligns with OpenClaw’s philosophy of user-friendly AI integration.

---

## References

- AINL OpenClaw unified integration: `AI_Native_Lang/docs/ainl_openclaw_unified_integration.md` (section: Token-aware startup context optimization)
- Legacy patch script (older OpenClaw only): `AI_Native_Lang/scripts/patch_bootstrap_loader.sh`
- Wrapper: `AI_Native_Lang/openclaw/bridge/wrappers/token_aware_startup_context.ainl`
- Integration docs: `AI_Native_Lang/docs/openclaw/TOKEN_AWARE_STARTUP_CONTEXT.md`

---

**Suggested commit message (if submitting PR):**
```
feat: support OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT natively

Add native check in workspace loader to prefer session_context.md when
the env flag is set. This enables AINL token-aware startup to work
without manual host binary patches, improving upgrade persistence and
setup simplicity.

Closes #XXXX
```