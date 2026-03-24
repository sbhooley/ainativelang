# AI Native Lang (AINL): An AI-Native Programming Language for Deterministic Agent Workflows

Graph-based agent orchestration, canonical IR, and compile-once / run-many execution for production AI systems.

**Version:** 1.2.4
**Project status:** active human + AI co-development
**Primary implementation:** `compiler_v2.py`, `runtime/engine.py`, `scripts/runtime_runner_service.py`
**Reference ecosystem:** OpenClaw/NemoClaw-integrated autonomous workflows, canonical strict validation, multi-target emitters, sandboxed operator deployments

---

## Abstract

AI Native Lang (AINL) is a graph-first programming system designed for AI-oriented workflow generation, validation, and execution. It provides a compact domain-specific language (DSL) that compiles into a canonical intermediate representation (IR) consisting of nodes and edges. The system is built around deterministic runtime execution, strict validation, explicit side effects, pluggable adapters, and optional multi-target emission to downstream artifacts such as FastAPI, React/TypeScript, Prisma, OpenAPI, Docker, cron, and other deployment surfaces.

AINL addresses an emerging systems problem in modern AI engineering: as large language models (LLMs) gain larger context windows and stronger reasoning capabilities, many agent systems still rely on prompt loops for orchestration, state handling, and tool invocation. This creates rising token cost, hidden state, degraded predictability, and weak auditability. AINL proposes a different architecture: use the model to generate a compact graph workflow once, then rely on a deterministic runtime to execute it repeatedly.

The language has been exercised in production-style OpenClaw workflows involving email, calendar, social monitoring, database access, infrastructure checks, queues, WebAssembly modules, cache, memory, and autonomous operational monitors. This whitepaper describes AINL's architecture, semantics, strict-mode guarantees, operational role, benchmark posture, and relevance to AI-native systems design.

---

## 1. Introduction

Recent progress in large language models has shifted the software engineering conversation from "can models write code?" to "what is the right substrate for systems built by and for AI agents?"

The default answer in many contemporary frameworks has been the **prompt loop**:

1. Send a task to the LLM
2. Let the LLM decide what tool to call
3. Append results back into prompt history
4. Continue until a stopping condition is reached

This pattern is easy to prototype, but it creates architectural problems:

- Prompt growth over time
- Weak control over execution ordering
- Hidden internal state
- Difficult debugging
- Repeated reasoning over prior steps
- High inference cost for recurring workflows

At the same time, model vendors are pushing toward increasingly large context windows to support coding, long documents, research synthesis, and agents. Larger contexts help, but they do not eliminate the core orchestration issue. Even with improved attention mechanisms, a system that relies on repeated long prompt histories remains expensive and brittle.

AINL addresses this by introducing a **graph-canonical substrate** for AI-generated workflows.

Instead of treating the prompt as the execution fabric, AINL treats the prompt as the place where the workflow is authored. Once authored, the workflow becomes a graph IR that can be validated, executed, audited, emitted, and reused independently of the model.

---

## 2. Problem Statement

AINL is motivated by three overlapping challenges.

### 2.1 Prompt-Orchestrated Agents Do Not Scale Cleanly

Prompt-loop agents combine planning, state, control flow, and tool use inside a model-mediated conversation. This often works for short tasks, but degrades for long-running or recurring workflows.

Typical symptoms include:

- Bloated prompts
- Token-cost escalation
- Inconsistent reasoning paths
- Repeated tool misuse
- Lack of stable execution trace

### 2.2 Long Context Windows Are Helpful but Insufficient

LLMs increasingly support large context windows, but long context introduces its own scaling issues:

- KV cache memory growth
- Expensive attention over large sequences
- Greater pressure to summarize or compress state
- Higher cost when orchestration remains prompt-centric

Architectural innovations such as sliding-window attention, sparse attention, and state-space/hybrid sequence models can help inference scale. But they operate primarily at the model level, not the workflow layer.

### 2.3 AI Systems Need a Native Intermediate Representation

If AI agents are to generate reliable systems, they benefit from a representation that is:

- **Compact**
- **Structured**
- **Deterministic**
- **Analyzable**
- **Emitter-friendly**
- **Separable** from any one runtime target

AINL is designed to be that representation.

---

## 3. System Overview

AINL consists of five main layers:

1. AINL surface language
2. Compiler
3. Canonical graph IR
4. Runtime engine
5. Emitters and adapters

### 3.1 High-Level Flow

The graph IR is central. The surface syntax is one way to serialize it; emitter targets are other serializations or projections.

### 3.2 Core Invariant

AINL's central invariant is:

> **Canonical IR = nodes/edges; everything else is serialization.**

This prevents conceptual drift between:

- Source syntax
- Step execution
- Emitted artifacts
- Runtime semantics

---

## 4. Language Design Principles

AINL's design reflects a specific AI-native philosophy.

### 4.1 Compact and Low-Entropy by Design

AINL is intentionally not optimized for traditional human readability. Its surface syntax is compact and regularized to improve generation reliability for AI systems.

This is not a rejection of human use; it is a choice about primary optimization target.

### 4.2 Graph-First Semantics

Workflow semantics are defined by graph structure rather than conversational sequencing.

This allows:

- Static analysis
- Canonicalization
- Runtime determinism
- Graph introspection
- Future semantic diffing and patching

### 4.3 Explicit Binding and Explicit Effects

AINL makes dataflow and side effects explicit.

Adapter invocations follow structured forms such as:

- `R group verb ... ->out`
- `If condition ->L_then ->L_else`
- `J`, `Ret`
- Declarations such as `S`, `D`, `E`, `Rt`, `Lay`, `P`, `A`, `Pol`, etc.

This gives both humans and machines clear visibility into what a program is doing.

### 4.4 Pluggable Backends

AINL describes intent and orchestration. Adapters and emitters implement concrete behavior.

This separation makes AINL suitable as an intermediate representation spanning:

- Backend logic
- Frontend declarations
- Workflow automation
- Operational monitoring
- External integrations

---

## 5. Compiler and Canonical IR

The primary compiler implementation is `compiler_v2.py`, which parses AINL source, validates it, and emits canonical graph IR.

### 5.1 Canonical IR Structure

The canonical graph IR is organized around labels containing nodes and edges. This makes the IR suitable for:

- Deterministic runtime execution
- Structural validation
- Graph inspection
- Round-trip conversion
- Compatibility handling for legacy step forms

