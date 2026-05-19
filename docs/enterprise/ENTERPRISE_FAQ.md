# Enterprise AINL: Frequently Asked Questions

**Last updated**: May 2026

**Enterprise index:** [`README.md`](README.md) · **Shared responsibility (canonical):** [`SHARED_RESPONSIBILITY.md`](SHARED_RESPONSIBILITY.md) · **Evidence bundle recipe:** [`EVIDENCE_BUNDLE_RECIPE.md`](EVIDENCE_BUNDLE_RECIPE.md) · **Telemetry surfaces:** [`../operations/AUDIT_AND_TELEMETRY_MAP.md`](../operations/AUDIT_AND_TELEMETRY_MAP.md) · **Repo reality vs design:** [`../../STATUS.yaml`](../../STATUS.yaml)

---

## General Questions

### Q: What is AINL?

AINL (AI Native Language) is a programming language for deterministic AI workflows. It compiles to validated intermediate representation (IR) with **explicit, reviewable** execution paths. For **structured execution evidence** (JSONL traces, optional audit adapter, HTTP runner logs), see the telemetry map and shared-responsibility doc—retention and immutability are **operator-owned** when you self-host.

### Q: How does AINL differ from LangGraph or Temporal?

- **Deterministic by default** – same input always produces same execution path
- **Compile-time validation** – catch graph errors before runtime
- **Token efficient** – 90-95% reduction in orchestration tokens
- **Audit-ready (technical)** – optional **CLI trajectory JSONL**, optional **`audit_trail`** adapter, and **HTTP runner** structured logs; see [`../operations/AUDIT_AND_TELEMETRY_MAP.md`](../operations/AUDIT_AND_TELEMETRY_MAP.md)

### Q: Is AINL open-source?

Yes. The core language, compiler, runtime, and adapters are Apache 2.0 licensed.

**Commercial** offerings, support SLAs, and any managed services are described separately—see [`COMMERCIAL.md`](../../COMMERCIAL.md). Several **hosted / marketplace** concepts are **not** shipped as open-source product surfaces today; see **`aspirational_not_built`** in [`STATUS.yaml`](../../STATUS.yaml) for the honesty contract.

---

## Technical & Integration

### Q: What LLM providers are supported?

Open-source adapters exist for:
- OpenRouter (50+ models)
- Ollama (local models)
- Anthropic (MCP via Claude Desktop)
- OpenAI (direct API)
- Custom adapters can be built for internal LLMs

### Q: Can AINL integrate with our existing tools?

Yes. Adapters exist for:
- **HTTP/REST APIs** – any web service
- **Databases** – PostgreSQL, MySQL, SQLite
- **Message queues** – RabbitMQ, Kafka (via HTTP bridge)
- **Monitoring** – Prometheus, Datadog, OpenTelemetry
- **Enterprise** – Salesforce, SAP, ServiceNow (custom adapters)

### Q: How do you handle secrets?

AINL never logs secrets. Use environment variables or external secret managers:

```ainl
node api: HTTP("call-service") {
  url: "https://api.example.com"
  headers: {
    Authorization: "Bearer ${env.API_KEY}"
  }
}
```

Secrets are consumed from **your** environment (env vars, secret managers, orchestrator-injected files). AINL does not replace Vault, AWS Secrets Manager, or Azure Key Vault—**you** wire those into the process.

### Q: What are the resource requirements?

- **CLI / self-hosted runner**: ~200MB RAM, minimal CPU (workload-dependent)
- **Managed / hosted runtime** (if offered under commercial terms): sizing and isolation are per order form—**not** part of the OSS repo’s shipped surface; see [`STATUS.yaml`](../../STATUS.yaml) and [`COMMERCIAL.md`](../../COMMERCIAL.md)
- **Local models** (Ollama): 8GB+ RAM recommended for 70B parameter models

---

## Compliance & Security

### Q: Is AINL SOC 2 compliant?

**No**—SOC 2 is an **organizational attestation**, not a property of a language runtime. AINL’s **design and shipped logs** can **support evidence** that your team maps to common TSC themes (see [`SOC2_CHECKLIST.md`](SOC2_CHECKLIST.md) and [`../operations/AINL_SOC2_CONTROL_MAPPING.md`](../operations/AINL_SOC2_CONTROL_MAPPING.md)). **You** run the audit program, SIEM, retention, and access control.

**Open-core:** use [`EVIDENCE_BUNDLE_RECIPE.md`](EVIDENCE_BUNDLE_RECIPE.md) to assemble artifacts (strict check output, traces, optional `audit_trail`, runner logs). **Commercial** packaging of evidence or managed services—if offered—is described in [`COMMERCIAL.md`](../../COMMERCIAL.md), not implied by the OSS repo alone.

