---
name: Submit Workflow (Clawflows-style)
about: Add or update a scheduled workflow as deterministic AINL under examples/ecosystem
title: "[Workflow] "
labels: workflow, ecosystem
---

## Checklist

- [ ] Original Markdown (`WORKFLOW.md` or equivalent) included in this PR **or** link to upstream source
- [ ] Converted `.ainl` produced with `ainl import markdown … --type workflow` (or matches that output)
- [ ] Placed under `examples/ecosystem/clawflows/<slug>/` with `original.md`, `converted.ainl`, and `README.md` (diff / notes vs upstream)
- [ ] Compiles cleanly: `ainl compile examples/ecosystem/clawflows/<slug>/converted.ainl` (or your path)
- [ ] OpenClaw-oriented hooks (`memory` / `queue` / cron) called out in README if relevant

## Description

Describe the workflow, intended schedule, and main steps.

## Upstream source (if any)

Link to the original Clawflows `WORKFLOW.md` or other canonical Markdown.

## Runtime notes

Adapters, strict mode, or execution expectations (if any).
