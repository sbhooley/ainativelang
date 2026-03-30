# Next Steps After the Basics

Congratulations on completing the first three tutorials! You now understand:

✅ What AINL is and when to use it
✅ How to install and configure adapters
✅ How to build a monitoring agent with graphs, nodes, and routing
✅ The validate → run workflow and execution tracing

## Choose Your Path

AINL has something for everyone. Pick the track that matches your goals:

---

## 👨‍💻 For Developers Who Build Things

You've seen the basics. Now go deeper:

### Intermediate Path (2-4 weeks)

1. **[Adapters Intermediate](../intermediate/adapters/README.md)**
   - Build custom adapters for your internal tools
   - Implement rate limiting, retries, circuit breakers
   - Connect to databases, message queues, APIs

2. **[Emitters](../intermediate/emitters/README.md)**
   - Compile to LangGraph if you need their ecosystem
   - Emit to Temporal for durable workflows
   - Generate FastAPI servers with OpenAPI docs

3. **[Graphs & IR](../intermediate/graphs-and-ir.md)**
   - Understand the Intermediate Representation (IR)
   - Optimize graphs for token efficiency
   - Compile-time vs runtime evaluation

4. **[Testing Strategies](../intermediate/testing.md)**
   - Unit test individual nodes
   - Integration test full graphs with mocks
   - Property-based testing with hypothesis

5. **[Monitoring & Observability](../intermediate/monitoring.md)**
   - Set up health envelopes
   - Build Grafana dashboards from traces
   - Alert on anomalies

### Project Ideas

- **Personal automation**: Morning briefing agent that checks weather, calendar, news
- **Data pipeline**: nightly ETL with validation at each step
- **API aggregator**: Single endpoint that fans out to multiple services
- **Chatbot with memory**: RAG system with vector DB retrieval

---

## 🏢 For Enterprise Teams

You care about compliance, support, and production guarantees.

### Enterprise Path (Immediate)

1. **[Enterprise Deployment](../enterprise/deployment.md)**
   - Hosted runtimes vs self-hosting
   - Multi-tenant isolation patterns
   - Secrets management (Vault, AWS Secrets Manager)

2. **[Compliance Framework](../enterprise/compliance.md)**
   - SOC 2 mapping (CC6.1, CC7.2, CC8.1)
   - HIPAA considerations for PHI
   - GDPR data handling patterns
   - Automated evidence bundle generation

3. **[Security Hardening](../enterprise/security.md)**
   - Network policies and egress controls
   - Token budget policies per environment
   - RBAC for graph execution
   - Immutable audit logs

4. **[SRE & Operations](../enterprise/sre.md)**
   - Runbook templates
   - Incident response with execution traces
   - Capacity planning and autoscaling
   - Disaster recovery

5. **[Support & SLAs](../enterprise/support.md)**
   - Understanding enterprise support tiers
   - What's covered vs. not covered
   - Escalation paths and response times
   - Implementation review process

### Enterprise Adoption Checklist

- [ ] Deploy to staging with production-like data
- [ ] Validate policy compliance (run `ainl validate --strict`)
- [ ] Set up trace aggregation (Loki, Datadog, Splunk)
- [ ] Configure alerting on node failures or budget exceedance
- [ ] Conduct tabletop incident response drill
- [ ] Sign enterprise agreement for SLA coverage

**Contact**: [Enterprise Sales](/enterprise) for hosted runtime trials.

---

## 🧠 For AI Researchers & Experimenters

You want reproducible experiments and clean evaluation pipelines.

### Research Path

1. **[Deterministic Evaluation](../advanced/experiment-design.md)**
   - Fixed seed graphs for fair comparison
   - Metrics collection across runs
   - Ablation studies via graph variants

2. **[Fine-tuning Integration](../how-to/finetune-model.md)**
   - Generate training data from execution traces
   - Evaluate fine-tuned models in AINL graphs
   - A/B test with canary deployments

3. **[Benchmarking](../reference/benchmarks.md)**
   - Compare token efficiency vs LangGraph/Temporal
   - Measure latency through each node
   - Cost per successful execution

4. **[Latent Space Analysis](../advanced/sae-analysis.md)** (if supported)
   - Extract activations from LLM nodes
   - Visualize decision boundaries
   - Detect model drift over time

---

## 🤝 For Community Contributors

You want to help others and earn $AINL tokens.

### Community Path

1. **[Token Utility](../community/token)** – Understand how $AINL works
2. **[Template Marketplace](../how-to/create-template.md)** – Submit reusable templates
3. **[Documentation Guide](../reference/contributing.md)** – Write tutorials and examples
4. **[Champions Program](../community/champions.md)** – Become a recognized leader

**Earn tokens by:**
- Submitting high-quality templates (10k–100k $AINL each)
- Writing tutorials (5k–50k $AINL depending on depth)
- Answering questions in Discussions (weekly rewards)
- Organizing local meetups or streams

---

## 📚 Reference Materials

### By Topic

| Topic | Where to Go |
|-------|-------------|
| CLI commands | [CLI Reference](../reference/cli-reference.md) |
| Configuration | [Config Reference](../reference/config-reference.md) |
| Schema formats | [Schemas](../reference/schemas/) |
| Emitters | [Emitter Docs](../intermediate/emitters/) |
| MCP integration | [MCP Guide](../how-to/integrate-mcp.md) |
| Migration from LangGraph | [Migration Guide](../how-to/migrate-from-langgraph.md) |
| Troubleshooting | [FAQ](../enterprise/faq.md) |

### Quick Navigation

```
docs/
├── learning/
│   ├── basics/          # You are here
│   ├── intermediate/   # Next stop for most users
│   ├── enterprise/     # For business deployments
│   └── advanced/       # For deep technical dives
├── reference/           # Look up specific details
├── how-to/             # Task-oriented recipes
└── examples/           # Copy-paste starting points
```

---

## Keep Learning

### Weekly Content Series

Check the **[AINL Blog](https://ainativelang.com/blog)** for:
- Mondays: Competitive comparisons (AINL vs X)
- Wednesdays: Real-world case studies
- Fridays: Deep technical dives
- Monthly: Community showcase and token rewards

### Community Resources

- **Discussions**: <https://github.com/sbhooley/ainativelang/discussions>
- **Discord**: `#beginners`, `#help`, `#showcase`
- **YouTube**: AINL channel with build-alongs
- **Office Hours**: Fridays 2pm PT (Zoom link in Discord)

### Stay Updated

- **Newsletter**: [Subscribe](https://ainativelang.com/newsletter) for monthly updates
- **Twitter/X**: `@sbhooley` for announcements
- **Release Notes**: `docs/CHANGELOG.md`

---

## What's Missing?

Did you hit a wall? Let us know:

1. **[Search existing issues](https://github.com/sbhooley/ainativelang/issues?q=is%3Aissue+is%3Aopen)** – Someone might have answered
2. **[Ask in Discussions](https://github.com/sbhooley/ainativelang/discussions)** – Community will help
3. **[Open an issue](https://github.com/sbhooley/ainativelang/issues/new)** – Report bugs or request docs

Feedback on these tutorials? **[Start a discussion](https://github.com/sbhooley/ainativelang/discussions/categories/ideas)** about how to improve the learning experience.

---

**Ready for more?** Pick a path above and dive in. Happy AINL-ing!