### 5.2 Strict Mode

Strict mode provides a high-confidence subset of language behavior suitable for AI-generated code and public benchmark claims.

Strict guarantees include:

- Canonical graph emission
- Single-exit discipline for endpoint labels
- Validated call returns
- No undeclared references
- No unknown module operations
- Adapter arity validation
- No unreachable or duplicate nodes
- Canonical node IDs

This is a key part of AINL's value proposition: the system is not merely expressive, but also aggressively validating.

### 5.3 Compatibility Lane

AINL also supports compatibility-oriented or non-strict examples. These are useful operationally and historically, but they should be segmented from strict canonical headline claims.

This distinction is important for truthful documentation and benchmarking.

### 5.4 Compile-time composition (includes)

AINL programs can **`include`** other `.ainl` sources before compilation completes. The compiler **merges** included labels under an **alias prefix** (`alias/LABEL`, e.g. `retry/ENTRY`, `retry/EXIT_OK`). Shared modules declare **`LENTRY:`** and **`LEXIT_*:`** labels; parents invoke them with **`Call alias/ENTRY ->out`**. This is **compile-time** composition only—no runtime plugin loader—so agents and humans can reuse **verified** subgraphs, shrink duplicated control flow, and reason over **qualified** names in the canonical IR. **`include` directives must appear before the first top-level `S` / `E`** in the host file so the prelude merges into IR. At runtime, **`RuntimeEngine`** may **qualify bare child label names** (e.g. on **If** / **Loop** edges) using the current **`alias/`** stack frame so graph execution reaches merged keys—see §6.4. Starter modules ship under `modules/common/` with strict-safe patterns (including **guard**, **session_budget**, and **reflect** helpers for operational ceilings and gates), and a minimal include demo is provided in `examples/timeout_demo.ainl`. Semantics and tests: `tests/test_includes.py`; introspection: `docs/architecture/GRAPH_INTROSPECTION.md`; reader-facing summary: **`docs/WHAT_IS_AINL.md`** (canonical primer; root **`WHAT_IS_AINL.md`** is a stub).

### 5.5 Graph visualization CLI and diagnostic surfacing

The reference implementation ships **CLI** tools that compile in **strict** mode and surface **native structured diagnostics** (`Diagnostic` rows with lineno, optional character spans, kinds, and suggested fixes) alongside legacy string errors. Validators and the **Mermaid graph visualizer** (`ainl visualize` / `ainl-visualize`, `scripts/visualize_ainl.py`) reuse this path; output can be **rich**-styled (optional dependency), plain text, or **JSON** for automation. The visualizer renders **`ir["labels"]`** as **Mermaid** flowcharts with **subgraph clusters** per include alias and explicit **synthetic edges** for **`Call`** into callee entry labels where helpful for human understanding. As of `v1.2.1`, the same CLI supports direct image export (`--png`, `--svg`, with `--width`/`--height` and extension auto-detect for `.png`/`.jpg`/`.jpeg`/`.svg`) via Playwright-backed rendering.

---

## 6. Runtime Architecture

The runtime implementation lives primarily in `runtime/engine.py`.

### 6.1 Deterministic Execution

The runtime executes graph nodes in dependency-consistent order and does not rely on accumulating conversational state.

This yields:

- Bounded execution semantics
- Reproducible traces
- Explicit state flow
- Easier debugging

### 6.2 Graph-Preferred Execution

AINL's runtime is graph-preferred rather than prompt-preferred. The workflow exists independently of model context.

### 6.3 Safety Limits

The runtime enforces operational limits such as:

- Maximum steps
- Depth restrictions
- Timeout boundaries
- Adapter capabilities
- Optional policy validation

This makes it suitable for recurring and semi-autonomous workflows.

### 6.4 Label routing after `include` (bare vs qualified ids)

Merged IR stores most label keys as **`alias/LABEL`**. Branch and loop steps sometimes still name a target as a **short** id (e.g. a child of the same module). The reference runtime resolves **`Call`**, **Jump**, and graph edges to **`labels`** keys by: (1) using the name as-is when it is already a key; (2) if the name contains no `/` and is missing, prepending the **`alias/`** segment taken from the innermost stacked label id that contains **`/`** (e.g. executing under **`accmem/LACCESS_LIST`** qualifies **`_child`** to **`accmem/_child`** when that key exists). This is deterministic, preserves programs that already use fully qualified names, and keeps nested control flow inside included subgraphs aligned with graph-preferred execution. Spec pointer: `docs/RUNTIME_COMPILER_CONTRACT.md`.

### 6.5 Optional CLI trajectory and Hyperspace agent emission

The reference **CLI** can append **one JSON object per executed step** to **`<source-stem>.trajectory.jsonl`** beside the `.ainl` source when enabled (`ainl run --log-trajectory` or **`AINL_LOG_TRAJECTORY`**). This **per-step trace** is separate from the HTTP runner service’s structured audit JSON stream (`docs/operations/AUDIT_LOGGING.md`). The validate CLI can emit a **standalone Python module** with **`--emit hyperspace`**, embedding compiled IR for hosts that want a single-file agent; the emitted scaffold wires **`vector_memory`** and **`tool_registry`** (local JSON-backed adapters; **`docs/reference/ADAPTER_REGISTRY.md`** §9). See **`docs/trajectory.md`**, **`docs/emitters/README.md`**, and **`examples/hyperspace_demo.ainl`**.

---

## 7. State Discipline

AINL manages workflow state through explicit, adapter-mediated tiers rather
than hiding state inside prompt history or ad hoc globals.

### 7.1 Four-Tier State Model

| Tier | Scope | Mechanism | Example |
|------|-------|-----------|---------|
| **Frame** (ephemeral) | Single run | Built-in variable dict | `R core.ADD 2 3 ->sum` |
| **Cache** (short-lived) | Runtime instance | Cache adapter with optional TTL | Cooldown tracking, throttle state |
| **Persistent** (durable) | Across restarts | Memory adapter, SQLite, filesystem | Session context, long-term facts, workflow checkpoints |
| **Coordination** (cross-workflow) | Between workflows/agents | Queue adapter, agent mailbox | Downstream handoffs, inter-agent tasks |

The frame is always available. Higher tiers require the corresponding adapter
to be in the allowlist.

### 7.2 Why Tiered State Matters

Systems that rely on prompt history for state suffer from growing context
windows, rising token costs, hidden state that is hard to inspect or
reproduce, and scattered conventions across memory, cache, and database.

