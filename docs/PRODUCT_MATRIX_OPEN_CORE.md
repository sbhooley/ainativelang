# Product Matrix and Open-Core Boundary Proposal

**Purpose:** Practical decision matrix and boundary proposal for what stays open, what becomes paid, and how to package offerings. Design/documentation only—no runtime, compiler, or license changes.

**Source:** Builds on `docs/MONETIZATION_OPEN_CORE_AUDIT.md` and current repo state.

**Decision layer:** For final internal choices (commit open / commit paid / defer / discuss later), see **[docs/OPEN_CORE_DECISION_SHEET.md](OPEN_CORE_DECISION_SHEET.md)**. The boundary is **locked for planning purposes**; signoff and lock statement: **[docs/OPEN_CORE_REVIEW_CHECKLIST.md](OPEN_CORE_REVIEW_CHECKLIST.md)** (§4–§5).

**Positioning (refined):**  
> AINL is the open language for agent workflows. We sell the operational layer: governance, visibility, managed runtime, deployment, and support.

**Strategic framing:**
- **Language legitimacy stays open.**
- **Operator labor / governance / convenience gets monetized.**

Paid offerings are grouped into three buckets: **Managed**, **Enterprise**, **Expertise**. Bias paid strategy toward operational guarantees, governance/compliance, managed service, and expert support—not thin utilities.

---

## 1. Product matrix

