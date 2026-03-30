# Template Marketplace Submission Guide

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

## Token Rewards

| Template Type | Base Reward | Bonus Conditions |
|---------------|-------------|------------------|
| Basic (1-2 nodes) | 5,000 $AINL | – |
| Standard (moderate complexity) | 10,000 $AINL | +2,500 if >100 stars in 30d |
| Advanced (production-ready) | 20,000 $AINL | +5,000 if adopted by enterprise |
| Enterprise (compliance patterns) | 50,000 $AINL | +10,000 if used in paid support |

Vesting: 25% immediate, 25% each quarter for 1 year.

---

## Submission Process

1. Create GitHub repository (your own or ainl-templates org)
2. Submit via GitHub Discussion (category: Template Submissions)
3. Review by community + core team (within 7 days)
4. If approved, listed in official gallery + author rewarded

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

**Share your AINL expertise, earn tokens, help the community.**
