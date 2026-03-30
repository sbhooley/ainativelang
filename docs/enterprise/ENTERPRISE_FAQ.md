# Enterprise AINL: Frequently Asked Questions

**Last updated**: March 2026

---

## General Questions

### Q: What is AINL?

AINL (AI Native Language) is a programming language for deterministic AI workflows. It compiles to validated graphs with immutable audit trails, making it suitable for regulated industries.

### Q: How does AINL differ from LangGraph or Temporal?

- **Deterministic by default** – same input always produces same execution path
- **Compile-time validation** – catch graph errors before runtime
- **Token efficient** – 90-95% reduction in orchestration tokens
- **Audit-ready** – JSONL execution tapes for compliance

### Q: Is AINL open-source?

Yes. The core language, compiler, runtime, and adapters are Apache 2.0 licensed.

We offer **commercial extensions** (hosted runtimes, enterprise support, compliance tooling) under separate terms.

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

Enterprise cloud supports Vault, AWS Secrets Manager, Azure Key Vault integrations.

### Q: What are the resource requirements?

- **CLI/runner**: ~200MB RAM, minimal CPU
- **Hosted runtime**: Scales horizontally; each tenant isolated
- **Local models** (Ollama): 8GB+ RAM recommended for 70B parameter models

---

## Compliance & Security

### Q: Is AINL SOC 2 compliant?

AINL's design aligns with SOC 2 Trust Services Criteria:
- **CC6.1** – Logical access controls (RBAC)
- **CC7.2** – Monitoring of system operations (execution traces)
- **CC8.1** – Integrity of data processing (deterministic graphs)

Our **enterprise offering** provides automated evidence bundles for auditors. The open-core version provides the tools; you're responsible for your SOC 2 audit.

### Q: Can AINL handle HIPAA-protected information (PHI)?

Yes, with proper configuration:
- Never log PHI in execution traces (scrub or hash)
- Use encrypted transport (HTTPS, TLS 1.2+)
- Store PHI only in compliant databases with access controls
- Enable strict mode to prevent accidental data leakage

Enterprise support includes HIPAA Business Associate Agreement (BAA) addendum.

### Q: What about GDPR?

AINL supports GDPR through:
- **Right to erasure** – delete execution traces on request
- **Data minimization** – explicit data flow; no hidden LLM storage
- **Controller/processor distinction** – you are data controller; AINL is processor (in hosted model)

### Q: How do you ensure immutable audit logs?

Execution traces (`--trace-jsonl`) can be:
- Written to append-only storage (WORM, S3 Object Lock)
- Hash-chained for tamper evidence
- Forwarded to SIEM (Splunk, Datadog, Elastic)

Enterprise cloud includes tamper-evident audit log service out of the box.

---

## Performance & Reliability

### Q: What is the uptime SLA for hosted runtimes?

Enterprise tier SLA: **99.9%** monthly uptime (excluding planned maintenance).

This applies to the hosted runtime service only. You are responsible for your graph logic.

### Q: How do you handle node failures?

AINL supports:
- **Retries** – automatic with backoff
- **Circuit breakers** – stop calling failing services
- **Fallback nodes** – alternate logic on failure
- **Alerting** – Webhook notifications on node errors

Enterprise customers get PagerDuty/Opsgenie integration.

### Q: What about performance at scale?

Hosted runtimes support:
- **Autoscaling** – Add workers based on queue depth
- **Priority queues** – Critical graphs run first
- **Rate limiting** – Per-tenant quotas
- **Cold start mitigation** – Keep workers warm (configurable)

Typical latencies:
- LLM node: 1–5s (depending on model)
- HTTP node: <100ms (local services), 200–1000ms (external APIs)
- Internal nodes: <10ms

---

## Commercial & Support

### Q: How much does enterprise AINL cost?

Pricing is usage-based:
- **Managed Runtime**: $0.15 per 1,000 graph executions + compute time
- **Enterprise Governance**: $2,000/mo base fee (includes RBAC, compliance tooling)
- **Premium Support**: $5,000/mo for 24/7 SLA with 2-hour response

Exact pricing depends on volume and commitment term. [Contact sales](/contact?topic=enterprise) for a quote.

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
| Hosted runtimes (SaaS) | ❌ | ✅ |
| SSO / SAML | ❌ | ✅ |
| RBAC & audit logs | ❌ (you build) | ✅ (out of box) |
| Compliance automation | ❌ (you configure) | ✅ (generated) |
| SLA-backed support | ❌ | ✅ |
| 24/7 phone support | ❌ | ✅ |

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

**No.** Enterprise billing is via invoice or credit card. $AINL tokens are for community features only (governance, template marketplace, contributor rewards).

Our enterprise customers should **not** hold tokens for business operations.

### Q: What is the token utility?

$AINL token powers:
- Governance voting (feature prioritization)
- Access to premium templates (token-gated)
- Contributor rewards (templates, docs, tutorials)
- Early feature access (staking)

Token economics are separate from enterprise SaaS revenue.

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

In production, always use `--trace-jsonl` to see what happened.

---

## Contact

- **Enterprise Sales**: enterprise@ainativelang.com
- **Support**: support@ainativelang.com (enterprise customers)
- **General**: GitHub Discussions or Discord
- **Security**: security@ainativelang.com (encrypted PGP available)

---

**Need more answers?** Start a [discussion](https://github.com/sbhooley/ainativelang/discussions) or [contact us](/contact).