| Repo surface / feature / area | Current repo grounding | Category | Paid bucket | Why | Replication risk | Buyer / user | Notes |
|------------------------------|-------------------------|----------|-------------|-----|-------------------|--------------|--------|
| AINL language spec, grammar | `docs/AINL_SPEC.md`, `docs/grammar.md`, `docs/AINL_CORE_AND_MODULES.md`, `docs/AINL_V0_9_PROFILE.md` | **Never paywall** | — | Language legitimacy; ecosystem compatibility | N/A | Everyone | Must stay open for trust and adoption |
| Parser, compiler, canonical IR | `compiler_v2.py`, `compiler_grammar.py`, `grammar_constraint.py`, `grammar_priors.py` | **Open** | — | Single auditable compile path; adoption | N/A | Developers, agents | Core of “compile once, run many” |
| Reference runtime engine | `runtime/engine.py`, `runtime/compat.py`, `runtime/values.py`, `SEMANTICS.md`, `docs/RUNTIME_COMPILER_CONTRACT.md` | **Open** | — | Conformance and portability | N/A | Everyone | Reference semantics must stay open |
| Core runtime adapters | `runtime/adapters/` (http, sqlite, fs, tools, wasm, base, replay) | **Open** | — | Baseline usefulness without paid pieces | N/A | Developers, agents | Needed for local/dev use |
| IR schema, graph schema | `docs/IR_SCHEMA.md`, `docs/GRAPH_SCHEMA.md` | **Never paywall** | — | Public contract for tooling and runtimes | N/A | Ecosystem | Paywalling blocks third-party runtimes |
| CLI fundamentals | `cli/main.py`, validate, run, basic emit | **Open** | — | Local dev and CI must work | N/A | Developers | Essential workflow |
| Baseline validation | `scripts/validate_ainl.py`, conformance tests in `docs/CONFORMANCE.md` | **Open** | — | “Does this compile?” is essential | N/A | Developers, agents | Never paywall validation |
| Core docs (architecture, spec, install, conformance) | `docs/DOCS_INDEX.md`, `docs/ARCHITECTURE_OVERVIEW.md`, `docs/INSTALL.md`, `docs/CONFORMANCE.md`, `README.md` | **Open** | — | Onboarding and trust | N/A | Everyone | Transparency |
| Baseline examples, golden curriculum | `examples/golden/*.ainl`, `docs/EXAMPLE_SUPPORT_MATRIX.md` | **Open** | — | Learning and model training | N/A | Developers, agents | Canonical learning path |
| Adapter registry (core), adapter manifest | `docs/ADAPTER_REGISTRY.md`, `tooling/adapter_manifest.json`, core entries in `ADAPTER_REGISTRY.json` | **Open** | — | “What can I call?” is language surface | N/A | Everyone | Discovery stays open |
| Capability registry (schema + canonical lane) | `tooling/capabilities.json`, `tooling/capabilities.schema.json`, `docs/CAPABILITY_REGISTRY.md` (core/canonical subset) | **Open** | — | Tool API v2 and agent discovery | N/A | Developers, agents | Open subset for open core |
| Baseline eval harness behavior, report schemas | Concepts (strict_ainl_rate, runtime_compile_rate, nonempty_rate); open report schemas | **Open** | — | Research and community reproducibility | N/A | Researchers, community | Schemas are contract |
| Bot onboarding, implementation preflight | `docs/BOT_ONBOARDING.md`, `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`, `tooling/bot_bootstrap.json` | **Open** | — | Universal implementation discipline | N/A | Agents, contributors | Reduces chaos; must stay free |
| Basic policy validator | `tooling/policy_validator.py` (forbidden_adapters/effects/tiers on IR) | **Open** | — | Lightweight governance; encourages safe use | N/A | Everyone | Simple utility; keep open |
| Standardized health envelope schema | `docs/STANDARDIZED_HEALTH_ENVELOPE.md` | **Open** | — | Interop for monitors and dashboards | N/A | Ecosystem | Schema stays public |
| Extension adapters (OpenClaw, agent) | `adapters/openclaw_integration.py`, `adapters/agent.py`, `examples/openclaw/` | **Open** (reference) | — | Adoption driver; reference implementation | — | Operators, adopters | Can offer *supported* paid tier |
| Graph / IR tooling | `tooling/graph_api.py`, `graph_export.py`, `graph_rewrite.py`, `ir_canonical.py`, `ir_compact.py`, `step_focus.py`, `trace_focus.py` | **Open** | — | Introspection and debugging for devs | N/A | Developers | Simple utilities |
| Tool API v2 projection (base) | `scripts/gen_tool_api_v2_tools.py`, `tooling/tool_api_v2.tools.json` (open capability subset) | **Open** | — | Agent discovery from open registry | N/A | Agents | Base projection open |
| Capability report and filter scripts | `scripts/capabilities_report.py`, `scripts/capabilities_filter.py` | **Open** | — | Discovery and filtering by domain/safety | Medium | Operators | Scripts easy to run; paid = packaged + SLA |
| Memory contract (doc) | `docs/MEMORY_CONTRACT.md` | **Open** | — | Extension contract; interop | N/A | Everyone | Contract stays open |
| Memory tooling (retention, validate, import/export) | `scripts/memory_retention_report.py`, `validate_memory_records.py`, `import/export_memory_*`, `tooling/memory_bridge.py`, `memory_markdown_import.py` | **Open** (scripts) | — | Operator hygiene; scripts are simple | High | Operators | *Packaged* governance = Enterprise |
| Operator-only audit script | `scripts/operator_only_adapter_audit.py` | **Open** (script) | — | Visibility into operator_only usage | High | Operators | *Packaged* audit suite = Enterprise |
| Coordination validator, mailbox validation | `tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py` | **Open** (tools) | — | Envelope validation; reference | High | Operators | *Packaged* compliance = Enterprise |
| Autonomous ops examples and run scripts | `examples/autonomous_ops/*.lang`, `demo/*.lang`, `scripts/run_*.py`, `docs/AUTONOMOUS_OPS_MONITORS.md` | **Open** (reference) | — | Reference monitors and patterns | — | Operators | *Supported* pack or Managed = paid |
| Hosted AINL runtime / managed ops platform | No repo code (hosted service) | **Paid** | **Managed** | Run at scale; scheduling; uptime; reduces operator labor | Low | Operators, platform teams | Operational guarantee |
| Managed alignment pipeline | Builds on `run_alignment_cycle.sh`, `sweep_checkpoints.py`, `eval_finetuned_model.py`, run health | **Paid** | **Managed** | We run sweep, eval gate, trends; SLA | Low | ML/platform teams | Operational guarantee |
| Managed dashboard / ops platform | Builds on health envelope, run health, `serve_dashboard.py`; aggregation, alerts | **Paid** | **Managed** | Visibility, regression, run health; reduces chaos | Medium | Operators | Only valuable if deep (see Risks) |
| Enterprise governance / audit suite | Package: operator_only audit, capability governance, coordination validation, memory retention, policy packs | **Paid** | **Enterprise** | “Who can do what”; audit trails; compliance | Low | Enterprises | Policy packs + integration = hard to clone |
| SSO / deployment kits | K8s, terraform, secrets, hardening playbooks (conceptual) | **Paid** | **Enterprise** | Deploy in your VPC with our playbook | Low | Enterprises | Reduces risk and labor |
| Premium connector packs | Enterprise adapters (CRM, calendar, email, proprietary APIs) beyond http/sqlite/fs/tools | **Paid** | **Enterprise** | Integration and support | Medium | Enterprises | Only valuable if deep (see Risks) |
| Policy packs (curated, industry/compliance) | Builds on `tooling/policy_validator.py`; curated policies + integration | **Paid** | **Enterprise** | Compliance and “prove we’re in control” | Low | Enterprises | Curated + support = differentiation |
| Supported ops monitor pack | Curated autonomous ops + runbooks + health envelope + updates + SLA | **Paid** | **Enterprise** or **Managed** | Guaranteed updates and support | Medium | Operators | Examples stay open; support = paid |
| Premium capability catalog / extended tool API | Extended verbs, proprietary adapters, curated sets beyond open registry | **Maybe later** | **Enterprise** | If demand for “enterprise tool API” emerges | Medium | Enterprises | Defer until core packages validated |
| Premium training / certified curriculum | Expanded golden + industry curriculum or certified model packs | **Maybe later** | **Enterprise** or **Expertise** | “AINL that works” out of the box | Medium | Teams | Defer until demand clear |
| Support (SLA-backed) | — | **Paid** | **Expertise** | Priority response; guarantees | Low | Everyone | Standard commercial |
| Onboarding | — | **Paid** | **Expertise** | Implementation reviews; success plans | Low | Teams | Reduces risk and time-to-value |
| Certification | — | **Paid** | **Expertise** | Operator/developer certification | Low | Individuals, teams | Trust and hiring signal |
| Consulting / custom engineering | — | **Paid** | **Expertise** | Custom integration, architecture | Low | Enterprises | Expert labor |

