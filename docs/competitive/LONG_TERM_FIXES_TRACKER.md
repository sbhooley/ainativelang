# Long-term fixes tracker (post-2026-05 critic review)

This is the **visible roadmap** for closing the credibility and scope gaps surfaced in the 2026-05 community review. Each row is a piece of committed work with an owner, a current state, and a definition of "done." Treat this as the authoritative tracker for evidence/positioning work that does not yet have an issue.

**Why this file exists:** Reviewers correctly observed that absence of in-progress work is worse than imperfect in-progress work. Better to ship this tracker than to look like nothing is being addressed.

**Source review:** the analysis that produced this list lives at [`docs/competitive/CRITICISM_RESPONSE_2026-05.md`](CRITICISM_RESPONSE_2026-05.md) *(TBD — short summary of the structural gaps the critic identified and how this tracker maps to each one)*.

---

## Status legend

- 🟢 **Done** — landed, evidence committed
- 🟡 **In progress** — work has started, ETA in the row
- 🔴 **Not started** — accepted as a gap, awaiting capacity
- ⚪ **Decided against** — explicitly out of scope (with reason)

---

## Tier 1 — Re-anchor positioning (target: 2 weeks)

| ID | Item | Status | Acceptance criteria |
|----|------|--------|---------------------|
| **T1.1** | README headline copy carries baseline A/B/C qualifier on every numeric claim | 🟢 | First-screen `README.md` table tags A/B/C; no bare "90%" / "80%" outside table |
| **T1.2** | "Current evidence" disclosure block in `README.md` naming the 3 committed cases + "no external paying customer yet" | 🟢 | Block exists above the install commands; linked from `PRODUCTION_EVIDENCE.md` |
| **T1.3** | `PRODUCTION_EVIDENCE.md` adds explicit "Class (a) third-party customer deployment: none committed yet" disclosure | 🟢 | Top of file before Case 1 |
| **T1.4** | `tooling/production_evidence.json` adds `classification` field (`a`/`b`/`c`/`d`) per case + top-level `external_paying_customer_count: 0` | 🟢 | Schema bumped; field present; CI lint can read it |
| **T1.5** | `docs/competitive/VS_HAND_WRITTEN_RUNNER.md` exists and concedes the token point against baseline B; sells compile/audit/emit | 🟢 | File exists; tied into `WHEN_AINL_DOES_NOT_HELP.md` and `COMPARISON_TABLE.md` |
| **T1.6** | `scripts/benchmark_langgraph_runtime.py` exists as TODO scaffold (script header documents intent + assumptions; emits placeholder JSON) | 🟢 | Script runs and writes `tooling/benchmark_langgraph_runtime.json` with `status: "not_implemented"` |
| **T1.7** | `scripts/benchmark_temporal_authoring.py` exists as TODO scaffold | 🟢 | Same shape as T1.6 |
| **T1.8** | `scripts/benchmark_token_savings.py` doc-comment surfaces the `doc_type_hint` assumption + the `support_triage` 3-vs-1-LLM-call nuance | 🟢 | Module docstring updated; honest scope visible |
| **T1.9** | `docs/CLAIMS_AND_EVIDENCE.md` tags every numeric claim row with required baseline (A/B/C) | 🟢 | Every claim row contains explicit baseline reference |
| **T1.10** | `docs/competitive/COMPETITIVE_MESSAGING.md` removes or flags numbers that don't trace to committed JSON (e.g. "$2,100/mo → $105/mo", "12+ enterprise customers", "2,500 GitHub stars") | 🟢 | Untraceable numbers either removed, marked **TBD — pending source**, or moved to clearly-labeled "draft messaging" sub-page |
| **T1.11** | `AINL_COST_SAVINGS_REPORT.md` / `AINL_INFRASTRUCTURE_DIAGNOSTIC.md` / `AINL_OPERATIONAL_DEPLOYMENT_REPORT.md` → one-line deprecation stubs pointing to `CLAIMS_AND_EVIDENCE.md` + `PRODUCTION_EVIDENCE.md` | 🟢 | Originals preserved under `archive/legacy_savings_reports/` for provenance; root files reduced to pointer stubs |

---

## Tier 2 — Close the real evidence gap (target: 1–3 months)

