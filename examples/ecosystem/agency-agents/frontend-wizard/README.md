# frontend-wizard

Upstream: [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) `engineering/engineering-frontend-developer.md` (example alias: frontend-wizard)

## Files

- `original.md` — source Markdown from the ecosystem repo.
- `converted.ainl` — deterministic AINL graph (parsed).

## Notes

This folder is a **deterministic AINL version** of the prose workflow/agent spec — structured graph, explicit cron/steps or gates, and predictable control flow for **100% reliability** at compile/run time (vs free-form Markdown prompts).

Diff vs upstream: headings and lists become `S core cron`, `Call` steps, `If` gates, and optional `memory` / `queue` bridge hooks instead of narrative instructions only.

**frontend-wizard** maps to `engineering-frontend-developer.md` in Agency-Agents.
