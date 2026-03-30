# Production Patterns for AINL

Common patterns and reusable templates for production AINL deployments.

---

## 📂 Pattern Categories

### Monitoring & Alerting
- Email/Slack alert on error classification
- Metric collection and threshold alerts
- Health check workflows
- Cron-based periodic checks

### Data Processing
- ETL pipelines with validation at each stage
- Data enrichment (LLM + deterministic transforms)
- Batch processing with error handling
- Schema migration workflows

### API Orchestration
- API aggregation (fan-out, combine results)
- Authentication and rate limiting
- Retry patterns with circuit breakers
- Request/response transformation

### Compliance & Audit
- Immutable audit trail generation
- GDPR erasure workflows
- SOC 2 evidence collection
- Data lineage tracking

### Integration Patterns
- Database sync (change data capture)
- Message queue consumers (Kafka, RabbitMQ)
- Webhook handlers with idempotency
- File-based ETL (watchers, processors)

---

## 🎯 How to Use Patterns

1. **Start with a pattern** that matches your use case
2. **Copy the example** to your project
3. **Customize** for your specific data and APIs
4. **Validate and test** before deploying to production

Each pattern includes:
- ✅ Complete `.ainl` file with comments
- ✅ Explanation of why this pattern works
- ✅ Configuration tips (adapters, policies)
- ✅ Testing strategy
- ✅ Production considerations (monitoring, scaling)

---

## 📖 Pattern Index

| Pattern | Complexity | Use Case | See Also |
|---------|------------|----------|----------|
| [Email Alert Classifier](email-alert-classifier.md) | Beginner | Route alerts by severity | [monitoring.ainl](../../examples/monitoring/) |
| [Retry with Backoff](retry-backoff.md) | Beginner | Resilient external API calls | [testing.md](../testing.md) |
| [Cache Warmup](cache-warmup.md) | Intermediate | Pre-populate caches reduce LLM calls | [adapters/](../adapters/) |
| [Data Validation Pipeline](data-validation-pipeline.md) | Intermediate | Schema checks + LLM verification | [graphs-and-ir.md](../graphs-and-ir.md) |
| [Idempotent Webhook](idempotent-webhook.md) | Intermediate | Handle duplicate events safely | [monitoring.md](../monitoring.md) |
| [Idempotent API Calls](idempotent-api-calls.md) | Intermediate | Safe retries for POST/PUT operations | [retry-backoff.md](retry-backoff.md) |
| [Template Submission](template-marketplace-submission.md) | All | Submit your own patterns | — |

| [Email Alert Classifier](email-alert-classifier.md) | Beginner | Route alerts by severity | [monitoring.ainl](../examples/monitoring/) |
| [Retry with Backoff](retry-backoff.md) | Beginner | Resilient external API calls | [testing.md](../testing.md) |
| [Data Validation Pipeline](data-validation.md) | Intermediate | Schema checks + LLM verification | [graphs-and-ir.md](../graphs-and-ir.md) |
| [Cache Warmup](cache-warmup.md) | Intermediate | Pre-populate caches reduce LLM calls | [adapters/](../adapters/) |
| [Idempotent Webhook](idempotent-webhook.md) | Intermediate | Handle duplicate events safely | [monitoring.md](../monitoring.md) |
| [Multi-Stage Approval](multi-stage-approval.md) | Intermediate | Human-in-the-loop workflows | [emitters/](../emitters/) |
| [Canary Deployment](canary-deployment.md) | Advanced | Gradual rollout with feature flags | [testing.md](../testing.md) |
| [Cross-Graph Orchestration](cross-graph.md) | Advanced | Chain multiple AINL graphs | [emitters/](../emitters/) |

---

## 🚀 Quick Start

Most common pattern: **Email Alert Classifier**

```ainl
graph AlertClassifier {
  input: Alert = { level: string, message: string }
  
  node classify: LLM("classify") {
    prompt: "Classify severity: {{input.message}}"
  }
  
  node route: switch(classify.result) {
    case "CRITICAL" -> slack
    case "WARNING" -> email
    case "INFO" -> log
  }
  
  node slack: HTTP("slack") { /* config */ }
  node email: HTTP("email") { /* config */ }
  node log: WriteFile("log") { /* config */ }
  
  output: { severity: classify.result, action: route.result }
}
```

**Next**: [Email Alert Classifier pattern](email-alert-classifier.md)

---

## 📊 Pattern Selection Guide

| Your Need | Start With |
|-----------|------------|
| "I need to monitor something and send alerts" | Email Alert Classifier |
| "I'm calling an external API that sometimes fails" | Retry with Backoff |
| "I need to validate data before processing" | Data Validation Pipeline |
| "I want to reduce LLM costs" | Cache Warmup |
| "I'm handling webhooks from Stripe/SendGrid" | Idempotent Webhook |
| "I need manager approval before actions" | Multi-Stage Approval |
| "I'm rolling out a new graph to production" | Canary Deployment |
| "I have multiple graphs that need to work together" | Cross-Graph Orchestration |

---

## 🔍 Pattern Depth Levels

**Beginner** patterns:
- Straightforward, single-graph
- Minimal external dependencies
- Easy to test and debug
- Good starting point for learning

**Intermediate** patterns:
- Multiple branches and error handling
- Integration with external systems (DBs, queues)
- State management considerations
- Production-ready with monitoring

**Advanced** patterns:
- Multi-graph orchestration
- Complex state transitions
- Scalability concerns
- Requires understanding of AINL runtime internals

---

## 🤝 Contribute a Pattern

Found a useful pattern? Share it with the community:

1. Fork the AINL repository
2. Add your pattern to `docs/learning/intermediate/patterns/`
3. Include: `.ainl` file + `README.md` explaining the pattern
4. Submit PR with `pattern` label

**Earn $AINL tokens** for accepted patterns (5,000–20,000 depending on quality and complexity).

---

## 📚 More Examples

For additional examples, see:
- [`examples/golden/`](https://github.com/sbhooley/ainativelang/tree/main/examples/golden) – Curated best practices
- [`examples/monitoring/`](https://github.com/sbhooley/ainativelang/tree/main/examples/monitoring) – Production monitoring workflows
- [`examples/enterprise/`](https://github.com/sbhooley/ainativelang/tree/main/examples/enterprise) – Enterprise-grade patterns

---

**Ready to build?** Pick a pattern and start adapting it to your needs.
