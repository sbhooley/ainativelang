# Open-Core Review Checklist

**Purpose:** Lightweight review tool to approve or revise the boundaries in `docs/OPEN_CORE_DECISION_SHEET.md`. Documentation/planning only—no code or license changes.

**How to use:** Work through the approval checklists, answer the review prompts, then complete the signoff block.

---

## 1. Approval checklist

### Commit open
- [ ] Spec, grammar, compiler, runtime, schemas are all committed open.
- [ ] Baseline validation, core docs/examples, CLI, core adapters are committed open.
- [ ] Onboarding/preflight, basic policy validator, health envelope schema are committed open.
- [ ] Core adapter discovery, registry, manifest (and open capability subset) are committed open.
- [ ] Extension adapters, graph/IR/capability scripts, memory/audit/coordination tools, autonomous ops reference are committed open.
- [ ] I am comfortable that nothing in "commit open" should be paid.

### Commit paid
- [ ] Managed: hosted runtime, managed alignment, managed dashboard/ops (with meaningful value only) are committed paid.
- [ ] Enterprise: governance/audit suite, deployment kits, policy packs, supported monitor pack, premium connectors (deep only) are committed paid.
- [ ] Expertise: support, onboarding, certification, consulting are committed paid.
- [ ] No thin wrappers or easily cloned utilities are in "commit paid."
- [ ] Paid value is clearly in operational guarantees, governance, managed service, expert support.

### Defer
- [ ] Premium capability catalog and premium curriculum are deferred.
- [ ] Thin dashboard, standalone script-in-cloud, weak connector pack are explicitly not premium / deferred.
- [ ] Rationale for deferral (too early or too easy to clone) is clear.

### Discuss later
- [ ] Enterprise tool API and industry-specific curriculum are "discuss later" only.
- [ ] **Revisit triggers** are explicit: first credible enterprise ask for premium Tool API; repeated onboarding/training demand or first real buyer for certified/vertical curriculum.

### Guardrails
- [ ] Do not paywall language legitimacy.
- [ ] Do not sell thin wrappers as premium strategy.
- [ ] Do not make the open core useless.
- [ ] Do not surprise-relicense.
- [ ] Do not blur open vs paid (clear labels, aligned boundary map).

### Final packaging
- [ ] Open Core = free; Managed Platform, Enterprise Governance, Expert Services = paid.
- [ ] Package contents match the decision sheet and are consistent with commit open / commit paid.

---

## 2. Decision prompts

### Commit open
- Are we comfortable committing these surfaces as **permanently** open (no future paywall)?
- Would closing any of these significantly harm trust or adoption?
- Is the open core sufficient for real workflows (run, validate, core adapters, examples)?

### Commit paid
- Is each paid surface **hard enough to clone** that it justifies monetization (not a thin UI or script wrapper)?
- Does each paid surface **reduce operator labor, risk, or chaos** enough that enterprises will pay?
- Are we avoiding "run this open script in the cloud" as a standalone product?

### Defer
- Should any of these be **committed** (open or paid) instead of deferred?
- Is "too early" or "too easy to clone" the right reason for each deferral?
- Do we have a clear trigger to revisit (e.g. demand, product maturity)?

### Discuss later
- When will we revisit (e.g. first enterprise ask, first curriculum request)?
- Is "discuss later" the right bucket vs Defer vs Commit paid?

### Guardrails
- Would any planned product or boundary change violate one of these rules?
- Are these five rules sufficient, or should we add one?

### Packaging
- Is the four-package split (Open Core, Managed, Enterprise, Expert) clear to both technical and business readers?
- Does the packaging align with the commit open / commit paid lists?

---

## 3. Final signoff block

| Area | Approved as written | Approved with revisions | Needs discussion |
|------|---------------------|-------------------------|------------------|
| **Commit open** | ☑ | ☐ | ☐ |
| **Commit paid** | ☐ | ☑ | ☐ |
| **Defer** | ☑ | ☐ | ☐ |
| **Discuss later** | ☐ | ☑ | ☐ |
| **Guardrails** | ☑ | ☐ | ☐ |
| **Packaging** | ☑ | ☐ | ☐ |

**Final choices applied:** Commit open, Defer, Guardrails, Packaging → Approved as written. Commit paid, Discuss later → Approved with revisions (revisions incorporated in decision sheet).

---

## 4. Final signoff notes

- **Commit open — Approved as written.** The open layer correctly protects language legitimacy and baseline usefulness: spec, compiler, runtime, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema, adapter discovery, open capability subset, and simple utilities/scripts.

- **Commit paid — Approved with revisions.** Approved with the tightened wording that: (1) Managed dashboard / ops platform is paid only if it provides meaningful operational value (aggregation, trends, regression visibility, alerts, governance integration, or SLA-backed service), not merely a UI over open outputs; (2) Premium connector packs are paid only when they are deep, support-heavy, compliance-aware, enterprise-grade integrations, not generic wrappers around public APIs.

- **Defer — Approved as written.** Premium capability catalog, premium curriculum, thin dashboard, standalone script-in-cloud, and weak connector pack remain deferred and should not drift into product plans without new evidence.

- **Discuss later — Approved with revisions.** Approved with explicit revisit triggers: Enterprise Tool API — revisit on first credible enterprise ask for premium Tool API or capability catalog; Industry-specific curriculum — revisit on repeated onboarding/training demand or first real buyer asking for certified or vertical curriculum.

- **Guardrails — Approved as written.** Hard rules intact: do not paywall language legitimacy; do not sell thin wrappers as premium strategy; do not make the open core useless; do not surprise-relicense; do not blur open vs paid boundaries.

- **Packaging — Approved as written.** Open Core | Managed Platform | Enterprise Governance | Expert Services. Clear for technical and business readers; matches the boundary decisions.

---

## 5. Boundary lock

The open-core boundary is approved with minor refinements already incorporated into the decision sheet. The boundary is now considered **locked for planning purposes**. Further changes should only happen in response to concrete product, customer, or operational evidence.

---

*Reference: `docs/OPEN_CORE_DECISION_SHEET.md`. This checklist does not change runtime, compiler, licenses, or product code.*
