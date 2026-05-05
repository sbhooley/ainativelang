# Cursor → graph memory bridge (AINL) — plan & tracker

**Purpose:** Reproducible path for Cursor users to turn local chat artifacts into **governed, graph-native memory** (AINL strict pipelines + optional ArmaraOS inbox), with a **defensible** position vs existing Cursor history tools.

**How to use this doc:** Treat checkboxes as the live backlog. Update dates and status as phases land. Implementation artifacts target this repo (`examples/`, `scripts/`, `docs/integrations/`).

**Last updated:** 2026-05-05

---

## 1. North-star positioning

We do **not** aim to beat every competitor on every axis with `.ainl` alone. We **own**:

- **Governance:** redaction and policy as **strict-valid** graphs.
- **Automation:** incremental, checkpointed pipelines (cron, hooks, ArmaraOS scheduled `ainl`).
- **Downstream memory:** `ainl_graph_memory` / ArmaraOS **`ainl_graph_memory_inbox.json`** (see ArmaraOS [graph-memory-sync](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory-sync.md)), not only Markdown dumps.

**One-line pitch:** *Cursor history tools give **access**; AINL gives **governance, distillation, and durable graph memory** — reproducible and reviewable.*

---

## 2. Competitive landscape (honest)

| Axis | Existing solutions | Our bet |
|------|-------------------|--------|
| In-editor auto-save | [SpecStory](https://docs.specstory.com/integrations/cursor) (extension → `.specstory/history/`) | No VS Code extension in this plan; **document co-install** or “watch exported folder.” |
| Fast local search / backup / SQLite | [cursor-history-mcp](https://github.com/S2thend/cursor-history-mcp), [cursor-history](https://github.com/S2thend/cursor-history) | **Do not reimplement SQLite grep in AINL for v1.** Pair or consume exports; our value is **downstream**. |
| Browse/search UI | [cursor-chat-browser](https://github.com/thomas-pedersen/cursor-chat-browser) | Out of scope unless a separate subproject; **link** as alternative. |
| Multi-format CLI export | [cursor-session](https://github.com/iksnae/cursor-session), older exporters | **Interoperate:** ingest JSONL/MD they produce. |
| Policy + graph automation | Mostly not addressed | **Lead here:** AINL + optional ArmaraOS. |

---

## 3. Reproducibility contract (every Cursor user)

- [ ] **Inputs documented:** `~/.cursor/projects/<id>/agent-transcripts/**/*.jsonl`; optional `state.vscdb` / SpecStory paths (cite community sources in doc; no flaky promises).
- [ ] **Single happy path:** `ainl validate --strict` + `ainl run` on pipeline graph(s); optional **bulk backfill** script clearly labeled (Python or other), not the default ongoing path.
- [ ] **Config:** env + small JSON — `CURSOR_HOME` / globs, checkpoint path, redaction profile, ArmaraOS `ARMARAOS_AGENT_ID` / home. No hard-coded machine paths in committed graphs.
- [ ] **Triggers:** Cursor hook template + cron / ArmaraOS scheduled `ainl` + “manual daily” documented minimum.
- [ ] **Safety:** redaction **on by default**; no silent promotion to personal `MEMORY.md` without review (align with OpenClaw workspace **INTEGRATION.md** capture → promote story).

---

## 4. Architecture (target)

```text
Sources (JSONL, optional vscdb export, optional SpecStory MD)
    → optional normalize/checkpoint (bulk or companion)
    → AINL: redact → distill (optional llm) → graph / inbox write
    → consumers: ArmaraOS graph memory, workspace digest, optional MCP resource
```

- **Ongoing:** bounded per run — mtime + checkpoint + caps (steps/time/bytes).
- **Marketing:** middle stages are **strict-valid `.ainl`**.

---

## 5. Deliverables (this repo)

| Item | Status |
|------|--------|
| `examples/compact/cursor_memory_redact.ainl` — strict-valid redactor + limits | [ ] |
| `examples/compact/cursor_memory_ingest_incremental.ainl` — fs + cache + checkpoint | [ ] |
| `examples/compact/cursor_memory_distill.ainl` — optional `llm.*`, dry-run frame for CI | [ ] |
| `docs/integrations/CURSOR_GRAPH_MEMORY.md` — this plan (sources, threats, pairing w/ other tools) | [x] |
| `scripts/cursor_memory_*` — optional bulk checkpoint/export (if needed) | [ ] |
| `tooling/artifact_profiles.json` — add new examples to `strict-valid` when clean | [ ] |
| Tests / golden strings for redaction | [ ] |

---

## 6. Phased roadmap

- [ ] **P0 — Trust:** Redactor graph + this doc + golden redaction tests; `ainl validate --strict` clean.
- [ ] **P1 — Live incremental:** Checkpointed ingest; second run is delta-only; caps enforced.
- [ ] **P2 — Memory write:** Verified writes to GraphStore and/or ArmaraOS inbox (`schema_version`, scope tags per bridge contract).
- [ ] **P3 — Distillation:** Optional summarization / entity extraction behind flag; offline path skips LLM.
- [ ] **P4 — Ecosystem parity:** **Either** documented pairing with **cursor-history-mcp** **or** minimal list/search companion — pick one so raw search is not “slow grep in IR.”

---

## 7. Marketing bullets

- **vs SpecStory:** cross-tool automation + memory semantics + ArmaraOS; not fighting their in-editor UX.
- **vs cursor-history-mcp:** they win raw DB access; we win **policy-as-code** + **graph** + **scheduled** composition.
- **AINL:** strict graphs are **reviewable** automation with explicit adapter grants — strong for teams.

---

## 8. Risks (keep in doc)

- Cursor **storage format changes** — versioned inputs, fixture samples in tests, changelog notes.
- **Redaction:** position as **best-effort**; compliance needs additional tooling.
- **Runtime limits:** recursion/step/time caps + checkpointing mandatory for production-shaped use.

---

## 9. References

- ArmaraOS: graph memory hub — [graph-memory.md](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory.md), inbox — [graph-memory-sync.md](https://github.com/sbhooley/armaraos/blob/main/docs/graph-memory-sync.md).
- AINL: **`ainl_graph_memory`** — `docs/adapters/AINL_GRAPH_MEMORY.md`; strict authoring — `AGENTS.md`.
- OpenClaw workspace: capture vs promotion — `INTEGRATION.md` (sibling workspace root).

---

## 10. Changelog

| Date | Note |
|------|------|
| 2026-05-05 | Initial plan + tracker committed. |
