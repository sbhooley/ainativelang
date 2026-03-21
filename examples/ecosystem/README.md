# Ecosystem templates

Curated **Markdown → AINL** examples that mirror real community workflows and agent specs:

- **`clawflows/morning-briefing/`** — deterministic port of [Clawflows](https://github.com/nikilster/clawflows) `morning-journal` (alias name for this layout).
- **`agency-agents/frontend-wizard/`** — deterministic port of [Agency-Agents](https://github.com/msitarzewski/agency-agents) `engineering-frontend-developer.md`.

Each folder contains `original.md`, `converted.ainl`, and a short `README.md`.

**Examples in `examples/ecosystem/` are kept fresh via weekly auto-sync from upstream Clawflows & Agency-Agents repos** — see [`.github/workflows/sync-ecosystem.yml`](../../.github/workflows/sync-ecosystem.yml) in this repository.

Refresh the broader sample set from upstream (network required):

```bash
ainl import clawflows
ainl import agency-agents
```
