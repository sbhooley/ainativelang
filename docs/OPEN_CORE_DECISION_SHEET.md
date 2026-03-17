# Open-Core Decision Sheet

**Purpose:** Final internal decision layer. Forces concrete choices: what we commit open, commit paid, defer, or leave for later discussion. Not an audit or exploratory matrix—this is the decision artifact.

**Source:** Distilled from `docs/MONETIZATION_OPEN_CORE_AUDIT.md` and `docs/PRODUCT_MATRIX_OPEN_CORE.md`.

**Positioning:**  
> AINL is the open language for agent workflows. We sell the operational layer: governance, visibility, managed runtime, deployment, and support.

**Strategic rule:**  
- **Language legitimacy stays open.**  
- **Operator labor / governance / convenience gets monetized.**

**Paid buckets:** Managed | Enterprise | Expertise. We do not position thin, easily cloned utilities as premium products.

---

## A. Decision summary

| Outcome | What it means |
|---------|----------------|
| **Commit open** | We commit now: this stays open. Language legitimacy, core tooling, baseline docs/examples, onboarding/preflight, adapter discovery, basic policy validator, health envelope schema, and all simple scripts/tools. |
| **Commit paid** | We commit now: these are commercial pillars. Managed (hosted runtime, managed alignment, managed dashboard/ops); Enterprise (governance/audit, deployment kits, policy packs, supported monitor pack, premium connectors with depth); Expert Services (support, onboarding, certification, consulting). |
| **Defer** | We explicitly do not decide yet. Premium capability catalog, premium curriculum/certified packs, and any offering that is too early or too easy to clone before we have product/support maturity. |
| **Discuss later** | Depends on future demand or execution reality. Revisit when we have signal (e.g. enterprise tool API, industry-specific curriculum). |

---

## B. Decision table

