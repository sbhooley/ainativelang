---
name: AI_Native_Lang
description: Deterministic graph-first DSL for AI-to-AI full-stack generation
version: 1.0.0
ainativelang_release: "1.8.0"
license: Apache-2.0
openclaw_integration: complete
adapters:
  - name: core
    verbs: [now, add, sub, mul, div, idiv, mod, pow, len, concat, join, stringify, lt, gt, lte, gte, eq, ne]
    effect: pure-compute
    description: Core builtins for time, math, string, collection operations
    openclaw: true
  - name: email
    verbs: [G]
    effect: io-read
    description: Read unread emails via openclaw mail check
    openclaw: true
  - name: calendar
    verbs: [G]
    effect: io-read
    description: List upcoming events via openclaw gog calendar
    openclaw: true
  - name: social
    verbs: [G]
    effect: io-read
    description: Web search for mentions via openclaw web search
    openclaw: true
  - name: db
    verbs: [F]
    effect: io-read
    description: Read leads from CSV (leads/lead_output.csv)
    openclaw: true
  - name: svc
    verbs: [caddy, cloudflared, maddy, crm]
    effect: io-read
    description: Service health checks (ports/processes); includes CRM on port 3000
    openclaw: true
  - name: cache
    verbs: [get, set]
    effect: io-readwrite
    description: Persistent JSON state in /tmp/monitor_state.json
    openclaw: true
  - name: queue
    verbs: [Put]
    effect: io-write
    description: Send notification via openclaw message send
    openclaw: true
  - name: wasm
    verbs: [CALL]
    effect: pure-compute
    description: Custom computation via wasmtime
    openclaw: true
  - name: extras
    verbs: [file_exists, docker_image_exists, http_status, newest_backup_mtime]
    effect: io-read
    description: Utility health checks: file + Docker + HTTP + backup mtime
    openclaw: false
  - name: tiktok
    verbs: [F, recent, videos]
    effect: io-read
    description: TikTok reports and videos from CRM SQLite DB
    openclaw: false
entry_points:
  - path: demo/monitor_system.lang
    purpose: Production cron monitor (15min interval)
    labels: 63
  - path: examples/openclaw/daily_digest.lang
    purpose: Daily digest combining email/calendar/social with notifications
    labels: TBD
  - path: examples/openclaw/lead_enrichment.lang
    purpose: Lead processing with db+cache+queue pipeline
    labels: TBD
  - path: examples/openclaw/infrastructure_watchdog.lang
    purpose: Service checks and health scoring
    labels: TBD
  - path: examples/openclaw/webhook_handler.lang
    purpose: Inbound webhook dispatch pattern
    labels: TBD
tooling:
  - ainl-validate
  - .venv/bin/python scripts/run_test_profiles.py --profile <name>
  - ainl-tool-api
  - python scripts/validate_ainl.py
documentation_index: docs/DOCS_INDEX.md
canonical_spec: docs/AINL_SPEC.md
bot_onboarding: docs/BOT_ONBOARDING.md
implementation_preflight: docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md
bot_bootstrap: tooling/bot_bootstrap.json
quickstart: AI_AGENT_QUICKSTART_OPENCLAW.md
consultant_report: AI_CONSULTANT_REPORT_APOLLO.md
test_profile: openclaw
production_cron: AINL Proactive Monitor (runs every 15 minutes)
strict_mode_conversion_plan: STRICT_MODE_CONVERSION_PLAN.md
---
