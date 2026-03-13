# AI Consultant Reports

This directory collects formal analysis reports from AI consultants who have evaluated or extended AINL for specific integrations or use cases. These reports serve as continuity artifacts for future AI agents and human maintainers.

## Reports

| Consultant | Date | Topic | Status |
|------------|------|-------|--------|
| **Apollo** (OpenClaw Assistant) | 2026-03-03 | OpenClaw integration assessment (adapters already live) + performance impact & adoption rationale | ✅ Complete — includes benchmarks and why AINL was adopted — see `AI_CONSULTANT_REPORT_APOLLO.md` |
| *[future reports added here]* | | | |

---

## Purpose

- **Analysis**: Deep dive on AINL's suitability for a given integration
- **Recommendations**: Clear actionable next steps
- **Developer guide**: Patterns, examples, and tooling for AI agents
- **Continuity**: Enable new AI agents to pick up work without context loss

**Agents implementing from these reports:** Follow `docs/BOT_ONBOARDING.md` and `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` before coding (see `tooling/bot_bootstrap.json`).

## Template

All consultants should use `AI_CONSULTANT_REPORT_TEMPLATE.md` as a starting point. The template includes:

- Executive Summary
- Project Health & Maturity
- Architecture Deep Dive
- Concrete Usage Examples
- Use Case & Reasoning
- Developer Guide for AI Agents
- Recommendations & Next Steps
- Conclusion
- Appendices (file references, commands, quality gates)

## Location

Save reports as `AI_CONSULTANT_REPORT_<CONSULTANT_ID>.md` in the repository root.

## Cross-Reference

Also see:
- `docs/AI_AGENT_CONTINUITY.md` — session handoff protocol
- `docs/CONTRIBUTING_AI_AGENTS.md` — contribution guidelines
- `docs/TRAINING_ALIGNMENT_RUNBOOK.md` — quality gates and evaluation
