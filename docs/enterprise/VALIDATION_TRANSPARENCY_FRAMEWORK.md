# Validation Transparency Framework

Technical specification for AINL's compile-time validation system and audit dashboard.

---

## 🎯 Purpose

Enterprise customers need **proof** that AINL graphs are validated against policies before execution. This framework provides:

1. **Complete validation reporting** – every check, result, and rationale
2. **Immutable audit record** – validation state stored with execution traces
3. **Dashboard visibility** – Grafana/enterprise UI to review validation status
4. **Compliance mapping** – Direct links to SOC 2, HIPAA, GDPR controls

---

## 📋 Validation Phases

When you run `ainl validate` or `ainl run`, these checks execute:

### Phase 1: Syntax & Parsing

- ✅ AINL grammar conforms to language spec
- ✅ AST construction succeeds
- ❌ **Failures**: Syntax errors, malformed graphs

**Output**: PASS/FAIL + error line numbers

---

### Phase 2: Type & Schema Validation

- ✅ All nodes have required fields
- ✅ Input/output JSON Schema matches
- ✅ Edge connections valid (node exists, type-compatible)
- ❌ **Failures**: Missing `prompt` in LLM node, type mismatch on edge

**Output**: PASS/FAIL + list of violations

---

### Phase 3: Policy Compliance

- ✅ Graph fits within token budget
- ✅ Adapter is on allow-list
- ✅ No forbidden node types (e.g., `exec` if banned)
- ✅ Timeout within limits
- ❌ **Failures**: Budget exceeded, disallowed adapter

**Output**: PASS/FAIL + policy name + constraint details

---

### Phase 4: Security Checks

- ✅ No hardcoded secrets in prompts (regex detection)
- ✅ No external network calls to unauthorized domains
- ✅ RBAC: user has permission to run this graph (if applicable)
- ❌ **Failures**: Hardcoded API key pattern, blocked domain

**Output**: PASS/FAIL + security rule ID

---

### Phase 5: Performance Estimation

- ✅ Total orchestration tokens under threshold
- ✅ Expected latency < max allowed
- ⚠️ **Warnings** (non-blocking): Near budget limit, high-latency nodes

**Output**: Estimates + warnings (if any)

---

## 📊 Validation Report Format

After `ainl validate --json`, output:

```json
{
  "graph": "monitor",
  "timestamp": "2025-03-30T14:22:15Z",
  "version": "1.8.0",
  "phases": [
    {
      "name": "syntax",
      "status": "passed",
      "duration_ms": 12
    },
    {
      "name": "types",
      "status": "passed",
      "duration_ms": 45
    },
    {
      "name": "policy",
      "status": "passed",
      "duration_ms": 8,
      "checks": [
        {"rule": "max_tokens", "limit": 10000, "actual": 5420, "status": "pass"},
        {"rule": "allowed_adapters", "adapters": ["openrouter"], "status": "pass"}
      ]
    },
    {
      "name": "security",
      "status": "warning",
      "duration_ms": 18,
      "violations": [
        {"rule": "hardcoded_secret", "node": "slack", "field": "webhook", "severity": "medium"}
      ]
    }
  ],
  "overall": "warning",
  "warnings": 1,
  "errors": 0
}
```

---

## 🔍 Dashboard Design

Enterprise customers need a UI to review validation status across all graphs.

### Validation Dashboard (Web UI)

**Pages**:

#### 1. Overview

- Total graphs: 124
- Validated today: 118 (95%)
- Failed validations: 6 (breakdown by reason)
- Trend graph: validation success rate over time

#### 2. Graph List

| Graph Name | Last Validated | Status | Duration | Budget Used |
|------------|----------------|--------|----------|-------------|
| monitor.ainl | 2 hours ago | ✅ Passed | 83ms | 54% |
| payment_processor.ainl | 1 day ago | ❌ Failed | - | - |
| alert.ainl | 4 hours ago | ⚠️ Warning | 120ms | 87% |

Filters: Status, date range, owner, environment.

#### 3. Graph Detail

**Header**: Graph name, repository, last validated, overall status

**Phases Panel**:

| Phase | Status | Duration | Details |
|-------|--------|----------|---------|
| Syntax | ✅ Passed | 12ms | |
| Types | ✅ Passed | 45ms | 0 violations |
| Policy | ✅ Passed | 8ms | Token budget OK |
| Security | ❌ Failed | 18ms | [View 1 violation] |
| Performance | ⚠️ Warning | 32ms | Near token budget |

**Security Violations** (expandable):

- **Rule**: hardcoded_secret
- **Node**: slack (line 45)
- **Field**: webhook
- **Severity**: Medium
- **Suggested fix**: Move webhook to environment variable `${env.SLACK_WEBHOOK_URL}`

**Action buttons**:
- [Re-validate now]
- [View source]
- [Download full JSON report]

---

## 🔐 Compliance Mapping

Each validation rule maps to a compliance control.

