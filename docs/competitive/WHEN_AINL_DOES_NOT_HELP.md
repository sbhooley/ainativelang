# When AINL does not help — moved

> **This page has been consolidated.** The full anti-pitch (the three baselines, the four workload patterns where AINL adds little or nothing, the decision tree, and the honest reviewer Q&A) now lives in the canonical ICP doc:
>
> **→ [`docs/WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md)**
>
> The URL of this file is preserved as a pointer so external links and search-engine results still resolve. All previously-existing content has been merged into the canonical page; nothing has been deleted.

## What was here

This page used to be the standalone "anti-pitch" — the document that let operators, reviewers, and community skeptics self-select **out** of AINL without a sales conversation. Specifically:

- The **three-baseline framework** (LLM-first, hand-optimized, pure-deterministic) and the typical AINL win against each
- The four workload patterns where AINL adds little or nothing (pure-deterministic automation, judgment-heavy semantic pipelines, already-gated triage, low-volume classifiers)
- The "what AINL is still good for when tokens aren't the play" table
- The 30-second decision tree
- The fair-questions reviewer Q&A

All of it is preserved verbatim or strengthened in [`docs/WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md), which is now the **single source of truth** for AINL's ICP and anti-ICP. The README's [60-second filter](../../README.md#is-ainl-for-you-60-second-filter) is the teaser; the canonical doc is the long answer.

## Why we consolidated

Tracker entry: [`docs/competitive/LONG_TERM_FIXES_TRACKER.md`](LONG_TERM_FIXES_TRACKER.md) **T3.8** — *Create canonical `docs/WHO_IS_THIS_FOR.md` merging `WHEN_AINL_DOES_NOT_HELP` + `ARMARAOS_GTM` + open-core/sales docs; deprecate overlapping docs with pointers. **Acceptance:** one source of truth; sales/marketing copy points here.*

Having two pages cover the same ICP material made it easy for one to drift out of sync with the other and for new readers to get inconsistent answers depending on where they landed. One canonical page, one set of words.

## Related

- **[`../WHO_IS_THIS_FOR.md`](../WHO_IS_THIS_FOR.md)** — canonical ICP
- [`ARMARAOS_GTM.md`](ARMARAOS_GTM.md) — ArmaraOS-specific product positioning (kept; covers stack diagram, install paths, persona-to-message mapping beyond ICP)
- [`COMPETITIVE_MESSAGING.md`](COMPETITIVE_MESSAGING.md) — persona-specific messaging
- [`../CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) — what we'll defend with measured artifacts
- [`VS_HAND_WRITTEN_RUNNER.md`](VS_HAND_WRITTEN_RUNNER.md) — measured AINL vs hand-written Python comparison
- [`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md) — committed operator case blocks