AINL's state discipline addresses these problems by:

- making every piece of state explicit and adapter-mediated,
- separating ephemeral scratch values from durable records,
- providing export/import bridges for persistent state (JSON/JSONL for memory,
  SQL for SQLite),
- mapping each sandbox profile to a specific set of available state tiers.

### 7.3 Memory as the Recommended Durable State Mechanism

The memory adapter provides structured records keyed by `(namespace,
record_kind, record_id)` with JSON payloads, timestamps, and optional TTL.
While classified as `extension_openclaw` by packaging origin, memory is the
**recommended durable state mechanism** for any workflow that needs persistence
beyond a single run. It is the primary persistent state tier across all
deployment environments.

See `docs/architecture/STATE_DISCIPLINE.md` for the full specification.

**Optional access metadata (opt-in module):** `modules/common/access_aware_memory.ainl` provides **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, and **`LACCESS_LIST_SAFE`** helpers that bump **`metadata.last_accessed`** (ISO timestamp) and **`metadata.access_count`** on selected **`memory.get`** / **`memory.list`** / **`memory.put`** paths. Plain adapter calls remain unchanged if you do not use the module. **`LACCESS_LIST_SAFE`** uses a **While** + index loop for graph-reliable list snapshots; **`LACCESS_LIST`** uses a **`ForEach`** surface form whose IR may not yet fully match **Loop** lowering—hosts that rely on **graph-preferred** execution should prefer **`LACCESS_LIST_SAFE`** until the compiler emits an equivalent **Loop**. Details: module header, `modules/common/README.md`, `docs/RELEASE_NOTES.md` (v1.2.4).

### 7.4 Narrative and integration references

For a single readable walkthrough of tiered state, the **`memory`** adapter
contract, MCP hosts (**OpenClaw** and **ZeroClaw**), and how **OpenClaw bridge**
daily markdown differs from SQLite-backed workflow memory, see **[AINL,
structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents)**.
Canonical specs: `docs/architecture/STATE_DISCIPLINE.md`,
`docs/adapters/MEMORY_CONTRACT.md`, `docs/getting_started/HOST_MCP_INTEGRATIONS.md`,
`docs/ainl_openclaw_unified_integration.md`, `docs/operations/UNIFIED_MONITORING_GUIDE.md`.

---

## 8. Adapter Model

AINL's runtime delegates concrete actions to adapters.

### 8.1 Adapter Philosophy

Adapters provide the implementation layer for effects while keeping the language surface stable.

Examples include:

- `core`
- `http`
- `sqlite`
- `fs`
- `email`
- `calendar`
- `social`
- `svc`
- `cache`
- `queue`
- `wasm`
- `memory`
- OpenClaw-specific operational extensions

### 8.2 Capability-Aware Safety

Adapters declare behavior through capability and metadata surfaces, including safety-oriented boundaries. The system makes operator-only or sensitive surfaces more explicit and easier to isolate.

Each adapter carries a `privilege_tier` in its metadata (`pure`, `local_state`, `network`, `operator_sensitive`). This classification is used by the policy validator and security reporting tools to make privileged boundary crossings visible and enforceable without changing language semantics.

### 8.3 Why This Matters

Without adapters, each new workflow often requires the model to regenerate API client code, state-handling logic, and integration boilerplate. With adapters, the workflow references a stable interface instead.

This reduces both generation burden and runtime ambiguity.

---

## 9. Multi-Target Emission

AINL is not just a runtime language. It is also an emitter source.

Supported target classes include:

- FastAPI
- React/TypeScript
- Prisma
- OpenAPI
- SQL
- Docker / Compose
- Kubernetes
- MT5
- Scraper outputs
- Cron / queue related projections

### 9.1 Single Spec, Many Targets

AINL allows a system to be described once and emitted into multiple downstream representations.

This has two important consequences:

1. It reduces duplicated generation effort
2. It provides a shared canonical source for backend, frontend, and operational surfaces

### 9.2 Emission Honesty

Benchmark and documentation claims must distinguish between:

- **full_multitarget** — expansion potential
- **minimal_emit** — practical deployment comparisons

This distinction is central to truthful benchmarking.

---

## 10. OpenClaw and Apollo as an Operational Validation Path

AINL has been validated in a real operational context through Apollo's OpenClaw workflows.

### 10.1 Core OpenClaw Integration

The implemented and exercised integrations include:

- Unread email retrieval
- Calendar event retrieval
- Social / web mention checks
- Leads and CRM access
- Service health checks
- Persistent JSON/cache state
- Notification queue dispatch
- WebAssembly computation modules

### 10.2 The Monitor Path

`demo/monitor_system.lang` serves as a key proof path for AINL's operational value.

It demonstrates:

- Cron scheduling
- Explicit state tracking
- Threshold logic
- Service health checks
- Queue-based notifications
- WASM-based scoring
- Cooldown logic
- Persistent state across runs

### 10.3 Autonomous Ops Extension Pack

AINL's role expanded further through a suite of autonomous ops workflows, including:

- Infrastructure watchdog
- TikTok SLA monitor
- Canary sampler
- Token cost tracker
- Token budget tracker
- Lead quality audit
- Session continuity
- Memory prune
- Meta monitor

These examples show that AINL is not limited to CRUD or toy orchestration; it is viable for:

- Self-monitoring systems
- Partial self-healing
- Stateful operational logic
- Coordinated monitor fleets

### 10.4 Memory surfaces in operational stacks

Operational validation spans **graph-local durable state** (the `memory`
adapter) and **host-specific surfaces**: OpenClaw **bridge** cron can append
**daily markdown** under the workspace memory directory, which is **orthogonal**
to structured SQLite records. **ZeroClaw**-hosted flows use the same AINL
memory path via MCP without depending on OpenClaw's markdown layout. See
**[AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents)**
and `docs/operations/UNIFIED_MONITORING_GUIDE.md`.

---

## 11. AINL and Long-Context LLM Systems

AINL is highly relevant to current long-context trends, but the relationship should be stated precisely.

### 11.1 What AINL Does Not Do

AINL is not itself a replacement for:

- Sparse attention
- Sliding-window attention
- State-space sequence compression
- KV-cache optimization inside the model

Those are model-architecture and inference-layer techniques.

### 11.2 What AINL Does Do

AINL reduces the need to solve orchestration by throwing ever more context at the model.

It does this by:

- Decomposing workflows into explicit nodes
- Storing state outside the prompt
- Making control flow deterministic
- Isolating LLM use to specific adapter calls
- Enabling compile-once / run-many operation

This means AINL operates at the **workflow layer**, complementing model-layer context optimizations.

### 11.3 Architectural Stack

AINL's contribution lives primarily in the third layer.

---

## 12. Benchmark Posture and Truthful Compactness Claims

AINL ships a **reproducible benchmark suite** spanning **size**, **runtime**, and optional **LLM-generation** quality—not a single scoreboard. Results must stay profile-scoped, mode-scoped, and honest about what each lane measures. Read **`BENCHMARK.md`** (generated tables + transparency notes) and the hub **`docs/benchmarks.md`** (highlights, glossary, commands).

### 12.1 Size Benchmark (Emitted Surface + Compiler Cost)

- **Default metric:** `tiktoken` with the **`cl100k_base`** encoder (shared with runtime tooling via `tooling/bench_metrics.py`). **`BENCHMARK.md`** foregrounds **tiktoken** in tables for billing-aligned reading; JSON rows still record the CLI **`--metric`** (default `tiktoken`) for viable-threshold logic and optional legacy lanes.
- **Legacy lane:** `approx_chunks` remains available as a **deprecated** lexical-size proxy; markdown de-emphasizes it—**not** equivalent to tokenizer-accurate billing.
- **Viable subset vs legacy-inclusive:** for `public_mixed` and `compatibility_only`, headline ratios use a **viable subset** (curated for representative workloads); **legacy-inclusive** totals appear separately in `BENCHMARK.md` for transparency.
- **minimal_emit fallback stub:** when no selected target emits code, the benchmark may attach a small **python_api** async stub (~20–30 tk)—documented per row in **`BENCHMARK.md`**.
- **Emitter compaction (Mar 2026):** **`prisma`** and **`react_ts`** benchmark stubs were shortened for efficiency (~50–70% tk reduction on those emitted lines in the benchmark set).
- **Compile latency:** each artifact reports **mean wall-clock compile time over three timed compiles** (`compile_time_ms_mean`, schema **`3.5+`** in `tooling/benchmark_size.json`), surfaced in `BENCHMARK.md` as **Compile ms (mean×3)**—separate from optional multi-run **compile reliability** batches.
- **Strict benchmark mode:** `scripts/benchmark_size.py` **`--strict-mode`** (honored only with **`--profile-name=canonical_strict_valid`**) enables strict reachability pruning for the headline strict-valid profile.
- **Economics:** optional estimated USD per generation from published list-price assumptions (same helper module as runtime).
- **Handwritten baselines:** `--compare-baselines` measures mapped AINL emits against `benchmarks/handwritten_baselines/` (pure async vs LangGraph-style stacks) using aligned metrics where possible.

**Outputs:** `scripts/benchmark_size.py` → **`BENCHMARK.md`** (human-readable, transparency notes), **`tooling/benchmark_size.json`**. Central doc hub: **`docs/benchmarks.md`**.

### 12.2 Runtime Benchmark (Compile-Once / Run-Many)

- **Post-compile** execution via `RuntimeEngine`: latency, peak RSS delta, adapter/trace counters.
- **Optional:** execution reliability batches, **scalability** probe on a large golden workflow, **cost** columns from source tiktokens + economics assumptions.
- **Baselines:** async handwritten stacks can be benchmarked beside AINL reference artifacts for latency and reliability.

**Outputs:** `scripts/benchmark_runtime.py` → `tooling/benchmark_runtime_results.json` (tracked for CI baseline when committed).

### 12.3 LLM Generation Benchmark (Ollama + Optional Cloud)

- **`ainl-ollama-benchmark`** runs the same prompt suite across local **Ollama** models.
- **`--cloud-model`** (e.g. `claude-3-5-sonnet`) optionally runs the same tasks through **Anthropic Messages** (`temperature=0`) for a cloud baseline; requires `ANTHROPIC_API_KEY` and `pip install anthropic` (optional extra `[anthropic]`). Missing key or SDK **skips** the cloud leg with a warning—local results still stand.

### 12.4 Profiles and Modes (Size / Runtime)

Profiles include:

- `canonical_strict_valid` (primary headline)
- `public_mixed`
- `compatibility_only`

Modes:

- **full_multitarget** — total downstream expansion potential across emitters
- **minimal_emit** — closer to practical deployment (capability-planned target set)

### 12.5 CI, Regression Gate, and Local Targets

- **`make benchmark`** — full local refresh (default JSON + markdown for size; runtime as configured in the Makefile).
- **`make benchmark-ci`** — CI-style JSON outputs (`tooling/benchmark_size_ci.json`, `tooling/benchmark_runtime_ci.json`) without editing `BENCHMARK.md` in automation.
- **GitHub Actions** `benchmark-regression` runs the CI slice, uploads JSON artifacts, and **`scripts/compare_benchmark_json.py`** fails the build on regressions beyond a tolerance (default 10%) against the baseline commit when baseline JSON exists in git.

### 12.6 Truthful Headline

The strongest current truthful claim is:

> AINL provides reproducible, profile-segmented compactness advantages in many canonical multi-target examples, and can materially reduce repeated generation effort by expressing workflow intent once and reusing it across execution and emission surfaces—while **runtime benchmarks** ground the **compile-once / run-many** cost story in measured post-compile behavior.

**Not supported:**

- Universal superiority claims over mainstream languages
- Guaranteed pricing claims from assumptions alone (economics tables are labeled and scenario-dependent)

---

## 13. Cost and Token Economics

AINL can save overall token expenditure in two distinct ways.

### 13.1 Authoring Density

Because the DSL is compact and structured, models can often express workflows with fewer generated tokens than they would need for equivalent boilerplate-heavy Python or TypeScript systems.

### 13.2 Compile-Once / Run-Many

AINL's bigger win is not just source compactness, but **execution architecture**.

Once the workflow is authored and compiled:

- It can be run repeatedly without needing the model to regenerate orchestration logic
- Runtime state is handled by adapters and stores
- Recurring workflows avoid repeated prompt-loop costs

This is especially meaningful for:

- Monitors
- Daemons
- Recurring reports
- Autonomous operational routines

### 13.3 Practical Framing

AINL should not be marketed as "always smaller than Python" in a universal sense. It should be framed as:

- Compact for graph/workflow expression
- Strong for multi-target leverage
- Efficient for compile-once / run-many scenarios
- Especially effective when orchestration would otherwise recur through LLM prompt loops

---

## 14. Why AINL Is Useful to AI Agents

AINL provides several concrete benefits to AI agents and automation systems.

### 14.1 Declarative Orchestration

Graphs are explicit. Sequencing is visible. Control flow becomes analyzable rather than implicit.

### 14.2 Capability-Aware Safety

Safety tags, adapter metadata, and policy validation help separate safe surfaces from operator-only or destructive ones.

### 14.3 Tiered State Discipline

Cross-run state is managed through a four-tier model (frame, cache, memory, coordination) rather than improvised file hacks or prompt-based memory accumulation. Memory is the recommended durable state mechanism for any workflow needing persistence across runs. See section 7.

### 14.4 Resilient Execution

The `Retry` operation supports both fixed and exponential backoff strategies with configurable caps. This allows workflows to express resilience against transient failures (e.g., network timeouts, rate limits) without external retry wrappers or manual sleep logic.

### 14.5 Policy Validation and Capability Discovery

The runner service validates workflows against declarative policies before execution, returning structured violations on failure. External orchestrators can discover runtime capabilities via the `/capabilities` endpoint. See section 15.

### 14.6 Oversight and Auditability

Pre/post-run reports and graph-level tracing provide operational visibility beyond shell logs or prompt histories.

---

## 15. Runner Service and Operator Boundary

AINL includes a FastAPI-based runner service (`scripts/runtime_runner_service.py`) that exposes the runtime as a framework-agnostic HTTP boundary for external orchestrators, sandbox controllers, and agent platforms.

### 15.1 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/capabilities` | GET | Returns runtime version, available adapters (with verbs, support tiers, effect defaults), and whether policy validation is supported |
| `/run` | POST | Accepts AINL source or pre-compiled IR, compiles, validates policy (if provided), executes, and returns structured output |
| `/enqueue` | POST | Asynchronous execution queue |
| `/result/{id}` | GET | Retrieve async execution results |
| `/health` | GET | Liveness check |
| `/ready` | GET | Readiness check |
| `/metrics` | GET | Runtime metrics |

### 15.2 Policy-Gated Execution

The `/run` endpoint accepts an optional `policy` object that specifies forbidden adapters, effects, effect tiers, and privilege tiers. If the compiled IR violates the policy, the runner responds with HTTP 403 and a structured list of violations **without executing**. This allows external orchestrators to enforce adapter, effect, and privilege-class restrictions at the runner boundary without modifying AINL's compiler or runtime semantics.

Supported policy fields include `forbidden_adapters`, `forbidden_effects`, `forbidden_effect_tiers`, and `forbidden_privilege_tiers`.

### 15.3 Capability Discovery

The `GET /capabilities` endpoint returns a machine-readable JSON response sourced from existing adapter metadata (`tooling/adapter_manifest.json`). Each adapter entry includes its verbs, support tier, effect default, recommended lane, and privilege tier. External orchestrators use this to discover what a given AINL runtime instance supports before submitting workflows, enabling dynamic adapter allowlist configuration and policy construction.

### 15.4 Sandbox and Operator Deployment

AINL is designed to run inside sandboxed, containerized, or operator-controlled environments. The runtime's adapter allowlist, resource limits, and policy validation provide the configuration surface that external orchestrators need. AINL is the **workflow layer**, not the sandbox or security layer; containment, network policy, and process isolation are the responsibility of the hosting environment.

Prescriptive sandbox profiles are documented for:

- **Minimal** — core adapter only, no I/O
- **Compute-and-store** — local computation and storage, no network
- **Network-restricted** — local + outbound HTTP, no agent coordination
- **Operator-controlled** — full adapter access with operator governance

These profiles are also packaged as machine-readable named security profiles in `tooling/security_profiles.json`, bundling recommended adapter allowlists, privilege-tier restrictions, runtime limits, and orchestrator expectations for each scenario.

A security/privilege report tool (`tooling/security_report.py`) generates per-label, per-graph privilege maps showing which adapters, verbs, and privilege tiers a workflow uses. This supports pre-deployment review and audit without modifying the workflow itself.

See `docs/operations/SANDBOX_EXECUTION_PROFILE.md`, `docs/operations/RUNTIME_CONTAINER_GUIDE.md`, `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`, and `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`.

### 15.5 Capability Grant Model

Each execution surface (runner service, MCP server) applies a **capability grant** — a restrictive-only envelope that constrains which adapters, privilege tiers, and resource limits are permitted for a given run.

The grant is loaded at startup from a named security profile via an environment variable (`AINL_SECURITY_PROFILE` for the runner, `AINL_MCP_PROFILE` for the MCP server). When a caller submits a request, the caller's restrictions are merged with the server grant using restrictive-only rules:

- **Allowlists**: intersection (narrows the permitted adapter set)
- **Forbidden sets**: union (widens the blocklist)
- **Limits**: per-key minimum (more restrictive wins)

This ensures callers can add restrictions but never widen beyond the server baseline. The effective grant is then decomposed into policy rules (for IR validation), an adapter allowlist (for runtime registration), and resource limits (for the execution engine).

The grant model operates entirely at the **program-level boundary** — it constrains what a run is allowed to do, not what individual nodes inside the graph can do. This avoids per-node capability complexity while giving operators a machine-enforceable restriction surface.

See `docs/operations/CAPABILITY_GRANT_MODEL.md` and `tooling/capability_grant.py`.

### 15.6 Mandatory Default Limits

The runner service and MCP server enforce conservative resource ceilings by default: `max_steps`, `max_depth`, `max_adapter_calls`, `max_time_ms`, `max_frame_bytes`, and `max_loop_iters`. Callers can tighten these per-request but cannot exceed the server defaults. This prevents runaway execution even when callers omit limits entirely.

### 15.7 Structured Audit Logging

The runner service emits structured JSON log events for every execution request and adapter call:

- `run_start` — UTC timestamp, trace ID, effective limits, policy presence
- `adapter_call` — per-call timestamp, adapter, verb, status, duration, SHA-256 result hash
- `run_complete` / `run_failed` — final outcome with trace correlation
- `policy_rejected` — pre-execution policy violations with replay artifact ID

No raw results or secrets are logged. Arguments are redacted (authorization, password, and similar tokens are replaced). Error messages are truncated. This supports compliance and debugging while maintaining operational safety.

See `docs/operations/AUDIT_LOGGING.md`.

