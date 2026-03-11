## Autonomous Ops Playbook (current AINL reality)

**Status:** This is a **truthful snapshot** of what AINL already supports for autonomous operations. It does **not** introduce new semantics. Anything beyond this is explicitly marked as deferred.

Use this as a starting point for building:

- monitoring and remediation agents
- workflow/orchestration agents
- “run this safely many times” backends for LLMs and tools

### 1. Compile once, run many (no runtime LLM dependency)

AINL programs are compiled to a **graph IR** that runtimes execute without any language‑model in the loop:

- `compiler_v2.AICodeCompiler(strict_mode=...)` produces IR (see `docs/IR_SCHEMA.md`).
- Runtimes execute **label graphs** (`labels[*].nodes` / `labels[*].edges`) according to `runtime_policy.execution_mode = "graph-preferred"`.
- There is **no requirement** to call an LLM at runtime once the program is compiled.

For agents, the recommended pattern is:

1. Use an LLM (or human) to synthesize or edit `.ainl`.
2. Compile and validate once with `ainl-validate` (or `scripts/validate_ainl.py`).
3. Run the resulting IR many times with the runtime/CLI.

Deterministic replay support (from `docs/INSTALL.md`):

- Record adapter calls:

```bash
ainl run app.ainl --json \
  --enable-adapter http \
  --record-adapters calls.json
```

- Replay from recorded calls (no live side effects):

```bash
ainl run app.ainl --json \
  --replay-adapters calls.json
```

This makes it possible to:

- test and debug flows without live io
- re‑run the same logical program over fixed adapter responses
- keep LLM usage out of the hot path.

### 1.1 Determinism & replay proof checklist

When you want to **prove** compile-once/run-many behavior for a given program without a runtime LLM in the loop:

1. **Compile and inspect IR (with strict checks):**

   ```bash
   ainl-validate app.ainl --strict --emit ir
   ```

   - Verify that `errors` is empty and note the `graph_semantic_checksum`.

2. **Run once with live adapters and record calls:**

   ```bash
   ainl run app.ainl --json \
     --enable-adapter http \
     --record-adapters calls.json
   ```

3. **Re-run using only the recorded adapter calls:**

   ```bash
   ainl run app.ainl --json \
     --replay-adapters calls.json
   ```

   - No LLM is involved at runtime; adapter behavior is replayed deterministically from `calls.json`.

Together, these steps show:

- a stable compiled graph (via `graph_semantic_checksum`), and
- repeatable execution for a fixed adapter trace (via record/replay),

without requiring any runtime language-model inference.

### 2. Deterministic, auditable control flow

Canonical execution is defined by the **graph IR**:

- `docs/GRAPH_SCHEMA.md` describes the node/edge schema.
- `docs/IR_SCHEMA.md` shows how labels, endpoints, and checksums are laid out.
- `graph_semantic_checksum` gives a stable hash of the graph semantics.

For **branching and exits**, see these canonical examples (all strict‑valid):

- `examples/status_branching.ainl` — smallest `Set` + `If` → `ok/alerted`.
- `examples/crud_api.ainl` — `Set` + `If` routing example.
- `examples/if_call_workflow.ainl` — branching plus sublabel calls.
- `examples/retry_error_resilience.ainl` — explicit `Retry` + `Err` fallback path.
- `examples/monitor_escalation.ainl` — scheduled escalation vs noop.

The **Example Support Matrix** and **Canonical Curriculum**:

- `docs/EXAMPLE_SUPPORT_MATRIX.md` — lists canonical vs compatible examples and their roles.
- `tooling/canonical_curriculum.json` — ordered curriculum, including a `status_branching` pattern.

For graph‑level introspection (before or instead of running):

- see `docs/GRAPH_INTROSPECTION.md` for how to:
  - emit IR/graph with `ainl-validate` / `scripts/validate_ainl.py`
  - query graphs with `tooling/graph_api.py`
  - use `graph_diff` / `graph_normalize` for audits.

### 3. Adapter orchestration (self‑hosted adapters)

Adapters are declared and validated via:

- `tooling/adapter_manifest.json` (canonical machine‑readable metadata)
- `ADAPTER_REGISTRY.json` + `docs/ADAPTER_REGISTRY.md` (richer operator view)

