# OpenClaw + AINL — gold standard (install / upgrade)

**Purpose:** Canonical reference for **agents and operators** after **`pip install`** / **`ainl install-mcp --host openclaw`** (or similar). Follow this to align **profiles**, **caps**, **cron**, **shared paths**, and **verification** so token savings and **`budget_hydrate`** behavior show up in real sessions. **Adapt numbers** to your measured workload (`bridge-sizing-probe`); the structure stays the same.

**AINL v1.2.8 host briefing (what the repo ships vs what OpenClaw must do):** [`OPENCLAW_HOST_AINL_1_2_8.md`](OPENCLAW_HOST_AINL_1_2_8.md) — copy-paste ready for operators; **`tooling/bot_bootstrap.json`** → **`openclaw_host_ainl_1_2_8`**.

**See also:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) (bundle index) · [`AINL_PROFILES.md`](AINL_PROFILES.md) · [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md) · [`TOKEN_AND_USAGE_OBSERVABILITY.md`](TOKEN_AND_USAGE_OBSERVABILITY.md) · [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`../INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md) · [`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md) · [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md)

---

## 1. Environment profile

- **Baseline (first install):** `openclaw-default` — safe defaults before you have measurements.
- **After measuring** (bridge report size, weekly trends, intelligence runs): switch to **`cost-tight`** for stricter bridge report caps and the same conservative defaults.

```bash
# Baseline
eval "$(ainl profile emit-shell openclaw-default)"

# After measured tuning (typical “cost-tight” path)
eval "$(ainl profile emit-shell cost-tight)"
```

Pin **one workspace** so SQLite, cache JSON, and FS roots stay consistent (see [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md)):

```bash
export OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
. tooling/openclaw_workspace_env.example.sh
eval "$(ainl profile emit-shell openclaw-default)"   # or cost-tight
```

---

## 2. Critical caps (start here, then tighten)

Set **after** you understand your gateway; **adjust** after `ainl bridge-sizing-probe` (see §5).

| Variable | Example start | Notes |
|----------|----------------|--------|
| `AINL_BRIDGE_REPORT_MAX_CHARS` | `500` | Bridge report size; raise only if evidence shows truncation pain. |
| `AINL_WEEKLY_TOKEN_BUDGET_CAP` | `200000` | Match **your** real weekly budget. |
| `PROMOTER_LLM_MAX_PROMPT_CHARS` | `2000` | **Gateway (Apollo)** — not in `ainl_profiles.json`; set on the promoter process. |
| `PROMOTER_LLM_MAX_COMPLETION_TOKENS` | `500` | **Gateway** — same. |

Staging order and hydrate flags: [`TOKEN_CAPS_STAGING.md`](TOKEN_CAPS_STAGING.md).

---

## 3. Cron schedule (recommended defaults)

| Job | Suggested schedule | Role |
|-----|---------------------|------|
| `python3 scripts/run_intelligence.py context` | Daily **02:00** | Fresh **session context** for morning sessions (writes bootstrap under workspace). |
| `python3 scripts/run_intelligence.py summarizer` | Every **other** day **03:00** | Summarizer / digest posture (see [`../INTELLIGENCE_PROGRAMS.md`](../INTELLIGENCE_PROGRAMS.md)). |
| Bridge **`weekly-token-trends`** (wrapper) | **Sunday 04:00** | Publishes rolling budget / **`weekly_remaining_v1`** into SQLite for hydration. |

Exact wrapper paths and env: [`openclaw/bridge/README.md`](../../openclaw/bridge/README.md). Use the same **`OPENCLAW_WORKSPACE`** (and derived env) for every job.

---

## 4. Host behavior (required for savings to show in chat)

Without this, AINL jobs may run “correctly” but **users do not see** reduced tokens at session start.

1. **Bootstrap load order:** Prefer **`.openclaw/bootstrap/session_context.md`** (or your path) **if present**; fall back to **`MEMORY.md`** only when the bootstrap file is missing.
2. **Shared paths:** All cron, bridge, and intelligence processes must use the **same** resolved paths:
   - `OPENCLAW_WORKSPACE`
   - `OPENCLAW_MEMORY_DIR`, `AINL_FS_ROOT`
   - `AINL_MEMORY_DB`, `MONITOR_CACHE_JSON`

Details: [`AGENT_AINL_OPERATING_MODEL.md`](AGENT_AINL_OPERATING_MODEL.md) · [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md).

---

## 5. Verification cadence

| When | Check |
|------|--------|
| After first **weekly** bridge run | **`weekly_remaining_v1`** exists in SQLite (`workflow` / `budget.aggregate` / `weekly_remaining_v1` row). |
| After **`run_intelligence.py`** (non–dry-run) | JSON includes **`budget_hydrate`** with **`ok: true`** when a rolling row exists (see [`WORKSPACE_ISOLATION.md`](WORKSPACE_ISOLATION.md)). |
| **Monthly** (or after load change) | `ainl bridge-sizing-probe --json` — tighten **`AINL_BRIDGE_REPORT_MAX_CHARS`** from evidence, not guesses. |

---

## 6. Expected outcomes (honest framing)

Under typical setups, **session startup** context alone often lands in **~85–92%** token reduction vs dumping full memory; **90–95%** is plausible when **combined** with **WASM compute**, **vector / embedding retrieval**, and **tight gateway caps** — all **measured**, not assumed. Treat percentages as **targets to validate**, not guarantees.

---

## Agent discovery

- **Machine-readable:** `tooling/bot_bootstrap.json` → **`openclaw_ainl_gold_standard`** (checklist) · **`openclaw_host_ainl_1_2_8`** (v1.2.8 host briefing: repo vs host)
- **Hub:** [`HOST_PACK_OPENCLAW.md`](HOST_PACK_OPENCLAW.md) · [`docs/README.md`](../README.md) § operations · [`DOCS_INDEX.md`](../DOCS_INDEX.md)
