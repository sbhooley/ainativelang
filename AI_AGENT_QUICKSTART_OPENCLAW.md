# AI Agent Quickstart: Integrating AINL with OpenClaw

This guide gets you from zero to generating OpenClaw automations in AINL within one session.

**Before implementation work:** Follow **`docs/BOT_ONBOARDING.md`** and complete the **implementation preflight** in **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** (inspect files, confirm not duplicate, verify adapter semantics, emit required output structure). Machine-readable pointers: `tooling/bot_bootstrap.json`.

---

## 1. Environment Setup (One-Time)

```bash
# Clone and install
cd /Users/clawdbot/.openclaw/workspace/AI_Native_Lang
python -m pip install -e ".[dev,web]"

# Verify installation
ainl-validate --version
ainl-tool-api --help

# Run core tests
.venv/bin/python scripts/run_test_profiles.py --profile core
```

If tests pass, you're ready.

---

## 2. Understand the AINL Landscape (15 min)

Read in order:

1. `docs/BOT_ONBOARDING.md` — bot entrypoint; points to preflight (required before implementation)
2. `README.md` — project overview
3. `docs/DOCS_INDEX.md` — map to all docs
4. `docs/AINL_SPEC.md` (sections 0-3 only) — core syntax and execution model
5. `examples/openclaw/daily_digest.lang` — a monitor workflow example
6. `AI_CONSULTANT_REPORT_APOLLO.md` — OpenClaw integration strategy
7. `agent_reports/README.md` — indexed **field reports** from agents running AINL in production (continuity narratives)
8. `docs/INTELLIGENCE_PROGRAMS.md` — `intelligence/*.lang` monitors + `scripts/run_intelligence.py` runner
9. `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` — required before coding (steps + output structure)

**Key concepts to internalize:**
- Canonical IR = nodes/edges (graph-first)
- `S` (service), `D` (type), `E` (endpoint), `L` (label graph)
- `R group verb ->out` — adapter calls
- `U/T/Rt/Lay/Fm/Tbl/Ev` — frontend declarations
- Strict mode guarantees

---

## 3. Explore Existing OpenClaw Adapters

Open `ADAPTER_REGISTRY.json` and look for:
- `email` adapter: `G` target returns unread emails
- `calendar` adapter: `G` returns upcoming events
- `social` adapter: `G` returns mentions
- `db` adapter: `F` returns leads CSV
- `svc` adapter: `caddy`, `cloudflared`, `maddy` health checks
- `queue` adapter: `Put` sends notifications

These are the building blocks for OpenClaw workflows.

---

## 4. Try the Tool API (Hands-On)

```bash
# Compile a simple program
echo 'S core web /api
E /ping G ->L1
L1: J "pong"' | ainl-tool-api --action compile

# Emit OpenAPI
echo 'S core web /api
E /health G ->L1
L1: J {"status":"ok"}' | ainl-tool-api --action emit --target openapi
```

The Tool API (`docs/reference/TOOL_API.md`) is your primary programmatic interface. Use it from your agent loop:
- `compile` → get IR
- `validate` → check errors
- `emit` → generate artifacts
- `plan_delta` → propose changes safely
- `patch_apply` → merge changes

---

## 5. Write Your First OpenClaw Workflow

Goal: A daily digest AINL program that:
1. Checks email (adapter `email.G`)
2. Checks calendar (adapter `calendar.G`)
3. Checks social mentions (adapter `social.G`)
4. Checks leads pipeline (adapter `db.F`)
5. Checks infrastructure (adapter `svc.*`)
6. Sends a summary email if thresholds exceeded (adapter `queue.Put` + email)

### Step 1: Skeleton

```ainl
S core cron "0 9 * * *"  # daily at 9am
E /run G ->L0
L0: J ok
```

### Step 2: Add types for config/state

```ainl
D Config email_threshold:N cal_threshold:N social_threshold:N
D State last_email_check:T last_cal_check:T ...
```

### Step 3: Add email check label