The current story:

- Core adapters (e.g. `http`, `sqlite`, `fs`, `queue`, `cache`, `tools`) have:
  - explicit **verbs**, **effect types**, and **support tiers**.
  - clear distinction between **core**, **extension_openclaw**, and **compatibility** tiers.
- Strict machinery uses the manifest to:
  - classify io vs pure vs meta effects (`ADAPTER_EFFECT`)
  - validate allowed verbs/arity in strict mode.

For ops‑oriented runs, see `docs/INSTALL.md`:

- `ainl run app.ainl --json --enable-adapter http ...`
- `ainl run app.ainl --enable-adapter sqlite ...`
- `ainl run app.ainl --enable-adapter fs ...`
- `ainl run app.ainl --enable-adapter tools ...`

All of this is designed to be **self‑hosted**; no external orchestration SaaS is required.

### 4. Cooldown, cadence, and durable patterns (current scope)

Cooldown/stateful scheduling is expressed today via:

- `Cr` (cron‑like declarations) and scheduled flows:
  - see `examples/monitor_escalation.ainl` (scheduled monitoring + escalation).
  - see `examples/cron/monitor_and_alert.ainl` (compatibility cron example).
- Scraper + cron:
  - see `examples/scraper/basic_scraper.ainl`.

Important constraints (current reality):

- Cooldown and long‑term state are **not** a special new semantic tier; they are modeled via:
  - existing cron/scrape declarations
  - queue/db/file adapters for persistence.
- There is **no** hidden “agent lifecycle” API; AINL is an execution substrate you can call repeatedly from your own scheduler/agent loop.

The safe pattern today:

- Use your own orchestrator/agent to:
  - schedule AINL program runs (cron, workflows, alerts)
  - store any **agent state** externally (db/queue/cache/etc.)
  - treat AINL as the deterministic execution engine for each run.

Concretely, cooldown / persistent-state behavior today is modeled by:

- reading and writing timestamps or counters via adapters such as `cache` / `db` / `queue`
- comparing those values to the current time or thresholds in user code
- branching (or choosing to emit/skip) based on those comparisons

Examples of this pattern (canonical + compatibility + OpenClaw):

- `examples/monitor_escalation.ainl` — scheduled escalation vs noop based on conditions.
- `examples/cron/monitor_and_alert.ainl` — compatibility cron flow with monitoring intent.
- `examples/openclaw/daily_digest.lang` — OpenClaw-style daily digest with `last_digest` tracked via cache.
- `examples/openclaw/backup_manager.lang` — OpenClaw-style backup manager with `last_backup` and `backup_count` in cache.

There is **no** first-class `Cooldown` or “suppression window” semantic today; last-run / last-alert / cooldown windows must be modeled explicitly using these adapters and your own orchestrator logic.

### 5. Proactive output: queues, HTTP actions, and escalation

AINL can already express proactive behavior in canonical or clearly‑marked examples:

- **Escalation / monitoring:**
  - `examples/monitor_escalation.ainl` — scheduled monitor/escalation split.
- **Webhook‑style remediation:**
  - `examples/webhook_automation.ainl` — validate vs accept/ignore + outbound `R http.POST`.
- **Scraper + cron:**
  - `examples/scraper/basic_scraper.ainl` — scraper + scheduled runs + persistence.
- **Branching status pattern:**
  - `examples/status_branching.ainl` — small, auditable `ok` vs `alerted` branch.

Queue‑ and remediation‑shaped flows:

- There are existing queue adapters and examples (see `docs/EXAMPLE_SUPPORT_MATRIX.md` and `tooling/support_matrix.json` for roles).
- These are **not** a new semantic tier; they are combinations of:
  - normal io ops (`R queue.*`, `R http.*`, `R sqlite.*`, etc.)
  - canonical branching (`If`, `Err`, `Retry`) and exits (`J`).

#### 5.2 Using the HTTP success envelope (current reality)

The `http` adapter now returns an additive **success envelope** for 2xx responses with fields:

- `ok` (True for 2xx),
- `status` and `status_code`,
- `error` (None on success),
- `body`, `headers`, and `url`.

A small monitoring-oriented AINL pattern that makes use of this (for the **success path only**) might look like:

```text
L1:
  R http.Get "https://api.example.com/health" ->resp
  # On success (2xx), resp has:
  #   ok, status, status_code, error=None, body, headers, url.
  # Non-2xx and transport errors still surface as AdapterError / Err and do not
  # produce a normal resp envelope in this pass.
```

Agents and tools can also inspect these fields directly from the runtime frame (e.g. when replaying runs or analyzing traces). Future passes may extend this into fully worked examples that branch on `resp.ok` / `resp.status_code`, but for now you should continue to treat non-2xx and transport failures as going through the existing `Err` / AdapterError paths rather than returning a failure envelope.

#### 5.1 Remediation patterns (current)

Using only current semantics, remediation is expressed through combinations of:

- **Retry + fallback**:
  - `examples/retry_error_resilience.ainl` — uses `Retry` + `Err` with an explicit fallback label to route failures.
- **Escalation vs noop**:
  - `examples/monitor_escalation.ainl` — scheduled monitor that escalates under certain conditions or does nothing.
- **Webhook-style outbound action**:
  - `examples/webhook_automation.ainl` — validate / accept / ignore, then call `R http.POST` to trigger external remediation.
- **Queue-based downstream handling**:
  - `examples/openclaw/webhook_handler.lang` — OpenClaw webhook handler that enqueues jobs via `queue.Put`.
  - `examples/autonomous_ops/*.lang` — extension/OpenClaw snapshot emitters that push structured payloads to queues for downstream agents.

Important limitations (current reality):

- There are **no** first-class built-in semantics today for:
  - suppression windows
  - acknowledgments / “once-only” processing
  - rate limiting or global policy DSLs
- These behaviors must be modeled explicitly via:
  - external state (db/cache/queue)
  - scheduler/orchestrator logic
  - application-specific branching and adapter usage.

For **extension/OpenClaw autonomous-ops snapshot emitters**, see:

- `examples/autonomous_ops/status_snapshot_to_queue.lang`
- `examples/autonomous_ops/backup_freshness_to_queue.lang`
- `examples/autonomous_ops/pipeline_readiness_snapshot.lang`

These are non-strict, extension-level examples that:

- gather operational facts from `svc`/`cache`/`core`
- emit structured snapshots to `queue`
- leave branching/policy decisions to downstream consumers

### 6. Meta‑monitoring: what is still deferred

There is **no** fully‑realized “AINL monitors itself over time” canonical example yet that:

- branches cleanly on HTTP success vs failure,
- enqueues alerts only on true fail paths,
- and stays small and unambiguous under strict effect typing.

Current state:

- `examples/status_branching.ainl` is intentionally **not** an HTTP monitor; it is a simple local status branch.
- More advanced meta‑monitoring (e.g. “watch traces”, “watch queues”, “auto‑remediate failures”) will require:
  - either richer adapter conventions, or
  - additional runtime/graph semantics.

Those changes are intentionally **deferred** to avoid semantic drift. For now, the recommended pattern is:

- use AINL for deterministic execution and clear branching;
- use your own agent/orchestrator layer to:
  - read logs/metrics/traces (from your infra)
  - synthesize/remediate AINL programs in response.

### 7. Where to look next (for agents)

If you are building an autonomous agent on top of AINL, the recommended reading order is:

1. `README.md` — overview and positioning.
2. `docs/AINL_CANONICAL_CORE.md` — canonical language surface.
3. `docs/EXAMPLE_SUPPORT_MATRIX.md` + `tooling/canonical_curriculum.json` — examples and roles.
4. `docs/GRAPH_INTROSPECTION.md` — how to inspect compiled IR/graphs.
5. `docs/GRAPH_SCHEMA.md` + `docs/IR_SCHEMA.md` — deeper IR/graph details if needed.
6. `docs/ADAPTER_REGISTRY.md` — adapter capabilities and tiers.
7. `docs/AGENT_COORDINATION_CONTRACT.md` — non-canonical, extension-level JSON envelopes for agent manifests, task requests, and task results (used over queues/files, not as core semantics).

When you need something AINL does **not** yet express cleanly (e.g. full meta‑monitoring), model it explicitly as “deferred” in your system design rather than assuming semantics that do not exist.

