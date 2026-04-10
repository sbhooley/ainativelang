# OpenClaw requests 2–6 → AINL v1.2.8 mapping (docs-only, honest)

> **Current `ainl` release:** **v1.5.0** (see `docs/RELEASE_NOTES.md`). The body below describes the **v1.2.8** request-mapping baseline; later releases add features (e.g. Hermes, OpenClaw CLI polish **v1.3.0**, native Solana **v1.3.1**, ArmaraOS host pack **v1.4.0**, docs alignment **v1.5.0**) without changing this lane analysis.

**Purpose:** This note maps OpenClaw’s “2–6” requests (summarizer, WASM compute, vector retrieval, per-feature caps, sparse attention) to what **AINL v1.2.8** **already implements**, what is **operator/host wiring**, and what is **out of scope** for AINL’s lane (compile-once deterministic graph runtime).

**Key principle (keep AINL in its lane):** AINL does **not** rewrite workflow logic at runtime. It does **not** generate new `.ainl` graphs during execution. It does **not** do dynamic prompt optimization as a first-class runtime feature. What *can* adapt is the **self-tuning resource & budget layer** around execution: caps, hydration, pruning, embedding selection, and observability feedback loops driven by OpenClaw scheduling + configuration.

---

## 2) Session Summarizer (prevent unbounded growth)

### What v1.2.8 ships
- **Summarizer program:** `intelligence/proactive_session_summarizer.lang`
- **Runner wiring:** `python3 scripts/run_intelligence.py summarizer`
- **Scheduling guidance:** `docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md` (cron)
- **Embedding-friendly output:** session summaries store the actual summary text in `payload.summary` so the embedding pilot can index meaningful content (see `docs/operations/EMBEDDING_RETRIEVAL_PILOT.md`).

### What it does (and does not do)
- **Does:** produce compact, durable summary artifacts/records that OpenClaw can use for bootstrap and retrieval.
- **Does not:** “replace old turns inside OpenClaw’s internal session DB” unless the OpenClaw host explicitly implements that behavior. The v1.2.8 posture is **write summaries + prefer curated bootstrap**.

### Where it plugs into OpenClaw
- Cron: OpenClaw triggers the intelligence run on a cadence (daily is the recommended default in the gold standard; higher frequency is a host choice).
- Bootstrap: OpenClaw should prefer injecting curated context (`session_context.md` and/or summary artifacts) over dumping raw history (see `docs/operations/OPENCLAW_HOST_AINL_1_2_8.md`).

### Why it saves tokens
- Keeps bootstrap context and retrieval payloads bounded; avoids “zombie context” growth.
- Complements rolling budget hydration (`budget_hydrate`) and caps so summarization remains cost-aware.

---

## 3) WASM for compute-heavy operations (deterministic transforms)

### What v1.2.8 ships
- **WASM adapter support:** AINL can call deterministic compute via the `wasm` adapter.
- **Operator notes:** `docs/operations/WASM_OPERATOR_NOTES.md`

### What it does (and does not do)
- **Does:** move parsing/aggregation/scoring into deterministic compute so LLM prompts contain only the minimal derived summary when needed.
- **Does not:** ship a “standard library” of Rust/C WASM modules for every OpenClaw workload unless the operator provides them. v1.2.8 is the **call surface**, not a full compute pack.

### Where it plugs into OpenClaw
- In scheduled workflows / bridges: load input via `fs`/memory, call WASM, then store a compact result (or send a small digest to an LLM adapter).

### Why it saves tokens
- Removes prompt-based data parsing and transformation (often thousands of tokens) from recurring jobs.

---

## 4) Vector search for memory retrieval (top-k relevance)

### What v1.2.8 ships
- **Embedding storage + search:** `runtime/adapters/embedding_memory.py`
- **OpenClaw bridge verbs:** `embedding_workflow_index` / `embedding_workflow_search`
- **Pilot doc:** `docs/operations/EMBEDDING_RETRIEVAL_PILOT.md`
- **Startup context integration (optional):** `intelligence/token_aware_startup_context.lang` supports an embedding-first candidate path when enabled.

### What it does (and does not do)
- **Does:** retrieve top-k relevant snapshots/snippets instead of listing many memory hits into a prompt.
- **Does not:** guarantee embeddings are always enabled. It is explicitly **optional** and gated by:
  - `AINL_STARTUP_USE_EMBEDDINGS=1` (selection logic enabled)
  - `AINL_EMBEDDING_MODE != stub` (real embeddings configured)

### Where it plugs into OpenClaw
- Startup context: embedding-first candidate selection can reduce `session_context.md` size versus filesystem-only selection.
- Retrieval: OpenClaw bridge tools can query embeddings to fetch only the highest-signal records.

### Why it saves tokens
- Reduces retrieval payload size and improves relevance, which reduces follow-up turns and “context stuffing.”

---

## 5) Strict per-feature token caps (budget discipline)

### What v1.2.8 ships
- **Caps staging + operator discipline:** `docs/operations/TOKEN_CAPS_STAGING.md`
- **Usage observability + alerts + trends:** `docs/operations/TOKEN_AND_USAGE_OBSERVABILITY.md`
- **Sizing probe:** `ainl bridge-sizing-probe` (suggests a sane `AINL_BRIDGE_REPORT_MAX_CHARS`)
- **Startup token clamps:** `AINL_STARTUP_CONTEXT_TOKEN_MIN` / `AINL_STARTUP_CONTEXT_TOKEN_MAX` (intelligence-side budget)
- **Rolling budget hydration:** `scripts/run_intelligence.py` merges rolling budget into `MONITOR_CACHE_JSON` (`budget_hydrate`)
- **Cap auto-tuner (resource/budget layer):** `scripts/auto_tune_ainl_caps.py` (invoked via `run_intelligence.py auto_tune_ainl_caps`)

### What it does (and does not do)
- **Does:** enforce and tune caps at the **resource and interface boundaries** (bridge report size, startup context allocation, gateway caps, rolling budgets, prune/cleanup flows documented in ops).
- **Does not:** assume the runtime has a universal `core.token_count` primitive or that every program dynamically measures LLM tokens mid-run. In v1.2.8, caps are enforced via **configuration + disciplined surfaces + observability**.

### Where it plugs into OpenClaw
- Host config (`openclaw.json` env vars), cron schedules, and gateway process env for promoter caps.
- Observability loops feed back into tightening/loosening caps via the **auto-tuner** and operator review.

### Why it saves tokens
- Prevents one monitor/digest from ballooning and starving the rest; makes “budget posture” explicit and enforceable.

---

## 6) Sparse attention in model calls (provider-dependent)

### What v1.2.8 ships
- **No provider-specific sparse-attention switch is claimed as shipped** in v1.2.8.

### Honest guidance
- Even when providers offer compute-side optimizations, **billing is usually per token**; the strongest, reproducible savings come from sending **fewer low-value tokens**.
- The v1.2.8 path to “sparse-effective” behavior is: **tight caps + hydration + summarization + embedding top-k**, not a magic flag.

---

## Bottom line

AINL v1.2.8 already provides a **self-managing with adaptive intelligence** posture via a **self-tuning resource & budget layer** (caps, hydration, pruning, embedding retrieval, observability, and cap auto-tuning) layered around a **compile-once deterministic graph runtime**. This is the correct technical foundation for sustaining **~84–95%+** (often **90–95%**) savings on OpenClaw-style scheduled monitoring/digest workflows without claiming runtime self-rewriting of workflow logic.

