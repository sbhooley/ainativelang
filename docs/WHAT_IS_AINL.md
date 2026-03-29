# What is AINL?

**Canonical primer — maintain this file.** When you update the product story or capability list, edit **this** document. **[`WHAT_IS_AINL.md`](../WHAT_IS_AINL.md)** at the repository root is a **short stub** that points here (GitHub and some agents open the repo root first).

> **AINL — Turn AI from a smart chat into a structured worker.**

Below: a **stakeholder narrative** (what it is, problem, fit, boundaries), then **compile-time includes**, a **v1.2+ capability snapshot** (trajectory, Hyperspace, adapters), and links. Packaging versions: `docs/RELEASE_NOTES.md`.

---

## What AINL is

AI Native Lang (AINL) is a **graph-canonical programming system** for building structured AI workflows, operational agents, and multi-step automation.

Instead of forcing an LLM to manage entire workflows through long prompt loops, AINL lets builders express those workflows as compact programs that compile into canonical graph IR and execute through a controlled runtime.

In plain English:

> **AINL helps turn AI from “a smart conversation” into “a structured process.”**

## The problem AINL solves

Most AI systems work well for one-off tasks, demos, or short interactions.

They become much harder to trust when they must:

- remember state across time
- use tools repeatedly
- make decisions across multiple steps
- run on schedules
- handle branching logic
- operate with human oversight
- stay understandable and reproducible

At that point, prompt loops start to break down. You get:

- prompt bloat
- rising token costs
- hidden state
- brittle orchestration
- hard-to-debug tool behavior
- weak auditability

AINL addresses this by moving workflow structure out of the prompt and into a deterministic execution system.

## What makes AINL different

1. **Graph-first, not prompt-first**  
   AINL compiles workflows into canonical graph IR. Execution follows explicit graph semantics instead of ad hoc conversational state.

2. **Built for AI-oriented execution**  
   AINL is designed for agent-oriented workflows where models, tools, state, memory, and validation must work together in a controlled way.

3. **Compile once, run many**  
   AINL programs can be compiled once and reused repeatedly, reducing repeated generation cost and avoiding prompt-based orchestration on every run.

4. **Explicit memory and state**  
   AINL externalizes memory and state into variables, adapters, databases, cache, and memory contracts rather than hiding them inside prompt history.

5. **Deterministic workflow control**  
   The compiler and runtime provide a stronger execution structure than “let the model figure it out live.”

6. **Validation and governance**  
   AINL includes strict validation, support-level contracts, profile-aware examples, and governance-oriented tooling for advanced workflows.

7. **Author once, validate, deploy to multiple runtimes (v1.2.5+)**  
   The same strict-valid **AINL** program can emit **LangGraph** (`--emit langgraph`), **Temporal** (`--emit temporal`), **Hyperspace**, **FastAPI**, **React**, and other targets — without treating any one vendor runtime as the permanent source of truth. See **[`HYBRID_GUIDE.md`](HYBRID_GUIDE.md)** and **[`competitive/README.md`](competitive/README.md)**.

## Positioning snapshot (operational agents, 2026)

For teams that want **LLMs to author the workflow** (not only call tools inside someone else’s loop) and need **deterministic, auditable, repeatable** execution, AINL combines:

- a **compact AI-native DSL** + **strict canonical IR** (compile guarantees LangGraph/CrewAI-style prompt loops do not provide),
- **compile-once / run-many** execution (recurring runs avoid re-spending orchestration tokens),
- **multi-target emission** including **to** ecosystems you already use (LangGraph, Temporal, etc.),
- **MCP-native** integration paths for **OpenClaw / ZeroClaw / NemoClaw** hosts.

Narrative guides (grounded in shipped emitters): **[`competitive/FROM_LANGGRAPH_TO_AINL.md`](competitive/FROM_LANGGRAPH_TO_AINL.md)**, **[`competitive/AINL_AND_TEMPORAL.md`](competitive/AINL_AND_TEMPORAL.md)**. Reproducible comparison methodology: **[`competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md`](competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md)**.

## Who AINL is for

AINL is best for people building serious AI workflows, not just casual prompt experiments.

### Best-fit users

- AI engineers
- agent builders
- platform engineers
- technical founders
- operator-minded automation teams
- enterprises needing structured AI workflows

### Best-fit use cases

- internal AI workers
- stateful automation
- recurring monitors
- multi-step research workflows
- long-running agent systems
- tool-using operational agents
- workflows that need validation, memory, and oversight

### Less ideal for

- casual chatbot builders
- one-off prompt scripting
- purely no-code users
- people who only need simple model calls

## Why businesses care

AINL helps organizations move from:

> “We have a clever AI demo.”

to:

> “We have an AI workflow we can actually run, inspect, and maintain.”

That matters when AI starts touching real operations.

AINL is especially valuable when teams need:

- repeatability
- control
- lower orchestration cost
- better long-session behavior
- memory and state discipline
- clearer separation between reasoning and execution
- a path from prototype to structured system

## Open core, with advanced operator surfaces

AINL’s public core is centered on:

- the canonical compiler/runtime
- graph IR
- strict validation
- core tooling
- canonical examples
- multi-target workflow leverage

The repository also includes advanced, noncanonical extension surfaces for operator-oriented workflows, including memory, coordination, and OpenClaw-oriented tooling.

These advanced surfaces are:

- powerful
- useful
- intentionally explicit
- not the default entry point
- not a built-in secure autonomous agent fabric

## The simplest way to explain AINL

Most AI tools are like talking to a smart assistant.  
AINL is for building the process, memory, structure, and execution layer that lets that assistant do real work reliably.

Or even shorter:

> **AINL helps make AI workflows more structured, repeatable, and controllable.**

## What AINL is not

AINL is not:

- just a prompt format
- just a chatbot framework
- just another Python wrapper around tools
- a magic autonomous agent layer
- a turnkey secure enterprise control plane
- a replacement for every note system, vector store, or app framework

AINL is a programming and execution system for structured AI workflows.

---

## Composable workflows with includes

AINL supports **compile-time composition** via top-level **`include`**:

```ainl
include "modules/common/retry.ainl" as retry

L1: Call retry/ENTRY ->out J out
```

- The compiler **merges** the included file into the parent IR. Every label from the module is prefixed as **`alias/LABEL`** (e.g. `retry/ENTRY`, `retry/EXIT_OK`). The default alias is the included file’s stem if you omit **`as`**.
- Shared modules typically define **`LENTRY:`** (surfaced as **`alias/ENTRY`**) and one or more **`LEXIT_*:`** exits. In **strict** mode this contract is enforced so callers and agents can rely on a stable entry/exit surface.
- **Benefits for agents:** reuse **verified** subgraphs instead of regenerating long control-flow; **qualified names** in IR match the mental model (`timeout/n1`, …); fewer merge conflicts when multiple agents edit different modules.

Starter modules in-repo include `modules/common/retry.ainl`, `modules/common/timeout.ainl`, `modules/common/access_aware_memory.ainl`, `modules/common/guard.ainl`, `modules/common/session_budget.ainl`, `modules/common/reflect.ainl`, and `modules/common/executor_bridge_request.ainl` (HTTP bridge JSON in the frame — pair with `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` §3 and `schemas/executor_bridge_request.schema.json`). Path resolution, cycles, and tests: `tests/test_includes.py`. Graph inspection: `docs/architecture/GRAPH_INTROSPECTION.md`.

---

## Current capabilities (v1.2 snapshot)

