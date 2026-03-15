# First Deliverables by Paid Pillar (Execution Planning)

**Purpose:** Execution-oriented plan for the first concrete deliverable in each approved paid pillar. Based on the locked boundary in `docs/OPEN_CORE_DECISION_SHEET.md`. No new strategy; no reopening of open-vs-paid decisions.

**Scope:** Managed Platform | Enterprise Governance | Expert Services. Grounded in the repo as it exists today.

---

## 1. Managed Platform

### First deliverable
**Managed alignment pipeline** — We run the alignment cycle for the customer (supervision build, train, sweep, eval gate, run health); deliver run health and trend outcomes with defined SLA. Alternative first: **Hosted AINL runtime** (runner service + scheduling) if infra exists before alignment demand.

### Repo grounding
- **Pipeline:** `scripts/run_alignment_cycle.sh`, `scripts/sweep_checkpoints.py`, `scripts/eval_finetuned_model.py`, `scripts/build_regression_supervision.py`; `docs/TRAINING_ALIGNMENT_RUNBOOK.md`, `docs/FINETUNE_GUIDE.md`.
- **Run health:** `corpus/curated/alignment_run_health.json` (machine-readable gate output).
- **Runner (for hosted runtime):** `scripts/runtime_runner_service.py` (FastAPI: `/run`, `/health`, `/ready`, `/metrics`); `services/runtime_runner/Dockerfile`, `services/runtime_runner/docker-compose.yml`.
- **Monitors (for managed ops):** `scripts/run_*.py` (e.g. `run_infrastructure_watchdog.py`, `run_meta_monitor.py`), `docs/AUTONOMOUS_OPS_MONITORS.md`, `docs/STANDARDIZED_HEALTH_ENVELOPE.md`.

### Missing pieces
- **Managed alignment:** Customer-specific dataset/config; secure execution environment; run scheduling; SLA monitoring and reporting; billing/entitlement.
- **Hosted runtime:** Multi-tenant or isolated execution; job queue/scheduler; auth and quotas; persistent run history and metrics.
- **Managed dashboard:** Decision sheet allows it only with meaningful operational value (aggregation, trends, regression, alerts, governance integration, SLA). Current `scripts/serve_dashboard.py` is emit/local—not yet that layer.

### Recommended first build steps
1. **Managed alignment:** Define one “alignment run” product shape (inputs: corpus/config; outputs: run health JSON, trend summary, pass/fail). Document runbook and support handoff. Add minimal customer config surface and a single execution path (e.g. run in customer VPC or in our env with their data). Do not build a full multi-tenant platform first.
2. **If hosted runtime first:** Expose runner service behind auth; add a simple job queue and cron-like scheduler; add run history and metrics persistence. Reuse existing Docker/runner as the execution unit.
3. **Dashboard:** Explicitly wait until we can deliver aggregation, regression visibility, or SLA-backed views—not a thin UI over existing open scripts.

### What to defer
- Full multi-tenant SaaS for alignment or runtime.
- Managed dashboard until we have aggregation/trends/alerting and governance integration (per boundary).
- Building net-new alignment logic; the open pipeline is the source of truth.

---

## 2. Enterprise Governance

### First deliverable
**Supported ops monitor pack** — Curated autonomous ops programs + runbooks + health envelope + updates and SLA. Examples stay open; paid = support, guaranteed updates, and runbook/SLA. Alternative first: **Governance audit package** — package existing scripts (operator_only audit, capability report, coordination validator, memory retention) with one curated policy pack and support.

### Repo grounding
- **Monitors:** `examples/autonomous_ops/*.lang`, `demo/*.lang`, `scripts/run_*.py`, `docs/AUTONOMOUS_OPS_MONITORS.md`, `docs/STANDARDIZED_HEALTH_ENVELOPE.md`, `openclaw/AUTONOMOUS_OPS_EXTENSION_IMPLEMENTATION.md`.
- **Audit/governance scripts:** `scripts/operator_only_adapter_audit.py`, `scripts/capabilities_report.py`, `scripts/capabilities_filter.py`; `tooling/coordination_validator.py`, `scripts/validate_coordination_mailbox.py`; `scripts/memory_retention_report.py`, `scripts/validate_memory_records.py`; `tooling/policy_validator.py` (open; policy packs would be curated policies).
- **Deployment:** Emitted `Dockerfile`, `docker-compose.yml`, `k8s.yaml` from `scripts/run_tests_and_emit.py`; `services/runtime_runner/` for runner.

### Missing pieces
- **Supported monitor pack:** Formal runbook (install, config, cron setup, health envelope consumption); versioning and changelog for “pack”; SLA definition; support channel and response targets.
- **Governance package:** One or more curated policy packs (e.g. “no network in this workspace”) that plug into open `policy_validator.py`; packaging and support; no new strategy.
- **Deployment kit:** Documented playbook (e.g. K8s/terraform) and hardening checklist; SSO/integration if required later.

