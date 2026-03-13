# OpenClaw implementation preflight

**Purpose:** Require a structured check before selecting or implementing work in this repo so that bots (and humans) are less likely to duplicate work, rely on stale assumptions, misread adapter/API semantics, or propose plans without checking current repo state.

**Status:** Repo-integrated discipline. Not an execution engine, policy engine, or planner. Discoverable via `docs/BOT_ONBOARDING.md` and `tooling/bot_bootstrap.json`.

---

## When to use it

- **Before** choosing a task to implement.
- **Before** writing code, tests, or docs that touch OpenClaw/extension surfaces, adapters, monitors, or memory.
- **Before** proposing an implementation plan.
- **Whenever** you are a bot or agent newly exposed to this repo and about to do implementation work.

If you only read docs or run existing scripts with no code changes, you may skip the full preflight; for any **implementation** work, the preflight is required.

---

## Required preflight steps

Before implementing, you **must**:

1. **Inspect relevant current files first** — Open the actual files (source, tests, adapter code, capability metadata) that your task touches. Do not rely on memory or summaries.
2. **Name the exact files inspected** — List paths. This grounds the plan in the current repo.
3. **Confirm the task is not already implemented** — Search the codebase and examples for existing behavior. If the feature or fix already exists, do not re-implement it.
4. **Confirm relevant adapter/function semantics from code** — Read the adapter implementation, capability registry, or runtime code that defines the verbs/APIs you will use. Do not infer semantics from names or documentation alone.
5. **Distinguish confirmed facts from assumptions** — Label what you read in the repo as fact; label what you inferred or assumed as assumption.
6. **Explicitly state any assumption that could break the plan** — If your plan depends on something you did not verify (e.g. payload shape, return format, namespace rules), state it. If that assumption is wrong, the implementation may fail.
7. **Prefer the smallest practical change** — Prefer add/extend over refactor/replace. Do not broaden scope beyond the chosen task.
8. **Avoid inferring payload access from list/enumeration APIs unless code proves it** — For example, `memory.list` returns metadata (e.g. `record_id`, `updated_at`); do not assume it returns full payloads unless you verified that in the adapter or contract.
9. **Provide a validation plan before coding** — State how you will verify the change (compile, run, test command, or manual check).
10. **Choose a different task if the chosen one is already implemented** — If you discover the work is done, pick another task or confirm with the user instead of redoing it.

---

## Required output structure before coding

Emit the following **before** writing implementation code. This forces grounding and reduces duplicate or misguided work.

| Section | Content |
|--------|---------|
| **Chosen task** | One clear sentence describing what you will implement or fix. |
| **Why it is not duplicate work** | What you checked (files, search terms) and why the task is not already done. |
| **Files inspected** | Exact paths of repo files you opened and used to ground the plan. |
| **Current behavior found** | Brief summary of what the inspected code/docs do today (relevant to your task). |
| **Verified semantics** | Adapter verbs, APIs, or contracts you read in code/registry and their actual behavior (e.g. `memory.list` returns `items` with metadata, not payloads). |
| **Assumptions** | Any assumption you are making that could break the plan if wrong. If none, say “None that could break the plan.” |
| **Smallest viable implementation** | What you will add or change (files, approximate changes). Keep scope minimal. |
| **Validation plan** | How you will verify the change (e.g. “Run `python3 scripts/validate_ainl.py demo/monitor_system.lang` and confirm exit 0”). |

---

## Grounding rules

- **Code over memory** — Use the current codebase and capability metadata as the source of truth. Do not rely on training data or prior summaries for adapter signatures, return shapes, or namespace rules.
- **Explicit over inferred** — If a contract or doc does not state that an API returns payloads (or a specific field), do not assume it does until you see it in the implementation or schema.
- **List what you read** — Naming the files you inspected makes it possible to check that the plan is grounded and to correct course if the wrong file was used.

---

## Duplicate-work prevention

- Before implementing, search for existing behavior: relevant examples, tests, adapter code, or docs that already implement or document the same capability.
- If you find the feature or fix already present, **do not** re-implement it. Either choose another task or report that the work is done and suggest a follow-up (e.g. docs, test coverage, or a different improvement).
- In the preflight output, under “Why it is not duplicate work,” cite what you searched and what you found.

---

## Adapter / API verification rules

- **Adapter verbs** — Confirm the verb name, arguments, and return shape from the adapter implementation (e.g. `runtime/adapters/memory.py`) or the capability registry (`tooling/capabilities.json`, `tooling/tool_api_v2.tools.json`). Do not assume from the verb name alone.
- **List vs get** — Enumeration/list APIs may return only keys or metadata. Verify whether payloads are included by reading the adapter or contract (e.g. `docs/MEMORY_CONTRACT.md`).
- **Namespaces and record kinds** — Use the contract or schema for allowed values (e.g. memory namespace whitelist, record_kind conventions). Do not invent new namespaces or kinds without checking the contract.

---

## Assumption-handling rules

- **Label assumptions** — Clearly separate “confirmed from code/docs” from “assumed.”
- **State breakage risk** — For each assumption, note whether it could break the plan if wrong. If it could, state it explicitly so the user or a later step can correct it.
- **Prefer verifying** — If an assumption is easy to verify (e.g. by opening one file), verify it instead of assuming.

---

## Smallest-change rule

- Prefer **add** over **extend** over **refactor** over **replace**.
- Do not broaden the task (e.g. “add memory retention report” should not become “redesign all memory tooling”).
- Do not combine unrelated roadmap items unless the user asked for that.
- In the preflight, describe the **smallest viable implementation** that satisfies the task.

---

## Validation-planning rule

- Before coding, state **how** you will validate the change.
- Examples: run a specific script (`scripts/validate_ainl.py`, `scripts/memory_retention_report.py`), run tests, compile and run one example, or compare output to an expected shape.
- If the task has no existing test, say how you will confirm correctness (e.g. manual run, diff output).

---

## Summary

Complete the preflight steps, emit the required output structure, then proceed to implementation. If at any step you find the task is already done or the assumptions are too risky, choose a different task or ask for clarification instead of implementing on stale or uncertain grounds.