| Validation Rule | SOC 2 | HIPAA | GDPR |
|-----------------|-------|-------|------|
| `syntax_valid` | CC6.1 | 164.308(a)(1)(ii)(A) | Art. 32 |
| `type_match` | CC7.2 | 164.308(a)(1)(ii)(B) | Art. 25 |
| `token_budget` | CC8.1 | 164.308(a)(1)(ii)(D) | Art. 25 |
| `no_hardcoded_secrets` | CC6.1 | 164.308(a)(1)(ii)(B) | Art. 32 |
| `allowed_adapter` | CC6.1 | 164.308(a)(1)(ii)(B) | Art. 32 |
| `rbac_check` | CC6.1 | 164.308(a)(3)(ii)(A) | Art. 25 |

**Dashboard feature**: Generate compliance evidence bundle:

- Export all validation reports for a date range
- Filter by control ID
- Include graph source diffs (changed graphs since last audit)
- Format: CSV, PDF, or native JSONL for SIEM import

---

## 🧩 Implementation Components

### 1. Enhanced `ainl validate`

Add `--json` and `--output` flags:

```bash
ainl validate --json --output reports/monitor-20250330.json monitor.ainl
```

Store reports in database or S3 for dashboard consumption.

---

### 2. Validation Storage Schema

```sql
-- PostgreSQL schema
CREATE TABLE validation_reports (
  id UUID PRIMARY KEY,
  graph_name TEXT NOT NULL,
  repository TEXT,
  branch TEXT,
  commit_sha CHAR(40),
  validated_at TIMESTAMPTZ NOT NULL,
  overall_status TEXT CHECK (overall_status IN ('passed','failed','warning')),
  raw_report JSONB NOT NULL
);

CREATE INDEX idx_validation_reports_graph ON validation_reports(graph_name);
CREATE INDEX idx_validation_reports_date ON validation_reports(validated_at);
```

---

### 3. API for Dashboard

```python
# GET /api/v1/validations
# Query params: graph, status, date_from, date_to
def list_validations(...):
    # Query DB, return paginated results
    pass

# GET /api/v1/validations/{id}
def get_validation_detail(id):
    # Return full JSON report + source diff
    pass

# POST /api/v1/validations/rebuild
def revalidate_graph(graph_name, commit_sha):
    # Trigger async validation job
    pass
```

---

### 4. Dashboard Frontend

Next.js app (existing `ainativelangweb` repo):

- Pages: `/enterprise/validation-dashboard`
- Requires SSO authentication
- Tables with sorting/filtering
- Click to expand phase details
- Export buttons (CSV, JSON)

---

## 🚀 Deployment Options

### Open-Core (Self-Hosted)

- Run `ainl-validator` daemon that watches Git repos
- PostgreSQL for storage
- Grafana dashboards (import JSON panel)
- API separate (FastAPI) or integrated

**Cost**: You operate it. No extra charge.

---

### Cloud (Enterprise SaaS)

- Hosted validation service included with Enterprise tier
- Multi-tenant data isolation
- Automatic: every push triggers validation
- SLA: 99.9% availability

**Cost**: Included in Enterprise subscription.

---

## 📈 Success Metrics

Track these for the validation framework:

| Metric | Target | Why |
|--------|--------|-----|
| Validation success rate | >95% | Most graphs should pass |
| Avg validation time | <100ms | Fast feedback loop |
| Dashboard uptime | 99.9% | Enterprise customers rely on it |
| Time-to-detect security violation | <5 min from commit | Fast response to risks |
| Compliance evidence generation time | <30 seconds | Audit efficiency |

---

## 🐛 Known Limitations & Future Work

### Current Gaps

- **No cross-graph analysis**: Can't detect when graph A calls graph B with incompatible inputs
- **No historical trends**: Can't see if a graph's validation status is degrading over time
- **False positive rate**: Security rules may flag benign patterns (configurable threshold)

### Roadmap

- **Phase 2**: Cross-graph dependency validation
- **Phase 3**: AI-assisted violation fix suggestions
- **Phase 4**: Validation as a service API (webhook on failure)

---

## 🔗 Integration Points

- **GitHub Actions**: Post validation status as PR comment
- **Slack**: Notify security team on security violation
- **PagerDuty**: Critical policy failures trigger alert
- **SIEM**: Forward JSON reports to Splunk/Datadog

Example GitHub Action:

```yaml
- name: Validate AINL graphs
  run: ainl validate --json --output report.json graphs/*.ainl
- name: Upload validation report
  uses: actions/upload-artifact@v3
  with:
    name: validation-reports
    path: report.json
- name: Post status to PR
  if: failure()
  uses: actions/github-script@v6
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        body: '❌ AINL validation failed. See report.'
      })
```

---

## ✅ Enterprise Adoption Checklist

- [ ] Deploy validation storage (PostgreSQL or cloud equivalent)
- [ ] Enable `ainl validate --json` in all CI/CD pipelines
- [ ] Configure report upload to storage
- [ ] Provision dashboard (self-hosted or cloud)
- [ ] Set up alerting for failed validations (Slack/PagerDuty)
- [ ] Create compliance evidence bundle generation job (daily)
- [ ] Train security team on dashboard usage
- [ ] Document runbook: "Responding to validation failures"

---

## 📞 Support

Questions? Contact enterprise@ainativelang.com or open a GitHub Discussion with `validation` label.

---

**Document version**: 1.0  
**Last updated**: 2026-03-30
