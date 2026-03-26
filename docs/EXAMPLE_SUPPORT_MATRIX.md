# AINL Example Support Matrix

This document classifies repository examples into support lanes so contributors
and AI agents can tell which examples define the public recommended path and
which ones are preserved mainly for compatibility.

Primary machine-readable sources:
- `tooling/support_matrix.json`
- `tooling/artifact_profiles.json`

## Scope of the classification contract

`tooling/artifact_profiles.json` and the tables below govern **onboarding/training/conformance expectations** for paths that are **explicitly listed** there (primarily `examples/*.ainl`, selected `examples/**/*.ainl` / `.lang`, and curated `corpus/` programs). CI and profile tests enforce that contract for those entries.

**Not in that contract unless added explicitly:**

- **`demo/`** — operator demos and experiments; may lag strict profiles; not treated as canonical training targets by default.
- **`intelligence/`** — OpenClaw-oriented monitors and helpers (not ZeroClaw-specific); indexed in `docs/INTELLIGENCE_PROGRAMS.md`; **outside** `artifact_profiles.json` unless a path is added there on purpose.

Evaluators should **not** assume every `.lang` / `.ainl` file in the repo shares the same `strict-valid` / `non-strict-only` guarantees as listed `examples/`.

### `compatible` in `support_matrix.json` (ops and syntax)

In `tooling/support_matrix.json`, **`compatible` does not mean “avoid” or “legacy-only.”** It marks surfaces that are **not** the top priority for *new strict-valid tutorial examples* and *canonical training-pack convergence*, while remaining **fully implemented and widely used** in real programs (e.g. `X`, `CacheGet`, `QueuePut`, `Loop` in monitors). Prefer **`canonical`** ops/forms when authoring **minimal** strict tutorials; use **`compatible`** ops where the workflow requires them.

Support levels:
- `canonical`: recommended for onboarding, docs, training, and future convergence
- `compatible`: supported for continuity, but not the preferred public path
- `deprecated`: retained only for retirement/migration context

## Canonical Examples

These examples are the recommended starting point and are expected to be
strict-valid.

| Example | Profile | Why it matters | Ops role (if applicable) |
|---------|---------|----------------|---------------------------|
| `examples/hello.ainl` | `strict-valid` | Smallest compute-and-return example | — |
| `examples/crud_api.ainl` | `strict-valid` | Clear `Set` + `If` branch behavior | Branching/control flow |
| `examples/rag_pipeline.ainl` | `strict-valid` | Explicit `Call ... ->out` return binding | Workflow composition |
| `examples/retry_error_resilience.ainl` | `strict-valid` | Canonical retry and failure routing | Resilience/remediation pattern |
| `examples/if_call_workflow.ainl` | `strict-valid` | Modular workflow via branch + sublabel call | Workflow composition + branching |
| `examples/webhook_automation.ainl` | `strict-valid` | Simple validation and outbound HTTP action | Webhook-style remediation/ops |
| `examples/monitor_escalation.ainl` | `strict-valid` | Scheduled monitoring/escalation flow | Monitoring/escalation |
| `examples/status_branching.ainl` | `strict-valid` | Simple status-branch branching (`ok` vs `alerted`) | Minimal status-based branch shape |
| `examples/web/basic_web_api.ainl` | `strict-valid` | Best starter for server/OpenAPI path | API surface for ops tooling |
| `examples/scraper/basic_scraper.ainl` | `strict-valid` | Scraper + cron + persistence path | Scraper + scheduled ops |

Recommended learning order:

1. `examples/hello.ainl`
2. `examples/crud_api.ainl`
3. `examples/rag_pipeline.ainl`
4. `examples/if_call_workflow.ainl`
5. `examples/retry_error_resilience.ainl`
6. `examples/web/basic_web_api.ainl`
7. `examples/webhook_automation.ainl`
8. `examples/scraper/basic_scraper.ainl`
9. `examples/monitor_escalation.ainl`

## Compatible Examples

These remain important for continuity, demos, and migration coverage, but they
should not be treated as the canonical public language surface.

### Root Compatibility Examples

| Example | Profile | Notes |
|---------|---------|-------|
| `examples/api_only.lang` | `non-strict-only` | Compatibility example |
| `examples/blog.lang` | `non-strict-only` | Compatibility example |
| `examples/ecom.lang` | `non-strict-only` | Compatibility example |
| `examples/internal_tool.lang` | `non-strict-only` | Compatibility example |
| `examples/ticketing.lang` | `non-strict-only` | Compatibility example |
| `examples/cron/monitor_and_alert.ainl` | `non-strict-only` | Compatibility cron example |
| `examples/integrations/executor_bridge_min.ainl` | `non-strict-only` | HTTP external executor bridge (see `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`; MCP preferred for OpenClaw / ZeroClaw) |
| `examples/integrations/executor_bridge_adapter_min.ainl` | `non-strict-only` | Optional `bridge` adapter — executor keys mapped to URLs on the host |

### OpenClaw Compatibility Family

These examples are **advanced**, **extension/OpenClaw-only**, and **not safe
defaults for unsupervised agents**. They are intended for operator-controlled
environments and should be treated as advisory patterns, not a secure or
fully-automated agent fabric.