| ID | Item | Status | Acceptance criteria |
|----|------|--------|---------------------|
| **T2.1** | `scripts/benchmark_langgraph_runtime.py` — implement for real. Actually run a LangGraph agent loop with token tracker on `enterprise_monitor` and `support_ticket_router` workloads. | 🔴 | Committed JSON shows AINL vs LangGraph per-run token deltas; defensible methodology in module docstring |
| **T2.2** | `scripts/benchmark_temporal_authoring.py` — hand-write Temporal worker for `enterprise_monitor`, count source tokens, commit JSON | 🔴 | `tooling/temporal_authoring_tokens.json` committed; methodology says runtime parity is **not** claimed |
| **T2.3** | `scripts/benchmark_vs_hand_runner.py` — port three workloads (`enterprise_monitor`, `support_ticket_router`, `data_pipeline`) to **competent_python** + **production_grade** baseline-B runners; measure source tokens, source LOC, and an 8-row audit checklist. Per-run runtime tokens deferred (no runtime delta vs baseline B). Compile-time error catch rate when LLM-authors source: qualitative only (no committed run). Lift-to-Temporal LOC: deferred to **T2.2**. | 🟢 | `tooling/benchmark_vs_hand_runner.json` committed (2026-05-19); aggregate competent ratio 1.41×t / 2.01×L; production ratio 3.41×t / 4.52×L; AINL audit 7/8 vs competent 0/8 vs production 5.33/8. `VS_HAND_WRITTEN_RUNNER.md` per-workload + audit-checklist tables rendered. `CLAIMS_AND_EVIDENCE.md §9` updated with measured numbers + caveats. |
| **T2.4** | Identify 3 candidate third-party deployments (fintech compliance / MSP / internal ops with audit requirement) + draft 1-page pilot outreach | 🔴 | Pipeline doc in `docs/competitive/PILOT_PIPELINE.md`; uses critic's quote ("show me production where this saved real money") as opening |
| **T2.5** | Pilot instrumentation kit — audit JSONL parser + before/after comparison script that a pilot customer can run locally and self-report | 🔴 | `scripts/pilot_kit/` directory; `pilot_kit/README.md` explains what to share + what stays private |
| **T2.6** | Add Class (a) customer case template to `OPENCLAW_PRODUCTION_SAVINGS.md` so a real third-party row can be added without re-architecting `PRODUCTION_EVIDENCE.md` | 🔴 | Template includes `classification: a`, `external_organization` (anonymized OK), and a "verified by" field |
| **T2.7** | First Class (a) row landed in `PRODUCTION_EVIDENCE.md` | 🔴 | Top-of-file `external_paying_customer_count` updates from `0` to `≥1` |

---

## Tier 3 — Fix the scope problem (target: 3–6 months)

| ID | Item | Status | Acceptance criteria |
|----|------|--------|---------------------|
| **T3.1** | Two-tier adapter classification (**Core** / **Extended** — naming chosen over `tier_1`/`tier_2` and over `Core`/`Ecosystem` for honesty until third-party adapters land) in `ADAPTER_REGISTRY.json`; surface in `ainl doctor` and README | 🟢 Done | Every entry carries `tier: "core" \| "extended"` + a top-level `tier_meanings` block (`ADAPTER_REGISTRY.json` + regenerator `scripts/update_adapter_registry_tiers.py`). `ainl doctor` prints `adapter_tiers: 29 core + 16 extended (all supported)`. README points at `docs/adapters/ADAPTER_TIERS.md`. Canonical doc lists both tiers in full. Verified by `tests/test_adapter_tier_shim_compat.py`. |
| **T3.2** | Adapter doc badges auto-generated from registry tier | 🟡 Partial | Tier metadata is authoritative in `ADAPTER_REGISTRY.json` and re-rendered by `scripts/update_adapter_registry_tiers.py`. Inline tier badges in every per-adapter doc page is a follow-up (low value: the single Core/Extended table in `docs/adapters/ADAPTER_TIERS.md` is canonical and easier to keep accurate). |
| **T3.3** | Move `adapters/solana.py` + Solana examples to a separate namespace; permanent stable-alias shim at old path (replaces the original "community-tier + deprecation stub" framing — no deprecations, both paths permanent) | 🟢 Done | `adapters/solana.py` → `adapters/extended/solana.py` (git mv). Old path is now a PEP 562 `__getattr__` alias forwarding every public + private symbol to the canonical module — verified by `tests/test_adapter_tier_shim_compat.py::test_solana_stable_and_canonical_resolve_to_same_class` and by re-running the existing solana suite unchanged. Registry tier set to `"extended"`. No examples moved (kept in `examples/` so `examples/README.md` curriculum stays stable). |
| **T3.4** | Move `adapters/tiktok.py` + replace hardcoded `~/.openclaw/...` path with layered config → permanent stable-alias shim at old path | 🟢 Done | `adapters/tiktok.py` → `adapters/extended/tiktok.py`. Old path is a PEP 562 alias (no warnings). New layered config: **explicit `db_path` arg → env `AINL_TIKTOK_DB` → legacy default with one-time `UserWarning` → `TiktokAdapterConfigError` fail-fast** with an actionable message. Side-effect: fixed a pre-existing broken `from ainl_adapters import AdapterBase` import that had been unimportable. Verified by `tests/test_adapter_tier_shim_compat.py` (4 layered-config cases). |
| **T3.5** | $AINL token / marketplace audit — **transparent restatement** (not mass-removal): every aspirational marketing claim is preserved but explicitly tagged with current shipping status and a pointer to live, verifiable data | 🟢 Done | **AI_Native_Lang side** (this PR): new [`tooling/token_status.json`](../../tooling/token_status.json) as canonical data substrate (live mint, on-chain placeholders for script refresh, git-verifiable contributor counts, original aspirational goals retained). New [`scripts/fetch_token_status.py`](../../scripts/fetch_token_status.py) refreshes the JSON from Solana RPC + GitHub API + local git (stdlib only, no auth required for public reads). New root [`CONTRIBUTORS.md`](../../CONTRIBUTORS.md) with C3 framing — founder-led, multi-contributor, AI-assisted; **Steven B Hooley** (founder), **Terrance Schonleber**, **Kobe Welker** as active human maintainers; AI co-author identities listed; classification methodology documented. Every $AINL-claim surface (`docs/community/CHAMPIONS_PROGRAM.md`, `docs/learning/intermediate/patterns/template-marketplace-submission.md`, `docs/learning/intermediate/patterns/README.md`, `docs/learning/intermediate/README.md`, `docs/learning/basics/README.md`, `docs/learning/basics/04-next-steps.md`, `docs/enterprise/ENTERPRISE_FAQ.md`, `docs/enterprise/METRICS_DASHBOARD_SPEC.md`) gets a **status banner** or inline `📋 planned` tags — numbers preserved, status owned. **ainativelangweb side** (separate follow-up PR — repo boundary): apply the same restatement pattern to `app/(marketing)/community/token/page.tsx`, sourcing live values from `tooling/token_status.json`. |
| **T3.6** | Move `demo/` → `experiments/` so reviewers don't conflate with `examples/`; keep `.ainl-library-skip` | 🔴 | `experiments/README.md` explains what's there + why it's skipped from CI |
| **T3.7** | Curate top 2–3 `agent_reports/` as `docs/case_studies/` entries; move rest to `archive/agent_reports/` | 🔴 | Curated set linked from README; archive preserved for provenance |
| **T3.8** | Canonical `docs/WHO_IS_THIS_FOR.md` merging `WHEN_AINL_DOES_NOT_HELP` + `ARMARAOS_GTM` + open-core/sales docs; deprecate overlapping docs with pointers | 🔴 | One source of truth; sales/marketing copy points here |
| **T3.9** | `tooling/emit_targets.json` (new) — `production_ready: bool` per emit target; CLI shows status in `ainl emit --list` | 🔴 | Targets with `production_ready: false` are marked when used; README lists only ready ones |
| **T3.10** | Examples audit — keep ~30 strict-valid canonical under `examples/`; move rest to `examples/showcase/` or `archive/`; CI runs strict on canonical set only | 🔴 | Canonical set agrees with `tooling/artifact_profiles.json` `strict-valid` list |
| **T3.11** | Docs root consolidation — `docs/*.md` root files into 4 sections (`architecture/`, `ops/`, `competitive/`, `learning/`) with one-line pointer stubs at old paths | 🔴 | Root `docs/` shows ≤ 10 files; rest in subdirs |

