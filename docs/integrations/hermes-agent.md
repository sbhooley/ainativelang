---
title: Hermes Agent — Official First-Class Support
description: Deterministic AINL graphs + Hermes closed learning loop + Honcho memory.
order: 9
---

# Hermes Agent — Official First-Class Support

Upstream host: **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (Nous Research).

**PyPI:** `ainativelang` **v1.7.1**.

AINL ships **official, first-class Hermes Agent support**: compile-once deterministic graphs (AINL) paired with Hermes’ **closed learning loop** and persistent memory via **Honcho**.

**Gold-standard combo:**

- **AINL**: strict, auditable graphs (compile → canonical IR → deterministic execution)
- **Hermes Agent**: skill-native agent runtime + self-improvement loop
- **Honcho**: durable memory surface the loop can write to and query

## One-command quickstart

```bash
pip install 'ainativelang[mcp]' && ainl hermes-install
```

Then emit a Hermes skill bundle:

```bash
ainl compile workflow.ainl --strict --emit hermes-skill -o ~/.hermes/skills/ainl-imports/my-skill/
```

## Full guide

Read the complete integration guide: [`docs/HERMES_INTEGRATION.md`](../HERMES_INTEGRATION.md).

