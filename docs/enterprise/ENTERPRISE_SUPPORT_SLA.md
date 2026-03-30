# Enterprise Support SLA

**Service**: AINL Hosted Runtime & Enterprise Features  
**Effective Date**: March 2026  
**Last Updated**: March 30, 2026  
**Customers**: Enterprise subscription holders (Business tier and above)

---

## 1. Support Tiers & Response Times

| Tier | Severity 1 (Critical) | Severity 2 (High) | Severity 3 (Medium) | Severity 4 (Low) |
|------|---------------------|-------------------|--------------------|------------------|
| Business | 8 business hours | 24 hours | 3 business days | 5 business days |
| Enterprise | 2 hours ❄️ | 4 hours | 1 business day | 3 business days |

### Severity Definitions

- **Severity 1 (Critical)**: Production service outage, no workaround, ≥50% workflow failures
- **Severity 2 (High)**: Major functionality degraded, limited workaround, <50% failures
- **Severity 3 (Medium)**: Non-critical issue, workaround exists, single workflow affected
- **Severity 4 (Low)**: Feature request, documentation bug, cosmetic issue

❄️ **Enterprise 2-hour response** means acknowledge and begin investigation within 2 hours, 24/7/365.

---

## 2. Coverage

### What's Included

✅ **Hosted Runtime Service**
- Graph compilation and execution
- Adapter availability (OpenRouter, Ollama, MCP)
- Multi-tenant isolation and scaling
- Execution trace storage (30-day retention)

✅ **Enterprise Features**
- SSO/SAML authentication
- RBAC and policy enforcement
- Compliance report generation
- Premium adapters and connectors
- Dedicated support channel

✅ **Bug Fixes**
- Reproducible defects in AINL runtime or enterprise features
- Security patches (critical CVEs)
- Regression issues from last 3 releases

### What's NOT Included

❌ **Custom development** (new adapters, emitters, integrations)
❌ **On-premise deployment assistance** (beyond documentation)
❌ **Third-party infrastructure** (your OpenRouter account, your cloud)
❌ **Graph logic tutoring** (help writing your specific AINL programs)
❌ **24/7 phone support** (Enterprise tier gets Slack; optional phone add-on)

---

## 3. Support Channels

| Channel | Business | Enterprise |
|---------|----------|------------|
| Email | support@ainativelang.com | ✅ (priority routing) |
| Slack | ❌ | ✅ dedicated channel |
| GitHub Discussions | ✅ (best effort) | ✅ (monitored, faster) |
| Phone | ❌ | ✅ (optional add-on: $2k/mo) |
| Zoom/Meet | ❌ | ✅ (on request) |

**Response Time**: Measured from ticket creation to first substantive reply (acknowledgment + initial diagnosis or request for more info).

---

## 4. Escalation Process

If your issue isn't resolved within the target resolution time:

1. **Level 1**: Support Engineer (initial response)
2. **Level 2**: Senior Engineer (if unresolved after 2× severity SLA)
3. **Level 3**: Engineering Manager / Tech Lead (if unresolved after 4× severity SLA)
4. **Executive**: VP Engineering (for Severity 1 unresolved after 8 hours)

 escalation request: email `support@ainativelang.com` with `[ESCALATE]` prefix and your ticket number.

---

## 5. Maintenance & Planned Outages

- **Maintenance windows**: Sundays 2am–6am PT (US Pacific)
- **Advance notice**: 72 hours for planned maintenance affecting >50% of customers
- **Communication**: Status page (status.ainativelang.com) and Slack/email notifications
- **Exclusions**: Force majeure events, third-party provider outages outside our control

Maintenance counts against SLA only if unannounced or outside agreed windows.

---

## 6. Uptime & Availability

### Service Level Objective (SLO)

- **Hosted Runtime Availability**: 99.9% monthly uptime
- **Compilation Service**: 99.9%
- **API Endpoints**: 99.9%

### Measurement

Availability = (Total minutes in month - downtime minutes) / (Total minutes in month)

Downtime = period when hosted runtime is completely unavailable for a given tenant (network issues on your side don't count).

### SLA Credits

If we miss the 99.9% SLA, you receive service credits:

| Uptime | Credit |
|--------|--------|
| <99.9% – ≥99.5% | 10% of monthly fee |
| <99.5% – ≥99.0% | 25% of monthly fee |
| <99.0% | 50% of monthly fee |

Credits applied to next invoice. Max 50% credit per month.

**Exclusions**: Customer-caused issues, scheduled maintenance, force majeure.

---

## 7. Data Retention & Backups

- **Execution traces**: 30-day rolling retention (configurable to 90 days for Enterprise +$500/mo)
- **Graph definitions**: Indefinitely (your graphs survive service outages)
- **Backups**: Daily encrypted backups; 30-day point-in-time recovery
- **Export**: You can export graphs and traces anytime via API

You are responsible for long-term archival if needed beyond retention period.

---

## 8. Security & Compliance

### Security Measures

- **Encryption**: TLS 1.3 in transit, AES-256 at rest
- **Isolation**: Each tenant runs in separate Kubernetes namespace with NetworkPolicy
- **Secrets**: Stored in HashiCorp Vault, rotated quarterly
- **Penetration testing**: Annual third-party assessment (report available under NDA)
- **Vulnerability scanning**: Daily container and dependency scans

### Compliance Offerings

- **SOC 2 Type II**: Available upon request (Enterprise tier, signed NDA)
- **HIPAA BAA**: Available for Enterprise + $1,000/mo compliance add-on
- **GDPR DPA**: Standard in Enterprise terms

Compliance reports are provided quarterly or upon audit.

---

## 9. Limitations & Restrictions

- **Rate limits**: Enterprise tier: 10,000 executions/hour per tenant (adjustable)
- **Graph size**: Maximum 500 nodes per graph (contact us for larger)
- **Execution timeout**: 60 minutes max (configurable to 4 hours for Enterprise)
- **File storage**: 10GB included; additional $0.10/GB/month
- **Trace retention**: 30 days standard, 90 days Enterprise add-on

---

## 10. Termination & Data Deletion

Upon subscription cancellation:
- **Graph definitions**: Deleted within 30 days (extractable beforehand)
- **Execution traces**: Deleted within 90 days (immediate deletion available for $500 processing fee)
- **Account data**: Personal data deleted per GDPR "right to be forgotten"

No data portability fee; we provide JSON export of all graphs and traces on request.

---

## 11. Contact & Notices

- **Support Portal**: <https://support.ainativelang.com> (Enterprise only)
- **Status Page**: <https://status.ainativelang.com>
- **Security**: security@ainativelang.com (PGP key available)
- **Billing**: billing@ainativelang.com
- **Legal**: legal@ainativelang.com

**Service addresses**: <https://api.ainativelang.com>, <https://runtime.ainativelang.com>

---

## 12. Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-30 | 1.0 | Initial SLA document |
| | | |

---

## Appendix: Example SLA Credit Calculation

**Scenario**: Enterprise customer, $5,000/mo fee. Uptime in March = 99.82%.

- Target SLA: 99.9%
- Actual: 99.82% → downtime 127.68 minutes
- Since uptime >=99.5% but <99.9%: Credit = 10% of monthly fee
- Credit amount: $5,000 × 0.10 = **$500**
- Applied to April invoice.

If 99.2% uptime: credit = 25% = $1,250.

---

**Questions about this SLA?** Contact your account manager or enterprise@ainativelang.com.