| Example | Profile | Notes |
|---------|---------|-------|
| `examples/openclaw/backup_manager.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/daily_digest.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/daily_digest.strict.lang` | `non-strict-only` | Transitional compatibility artifact (advanced) |
| `examples/openclaw/daily_lead_summary.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/infrastructure_watchdog.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/lead_enrichment.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/webhook_handler.lang` | `non-strict-only` | OpenClaw compatibility example (advanced / operator-oriented) |
| `examples/openclaw/agent_send_task.lang` | `non-strict-only` | Advanced coordination example: append AgentTaskRequest via agent.send_task (advisory-only, operator-controlled) |
| `examples/openclaw/agent_read_result.lang` | `non-strict-only` | Advanced coordination example: read AgentTaskResult via agent.read_result (advisory-only, operator-controlled) |
| `examples/openclaw/token_cost_advice_request.lang` | `non-strict-only` | Advanced coordination example: enqueue token-cost advisory request via agent.send_task (not for unsupervised auto-remediation) |
| `examples/openclaw/token_cost_advice_read.lang` | `non-strict-only` | Advanced coordination example: read token-cost advisory result via agent.read_result (not for unsupervised auto-remediation) |
| `examples/openclaw/monitor_status_advice_request.lang` | `non-strict-only` | Advanced coordination example: enqueue monitor-status advisory request via agent.send_task (not for unsupervised auto-remediation) |
| `examples/openclaw/monitor_status_advice_read.lang` | `non-strict-only` | Advanced coordination example: read monitor-status advisory result via agent.read_result (not for unsupervised auto-remediation) |

### Autonomous Ops Extension Pack (OpenClaw)

| Example | Profile | Notes |
|---------|---------|-------|
| `examples/autonomous_ops/status_snapshot_to_queue.lang` | `non-strict-only` | Extension/OpenClaw status snapshot → queue example |
| `examples/autonomous_ops/backup_freshness_to_queue.lang` | `non-strict-only` | Extension/OpenClaw backup freshness snapshot → queue example |
| `examples/autonomous_ops/pipeline_readiness_snapshot.lang` | `non-strict-only` | Extension/OpenClaw pipeline readiness snapshot → queue example |
| `examples/autonomous_ops/infrastructure_watchdog.lang` | `non-strict-only` | Extension/OpenClaw: service checks, cooldown, restart queue |
| `examples/autonomous_ops/tiktok_sla_monitor.lang` | `non-strict-only` | Extension/OpenClaw: TikTok pipeline SLA + backup freshness |
| `examples/autonomous_ops/lead_quality_audit.lang` | `non-strict-only` | Extension/OpenClaw: daily lead data quality audit |
| `examples/autonomous_ops/token_cost_tracker.lang` | `non-strict-only` | Extension/OpenClaw: OpenRouter usage + spend alert |
| `examples/autonomous_ops/canary_sampler.lang` | `non-strict-only` | Extension/OpenClaw: endpoint health + consecutive failure detection |
| `examples/autonomous_ops/token_budget_tracker.lang` | `non-strict-only` | Extension/OpenClaw: 7‑day token cost vs weekly budget |
| `examples/autonomous_ops/session_continuity.lang` | `non-strict-only` | Extension/OpenClaw: extract preferences from sessions; append daily log |
| `examples/autonomous_ops/memory_prune.lang` | `non-strict-only` | Extension/OpenClaw: physical deletion of expired memory records (daily) |
| `examples/autonomous_ops/meta_monitor.lang` | `non-strict-only` | Extension/OpenClaw: watchdog for monitors; alerts if any monitor is stale |
| `examples/autonomous_ops/monitor_system.lang` | `non-strict-only` | Extension/OpenClaw: multi‑monitor orchestration / reference shape |

### Golden Compatibility Family

| Example | Profile | Notes |
|---------|---------|-------|
| `examples/golden/01_web_server.ainl` | `non-strict-only` | Compatibility/golden artifact |
| `examples/golden/02_dashboard.ainl` | `non-strict-only` | Compatibility/golden artifact |
| `examples/golden/03_scraper.ainl` | `non-strict-only` | Compatibility/golden artifact |
| `examples/golden/04_alerting_monitor.ainl` | `non-strict-only` | Compatibility/golden artifact; uses operator-only `svc` adapter |
| `examples/golden/05_file_processor.ainl` | `non-strict-only` | Compatibility/golden artifact |

## PTC Hybrid Examples

These examples demonstrate opt-in PTC-Lisp integration. They require `--enable-adapter ptc_runner` and run cleanly in mock mode (`AINL_PTC_RUNNER_MOCK=1`).

| Example | Profile | Mock-friendly | Notes |
|---------|---------|---------------|-------|
| `examples/hybrid_order_processor.ainl` | `legacy-compat` | yes | PTC hybrid: parallel order batches, signatures, `_` context firewall, trace export, LangGraph bridge |
| `examples/price_monitor.ainl` | `legacy-compat` | yes | PTC hybrid: price monitor with parallel/recovery patterns and `_` context firewall |
| `examples/ptc_integration_example.ainl` | `legacy-compat` | yes | Canonical end-to-end PTC integration reference |

These are `legacy-compat` because they use `strict=False` (the `ptc_parallel` and `recovery_loop` modules require runtime relaxation due to strict compiler dataflow limitations with `Loop`-based patterns). They are fully functional and recommended for PTC integration exploration.

## Deprecated Examples

No repository examples are classified as `deprecated` yet in the current
machine-readable support matrix.

That is intentional: the project is still in compatibility-preserving
classification mode, not active retirement mode.

## Usage Guidance

Use canonical examples for:
- docs
- public onboarding
- canonical training/eval packs
- strict-mode conformance references

Use compatible examples for:
- migration coverage
- backward-compat testing
- historical context
- runtime behavior preservation during refactors

Do not present compatible examples as if they define the future public language.