---

## 2. Boundary proposal

### What is open and why

- **Spec, compiler, runtime, core adapters, IR/graph schemas, baseline validation, core docs and examples, onboarding/preflight, basic policy validator, health envelope schema.**  
  These are the **language legitimacy** layer. They stay open so that:
  - The language is a single, portable standard.
  - Developers and agents can adopt AINL without lock-in.
  - The ecosystem can build tooling and runtimes against a public contract.
  - Trust and contributions are maximized.

- **Simple utilities** (graph/IR introspection, capability report/filter, memory retention script, operator_only audit script, coordination validator) remain **open as scripts/tools**. They are “run locally and see.” That keeps the project useful and transparent. The **paid** value is not the script itself but **packaging**: governance suite, SLA, policy packs, integration into enterprise control plane, and support.

### What is paid and why

- **Managed:** Hosted runtime, managed alignment pipeline, managed dashboard/ops platform. These reduce **operator labor** and provide **operational guarantees** (uptime, SLA, “we run it”).

- **Enterprise:** Governance/audit/compliance suite, SSO/deployment kits, premium connector packs, policy packs, supported ops monitor pack. These reduce **risk and chaos** and answer “who can do what” and “prove we’re compliant.”

- **Expertise:** Support, onboarding, certification, consulting. These provide **expert labor and guarantees** without paywalling code.

### What must remain open for trust and adoption

- Anything required for **language legitimacy**: spec, grammar, compiler, reference runtime, IR/graph schemas.
- Anything required for **basic use**: core adapters, CLI (validate/run), baseline validation, core docs and examples.
- **Onboarding and preflight** so all agents follow the same discipline.
- **Basic policy validator** so safe use is the default.
- **Health envelope schema** so the ecosystem can consume monitor output.

### What is monetized because it reduces operator labor / risk / chaos

- **Managed:** Running AINL at scale, running the alignment pipeline, providing a visibility/dashboard layer with operational value.
- **Enterprise:** Governance, audit, compliance, deployment safety, premium integrations with support, policy packs.
- **Expertise:** Support, onboarding, certification, consulting.

---

## 3. Packaging proposal

Conceptual product packaging (no pricing):

| Package | Contents | Target |
|---------|----------|--------|
| **Open Core** | Spec, compiler, runtime, core adapters, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema, reference extension adapters and examples, graph/IR and capability scripts. | Developers, agents, researchers, community. |
| **Managed Platform** | Hosted AINL runtime; managed alignment pipeline; managed dashboard/ops (aggregation, run health, trends, alerts). Operational guarantees and SLA. | Operators, platform teams. |
| **Enterprise Governance** | Governance/audit suite (operator_only audit, capability governance, coordination validation, memory retention/hygiene, policy packs); deployment kits (K8s, terraform, hardening); premium connector packs; supported ops monitor pack. | Enterprises, compliance, security. |
| **Expert Services** | SLA-backed support; onboarding and success plans; certification (operators/developers); consulting and custom engineering. | Teams, enterprises. |