### 15.8 Stronger Adapter Metadata

Each adapter in `tooling/adapter_manifest.json` now carries additional classification fields beyond the privilege tier:

| Field | Type | Purpose |
|-------|------|---------|
| `destructive` | bool | Adapter can modify or delete external state |
| `network_facing` | bool | Adapter communicates over the network |
| `sandbox_safe` | bool | Adapter is safe for minimal sandbox profiles |

These fields are exposed via `/capabilities` and the MCP adapter-manifest resource. The policy validator supports `forbidden_destructive: true` to reject all destructive adapters in a single rule. Orchestrators use these fields for automated capability analysis and profile construction.

### 15.9 Security Architecture Layering

AINL's security model is organized into three layers with explicit responsibility boundaries:

| Layer | Provides |
|-------|----------|
| **AINL (workflow)** | Deterministic graph execution, adapter capability gating, policy validation hooks, structured audit events, privilege-tier metadata |
| **Runtime/host** (runner, MCP server) | Server-level capability grants, named security profiles, adapter registration, secret management, profile selection |
| **OS/container** (orchestrator) | Process isolation, filesystem mounts, network policy, CPU/memory limits, authentication, multi-tenant boundaries |

AINL stops at the program-level boundary: it constrains what a workflow run is allowed to do, but does not provide container isolation, network policy enforcement, authentication, encryption, or multi-tenant separation. These remain the explicit responsibility of the hosting environment.

### 15.10 MCP Server and MCP-Compatible Hosts

AINL now includes a thin, stdio-only MCP (Model Context Protocol) server that
exposes workflow-level tools and resources to MCP-compatible agent hosts such
as Gemini CLI, Claude Code, Codex-style agent SDKs, and generic MCP servers.
The MCP server:

- is implemented in `scripts/ainl_mcp_server.py` (CLI entrypoint `ainl-mcp`)
- reuses the existing compiler, policy validator, security-report tooling, and
  runtime engine rather than introducing new semantics
- exposes tools: `ainl_validate`, `ainl_compile`, `ainl_capabilities`,
  `ainl_security_report`, `ainl_run`
- exposes resources: `ainl://adapter-manifest`, `ainl://security-profiles`
- supports startup-configurable **MCP exposure profiles** and env-var-based
  tool/resource scoping so operators can present a narrow toolbox (for example
  `validate_only` or `inspect_only`) behind a gateway or MCP manager
- runs with safe-default restrictions:
  - core-only adapter allowlist
  - conservative runtime limits
  - `local_minimal`-style policy (forbidden `local_state`, `network`,
    `operator_sensitive` privilege tiers), with caller policies only allowed
    to add further restrictions

This MCP surface is **workflow-level and vendor-neutral**. It does not turn
AINL into an agent host, orchestration platform, sandbox, or MCP gateway; it
is an integration boundary that allows existing MCP-compatible tools and
gateways to call into AINL’s structured workflow layer. In Claude Code,
Claude Cowork / Dispatch, or Dispatch-style environments, operators should
typically start with `validate_only` or `inspect_only` MCP exposure profiles
and only enable `safe_workflow` after reviewing security profiles, capability
grants, policies, limits, and adapter exposure.

### 15.11 External executor bridge (HTTP) — AINL → workers

For **OpenClaw / NemoClaw** and other MCP-first stacks, the primary integration
path for driving AINL from a host remains **`ainl-mcp`** (§15.10).

When workflows must call **generic HTTP-backed executors** — webhooks, internal
microservices, CI callbacks, or a **single gateway that fans out to N plugin
backends** — operators can use the stable **`http`** adapter (`R http.Post …`)
with a small **JSON request/response contract**, or enable the optional
**`bridge`** adapter so programs use `R bridge.Post <executor_key> …` while
URLs stay in host configuration (CLI `--bridge-endpoint` or runner
`adapters.bridge.endpoints`). Both paths are **off unless explicitly granted**;
default surfaces remain **core-only** where applicable.

Full contract, security notes, multi-backend routing guidance, capacity
considerations, and phased rollout (examples, tests, optional `bridge` adapter)
are documented in **`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md`**.

---

## 16. Limitations

AINL is strong, but not magical.

### 16.1 Learning Curve

AINL introduces a new syntax and mental model.

### 16.2 Static Graph Bias

AINL's strengths come from explicit structure. Dynamic self-rewriting graph behavior is not the primary current model.

### 16.3 Benchmark Interpretation Must Stay Careful

Lexical compactness is useful, but it is not a universal proxy for economic value or runtime quality.

### 16.4 Some Integrations Are Environment-Specific

OpenClaw-specific adapters reflect a real deployment context and may require reimplementation elsewhere.

---

## 17. Future Directions

### 17.1 Recently Shipped

The following capabilities were listed as future work in earlier drafts and have since been implemented:

- **Policy tooling** — declarative policy validation at the runner boundary (`/run` with optional `policy` parameter, HTTP 403 on violation), including `forbidden_privilege_tiers` for privilege-class enforcement
- **Runtime observability** — structured JSON logging, label-level tracing, adapter call recording and replay
- **Capability discovery** — `GET /capabilities` endpoint for external orchestrators, now including adapter privilege tiers
- **Tiered state discipline** — four-tier state model with documentation and sandbox profile mapping
- **Exponential backoff** — optional `backoff_strategy` on the `Retry` operation with configurable cap
- **Sandbox/operator deployment** — prescriptive profiles, container guide, external orchestration guide
- **Adapter privilege-tier metadata** — each adapter in `tooling/adapter_manifest.json` carries a `privilege_tier` (`pure`, `local_state`, `network`, `operator_sensitive`)
- **Named security profiles** — `tooling/security_profiles.json` packages adapter allowlists, privilege-tier restrictions, and runtime limits for four deployment scenarios
- **Security/privilege introspection** — `tooling/security_report.py` generates per-label, per-graph privilege maps for pre-deployment review, including `destructive`/`network_facing`/`sandbox_safe` metadata
- **Capability grant model** — restrictive-only host handshake (`tooling/capability_grant.py`); execution surfaces load server grants from named security profiles and merge caller restrictions so callers can tighten but never widen
- **Mandatory default limits** — runner and MCP surfaces enforce conservative resource ceilings by default; callers can only tighten
- **Structured audit logging** — runner emits JSON events (`run_start`, `adapter_call`, `run_complete`, `run_failed`, `policy_rejected`) with UTC timestamps, trace IDs, and SHA-256 result hashes; no raw payloads or secrets logged
- **Stronger adapter metadata** — `tooling/adapter_manifest.json` schema 1.1 adds `destructive`, `network_facing`, `sandbox_safe` boolean fields; policy validator supports `forbidden_destructive`
- **MCP integration surface (v1)** — a thin, stdio-only MCP server (`ainl-mcp`)
  that exposes workflow-level tools and resources (validation, compilation,
  capabilities, security reports, safe-default `ainl_run`) to MCP-compatible
  hosts. It is workflow-focused, safe-default restricted, and reuses existing
  compiler/runtime semantics rather than widening the language.
