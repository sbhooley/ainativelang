# Metrics Dashboard & Monitoring Plan

Define KPIs, dashboards, and alerting for AINL adoption and operational health.

---

## 🎯 Goal

Track **business outcomes** (adoption, retention, revenue) alongside **technical health** (reliability, performance, cost).

---

## 📊 KPI Framework

### 1️⃣ Adoption Metrics

| Metric | Definition | Target (Q1-Q2 2026) | Source |
|--------|------------|--------------------|--------|
| **GitHub stars** | Public repository stars | 5,000 → 10,000 | GitHub API |
| **Weekly active users** | Unique `ainl run` executions / 7d | 500 → 2,000 | Self-reported via opt-in |
| **Average users** | Distinct email logins to docs/site | 200 → 1,000 | Google Analytics |
| **Enterprise leads** | Form submissions at /enterprise/contact | 10/mo → 50/mo | CRM |
| **OpenClaw integrations** | Active OpenClaw agents using AINL | 50 → 200 | OpenClaw telemetry |
| **Token holders** | Unique $AINL wallet holders | 1,500 → 5,000 | Solana RPC |
| **Revenue** | MRR from Enterprise SaaS | $0 → $50k/mo | Stripe |

---

### 2️⃣ Engagement Metrics

| Metric | Definition | Target | Source |
|--------|------------|--------|--------|
| **Docs pageviews** | /docs/* daily unique views | 500 → 2,000 | Google Analytics |
| **Tutorial completion** | Users who finish 1st agent tutorial | 30% | In-tutorial tracking |
| **Template submissions** | New templates / month | 5 → 25 | GitHub Discussions |
| **Champion applications** | Applications / quarter | 0 → 10 | Form responses |
| **GitHub contributions** | PRs merged / month | 20 → 50 | GitHub |
| **Discord active users** | Daily active Discord members | 100 → 500 | Discord analytics |

---

### 3️⃣ Technical Health Metrics

| Metric | Definition | SLA / Target | Source |
|--------|------------|--------------|--------|
| **Graph validation success rate** | % passing `ainl validate` | >99% | CI/CD logs |
| **Runtime success rate** | % executions complete without error | >99.5% | Execution traces |
| **P50 execution latency** | Median time from input to output | <2s (cloud LLM), <500ms (local) | Traces |
| **P99 execution latency** | 99th percentile | <10s | Traces |
| **Token budget adherence** | % runs under configured limit | 100% (hard limit) | Trace validation |
| **CI/CD build time** | Avg time from PR to merge | <15 min | GitHub Actions |
| **Test coverage** | Lines of AINL code covered by tests | >80% | `ainl test --coverage` |
| **Dependency vulnerabilities** | Known CVEs in dependencies | 0 critical | Dependabot / Renovate |
| **Documentation freshness** | Days since last doc update | <30 days | Git history |

---

### 4️⃣ Business Health Metrics

| Metric | Definition | Target | Source |
|--------|------------|--------|--------|
| **Lead-to-opportunity conversion** | % leads become qualified opportunities | 20% | CRM |
| **Opportunity-to-close rate** | % opportunities close as won | 30% | CRM |
| **Customer acquisition cost (CAC)** | Total sales & marketing / new customers | <$5k | Finance |
| **Customer lifetime value (LTV)** | Average revenue per customer over 2 years | >$50k | Finance |
| **LTV:CAC ratio** | LTV divided by CAC | >5:1 | Finance |
| **Churn rate** | % enterprise customers canceling / month | <2% | Stripe |
| **Net promoter score (NPS)** | Survey score (0-10) | >50 | SurveyMonkey |
| **Enterprise customer NRR** | Net revenue retention (expansion - churn) | >110% | Stripe |

---

## 📈 Dashboard Design

### Executive Dashboard (CEO/Board)

**Overview**: High-level health of AINL ecosystem.

Panels:
1. **Adoption funnel**: Stars → Active users → Enterprise leads → Customers
2. **Revenue chart**: MRR growth, LTV:CAC, churn
3. **Community metrics**: Discord active users, contributors, token holders
4. **Technical health**: Validation pass rate, runtime success rate

Refresh: Daily. Sent via email every Monday.

---

### Product Dashboard (Engineering + Product)

**Overview**: Technical health and feature adoption.

Panels:
1. **CI/CD health**: Build times, test pass rates, coverage trends
2. **Runtime metrics**: Latency (p50/p99), error rates by graph type
3. **Token efficiency**: Avg tokens / execution, budget exceedances
4. **Adapter usage**: Which LLM adapters most popular (OpenRouter vs Ollama)
5. **Emitter usage**: How many graphs emit to LangGraph, FastAPI, etc.
6. **Self-monitoring**: AINL monitoring itself (health envelope metrics)

Refresh: Every 5 minutes. Grafana or internal dashboard.

---

### Sales Dashboard (GTM Team)

**Overview**: Pipeline and conversion metrics.

Panels:
1. **Lead flow**: New leads by source (website, referral, event)
2. **Pipeline stages**: Leads → MQL → SQL → Opportunity → Won/Lost
3. **Conversion rates**: Stage-to-stage funnel
4. **Enterprise deals**: Deal size, sales cycle length, competitor mentioned
5. **Feature requests**: Most requested enterprise features (from calls)

Refresh: Real-time. Salesforce/Gemini dashboard.

---

### Community Dashboard (Developer Relations)

**Overview**: Community engagement metrics.

Panels:
1. **GitHub activity**: Issues opened/closed, PRs, stars, forks
2. **Documentation engagement**: Top pages, search queries, bounce rate
3. **Discord health**: Active users, message volume, help channels response time
4. **Champion program**: Applications, approvals, token distribution
5. **Template gallery**: Views, downloads, featured templates
6. **Blog post readership**: Views, time on page, shares

Refresh: Daily. Shared with community team.

---

## 🚨 Alerting Rules

### Critical (Page someone)

- **Validation success rate < 95%** (5 min window) – Something broke in compiler
- **Runtime error rate > 1%** (10 min window) – LLM or adapter failures
- **P99 latency > 30s** – Performance degradation affecting users
- **Security violation detected** – Hardcoded secret or unauthorized domain
- **Teammate reports**: Multiple issues from community

**Notification**: Slack #devops-alerts + PagerDuty (if no acknowledgment in 15 min)

---

### Warning (Notify channel)

- **Token budget exceedance** – Graph using > allocated tokens
- **CI/CD build time > 30 min** – Pipeline slowing down
- **Documentation stale** – No updates > 60 days for major pages
- **Lead volume drop > 30% WoW** – Marketing pipeline issue
- **Discord response time > 4 hours** – Community support lagging

**Notification**: Slack #warnings, email to responsible team

---

### Info (Log only)

- New GitHub star (if > 100/day, aggregate)
- New contributor merged PR (celebrate!)
- Enterprise deal closed (congrats channel)
- Tutorial completion milestone (100th, 500th, etc.)

---

## 📱 Monitoring Tools

### Technical Metrics

- **GitHub Actions** – CI/CD
- **Grafana Cloud** – Prometheus metrics + traces (Loki)
- **Datadog** – Infrastructure & custom metrics
- **Statuspal** – Status page for SaaS incidents

### Business Metrics

- **Stripe** – Revenue, churn, MRR
- **Google Analytics** – Website traffic, docs engagement
- **Mixpanel/Amplitude** – Product engagement (if we have login)
- **Salesforce** – Pipeline, leads, opportunities

### Community Metrics

- **Discord Analytics** – Active users, engagement
- **GitHub Insights** – Contribution metrics
- **Solana FM** – Token holder distribution
- **Twitter API** – Mentions, sentiment (future)

---

## 🔍 Data Collection Implementation

### Instrument AINL CLI

Add optional anonymous usage reporting (opt-in):

```bash
ainl config set telemetry.enabled true
```

Sends to `https://metrics.ainativelang.com`:
- Graph name, node count, adapter used
- Execution duration, token counts, success/failure
- No PII or graph contents (only metadata)

**Compliance**: Clear opt-in, data aggregation, can export and delete.

---

### Self-Monitoring Integration

Use AINL's own monitoring to track AINL usage:

IDEA: Run `ainl-monitor` as a cron job that:

1. Collects metrics from CLI usage logs (`~/.ainl/history.jsonl`)
2. Sends to internal Prometheus endpoint
3. Generates weekly report

---

## 📊 Public Metrics Page

Show some numbers publicly for transparency:

- `https://ainativelang.com/metrics` (public dashboard)
- Open-source friendly numbers:
  - Stars, forks, contributors
  - Docs pageviews (aggregate)
  - Active instances (rough estimate)
  - Token holders
  - Open issues/PRs

Keep sensitive metrics private (revenue, enterprise customer count).

---

## 🎯 Quarterly Review Process

Every quarter:

1. **Review** all dashboards with leadership
2. **Assess** progress against targets
3. **Adjust** targets for next quarter (moonshot vs realistic)
4. **Decide** on metric changes (add new, retire old)
5. **Publish** summary to team and (selectively) to community

---

## 🐛 Incident Response Metrics

During incidents (runtime outage, security breach):

- **MTTD** (Mean Time to Detect) – Target: <5 min
- **MTTR** (Mean Time to Resolve) – Target: <30 min (Severity 2), <4h (Severity 3)
- **Post-incident review** within 48 hours
- **Customer communication** within 1 hour of detection

Track these in post-mortem template.

---

## 📈 Success Criteria

By Q2 2026, we should see:

| Metric | Target (Q1) | Target (Q2) | Success? |
|--------|-------------|-------------|----------|
| GitHub stars | 5k | 10k | ✅ |
| Weekly active users | 500 | 1,000 | ✅ |
| Enterprise leads | 10/mo | 50/mo | 🟡 |
| MRR | $10k | $50k | 🟡 |
| Runtime success rate | 99.5% | 99.9% | ✅ |
| Validation success rate | 99% | 99.5% | ✅ |

🟡 = Needs more focus, ✅ = On track, 🔴 = Off track

---

## 🔗 Related Documents

- [STRATEGIC_GAME_PLAN.md](./STRATEGIC_GAME_PLAY.md) – Overall strategy
- [COMPETITIVE_MESSAGING.md](./competitive/COMPETITIVE_MESSAGING.md) – Battle cards
- [SELF_MONITORING_IMPLEMENTATION.md](../intelligence/monitor/README.md) – Technical setup

---

**Dashboard links** (internal):
- Grafana: https://grafana.ainativelang.com
- Salesforce: https://salesforce.my.salesforce.com
- Stripe: https://dashboard.stripe.com

---

*Last updated: 2026-03-30*  
*Owner: Head of Growth + Engineering Manager*