### Q: Can AINL handle HIPAA-protected information (PHI)?

Yes, with proper configuration:
- Never log PHI in execution traces (scrub or hash)
- Use encrypted transport (HTTPS, TLS 1.2+)
- Store PHI only in compliant databases with access controls
- Enable strict mode to prevent accidental data leakage

HIPAA-aligned deployments require **your** BAA coverage, PHI handling in logs, and infrastructure choices. AINL documentation does not constitute a BAA; engage legal and commercial channels if you need contractual HIPAA terms.

### Q: What about GDPR?

GDPR compliance is **program + deployment** work. AINL can help with **data minimization in design** (explicit graph data flow) and **deletion of artifacts you control** (trace files, databases you configure). **Controller vs processor** roles depend on **how** you deploy (self-hosted vs any future hosted offering). See [`SHARED_RESPONSIBILITY.md`](SHARED_RESPONSIBILITY.md).

### Q: How do you ensure immutable audit logs?

**Immutability is not automatic.** Execution traces (`--trace-jsonl` / `--log-trajectory`) and `audit_trail` JSONL are **files or streams you operate**:

- You may write them to **append-only** or **WORM** storage (S3 Object Lock, etc.).
- `audit_trail` records include an **`event_hash`**; verify with `ainl audit verify-jsonl` (see [`EVIDENCE_BUNDLE_RECIPE.md`](EVIDENCE_BUNDLE_RECIPE.md)).
- Forward to your **SIEM** (Splunk, Datadog, Elastic, …).

**Managed** tamper-evident log SaaS is **not** claimed as an open-source shipped product; see [`STATUS.yaml`](../../STATUS.yaml) and [`COMMERCIAL.md`](../../COMMERCIAL.md) for what may exist commercially.

---

## Performance & Reliability

### Q: What is the uptime SLA for hosted runtimes?

SLA-backed hosted offerings—if and when purchased—are governed by **your order form** and [`COMMERCIAL.md`](../../COMMERCIAL.md), not this FAQ. Self-hosted open-core has **no** uptime SLA from the repo.

### Q: How do you handle node failures?

AINL supports:
- **Retries** – automatic with backoff
- **Circuit breakers** – stop calling failing services
- **Fallback nodes** – alternate logic on failure
- **Alerting** – Webhook notifications on node errors

Enterprise customers get PagerDuty/Opsgenie integration.

### Q: What about performance at scale?

**Self-hosted:** scale your runner processes, queues, and infra like any service. **Commercial hosted** shapes (if offered) may include autoscaling and quotas per contract—see [`COMMERCIAL.md`](../../COMMERCIAL.md).

Typical latencies (indicative, not a guarantee):
- LLM node: 1–5s (depending on model)
- HTTP node: &lt;100ms (local services), 200–1000ms (external APIs)
- Internal nodes: &lt;10ms

---

## Commercial & Support

### Q: How much does enterprise AINL cost?

Illustrative figures may appear in older collateral; **authoritative** commercial terms are in [`COMMERCIAL.md`](../../COMMERCIAL.md) and your quote. [Contact sales](/contact?topic=enterprise) for current pricing.

### Q: What support tiers are available?

| Tier | Response Time | Included |
|------|---------------|----------|
| Community | Best effort | GitHub Discussions, Discord |
| Business | 8 hours | Email support, bug fixes |
| Enterprise | 2 hours (24/7) | Slack channel, phone, architecture review |

### Q: Do we need to purchase support to use AINL?

No. The open-core version is free and fully functional.

Enterprise support and hosted runtimes are optional paid services.

### Q: What is the difference between open-core and commercial?

| Feature | Open Core (Free) | Commercial |
|---------|-----------------|------------|
| Language & compiler | ✅ | ✅ |
| CLI & local runner | ✅ | ✅ |
| Basic adapters | ✅ | ✅ |
| Self-hosted deployment | ✅ | ✅ |
| Structured execution evidence (trajectory, runner audit, `audit_trail`) | ✅ (you operate log path / SIEM) | May include packaged support—see [`COMMERCIAL.md`](../../COMMERCIAL.md) |
| Hosted runtimes (SaaS) | ❌ in OSS repo ([`STATUS.yaml`](../../STATUS.yaml)) | If offered—see [`COMMERCIAL.md`](../../COMMERCIAL.md) |
| SSO / SAML | ❌ in OSS | If offered—commercial |
| Central RBAC for AINL product | ❌ (your IdP + deployment) | If offered—commercial |
| SLA-backed support | ❌ | If purchased |
| 24/7 phone support | ❌ | If purchased |