Open Core is the free, open layer. Managed Platform, Enterprise Governance, and Expert Services are commercial offerings. A customer might use only Open Core; or Open Core + Managed; or Open Core + Enterprise + Expert Services.

---

## 4. Risks and guardrails

### What not to accidentally paywall

- **Spec, compiler, runtime, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema.**  
  These are “never paywall.” Moving any of them to paid would damage language legitimacy and adoption.

- **Core adapter registry and manifest** for core adapters: discovery is part of the language surface; keep it open.

- **Baseline eval harness behavior and report schemas:** keep open so research and community can reproduce and compare.

### What paid offerings are too easy to clone

- **Thin dashboards:** A shallow UI over open scripts (e.g. a simple table of `memory_retention_report` output or run health JSON) is easy to replicate. Mitigation: only position “dashboard” as paid when it delivers **meaningful operational value**—aggregation across many runs, regression analysis, alerting, SLA, integration with governance.

- **Shallow wrappers around open scripts:** Selling “we run `operator_only_adapter_audit` for you” with no policy packs, no integration, no SLA is weak. Mitigation: package scripts as part of **Enterprise Governance** (policy packs, audit workflows, compliance reporting, support)—not as standalone “run this script in the cloud.”

- **Weak connector packs:** Thin adapters that only wrap a well-documented API with no added logic or support are easy to recreate. Mitigation: premium connectors should offer **support, compliance, and integration** (SSO, deployment, audit) or deep vertical value—not just “another adapter.”

### How to avoid confusing or hostile boundary decisions

- **Label clearly:** In docs and UI, mark “Open Core,” “Commercial,” “Planned.” Keep `docs/OPEN_CORE_BOUNDARY_MAP.md` and this matrix aligned and up to date.

- **No surprise relicensing:** Do not move previously open material to paid without announcement and documented rationale.

- **Open core is useful by itself:** The free layer must be sufficient for real workflows (run, validate, core adapters, examples). Paid = convenience, scale, governance, support—not “everything you need.”

### How to preserve community trust

- **Transparency:** Publish boundary and matrix (this doc and the audit); keep conformance and release-readiness docs open.

- **Contribution clarity:** Contributors know what is open and what is commercial; no ambiguity on license or boundary.

- **Bias paid toward high-value layers:** Operational guarantees, governance/compliance, managed service, expert support. Avoid paywalling simple utilities that the community can run themselves; sell the **packaging and guarantees** instead.

---

## 5. Recommended decision prompts

Use these when deciding whether a surface is open, paid, maybe-later, or never paywall:

1. **Is this required for language legitimacy?**  
   If yes → **Open** or **Never paywall** (spec, compiler, runtime, schemas, baseline validation, core docs/examples).

2. **Does this reduce operator labor enough that enterprises will pay?**  
   If yes and it’s not language-legitimacy → candidate for **Paid** (Managed / Enterprise / Expertise). Ensure it’s not a thin wrapper (see replication risk).

3. **Is this too easy to reproduce from the open repo?**  
   If yes → keep the **script/tool open**; sell **packaging** (SLA, policy packs, integration, support) rather than the script alone. Avoid positioning thin dashboards or shallow wrappers as premium products.

4. **Does closing this damage trust or adoption more than it helps revenue?**  
   If yes → keep it **Open** or **Never paywall**. When in doubt, keep the language and core tooling open.

5. **Is this a simple utility (run once, see result) or a high-value operational layer?**  
   Simple utility → **Open**. High-value operational layer (governance, managed runtime, deployment, support) → **Paid** in the appropriate bucket.

6. **Would the community reasonably expect this to be free?**  
   If yes (e.g. “does it compile?”, adapter discovery, onboarding) → **Open**.

---

## Summary

- **Open / Never paywall:** Spec, compiler, runtime, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema, core adapter registry, open capability subset. Simple utilities (scripts) stay open; paid value is in packaging and guarantees.
- **Paid:** Managed (hosted runtime, managed alignment, managed dashboard/ops); Enterprise (governance/audit/compliance, deployment kits, premium connectors, policy packs, supported ops pack); Expertise (support, onboarding, certification, consulting).
- **Maybe later:** Premium capability catalog, premium training/certified curriculum—defer until core packages are validated.
- **Positioning:** AINL is the open language for agent workflows; we sell the operational layer: governance, visibility, managed runtime, deployment, and support.

This document is a planning artifact only. No runtime or compiler semantics, licenses, or product code have been changed.