```ainl
L0: R core now ->ts J L1

L1: R cache get "state" "last_email_check" ->last_check J L2
L2: R email G ->emails J L3
L3: Filter emails where date > last_check ->new_emails
L4: X email_count len new_emails
L5: R cache set "state" "last_email_check" ts J L6
```

### Step 4: Add calendar, social, leads, infra (similar pattern)

### Step 5: Decision & notification

```ainl
L50: If (core.gt needs_notify 0) ->L51 ->L52
L51: R queue Put notify {"email_count":email_count,...} J L52
L52: R cache set "state" "last_notified" ts J L53
L53: J done
```

**Full reference**: See `demo/monitor_system.lang` — this is the production monitor already running.

---

## 6. Validate and Test

```bash
# Strict validation
ainl-validate my_monitor.lang --strict

# Check IR shape (must have nodes/edges)
python scripts/validate_ainl.py my_monitor.lang --emit ir | jq '.labels["0"] | has("nodes") and has("edges")'

# Test runtime (requires adapters configured)
ainl-test-runtime my_monitor.lang

# Emit server
python scripts/validate_ainl.py my_monitor.lang --emit server
# Inspect tests/emits/server/ — FastAPI server with all adapters

# Run full integration profile
.venv/bin/python scripts/run_test_profiles.py --profile integration
```

---

## 7. Integrate with OpenClaw (Deploy)

1. **Add the `ocl` adapter** (if not yet implemented):
   - Extend `ADAPTER_REGISTRY.json` with `ocl` namespace
   - Implement `adapters/ocl.py` mapping verbs to OpenClaw SDK
   - Register in runtime `AdapterRegistry`

2. **Update your AINL** to use `ocl.*` verbs instead of `email.G` etc. directly:
   ```ainl
   R ocl.Email.List days:7 ->emails
   ```

3. **Add policy rules** to restrict `ocl` usage per workspace in `tooling/policy_validator.py`.

4. **Run the alignment gate**:
   ```bash
   python scripts/run_alignment_cycle.sh
   # Check corpus/curated/alignment_run_health.json
   ```

5. **Commit** your changes with a clear handoff note (see `docs/AI_AGENT_CONTINUITY.md`).

---

## 8. Ongoing Operation (Monitoring)

- Monitor cron job logs: `openclaw cron list` and `openclaw cron logs <id>`
- Check `corpus/curated/model_eval_trends*.json` for model quality changes
- Watch AINL monitor runs (every 15 min) — they compile and execute `demo/monitor_system.lang`
- If quality drops: follow `docs/TRAINING_ALIGNMENT_RUNBOOK.md` triage

---

## 9. Handoff Template (When Your Session Ends)

When ending a session, leave a note in `docs/SESSION_NOTES.md` or as a system message:

```
## Handoff: <Topic>

**Changed files**: <list>
**Behavior**: <summary>
**Validation commands run**: <commands + pass/fail>
**Current bottleneck**: <if any>
**Next recommended command**: <precise command for next agent>
```

This ensures smooth continuity.

---

## 10. Resources

| Resource | Purpose |
|----------|---------|
| `docs/AINL_SPEC.md` | Formal language spec |
| `docs/AI_AGENT_CONTINUITY.md` | Handoff protocol |
| `docs/TRAINING_ALIGNMENT_RUNBOOK.md` | Quality gates and eval |
| `docs/reference/TOOL_API.md` | Structured tool interface |
| `OPENCLAW_AI_AGENT.md` | OpenClaw agent index and integration |
| `AI_CONSULTANT_REPORT_APOLLO.md` | OpenClaw-specific recommendations |
| `CONSULTANT_REPORTS.md` | Index of all consultant reports |
| `examples/openclaw/` | Reference examples (daily_digest, lead_enrichment, infrastructure_watchdog, webhook_handler) |
| `ADAPTER_REGISTRY.json` | Machine-readable adapter catalog |
| `corpus/curated/` | Evaluation reports and trends |

---

**Got a question?** Check `docs/AI_AGENT_CONTINUITY.md` first; then `docs/CONTRIBUTING_AI_AGENTS.md`. The docs are written for AI agents — they tell you exactly what to do next.
