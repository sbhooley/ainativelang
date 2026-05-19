# Template Marketplace Submission Guide

> **Status (as of 2026-05-19): planned community feature, not yet shipped.**
> The template marketplace UI, contributor reward payouts, vesting, and review process described below are **aspirational** — they reflect the originally-published design goal and **have not yet launched**. We keep this document visible (rather than deleting older drafts) because git history is public and readers deserve to see both the goal and the current gap. The $AINL token itself exists on Solana (mint `56hrCR3n7danhHNjWaU4VeUHpE1eRE9VRBWpHRPKpump`); live token metrics, treasury status, and feature shipping status are in [`tooling/token_status.json`](../../../../tooling/token_status.json). Enterprise customers do **not** need to hold $AINL — see [`docs/enterprise/ENTERPRISE_FAQ.md`](../../../enterprise/ENTERPRISE_FAQ.md).
>
> Until the marketplace ships, the actionable path is: **author great templates as PRs against the `examples/` directory** — those get reviewed and merged, public attribution lands in [`CONTRIBUTORS.md`](../../../../CONTRIBUTORS.md), and you carry first claim on any future reward backfill if the program below ships.

How to create, document, and submit AINL templates for the community marketplace.

---

## What Makes a Good Template?

A template is a reusable AINL graph that solves a common problem. Good templates:
- Configurable (parameters exposed as inputs)
- Well-documented
- Production-ready (error handling, validation)
- Focused (solves one problem)
- Tested

---

## Template Structure

```
my-template/
├── template.ainl
├── README.md              (required)
├── config.example.yaml
├── tests/
│   ├── test_integration.py
│   └── fixtures/
├── screenshots/           (optional)
└── LICENSE                (Apache 2.0 or MIT)
```

---

## Token Rewards (planned schedule — not yet active)

> **Status: planned.** This is the originally-published reward schedule from the v1.0 token utility design. Payouts have **not yet begun**; the treasury and distribution mechanism are still in design. Numbers below are aspirational targets, kept visible for transparency. If and when payouts start, contributors of templates merged before the program launches will be eligible for backfill consideration at the program's discretion.

| Template Type | Base Reward (planned) | Bonus Conditions (planned) |
|---------------|------------------------|------------------------------|
| Basic (1-2 nodes) | 5,000 $AINL | – |
| Standard (moderate complexity) | 10,000 $AINL | +2,500 if >100 stars in 30d |
| Advanced (production-ready) | 20,000 $AINL | +5,000 if adopted by enterprise |
| Enterprise (compliance patterns) | 50,000 $AINL | +10,000 if used in paid support |

**Planned vesting:** 25% immediate, 25% each quarter for 1 year. This vesting schedule will only apply once payouts begin; nothing is being distributed today.

---

## Submission Process (current — not the planned marketplace)

Until the marketplace ships, contributions go through standard GitHub PR review:

1. Fork [`sbhooley/ainativelang`](https://github.com/sbhooley/ainativelang); add your template under `examples/`
2. Open a PR against `main`; ensure `ainl validate <file> --strict` passes
3. Review by a maintainer (Steven Hooley, Terrance Schonleber, Kobe Welker — see [`CONTRIBUTORS.md`](../../../../CONTRIBUTORS.md))
4. On merge: public attribution, optional spotlight in `docs/community/SPOTLIGHTS.md`, eligibility for any future reward backfill if the program above launches

The "GitHub Discussion + community gallery + author rewarded" flow is the **planned** future shape; the PR-against-`examples/` flow is what's live today.

---

## Common Rejection Reasons

- Hardcoded API keys
- Graph doesn't validate (`ainl validate --strict`)
- Missing error handling
- No test cases
- Unclear documentation
- Incompatible license

See individual pattern files in this directory for complete examples.

---

**Share your AINL expertise — get merged, get credit in [`CONTRIBUTORS.md`](../../../../CONTRIBUTORS.md), and stay first in line for any reward backfill if the planned program above launches.**
