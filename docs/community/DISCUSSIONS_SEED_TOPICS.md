# GitHub Discussions — seed topics (copy-paste)

Use this file to **seed** the [AINL GitHub Discussions](https://github.com/sbhooley/ainativelang/discussions) forum.

**Ready-to-post bodies:** one file per topic in [`docs/community/discussions/`](discussions/) (title + body blocks). Prefer copying from there to avoid drift.

## Maintainer: create discussions (GitHub UI)

GitHub does not create Discussions from the API without a token in this repo. **Do this once per topic:**

1. Open **https://github.com/sbhooley/ainativelang/discussions**
2. Click **New discussion**
3. Pick a category (**General**, **Ideas**, or **Show and tell** — “Show and tell” fits Topics 1–2 well)
4. Paste the **Title** and **Body** from the matching section below
5. Submit, then optionally pin Topic 1 for visibility

After posting, add the discussion URL next to **Posted:** in each section (optional housekeeping).

---

## Topic 1 — Share your first AINL workflow

**Posted:** _(add GitHub discussion URL after creating)_

**Title:** Share your first AINL workflow

**Body:**

We’re building a library of real `.ainl` patterns — monitoring, digests, chain watchers, MCP bridges — **built by the growing AINL community**.

Reply with:

- What problem you solved (one paragraph)
- Link to a public repo or gist (if you can share)
- Stack notes: OpenClaw, Hermes, bare `ainl run`, emit target, etc.

No workflow is too small. Early examples help the next person ship faster.

---

## Topic 2 — LangGraph migration experiences

**Posted:** _(add GitHub discussion URL after creating)_

**Title:** LangGraph → AINL: migration experiences

**Body:**

If you’ve moved (or experimented with moving) orchestration from **LangGraph** (or similar) to **AINL**, share what worked and what didn’t:

- What stayed in Python vs what you expressed in `.ainl`
- Token/cost or determinism wins (rough numbers welcome)
- Gaps or feature requests

See also: [`docs/migration/LANGGRAPH_MIGRATION_GUIDE.md`](https://github.com/sbhooley/ainativelang/blob/main/docs/migration/LANGGRAPH_MIGRATION_GUIDE.md).

---

## Topic 3 — Enterprise audit use cases

**Posted:** _(add GitHub discussion URL after creating)_

**Title:** Enterprise audit & compliance use cases

**Body:**

For **security, GRC, and platform** folks: how are you using (or evaluating) AINL for auditability — JSONL tape, policy gates, strict validation in CI?

- Industry / rough context (no secrets)
- Which controls or narratives you’re mapping (e.g., change management, monitoring)
- What evidence you wish the project documented better

Pointers: [`docs/enterprise/SOC2_CHECKLIST.md`](https://github.com/sbhooley/ainativelang/blob/main/docs/enterprise/SOC2_CHECKLIST.md), [validation deep dive](https://ainativelang.com/docs/validation-deep-dive).

---

## CLI alternative (authenticated)

If you use the GitHub CLI with `discussions` write access:

```bash
# Requires: gh auth login with repo scope, and discussions enabled on the repo
gh discussion create --repo sbhooley/ainativelang \
  --title "Share your first AINL workflow" \
  --body-file /dev/stdin <<'EOF'
(paste body here)
EOF
```

Repeat per topic. Category flags depend on `gh` version; the web UI is the most reliable path.