### Recommended first build steps
1. **Supported ops monitor pack:** Pick 2–3 monitors (e.g. infrastructure watchdog, meta_monitor, token cost tracker). Write a single “Supported monitor pack” runbook (install, env, cron, health envelope). Define “update” (e.g. quarterly) and “support” (response time). Ship as a bundle (same open programs + runbook + support agreement). Do not close the examples.
2. **Governance audit package:** Add one curated policy pack (JSON + doc) that uses open `policy_validator.py`. Package `operator_only_adapter_audit` + capability report + coordination validator + memory retention report as “governance audit” with a short integration doc and support. Do not build a new platform; package and support existing scripts.
3. **Deployment kit:** Document current Docker/K8s emit and runner service as “reference deployment”; add a short hardening/checklist doc. Defer full SSO/terraform until there is a customer ask.

### What to defer
- Premium connector packs until we have a deep, support-heavy integration (per boundary).
- Multiple policy packs or vertical-specific packs until we have evidence of demand.
- Building new governance tooling; package and support what exists.

---

## 3. Expert Services

### First deliverable
**Structured onboarding / implementation review** — Defined engagement: review customer’s use of AINL (conformance, adapter usage, ops patterns); deliver a short report and success plan using existing docs (e.g. BOT_ONBOARDING, OPENCLAW_IMPLEMENTATION_PREFLIGHT, CONFORMANCE). Follow-on: **SLA-backed support** once we have a way to receive, route, and respond to requests.

### Repo grounding
- **Contact:** `COMMERCIAL.md` — “Open a GitHub issue/discussion requesting commercial contact.”
- **Onboarding content:** `docs/BOT_ONBOARDING.md`, `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`, `docs/CONFORMANCE.md`, `docs/RELEASE_READINESS.md`, `docs/DOCS_INDEX.md`; `tooling/bot_bootstrap.json`.
- **No existing:** Support portal, certification program, or formal onboarding playbook.

### Missing pieces
- **Onboarding:** Defined process (intake, scope, deliverables); template report; pricing/engagement terms.
- **Support:** Issue routing; response-time targets; entitlement (who gets support); optionally a dedicated channel or queue.
- **Certification:** Curriculum and assessment; not needed for first deliverable.
- **Consulting:** Ad hoc; can be offered as-is without new build.

### Recommended first build steps
1. **Onboarding:** Document a single “implementation review” offering: inputs (repo or description), outputs (short conformance/usage report + recommendations), process (e.g. 1–2 calls + async review). Use existing docs as the checklist. Publish the offering (e.g. in COMMERCIAL.md or a one-pager) and route inquiries from COMMERCIAL.md.
2. **Support:** Define “support” (e.g. GitHub issue with label, or email) and target response times. Add to COMMERCIAL.md. Defer heavy tooling until volume justifies it.
3. **Certification / consulting:** Wait. Certification needs curriculum and assessment; consulting can be sold as expert labor without new product.

### What to defer
- Certification program until we have repeated demand (per Discuss later).
- Custom support infrastructure until we have paying customers and clear volume.
- New monetization strategy or boundary changes.

---

## Summary table

| Pillar | First deliverable | Repo assets used | Build first | Wait |
|--------|-------------------|------------------|-------------|------|
| **Managed Platform** | Managed alignment pipeline (we run cycle, run health, SLA) | run_alignment_cycle.sh, sweep, eval, alignment_run_health.json; runtime_runner_service, Docker | One product shape + runbook + execution path; or hosted runner with auth + queue | Full multi-tenant; thin dashboard |
| **Enterprise Governance** | Supported ops monitor pack (runbooks + updates + SLA) or Governance audit package (scripts + 1 policy pack + support) | run_*.py, AUTONOMOUS_OPS_MONITORS, health envelope; operator_only_audit, capabilities_*, coordination_validator, memory_retention_report, policy_validator | Runbook + support definition; one policy pack + packaging | Premium connectors; many policy packs |
| **Expert Services** | Structured onboarding / implementation review | COMMERCIAL.md, BOT_ONBOARDING, PREFLIGHT, CONFORMANCE, DOCS_INDEX | Defined engagement + template report + routing from COMMERCIAL | Certification; heavy support tooling |

---

## Alignment with locked boundary

- **Managed:** Delivers on “we run sweep, eval gate, trends; SLA” and “run at scale” without paywalling the open pipeline or runner. Dashboard is explicitly deferred until we can deliver meaningful operational value (per decision sheet).
- **Enterprise:** Delivers on “supported ops monitor pack” and “governance/audit suite” by packaging existing open scripts and one policy pack with support—no thin wrapper; examples stay open.
- **Expertise:** Delivers on “onboarding” and “support” using existing docs and COMMERCIAL.md contact; certification and consulting deferred per boundary.

These are realistic first steps because they reuse existing repo assets, add packaging/process/support rather than new product from scratch, and respect the boundary (no paywalling of language legitimacy; no thin wrappers as premium).

---

*This document is execution planning only. It does not change the open-core boundary, runtime/compiler semantics, licenses, or product code. Boundary is locked; see `docs/OPEN_CORE_DECISION_SHEET.md` and `docs/OPEN_CORE_REVIEW_CHECKLIST.md`.*