---

## Tier 4 — Guardrails (target: alongside Tier 1–3)

| ID | Item | Status | Acceptance criteria |
|----|------|--------|---------------------|
| **T4.1** | CI check: any new claim ratio in markdown is tagged "vs A" / "vs B" / "vs C" (regex in `scripts/check_claims_baselines.py`) | 🔴 | CI fails on unqualified `\d+%` / `\d+×` near words like "savings" / "fewer" outside whitelisted contexts |
| **T4.2** | CI check: `PRODUCTION_EVIDENCE.md` entries have a `last_verified` date < 12 months old; warn if older | 🔴 | Field added to each case; CI prints warning + opens issue if stale |
| **T4.3** | CI check: no marketing doc mentions "80%" / "90%" / "95%" / "7.2x" without an immediately-adjacent baseline tag | 🔴 | Builds on T4.1; sweep applied to `docs/competitive/`, `README.md`, `WHITEPAPERDRAFT.md` |
| **T4.4** | `CONTRIBUTING.md` requires quarterly review of `CLAIMS_AND_EVIDENCE.md` + `PRODUCTION_EVIDENCE.md`; date-stamp the review in `tooling/evidence_review_log.json` | 🔴 | Process doc + log file exist; first scheduled review on calendar |

---

## How to update this file

1. When work lands, change status (🔴 → 🟡 → 🟢) and append a short evidence link (PR, commit, file path).
2. When scope changes, append a dated note under the row rather than rewriting silently.
3. When a row is decided against, set ⚪ and explain the trade-off — do not delete it.

---

## Related

- [`PRODUCTION_EVIDENCE.md`](PRODUCTION_EVIDENCE.md) — committed cases + missing-evidence disclosure
- [`WHEN_AINL_DOES_NOT_HELP.md`](WHEN_AINL_DOES_NOT_HELP.md) — baseline A/B/C honest filter
- [`VS_HAND_WRITTEN_RUNNER.md`](VS_HAND_WRITTEN_RUNNER.md) — the five-axis comparison
- [`COMPARISON_TABLE.md`](COMPARISON_TABLE.md) — what's measured, what's TBD
- [`../CLAIMS_AND_EVIDENCE.md`](../CLAIMS_AND_EVIDENCE.md) — claim-to-evidence crosswalk
