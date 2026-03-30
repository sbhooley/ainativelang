# GitHub Discussions — exact posts (title + body)

**Live threads (created March 2026):**

| # | Topic | URL |
|---|--------|-----|
| 14 | Share your first AINL workflow | https://github.com/sbhooley/ainativelang/discussions/14 |
| 15 | LangGraph → AINL: migration experiences | https://github.com/sbhooley/ainativelang/discussions/15 |
| 16 | Enterprise audit use cases with AINL | https://github.com/sbhooley/ainativelang/discussions/16 |
| 13 | Welcome (hub reply links to #14–#16) | https://github.com/sbhooley/ainativelang/discussions/13 |

Use these blocks as the canonical copy for edits or reposts. GitHub Discussions do **not** support tags like issues; **category** replaces that.

**Welcome thread hub reply:** A maintainer reply on [#13](https://github.com/sbhooley/ainativelang/discussions/13) points newcomers to #14–#16.

## Pin #14 as the top discussion (maintainer)

GitHub does **not** expose a public GraphQL `pinDiscussion` mutation (verified March 2026). Pinning is **UI-only**:

1. Open https://github.com/sbhooley/ainativelang/discussions/14
2. In the discussion header, open the **⋯** menu (or use the **Pin** control if shown in your layout).
3. Choose **Pin discussion** — you can pin up to **four** discussions per repository.

Prefer pinning **#14** so “Share your first AINL workflow” stays visible at the top of the Discussions index.

---

## Thread 1 — Share your first AINL workflow

**Suggested category:** Show and tell

**Title**

```
Share your first AINL workflow
```

**Body** (markdown)

```markdown
We're building a library of real `.ainl` patterns — monitoring, digests, chain watchers, MCP bridges — **built by the growing AINL community**.

Reply with:

- What problem you solved (one paragraph)
- Link to a public repo or gist (if you can share)
- Stack notes: OpenClaw, Hermes, bare `ainl run`, emit target, etc.

No workflow is too small. Early examples help the next person ship faster.
```

---

## Thread 2 — LangGraph → AINL migration experiences

**Suggested category:** General

**Title**

```
LangGraph → AINL: migration experiences
```

**Body** (markdown)

```markdown
If you've moved (or experimented with moving) orchestration from **LangGraph** (or similar) to **AINL**, share what worked and what didn't:

- What stayed in Python vs what you expressed in `.ainl`
- Token/cost or determinism wins (rough numbers welcome)
- Gaps or feature requests

See also: [`docs/migration/LANGGRAPH_MIGRATION_GUIDE.md`](https://github.com/sbhooley/ainativelang/blob/main/docs/migration/LANGGRAPH_MIGRATION_GUIDE.md).
```

---

## Thread 3 — Enterprise audit use cases with AINL

**Suggested category:** General

**Title**

```
Enterprise audit use cases with AINL
```

**Body** (markdown)

```markdown
For **security, GRC, and platform** folks: how are you using (or evaluating) AINL for auditability — JSONL tape, policy gates, strict validation in CI?

- Industry / rough context (no secrets)
- Which controls or narratives you're mapping (e.g., change management, monitoring)
- What evidence you wish the project documented better

Pointers: [`docs/enterprise/SOC2_CHECKLIST.md`](https://github.com/sbhooley/ainativelang/blob/main/docs/enterprise/SOC2_CHECKLIST.md), [Validation deep dive](https://ainativelang.com/docs/validation-deep-dive).
```

---

## After posting

URLs are recorded in [`DISCUSSIONS_SEED_TOPICS.md`](DISCUSSIONS_SEED_TOPICS.md). Pin **#14** via the UI (see **Pin #14** above).