- **Compiler / IR:** `compiler_v2.py` → canonical **`labels`** graph (`nodes`, `edges`, `entry`, `exits`), strict-mode validation, include merge.
- **Structured diagnostics:** native **`Diagnostic`** records (lineno, spans, kinds, suggested fixes) via **`CompilerContext`**; **`ainl-validate`** and **`ainl visualize`** support **`--diagnostics-format`** (`auto` / `plain` / `rich` / `json`) and optional **rich** UI with **`pip install -e ".[dev]"`**. See `docs/INSTALL.md`, `compiler_diagnostics.py`.
- **Graph visualizer CLI:** **`ainl visualize`** / **`ainl-visualize`** / `scripts/visualize_ainl.py` emit **Mermaid** (`graph TD`, subgraph **clusters** per include alias, synthetic **`Call →` entry** edges with a `%%` comment). Paste into [mermaid.live](https://mermaid.live). Flags: `--no-clusters`, `--labels-only`, `-o -`. Details: root **`README.md`** (*Visualize your workflow*), `docs/architecture/GRAPH_INTROSPECTION.md` §7.
- **Runtime:** `ainl run`, runner service, MCP server, record/replay adapters — see `docs/getting_started/README.md`. **Graph + includes:** bare child label targets in merged IR are qualified with the current **`alias/`** stack frame when needed (`runtime/engine.py`). See `docs/RUNTIME_COMPILER_CONTRACT.md`, **`docs/RELEASE_NOTES.md`** (**current: v1.3.3**; access-aware memory module notes under **v1.2.4** in that file).
- **Memory helpers (opt-in):** `modules/common/access_aware_memory.ainl` — **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, **`LACCESS_LIST_SAFE`** for optional **`last_accessed` / `access_count`** metadata on **`memory`**; use **`LACCESS_LIST_SAFE`** for graph-reliable list touches. Index: `modules/common/README.md`.
- **Guard / budget / reflect includes:** `modules/common/guard.ainl`, `session_budget.ainl`, `reflect.ainl` — strict-safe ceilings, spend accounting, and reflect gates (`modules/common/README.md`).
- **Trajectory logging (CLI):** optional **`<stem>.trajectory.jsonl`** next to the `.ainl` source (`ainl run --log-trajectory` or **`AINL_LOG_TRAJECTORY`**). Doc: `docs/trajectory.md`.
- **Local adapters for Hyperspace-style graphs:** **`vector_memory`** (keyword-scored JSON store) and **`tool_registry`** (JSON tool catalog) in `adapters/`; enable with **`--enable-adapter`**. Catalog: `docs/reference/ADAPTER_REGISTRY.md` §9.
- **Optional tiered code context:** **`code_context`** indexes a repo to JSON and serves ctxzip-style tiers (TF–IDF summaries by default), plus **import-graph dependencies**, **reverse impact** (transitive importers + PageRank), and **`COMPRESS_CONTEXT`** (greedy token-budget packing of ranked chunks); enable with **`--enable-adapter code_context`** on **`ainl run`**. Guide: **`docs/adapters/CODE_CONTEXT.md`**.
- **Hyperspace emitter:** **`--emit hyperspace`** on validate emits a standalone Python agent with embedded IR — `docs/emitters/README.md`, `examples/hyperspace_demo.ainl`, root `README.md`.
- **HTTP executor bridge (AINL → external workers):** small JSON **request envelope** for `http.Post` / optional `bridge.Post` (`docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` §3); machine-readable **`schemas/executor_bridge_request.schema.json`**; Python **`schemas/executor_bridge_validate.py`**; reusable include **`modules/common/executor_bridge_request.ainl`**. **MCP (`ainl-mcp`) first** for OpenClaw / NemoClaw / ZeroClaw; HTTP bridge is secondary.
- **OpenClaw operations (current v1.3.2):** **`scripts/run_intelligence.py`** (startup context, summarizer, consolidation, optional **`auto_tune_ainl_caps`**) with rolling **budget hydrate**; pinned env **`tooling/openclaw_workspace_env.example.sh`**, profiles **`tooling/ainl_profiles.json`**; operator playbooks **`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`**, **`docs/operations/OPENCLAW_HOST_AINL_1_2_8.md`**; optional **embedding-backed** startup context and caps (**`docs/operations/EMBEDDING_RETRIEVAL_PILOT.md`**, **`TOKEN_CAPS_STAGING.md`**); weekly cap tuner **`scripts/auto_tune_ainl_caps.py`**. Graph-safe patterns for intelligence: **`docs/RUNTIME_COMPILER_CONTRACT.md`**, **`docs/INTELLIGENCE_PROGRAMS.md`**.

---

## Related links

| Topic | Doc |
|--------|-----|
| Install & CLI flags | `docs/INSTALL.md` |
| Graph / IR introspection | `docs/architecture/GRAPH_INTROSPECTION.md` |
| Strict / conformance | `docs/CONFORMANCE.md` |
| OpenClaw gold standard + host briefing (v1.3.2) | `docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`, `docs/operations/OPENCLAW_HOST_AINL_1_2_8.md` |
| Integration paths | `docs/getting_started/README.md`, `docs/INTEGRATION_STORY.md` |
| HTTP executor bridge (envelope + schema + include) | `docs/integrations/EXTERNAL_EXECUTOR_BRIDGE.md` §3; `schemas/executor_bridge_request.schema.json`; `modules/common/executor_bridge_request.ainl` |
| Trajectory JSONL / Hyperspace emit | `docs/trajectory.md`; `docs/emitters/README.md` |
| Adapter catalog (vector_memory, tool_registry, code_context, memory) | `docs/reference/ADAPTER_REGISTRY.md` |

---

## Evidence and benchmarks

Reproducible **size** tables (**tiktoken cl100k_base**, viable subset vs legacy-inclusive transparency): [`BENCHMARK.md`](../BENCHMARK.md). Hub (commands, CI, runtime + LLM eval pointers): [`docs/benchmarks.md`](benchmarks.md).

Long-form architecture: [`WHITEPAPERDRAFT.md`](../WHITEPAPERDRAFT.md) (repository root) — **v1.3.3** positioning: OpenClaw intelligence, token caps, embedding pilot, graph-runtime pitfalls, weekly cap auto-tuner, and native Solana + prediction-market workflows (**`docs/solana_quickstart.md`**).

## Why now

As AI systems grow more capable, the bottleneck is no longer only model intelligence.

The bottleneck is how workflows are structured, controlled, remembered, validated, and operated.

AINL exists for that layer.

## AINL in agent stacks

AINL is designed to fit inside agent platforms and orchestrators — OpenClaw, NemoClaw, custom hosts — as the structured workflow execution layer. It reduces workflow sprawl, prompt-loop chaos, brittle orchestration, messy state, and poor reproducibility by providing explicit graph execution, tiered state discipline, and operator governance surfaces.

For the full integration story, pain-to-solution map, and architecture diagram, see `docs/INTEGRATION_STORY.md`.

For a detailed comparison of graph-native agents vs prompt-loop agents with production evidence, see `docs/case_studies/graph_agents_vs_prompt_agents.md`.

For explicit "thinking budget" framing (tokens/cost/latency/carbon) and how AINL maps to energy-pattern design, see `docs/case_studies/DESIGNING_ENERGY_CONSUMPTION_PATTERNS.md`.

For an OpenClaw-specific quickstart, see `AI_AGENT_QUICKSTART_OPENCLAW.md`.

## One-sentence positioning

**AINL is a graph-canonical AI workflow programming system for building deterministic, stateful, multi-step agent workflows without relying on ever-growing prompt loops.**