| Surface / feature / area | Repo grounding | Decision | Paid bucket | Why | Replication risk | Notes / conditions |
|--------------------------|-----------------|----------|-------------|-----|------------------|--------------------|
| AINL spec, grammar | `docs/AINL_SPEC.md`, `docs/language/grammar.md`, `docs/language/AINL_CORE_AND_MODULES.md`, `docs/reference/AINL_V0_9_PROFILE.md` | **Commit open** | — | Language legitimacy | — | Non-negotiable |
| Parser, compiler, canonical IR | `compiler_v2.py`, `compiler_grammar.py`, `grammar_constraint.py`, `grammar_priors.py` | **Commit open** | — | Single auditable compile path | — | Core of compile-once-run-many |
| Reference runtime | `runtime/engine.py`, `runtime/compat.py`, `runtime/values.py`, `SEMANTICS.md`, `docs/RUNTIME_COMPILER_CONTRACT.md` | **Commit open** | — | Conformance and portability | — | Reference semantics |
| Core runtime adapters | `runtime/adapters/` (http, sqlite, fs, tools, wasm, base, replay) | **Commit open** | — | Baseline usefulness | — | Required for local use |
| IR schema, graph schema | `docs/reference/IR_SCHEMA.md`, `docs/reference/GRAPH_SCHEMA.md` | **Commit open** | — | Public contract for ecosystem | — | Never paywall |
| CLI (validate, run, basic emit) | `cli/main.py`, validate/run/emit entrypoints | **Commit open** | — | Local dev and CI | — | Essential workflow |
| Baseline validation | `scripts/validate_ainl.py`, conformance tests, `docs/CONFORMANCE.md` | **Commit open** | — | “Does this compile?” essential | — | Never paywall validation |
| Core docs | `docs/DOCS_INDEX.md`, `ARCHITECTURE_OVERVIEW`, `INSTALL`, `CONFORMANCE`, `README.md` | **Commit open** | — | Onboarding and trust | — | Transparency |
| Baseline examples, golden | `examples/golden/*.ainl`, `docs/EXAMPLE_SUPPORT_MATRIX.md` | **Commit open** | — | Learning and training | — | Canonical path |
| Adapter registry, manifest (core) | `docs/reference/ADAPTER_REGISTRY.md`, `tooling/adapter_manifest.json`, core in `ADAPTER_REGISTRY.json` | **Commit open** | — | “What can I call?” is language surface | — | Discovery stays open |
| Capability registry (schema + canonical) | `tooling/capabilities.json`, `capabilities.schema.json`, `docs/reference/CAPABILITY_REGISTRY.md` (core subset) | **Commit open** | — | Tool API v2 and agent discovery | — | Open subset for open core |
| Baseline eval harness, report schemas | Concepts and open report schemas | **Commit open** | — | Reproducibility and contract | — | Research and community |
| Bot onboarding, preflight | `docs/BOT_ONBOARDING.md`, `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`, `tooling/bot_bootstrap.json` | **Commit open** | — | Universal implementation discipline | — | Must stay free |
| Basic policy validator | `tooling/policy_validator.py` | **Commit open** | — | Lightweight governance; safe default | — | Simple utility; keep open |
| Health envelope schema | `docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md` | **Commit open** | — | Interop for monitors/dashboards | — | Schema stays public |
| Extension adapters (OpenClaw, agent) | `adapters/openclaw_integration.py`, `adapters/agent.py`, `examples/openclaw/` | **Commit open** | — | Reference implementation; adoption | — | Paid = supported tier only |
| Graph / IR tooling | `tooling/graph_*.py`, `ir_canonical.py`, `ir_compact.py`, `step_focus.py`, `trace_focus.py` | **Commit open** | — | Introspection; simple utility | — | Dev tooling |
| Tool API v2 (base projection) | `scripts/gen_tool_api_v2_tools.py`, `tooling/tool_api_v2.tools.json` (open subset) | **Commit open** | — | Agent discovery | — | Base open |
| Capability report/filter scripts | `scripts/capabilities_report.py`, `scripts/capabilities_filter.py` | **Commit open** | — | Discovery; simple utility | High | Paid = packaged + SLA, not script |
| Memory contract | `docs/adapters/MEMORY_CONTRACT.md` | **Commit open** | — | Extension contract | — | Interop |
| Memory tooling (retention, validate, import/export) | `scripts/memory_retention_report.py`, validate/import/export, `tooling/memory_bridge.py`, etc. | **Commit open** | — | Operator hygiene; simple scripts | High | Paid = governance suite packaging |
| Operator-only audit script | `scripts/operator_only_adapter_audit.py` | **Commit open** | — | Visibility; simple script | High | Paid = audit suite packaging |
| Coordination validator, mailbox validation | `tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py` | **Commit open** | — | Envelope validation; reference | High | Paid = compliance packaging |
| Autonomous ops examples, run scripts | `examples/autonomous_ops/*.lang`, `demo/*.lang`, `scripts/run_*.py`, `docs/operations/AUTONOMOUS_OPS_MONITORS.md` | **Commit open** | — | Reference monitors and patterns | — | Paid = supported pack / Managed |
| Hosted AINL runtime / managed ops | Hosted service (no repo code) | **Commit paid** | Managed | Run at scale; uptime; operator labor | Low | Operational guarantee |
| Managed alignment pipeline | Builds on `run_alignment_cycle.sh`, sweep, eval, run health | **Commit paid** | Managed | We run sweep, eval gate, trends; SLA | Low | Operational guarantee |
| Managed dashboard / ops platform | Builds on health envelope, run health; aggregation, alerts | **Commit paid** | Managed | Visibility; regression; run health | Medium | Only if it provides aggregation, trends, regression visibility, alerts, governance integration, or SLA-backed operational value—not just UI over open outputs |
| Enterprise governance / audit suite | Package: audit, capability governance, coordination validation, memory hygiene, policy packs | **Commit paid** | Enterprise | “Who can do what”; compliance | Low | Policy packs + integration |
| Deployment kits (SSO, K8s, terraform, hardening) | Conceptual playbooks | **Commit paid** | Enterprise | Deploy in your VPC; reduce risk | Low | Reduces labor and risk |
| Policy packs (curated, industry/compliance) | Builds on open policy validator | **Commit paid** | Enterprise | Compliance; “prove we’re in control” | Low | Curated + support |
| Supported ops monitor pack | Curated autonomous ops + runbooks + health envelope + updates + SLA | **Commit paid** | Enterprise / Managed | Guaranteed updates and support | Medium | Examples stay open; support = paid |
| Premium connector packs | Enterprise adapters beyond http/sqlite/fs/tools | **Commit paid** | Enterprise | Integration and support | Medium | Only deep, support-heavy, compliance-aware, enterprise-grade integrations—not generic wrappers around public APIs |
| Support (SLA-backed) | — | **Commit paid** | Expertise | Priority response; guarantees | Low | Standard commercial |
| Onboarding | — | **Commit paid** | Expertise | Implementation reviews; success plans | Low | Reduces risk and time-to-value |
| Certification | — | **Commit paid** | Expertise | Operator/developer certification | Low | Trust and hiring signal |
| Consulting / custom engineering | — | **Commit paid** | Expertise | Custom integration, architecture | Low | Expert labor |
| Premium capability catalog / extended tool API | Extended verbs, proprietary adapters beyond open registry | **Defer** | Enterprise | Too early; validate core packages first | Medium | Revisit when demand exists |
| Premium training / certified curriculum | Expanded golden, industry curriculum, certified model packs | **Defer** | Enterprise / Expertise | Too early; need product/support maturity | Medium | Revisit when demand clear |
| Thin dashboard (UI over open scripts only) | — | **Defer** | — | Too easy to clone; weak product | High | Do not position as premium |
| Standalone “run this script in cloud” | — | **Defer** | — | Shallow wrapper; weak | High | Only sell as part of governance/support |
| Weak connector pack (thin API wrapper only) | — | **Defer** | — | Easy to recreate | High | Only ship connectors with depth |
| Enterprise tool API demand | — | **Discuss later** | Enterprise | Revisit when we have customer signal | — | Trigger: first credible enterprise ask for premium Tool API |
| Industry-specific curriculum demand | — | **Discuss later** | Enterprise / Expertise | Revisit when we have demand | — | Trigger: repeated onboarding/training demand or first real buyer for certified/vertical curriculum |