---

## Development & Workflow

### Q: Can I develop locally and deploy to hosted runtime?

Yes. Write and test locally with `ainl validate` and `ainl run`. When ready, push graphs to your hosted runtime via API or CLI.

AINL's "write once, run anywhere" philosophy means your graph is portable.

### Q: How do I version control AINL graphs?

AINL files are plain text. Use Git like any code:

```bash
git add monitor.ainl
git commit -m "Add error classification node"
git push origin main
```

We recommend branching strategies:
- `main` – production graphs
- `staging` – pre-production validation
- `feature/*` – experimental graphs

### Q: What is the release cadence?

- **Minor releases** (1.3.x): Every 2 weeks (bug fixes, small features)
- **Major releases** (1.x → 2.0): Every 6-12 months (breaking changes)

We follow [SemVer](https://semver.org/). Breaking changes bump major version.

---

## Migration & Adoption

### Q: Can we migrate from LangGraph?

Yes. Common migration steps:
1. Export LangGraph state machines to AINL graphs
2. Replace `ConditionalEdges` with `switch` statements
3. Remove LLM call nodes where AINL nodes are deterministic
4. Validate and test against same inputs
5. Deploy to hosted runtime or self-host

We provide a [migration guide](../how-to/migrate-from-langgraph.md) and tools.

### Q: How long does enterprise onboarding take?

Typical timeline:
- **Week 1**: Training, sandbox environment, first graph deployment
- **Week 2-3**: Integration with CI/CD, monitoring setup
- **Week 4**: Production rollout, compliance review

Enterprise support includes implementation onboarding package.

### Q: Do you offer training?

Yes:
- **Public workshops**: Monthly, free for community
- **Private training**: 2-day on-site or virtual for enterprise customers
- **Self-paced**: Tutorials in `docs/learning/` and video library

---

## Token & Community

### Q: Does enterprise require holding $AINL tokens?

**No.** Enterprise billing is via invoice or credit card. $AINL tokens are for community features only, and most of those features are **planned and not yet shipped** (governance, template marketplace, contributor reward payouts, premium template gating — see status below).

Our enterprise customers should **not** hold tokens for business operations.

### Q: What is the token utility?

$AINL is intended to power community features. **Current shipping status** of each utility:

- **Token exists on Solana** — ✅ shipped. Mint: `56hrCR3n7danhHNjWaU4VeUHpE1eRE9VRBWpHRPKpump`. Live metrics in [`tooling/token_status.json`](../../tooling/token_status.json).
- **Governance voting (feature prioritization)** — 📋 planned (no Snapshot space or vote yet).
- **Access to premium templates (token-gated)** — 📋 planned (no premium-template gating implemented; everything is open-source today).
- **Contributor rewards (templates, docs, tutorials)** — 📋 planned (originally-published reward schedule in [`docs/learning/intermediate/patterns/template-marketplace-submission.md`](../learning/intermediate/patterns/template-marketplace-submission.md); **payouts have not begun**; treasury wallet not yet capitalized).
- **Early feature access (staking)** — 📋 planned (no staking contract).

Token economics are entirely separate from enterprise SaaS revenue. Enterprise customers are not exposed to $AINL — none of the planned community features above gate enterprise functionality.

---

## Troubleshooting

### Q: Validation fails but I don't understand the error

Check the error message carefully – it includes line numbers and node names.

Common fixes:
- Typos in variable names (AINL is case-sensitive)
- Missing required fields in node definitions
- Type mismatches between connected nodes

Still stuck? [Ask in Discussions](https://github.com/sbhooley/ainativelang/discussions).

### Q: Runtime errors: node fails but graph continues

By default, AINL tries to continue on node failure if possible. Use `strict` mode to fail fast:

```bash
ainl run graph.ainl --strict
```

In production, enable **trajectory logging** (`--trace-jsonl PATH` or `--log-trajectory` / `AINL_LOG_TRAJECTORY`) when you need per-step JSONL; see [`../trajectory.md`](../trajectory.md).

---

## Contact

- **Enterprise Sales**: enterprise@ainativelang.com
- **Support**: support@ainativelang.com (enterprise customers)
- **General**: GitHub Discussions or Discord
- **Security**: security@ainativelang.com (encrypted PGP available)

---

**Need more answers?** Start a [discussion](https://github.com/sbhooley/ainativelang/discussions) or [contact us](/contact).