- **Conformance matrix runner** — `make conformance` executes the full parallelized snapshot suite (tokenizer round-trip, IR canonicalization, strict validation, runtime parity, emitter stability) with CI execution on push/PR and generated status artifacts (`summary.md`, SVG badge).
- **Visualizer image export** — `ainl visualize` supports direct PNG/SVG rendering for shareable architecture snapshots (`--png`, `--svg`, width/height controls, and extension auto-detect from `-o`).
- **Starter include demo artifact** — `examples/timeout_demo.ainl` provides a strict-safe timeout include example for docs and social/demo usage.
- **Memory v1.1 deterministic contract upgrade** — extension-level memory now supports additive deterministic metadata (`source`, `confidence`, `tags`, `valid_at`), bounded list filters (`tags_any`/`tags_all`, created/updated windows, `limit`/`offset`), namespace TTL/prune policy hooks, response operational counters, and capability-advertised memory profile metadata (`memory_profile`) without introducing semantic retrieval or policy cognition into core runtime semantics.
- **External executor bridge (HTTP)** — documented contract in `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` for calling non-MCP workers via `http.Post` (and optional host-mapped **`bridge`** adapter for executor keys → URLs). **MCP (`ainl-mcp`) remains primary** for OpenClaw/NemoClaw; the HTTP bridge is the secondary pattern for generic gateways and plugins.
- **Reproducible benchmark suite** — `tiktoken` **cl100k_base** default sizing with **`BENCHMARK.md`** transparency (viable subset, legacy-inclusive tables, **minimal_emit fallback stub**, Mar 2026 **prisma/react_ts** compaction notes), **Compile ms (mean×3)** in size tables, runtime benchmark (latency/RSS, optional reliability and scalability probe), shared **economics** helpers (`tooling/bench_metrics.py`), handwritten **baseline** comparison, **CI regression** gating (`scripts/compare_benchmark_json.py`, `make benchmark` / `make benchmark-ci`, workflow `benchmark-regression`), hub **`docs/benchmarks.md`**, and **`ainl-ollama-benchmark --cloud-model`** for an optional **Anthropic Claude** baseline (`temperature=0`, graceful skip without key/SDK).

### 17.2 Remaining Future Work

Promising future work includes:

- Interactive graph UX beyond static Mermaid/DOT exports (graph diffing, live drill-down, and runtime-overlay views)
- Stronger patch / semantic diff tooling
- Broader emitter maturity across additional target platforms
- Deeper benchmark normalization (e.g. cross-hardware runtime baselines, richer adapter-reported token usage to tighten economics)
- Circuit breaker patterns and retryable vs non-retryable error classification
- Deeper MCP and A2A protocol bridges (beyond the current thin workflow-level
  MCP server) as standards and host ecosystems stabilize
- Continued small-model alignment and constrained decoding work
- Deeper AI-agent onboarding and continuity tooling

---

## 18. Competitive Landscape

AINL sits at the intersection of several emerging directions in AI systems:

- graph-based agent orchestration
- deterministic workflow execution
- AI-oriented programming languages
- multi-target code generation

No single existing system fully combines these concerns. Instead, the current ecosystem is fragmented across multiple layers.

### 18.1 Agent Orchestration Frameworks

Frameworks such as LangChain, LangGraph, and CrewAI introduce various models for AI agent orchestration.

**LangChain / LangGraph** validate the importance of explicit workflow structure and stateful execution. LangGraph adds graph-based execution on top of LangChain's chain abstraction.

However, they typically:
- operate as runtime frameworks rather than compiled languages
- lack a canonical intermediate representation
- do not support compile-once / run-many execution
- remain partially prompt-driven for orchestration decisions

**CrewAI** focuses on multi-agent role-based coordination, enabling flexible agent collaboration through role definitions and task delegation.

However, it:
- relies on prompt-driven orchestration and role assignment
- does not provide deterministic graph execution
- lacks adapter-level effect control and policy validation
- does not separate compile-time from runtime concerns

AINL differs by compiling workflows into a **canonical graph IR with strict validation guarantees**, rather than treating graphs as an execution convenience or relying on prompt-driven role assignment.

---

### 18.2 Durable Workflow Systems

Systems such as Temporal and Restate focus on **deterministic, durable execution** of workflows.

These platforms provide:
- replayable execution
- fault tolerance
- state persistence
- strong operational guarantees

They are conceptually close to AINL’s runtime philosophy.

However, they:
- are not AI-native languages
- do not provide compact DSLs optimized for model generation
- do not integrate multi-target emission
- do not treat workflows as AI-generated artifacts

AINL extends this space by introducing a **language + compiler layer** designed specifically for AI-authored workflows.

---

### 18.3 Multi-Agent and Prompt-Oriented Systems

Frameworks such as AutoGen emphasize multi-agent interaction and coordination.

These systems:
- enable flexible agent collaboration
- support conversational tool usage
- are effective for exploratory workflows

However, they:
- rely heavily on prompt-mediated orchestration
- lack deterministic execution guarantees
- embed state implicitly in conversation history

AINL replaces prompt loops with **explicit graph structure**, making execution predictable and auditable.

---

### 18.4 Emerging Graph-Based Agent Platforms

Recent systems, including typed agent workflow frameworks, are beginning to incorporate:

- graph-based execution
- type-aware routing
- checkpointing and recovery

This represents a broader industry shift toward structured orchestration.

AINL aligns with this direction but differs in one key respect:

> It defines a **standalone programming system**, not just a framework abstraction.

---

### 18.5 AINL’s Position

AINL unifies multiple layers that are typically separate:

1. Language (compact AI-native DSL)
2. Compiler (canonical graph IR)
3. Runtime (deterministic execution engine)
4. Adapters (effect system with tiered state discipline)
5. Emitters (multi-target outputs)
6. Operator boundary (runner service with policy validation and capability discovery)