---

## C. Commit open

We commit the following as **open** now. These surfaces will remain free and open for trust, adoption, and language legitimacy.

- **Spec and grammar:** AINL language spec, grammar references, core and profile docs (`docs/AINL_SPEC.md`, `docs/language/grammar.md`, `docs/language/AINL_CORE_AND_MODULES.md`, `docs/reference/AINL_V0_9_PROFILE.md`).
- **Compiler:** Parser, compiler, canonical IR generation (`compiler_v2.py`, `compiler_grammar.py`, `grammar_constraint.py`, `grammar_priors.py`).
- **Runtime:** Reference runtime engine and execution semantics (`runtime/engine.py`, `runtime/compat.py`, `runtime/values.py`, `SEMANTICS.md`, `docs/RUNTIME_COMPILER_CONTRACT.md`).
- **Schemas:** IR schema, graph schema (`docs/reference/IR_SCHEMA.md`, `docs/reference/GRAPH_SCHEMA.md`).
- **Baseline validation:** Validation and conformance tooling and tests (`scripts/validate_ainl.py`, conformance tests, `docs/CONFORMANCE.md`).
- **Core docs and examples:** Architecture, install, conformance, DOCS_INDEX, README; baseline examples and golden curriculum (`examples/golden/*.ainl`, `docs/EXAMPLE_SUPPORT_MATRIX.md`).
- **Onboarding and preflight:** Bot onboarding and implementation preflight (`docs/BOT_ONBOARDING.md`, `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`, `tooling/bot_bootstrap.json`).
- **Basic policy validator:** IR-level policy check (`tooling/policy_validator.py`).
- **Health envelope schema:** Standardized health envelope (`docs/operations/STANDARDIZED_HEALTH_ENVELOPE.md`).
- **Core adapter discovery / registry / manifest:** Adapter registry and manifest for core adapters (`docs/reference/ADAPTER_REGISTRY.md`, `tooling/adapter_manifest.json`, core entries in `ADAPTER_REGISTRY.json`).
- **Capability registry (open subset):** Schema and canonical-lane capability entries (`tooling/capabilities.json`, `capabilities.schema.json`, `docs/reference/CAPABILITY_REGISTRY.md`).
- **Baseline eval harness and report schemas:** Concepts and open report schemas for reproducibility.
- **CLI fundamentals:** Validate, run, basic emit (`cli/main.py` and related entrypoints).
- **Core runtime adapters:** http, sqlite, fs, tools, wasm, base, replay (`runtime/adapters/`).
- **Extension adapters and examples (reference):** OpenClaw integration, agent adapter, examples (`adapters/openclaw_integration.py`, `adapters/agent.py`, `examples/openclaw/`).
- **Graph/IR and capability scripts:** Graph API, export, rewrite, ir_canonical, ir_compact, step_focus, trace_focus; capability report and filter scripts; memory tooling (retention, validate, import/export); operator-only audit script; coordination validator and mailbox validation.
- **Autonomous ops examples and run scripts:** Reference monitors and patterns (`examples/autonomous_ops/`, `demo/*.lang`, `scripts/run_*.py`, `docs/operations/AUTONOMOUS_OPS_MONITORS.md`).
- **Memory contract:** `docs/adapters/MEMORY_CONTRACT.md`.
- **Tool API v2 base projection:** Open capability subset (`scripts/gen_tool_api_v2_tools.py`, `tooling/tool_api_v2.tools.json`).

---

## D. Commit paid

We commit the following **commercial pillars** now. Paid value is in operational guarantees, governance/compliance, managed service, and expert support—not in thin wrappers or easily cloned utilities.

**Managed**
- **Hosted AINL runtime / managed ops platform:** Run AINL at scale; scheduling; uptime; reduces operator labor.
- **Managed alignment pipeline:** We run sweep, eval gate, trends, run health; SLA.
- **Managed dashboard / ops platform:** Only when it provides aggregation, trends, regression visibility, alerts, governance integration, or SLA-backed operational value—not just UI over open outputs.

