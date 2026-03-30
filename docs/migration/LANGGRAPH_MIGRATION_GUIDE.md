# Migrating from LangGraph to AINL

This guide is for teams comparing **LangGraph** (or similar prompt-centric Python graphs) to **AINL**: a compiled workflow language with **strict validation**, **deterministic runtime** options, and **emit** to LangGraph, Temporal, FastAPI, Kubernetes, or the native runtime from a **single source**.

## Why move from LangGraph to AINL

| Concern | LangGraph-style (typical) | AINL |
|--------|---------------------------|------|
| **Token cost** | Orchestration often re-invokes the model per step or per run | **Compile once, run many** — no recurring orchestration LLM tokens on deterministic paths |
| **Determinism** | Control flow can be model-dependent | **Compiled graph IR** — same inputs and adapter results → same control flow |
| **Single source of truth** | Target-specific rewrites for Temporal, K8s, etc. | **Author in `.ainl`** → emit multiple targets; benchmarks in-repo |
| **Audit** | Hard to reconstruct “why” from chat or ad hoc code paths | **JSONL execution tape**, policy gates, strict diagnostics |

AINL does not remove your LLM from the system where you still want reasoning — it **removes the LLM from the orchestration plane** for workflows you compile and validate.

## Side-by-side: prompt-style vs AINL graph

| Aspect | Prompt / LangGraph agent loop | AINL graph |
|--------|------------------------------|------------|
| Control flow | Implicit in model + Python | Explicit labels, `J`, `If`, `Call` |
| Validation | Mostly runtime | **`ainl check --strict`** before deploy |
| Side effects | Scattered in tools | Declared **adapter** operations with capability boundaries |
| Cost model | Tokens every orchestration turn | **~0** orchestration tokens after compile on pure deterministic runs |

## Step-by-step: simple LangGraph agent → AINL

**1. Identify the skeleton**  
List states/nodes and edges: “read inbox → evaluate threshold → escalate or noop.”

**2. Scaffold**  
```bash
pip install ainativelang
ainl init my-worker
```

**3. Write the core in `.ainl`**  
Express branches with `If` and fixed labels; call adapters with `R adapter.OP … ->var`. See [`examples/hello.ainl`](../../examples/hello.ainl) and [`examples/monitor_escalation.ainl`](../../examples/monitor_escalation.ainl).

**4. Hybrid emit (optional)**  
Keep an outer LangGraph or host process while the **core** is AINL-compiled — see hybrid examples under `examples/hybrid/` and the [comparison tables](https://ainativelang.com/docs/competitive/COMPARISON_TABLE).

**5. Validate and ship**  
```bash
ainl check workflow.ainl --strict
ainl run workflow.ainl --trace-jsonl run.jsonl
```

**6. Benchmark honestly**  
Use committed CI artifacts in **`BENCHMARK.md`** and [`docs/competitive/`](../competitive/) on the site — no hand-waved competitor numbers.

## Related reading

- [Comparison tables (committed data only)](https://ainativelang.com/docs/competitive/COMPARISON_TABLE)
- [Validation deep dive](../validation-deep-dive.md)
- [OpenClaw / MCP integrations](../getting_started/HOST_MCP_INTEGRATIONS.md)