This collapses:

- orchestration
- execution
- generation
- operator governance

into a single coherent system.

---

### 18.6 Key Insight

Most existing systems split responsibilities:

| Concern | Typical System |
|--------|---------------|
| Orchestration | LangChain / LangGraph / CrewAI |
| Execution | Temporal / Restate |
| Generation | LLM-based code tools |
| Operator governance | Platform-specific, ad hoc |

AINL combines all four into a **graph-native programming model**.

---

### 18.7 Positioning Summary

AINL should not be viewed as:

- only an agent framework
- only a workflow engine
- only a code generator

It is best understood as:

> **An AI-native programming system for deterministic, graph-based workflows with multi-target execution and generation capabilities.**

---

## 19. Conclusion

AINL represents a distinct position in AI systems design.

It is not just a DSL, and not just a code emitter. It is a **graph-canonical programming system** designed around a practical thesis:

> AI systems become more reliable when reasoning, orchestration, state, and execution are separated cleanly.

AINL gives AI agents a compact way to describe workflows, a deterministic way to execute them, and a reusable canonical representation that can drive runtime behavior and downstream artifacts alike.

Its value is especially clear in recurring, stateful, branching, and operational workflows, where prompt-loop orchestration becomes expensive and fragile. Through strict validation, adapters, graph introspection, tiered state discipline, policy-gated execution, capability discovery, and real OpenClaw-based operational deployments, AINL demonstrates that the next layer of AI-native engineering is not just bigger models — it is **better execution substrates**.

AINL is designed to fit inside agent platforms and orchestrators — OpenClaw, NemoClaw, custom hosts — as the structured workflow execution layer. It does not replace these platforms; it sits inside them and makes agent workflows reproducible, inspectable, and controllable.

---

## Appendix A: Representative File Map

Paths are relative to the repository root.

### Core system
- `compiler_v2.py` — main compiler
- `runtime/engine.py` — graph-first runtime engine
- `runtime/adapters/` — adapter implementations (memory, SQLite, filesystem, cache, HTTP, optional executor `bridge`, agent, etc.)
- `scripts/runtime_runner_service.py` — FastAPI runner service (`/run`, `/capabilities`, `/health`, etc.)
- `SEMANTICS.md` — runtime semantics
- `docs/AINL_SPEC.md` — language specification

### State and governance
- `docs/architecture/STATE_DISCIPLINE.md` — four-tier state model
- `docs/adapters/MEMORY_CONTRACT.md` — memory adapter contract
- `tooling/policy_validator.py` — pre-execution policy validation (supports `forbidden_privilege_tiers`, `forbidden_destructive`)
- `tooling/capability_grant.py` — capability grant model (restrictive-only merge, profile loading)
- `tooling/adapter_manifest.json` — adapter metadata, capabilities, privilege tiers, and `destructive`/`network_facing`/`sandbox_safe` classification
- `tooling/capabilities.json` — capability definitions
- `tooling/security_profiles.json` — named security profiles for deployment scenarios
- `tooling/security_report.py` — per-workflow privilege/security map generator

### Deployment and operations
- `docs/operations/SANDBOX_EXECUTION_PROFILE.md` — sandbox adapter profiles
- `docs/operations/CAPABILITY_GRANT_MODEL.md` — capability grant model and operator walkthrough
- `docs/operations/AUDIT_LOGGING.md` — structured audit logging event schema
- `docs/operations/RUNTIME_CONTAINER_GUIDE.md` — containerized deployment
- `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md` — external orchestrator integration
- `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` — AINL → external workers over HTTP (`http.Post` contract; optional `bridge` adapter); MCP-first for OpenClaw/NemoClaw
- `docs/INTEGRATION_STORY.md` — integration positioning and pain-to-solution map
- `services/runtime_runner/Dockerfile` — runner service container
- `tests/emits/server/Dockerfile` — emitted server container

### Examples and validation
- `examples/` — canonical `.ainl` examples (hello, CRUD, RAG, retry, webhook, monitors, golden series)
- `examples/openclaw/` — OpenClaw example programs
- `examples/autonomous_ops/` — autonomous ops examples
- `demo/monitor_system.lang` — monitor system demo
- `docs/case_studies/` — graph-native vs prompt-loop, cost analysis, long-context memory
- `docs/PATTERNS.md` — workflow patterns (RetryWithBackoff, RateLimit, BatchProcess, CacheWarm)

### Benchmarks and tooling
- `docs/benchmarks.md` — hub: metrics, Mar 2026 highlights, `make benchmark` / `make benchmark-ci`, CI gate, LLM bench links
- `BENCHMARK.md` — human-readable **size** benchmark (generated; **tiktoken cl100k_base** tables, transparency notes, **Compile ms (mean×3)**)
- `scripts/benchmark_size.py`, `scripts/benchmark_runtime.py` — size and runtime generators
- `tooling/benchmark_size.json` — machine-readable size report (schema `3.5+`; viable subset + parallel fields as documented)
- `tooling/benchmark_runtime_results.json` — machine-readable runtime report (CI baseline when committed)
- `tooling/bench_metrics.py` — shared `tiktoken` counting and pricing helpers
- `scripts/compare_benchmark_json.py` — regression checker for CI
- `scripts/benchmark_ollama.py` / `ainl-ollama-benchmark` — multi-model LLM bench; optional **`--cloud-model`** (Anthropic)
- `tooling/artifact_profiles.json` — artifact/strict profiles
- `tooling/benchmark_manifest.json` — benchmark manifest
- `tooling/support_matrix.json` — support levels

---

## Appendix B: Suggested Short Positioning Statement

> AINL is a graph-canonical, AI-native programming system for deterministic workflows, multi-target generation, and operational agents — designed to reduce orchestration complexity without depending on ever-growing prompt loops.

# KEYWORDS
- canonical graph IR
- graph-canonical programming system
- strict-mode validation for AI-generated code
- multi-target code generation for AI workflows
- effect-typed workflow language
- adapter-based AI orchestration
- LangChain alternative
- LangGraph alternative
- CrewAI alternative
- Temporal for AI agents
- deterministic alternative to prompt loops
- sandboxed agent deployment
- policy-gated workflow execution
- tiered state management for AI agents
- capability grant model for agent workflows
- structured audit logging for AI agents
- adapter privilege tier metadata
- restrictive-only security model
