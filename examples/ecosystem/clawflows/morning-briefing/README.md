# morning-briefing

Upstream: [nikilster/clawflows](https://github.com/nikilster/clawflows) `morning-journal` (example alias: morning-briefing)

## Files

- `original.md` — source Markdown from the ecosystem repo.
- `converted.ainl` — deterministic AINL graph (parsed).

## Notes

This folder is a **deterministic AINL version** of the prose workflow/agent spec — structured graph, explicit cron/steps or gates, and predictable control flow for **100% reliability** at compile/run time (vs free-form Markdown prompts).

Diff vs upstream: headings and lists become `S core cron`, `Call` steps, `If` gates, and optional `memory` / `queue` bridge hooks instead of narrative instructions only.

**morning-briefing** here mirrors Clawflows `morning-journal` (same ritual, repo name differs for this example layout).
