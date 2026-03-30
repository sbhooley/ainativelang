# GitHub Discussions — exact posts (title + body)

Use these blocks to create the first three threads in **[Discussions](https://github.com/sbhooley/ainativelang/discussions)**. Pick a **category** when posting (suggestions below). GitHub Discussions do **not** support tags like issues; category replaces that.

**Repo check:** If `https://github.com/sbhooley/ainativelang/discussions` shows Discussions as disabled, turn them on: **Settings → General → Features → Discussions**. The GraphQL field `hasDiscussionsEnabled` must be true before API or `gh` can create threads.

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

Add the discussion URLs to [`DISCUSSIONS_SEED_TOPICS.md`](DISCUSSIONS_SEED_TOPICS.md) under **Posted:** for each topic, or pin Thread 1 for visibility.