**Enterprise**
- **Governance / audit / compliance suite:** Operator-only audit, capability governance, coordination validation, memory retention/hygiene, policy packs—packaged with integration and support.
- **Deployment kits:** SSO, K8s, terraform, hardening playbooks; deploy in your VPC.
- **Policy packs:** Curated, industry/compliance policies built on open validator; integration and support.
- **Supported ops monitor pack:** Curated autonomous ops + runbooks + health envelope + updates + SLA (examples stay open; support and guarantees = paid).
- **Premium connector packs:** Only deep, support-heavy, compliance-aware, enterprise-grade integrations—not generic wrappers around public APIs.

**Expertise**
- **Support:** SLA-backed; priority response; guarantees.
- **Onboarding:** Implementation reviews; success plans.
- **Certification:** Operator/developer certification.
- **Consulting:** Custom integration; architecture; custom engineering.

---

## E. Defer

We **do not decide now** on the following. Revisit when we have product/support maturity or clear demand.

- **Premium capability catalog / extended tool API:** Extended verbs, proprietary adapters, curated sets beyond open registry. Too early; validate core packages first.
- **Premium training / certified curriculum:** Expanded golden, industry curriculum, certified model packs. Need product and support maturity before committing.
- **Thin offerings we will not position as premium:** Thin dashboard (UI over open scripts only); standalone “run this script in the cloud” with no policy packs or integration; weak connector pack (thin API wrapper only). These are too easy to clone and do not become our paid strategy. Do not let them drift into product plans later.

---

## F. Discuss later

Revisit when we have **demand or execution reality** (explicit triggers below):

- **Enterprise tool API:** Revisit after **first credible enterprise ask** for premium Tool API or capability catalog.
- **Industry-specific curriculum:** Revisit after **repeated onboarding/training demand** or **first real buyer** asking for certified/vertical curriculum.

These are not committed; they are on the list for future discussion.

---

## G. Guardrails

Hard rules for boundary and product decisions:

1. **Do not paywall language legitimacy.** Spec, compiler, runtime, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema, and core adapter discovery stay open.
2. **Do not sell thin wrappers as premium strategy.** Do not position a shallow UI over open scripts, or “we run this script for you” with no policy packs/integration/SLA, as a standalone premium product.
3. **Do not make the open core useless.** The free layer must be sufficient for real workflows (run, validate, core adapters, examples). Paid = convenience, scale, governance, support.
4. **Do not surprise-relicense.** Do not move previously open material to paid without announcement and documented rationale.
5. **Do not blur open vs paid.** Label clearly (Open Core / Commercial / Planned). Keep this decision sheet and `docs/OPEN_CORE_BOUNDARY_MAP.md` aligned.

---

## H. Final recommended packaging

| Package | Contents | Role |
|---------|----------|------|
| **Open Core** | Spec, compiler, runtime, core adapters, schemas, baseline validation, core docs/examples, onboarding/preflight, basic policy validator, health envelope schema, core adapter registry and open capability subset, baseline eval/report schemas, CLI, graph/IR and capability scripts, memory/coordination/audit scripts, extension adapters and autonomous ops as reference. | Free, open. |
| **Managed Platform** | Hosted AINL runtime; managed alignment pipeline; managed dashboard/ops (with meaningful operational value). Operational guarantees and SLA. | Paid. |
| **Enterprise Governance** | Governance/audit suite (audit, capability governance, coordination validation, memory hygiene, policy packs); deployment kits; premium connector packs (when deep); supported ops monitor pack. | Paid. |
| **Expert Services** | SLA-backed support; onboarding and success plans; certification; consulting and custom engineering. | Paid. |

Open Core is the free layer. Managed Platform, Enterprise Governance, and Expert Services are commercial. We do not overcommit to weak or easily cloned products; we bias paid strategy toward operational guarantees, governance/compliance, managed service, and expert support.

---

## Boundary approval and lock

The open-core boundary is approved with minor refinements already incorporated into this decision sheet. The boundary is now considered **locked for planning purposes**. Further changes should only happen in response to concrete product, customer, or operational evidence.

Final signoff choices and notes are recorded in **`docs/OPEN_CORE_REVIEW_CHECKLIST.md`** (Section 4. Final signoff notes; Section 5. Boundary lock). For execution planning on first deliverables per pillar, see **`docs/OPEN_CORE_FIRST_DELIVERABLES.md`**.

---

*This document is the final decision-layer planning artifact. No runtime or compiler semantics, licenses, or product code have been changed. For strategic context, see `docs/MONETIZATION_OPEN_CORE_AUDIT.md`. For the full product matrix and decision prompts, see `docs/PRODUCT_MATRIX_OPEN_CORE.md`.*
