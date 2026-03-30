# SOC 2 alignment checklist (AINL)

This document helps security and GRC teams map AINL deployments to common **SOC 2 (Trust Services Criteria)** expectations. It is **not legal or compliance advice**. Final control design, evidence collection, and auditor sign-off are your organization’s responsibility.

## Purpose

- Give security and GRC teams a structured starting point when AINL sits inside the control boundary.
- Tie **product behaviors** (policy gates, execution tape, compiler validation) to audit-friendly language.
- Complement the technical detail in [`docs/validation-deep-dive.md`](../validation-deep-dive.md).

## Hosted runner and support

For SLA-backed execution, priority support, or managed runner options, see **[COMMERCIAL.md](../../COMMERCIAL.md)** and your order form. Open-source AINL remains the reference compiler and runtime; commercial offerings address operational and support expectations that auditors often ask about for production workloads.

---

## Control mapping (high level)

| TSC area | Typical control theme | How AINL helps (product / design) | Your environment completes |
|----------|----------------------|-------------------------------------|-----------------------------|
| **CC6.1** — logical access | Restrict who can change workflows and what side effects are allowed | **Policy gates** and **capability boundaries** on adapters (e.g., email, HTTP, secrets, chain RPC) limit what compiled graphs can do per deploy; graphs are explicit, not prompt-hidden | IdP, RBAC on repos, secrets store, production promote process |
| **CC6.6** — encryption / credentials | Protect credentials and sensitive data in transit and at rest | Adapters integrate with your configured stores; **no hidden tool calls** — effects are declared in the graph | TLS, KMS, vault policies, key rotation |
| **CC7.2** — monitoring | Detect and respond to security events and anomalies | **JSONL execution tape** records step-level execution for incident review; reachability and strict diagnostics reduce “silent wrong branch” failures | SIEM forwarding, alerting, log retention, runbook |
| **CC8.1** — change management | Changes are authorized, tested, and traceable | **Strict compiler** (`ainl check --strict`) and **CI gates** treat `.ainl` / graph IR as versioned artifacts; diffs are reviewable | Git policy, PR review, deployment pipeline |
| **A1** — availability (optional) | Resilience of service commitments | Deterministic runtime behavior and explicit control flow aid predictable operations; **hosted / commercial** options may add SLAs | Infra redundancy, backups, DR |

---

## Example: email-escalator workflow and CC6.1 / CC7.2

**Scenario:** A monitoring workflow (see [`examples/monitor_escalation.ainl`](../../examples/monitor_escalation.ainl) and the [OpenClaw email monitor](https://github.com/sbhooley/ainativelang/blob/main/openclaw/bridge/wrappers/email_monitor.ainl)) checks a signal (e.g., volume threshold) and escalates through **policy-gated** channels.

| Criterion | Mapping |
|-----------|---------|
| **CC6.1 (logical access)** | The graph declares which adapters run and under which gates. Escalation paths are **not** improvised by an LLM at runtime — access to “send mail / notify” is encoded in the compiled workflow and your deployment policy. Reviewers can answer *who can change the graph* via your Git and CI process. |
| **CC7.2 (monitoring)** | Running with **JSONL execution tape** (`ainl run … --trace-jsonl …`) produces a chronological record of node execution. For investigations, teams can correlate “what the workflow did” with **replay-oriented analysis** instead of reconstructing intent from chat transcripts. Pair tape retention and access control with your log management controls. |

**Evidence ideas (illustrative):** exported trace files for test runs, CI output from `ainl check --strict`, change tickets linking PRs to promoted graph versions, and screenshots or queries from your SIEM if you forward structured logs.

---

## Production tape replay example

The repository includes a **self-contained, core-only** workflow intended for audit narratives and dry runs: [`examples/enterprise/audit-log-demo.ainl`](https://github.com/sbhooley/ainativelang/blob/main/examples/enterprise/audit-log-demo.ainl). It models a small **monitoring slice** with explicit **policy thresholds** (latency and error-rate stand-ins), **explicit branches** (`within_policy` vs `policy_violation`), and comments mapping behavior to **CC7.2** (tape as monitoring evidence) and **CC8.1** (versioned graph + strict checks).

**How to capture and replay evidence**

1. From the repo root, validate the graph:  
   `uv run ainl check examples/enterprise/audit-log-demo.ainl --strict`
2. Run once and write a JSONL execution tape:  
   `uv run ainl run examples/enterprise/audit-log-demo.ainl --trace-jsonl audit_demo.tape.jsonl`
3. For auditor review, retain the **`.ainl` revision** (commit SHA), the **strict check output**, and the **tape file(s)** together. Re-running the same graph with the same inputs reproduces the branch outcome; the tape lists node-level steps in order.

This does **not** replace your SIEM, change tickets, or control testing — it gives a **concrete, inspectable artifact** that ties product behavior (policy gates + tape) to common SOC 2 discussion points.

---

## Next steps for your audit pack

1. Map each row above to your actual IdP, secrets, SIEM, and change tickets.
2. Reference [`docs/validation-deep-dive.md`](../validation-deep-dive.md) for reachability, strict diagnostics, and tape semantics.
3. Replace marketing language with **your** control narratives before external “certification” claims.
4. Involve counsel or a SOC 2 advisor before customer-facing compliance statements.

## Related links

- [Validation deep dive](../validation-deep-dive.md)
- [COMMERCIAL.md](../../COMMERCIAL.md) — hosted runner and support
- [Community spotlights](../community/SPOTLIGHTS.md) — real workflows (e.g., monitoring, cost reports)
- [Production tape replay example](#production-tape-replay-example) — `examples/enterprise/audit-log-demo.ainl`
