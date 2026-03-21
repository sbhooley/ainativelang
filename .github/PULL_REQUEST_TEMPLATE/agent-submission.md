---
name: Submit Agent (Agency-Agents-style)
about: Add or update a personality / agent spec as deterministic AINL under examples/ecosystem
title: "[Agent] "
labels: agent, ecosystem
---

## Checklist

- [ ] Source Markdown included **or** link to upstream Agency-Agents (or other) personality file
- [ ] Converted `.ainl` from `ainl import markdown … --type agent` (with `--personality` / `--generate-soul` if used)
- [ ] Placed under `examples/ecosystem/agency-agents/<slug>/` with `original.md`, `converted.ainl`, and `README.md`
- [ ] Compiles cleanly: `ainl compile …/converted.ainl`
- [ ] Optional sidecars (`SOUL.md`, `IDENTITY.md`) described in PR if applicable

## Description

Role, mission, tone, and how this agent should be used.

## Upstream source (if any)

Link to the original `.md` in Agency-Agents or elsewhere.

## Frontmatter / rules

Summarize critical rules, deliverables, or workflow hints the graph encodes.
