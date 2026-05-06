# ToolRegistry + ToolPatch — platform plan (AINL-wide vocabulary)

**Status:** Canonical vocabulary + phased adoption plan (implementations live outside this repo).  
**Audience:** Language authors, compiler/runtime maintainers, ArmaraOS / control-plane integrators, MCP hosts.  
**Language binding:** **[`AINL_SPEC.md`](../AINL_SPEC.md) §7** — ToolRegistry / ToolPatch / PatchRegistry in the **same normative document** as GraphPatch (§6): IR hooks, design-preview syntax, compiler/runtime roadmap.  
**Read with:** [`AINL_GRAPH_VOCABULARY.md`](../AINL_GRAPH_VOCABULARY.md) (three graphs), [`operations/CAPABILITY_GRANT_MODEL.md`](../operations/CAPABILITY_GRANT_MODEL.md) (host grants), [`adapters/`](../adapters/README.md) (adapter contracts).

---

## 1. Why this document lives in **AI_Native_Lang**

**ToolRegistry** and **ToolPatch** are **platform concepts**, not a single product detail of one desktop shell. Defining them here first ensures:

- Every host (ArmaraOS, OpenClaw MCP, CI runners, future kernels) can share **names and invariants**.
- Implementations (Rust control plane, Python runtime grants) stay **aligned** without copying prose from issue threads.

This repo owns **vocabulary and semantics**; reference implementations own **wire formats and HTTP**.

---

## 2. Analogy: GraphPatch + PatchRegistry

Elsewhere in the ecosystem, **bounded graph mutation** uses **patch** language: apply a **minimal delta** on top of a **registry** of allowed structure, validated before execution.

**ToolPatch + ToolRegistry** follow the **same discipline** at the **capability** layer—they are **not** a second implementation of **`memory.patch`** ([`AINL_SPEC.md`](../AINL_SPEC.md) §6). §6 **GraphPatch** installs **new IR labels** from procedural memory; §7 **ToolPatch** narrows **which adapter/tool invocations** are legal on the **existing** execution graph. Same **registry ⊇ patch ⊇ enforcement** pattern; different **patch domain** (structural vs capability). See **[`AINL_SPEC.md`](../AINL_SPEC.md) §7** intro table.

| §6-style (structural) | §7-style (capability) |
|------------------------|-------------------------|
| Registry of allowed structure / patterns | **ToolRegistry** — canonical tool/adapter identities + contracts for a scope |
| Patch promotes or replaces **labels** | **ToolPatch** — **active subset** of allowed **calls** for this phase / turn / mode |
| Host applies & enforces | **PatchRegistry** (host) — refuse execution outside active patch |

Exact GraphPatch planning artifacts may live in product repos; **this file** aligns vocabulary with **[`AINL_SPEC.md`](../AINL_SPEC.md) §6–§7**.

---

## 3. Definitions

### 3.1 ToolRegistry

**ToolRegistry** is the **canonical allowlist** of invocable capabilities for a **scope** (examples: agent session, compiled graph run, org policy bundle), represented as **stable names** and **machine-readable contracts** (e.g. JSON Schema for arguments/results where applicable).

- **Source of truth** is always the **host** (or policy bundle the host loads)—not the LLM and not the control plane alone.
- **Registry membership** can change over time via explicit **patch events** (see §6).

### 3.2 ToolPatch

**ToolPatch** is the **active subset** of **ToolRegistry** that a particular phase should **consider, surface, or validate against**.

- Invariants: **`ToolPatch ⊆ ToolRegistry`** (same scope).
- **Widening** beyond the registry is forbidden; **narrowing** is the normal mode (deterministic / safety / cost reduction).

### 3.3 PatchRegistry (host enforcement)

**PatchRegistry** is the **host mechanism** that ensures **only ToolPatch-allowed** calls execute—even if a model proposes something else. Naming aligns with graph vocabulary; the implementation is host-specific (ArmaraOS tool runner, sandbox policy, etc.).

---

## 4. Two surfaces, one vocabulary

AINL appears in **two** capability contexts; **ToolRegistry / ToolPatch** unify how we talk about both:

| Surface | What is registered | Typical registry source |
|---------|--------------------|-------------------------|
| **Compiled graph (`R adapter.op`)** | **Adapters** referenced in IR + host **grant** policy | `compiler_v2` IR resolution + `AINL_HOST_ADAPTER_*` / security profiles |
| **Agent orchestration (chat / planner / MCP tools)** | **Named tools** (`file_read`, `mcp_ainl_validate`, …) | Agent manifest + MCP servers + dashboard policy |

**Same rules:** registry = what **may** exist; patch = what is **active now**; host = what **actually runs**.

Cross-links: adapter contracts ([`ADAPTER_DEVELOPER_GUIDE.md`](../ADAPTER_DEVELOPER_GUIDE.md)), runtime grants ([`operations/CAPABILITY_GRANT_MODEL.md`](../operations/CAPABILITY_GRANT_MODEL.md)).

---

## 5. Control plane vs host (trust boundary)

- **Control plane** (when present): may **shape prompts**, **validate proposal-shaped outputs**, and **attach contracts** so models see a consistent ToolPatch—see sibling **[`ainl-inference-server` docs](https://github.com/sbhooley/ainl-inference-server)** (`TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md`, `PLANNER_HOST_BOUNDARIES.md`).
- **Host**: **must enforce** ToolPatch at execution; if proposals and registry disagree, **host wins**.

AINL’s Python **`ainl run`** and MCP **`ainl_run`** remain **host-authoritative** for adapter execution; the control plane never replaces that boundary.

---

## 6. Lifecycle (conceptual)

1. **Bootstrap** — Populate **ToolRegistry** for the scope (full contract set allowed by policy).
2. **Narrow** — Select **ToolPatch** for the current **mode** or **turn** (e.g. deterministic AINL work vs general agent work).
3. **Mutate registry** — On manifest/MCP/policy change, apply a **registry patch** (add/remove/revise entries)—not silent expansion without host approval.
4. **Enforce** — On each invocation, **PatchRegistry** checks **name ∈ ToolPatch** (and usual policy).

Session-scoped **bootstrap + delta patches** for HTTP stacks are specified in **[`INFER_SESSION_PROTOCOL_AND_CACHE_PLAN.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/INFER_SESSION_PROTOCOL_AND_CACHE_PLAN.md)** (sibling repo)—same lifecycle pattern at the wire level.

---

## 7. Modes (informal)

Product embeddings may label patches:

| Mode | Typical ToolPatch |
|------|-------------------|
| **Deterministic** | Minimal **floor** (files, shell policy, web as needed, **MCP AINL** cluster, …)—see **[ToolPatch architecture](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md)** §6 |
| **Heuristic** | Dynamic subset ⊆ registry (router / policy hints) |
| **Freestyle** | Largest honest subset ⊆ registry for the agent |

Exact tool ids remain **host-defined strings**—AINL does not mint new ids from prose.

---

## 8. Router tier (optional, implementation-specific)

A **small classifier model** or **structured router** may suggest **which ToolPatch profile** applies; suggestions are **non-authoritative** unless validated and **never** widen past **ToolRegistry**. Default checkpoint and **JSON schema + retry + fallback** semantics are documented in the control-plane repo (**§5** of `TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md`).

---

## 9. Phased adoption

| Phase | In **AI_Native_Lang** (this repo) | Elsewhere |
|-------|-------------------------------------|-----------|
| **P0** | This doc + links from vocabulary / architecture indexes | — |
| **P1** | Cross-links from [`operations/MCP_AINL_WIZARD_AND_CORPUS.md`](../operations/MCP_AINL_WIZARD_AND_CORPUS.md) / grants docs where “allowed tools” is discussed | Implement registry/patch on host + control plane per their plans |
| **P2** | Optional: shared JSON Schema artifacts under `schemas/` **if** multiple repos consume identical shapes | `armara-provider-api` or sibling crates vendored per repo policy |

**Canonicalization (code):** **[`TOOL_SURFACE_CANONICALIZATION_CHECKLIST.md`](TOOL_SURFACE_CANONICALIZATION_CHECKLIST.md)** — schemas, compiler, runtime deny guard, tests.

**Rule:** Vocabulary and **[`AINL_SPEC.md`](../AINL_SPEC.md) §7** land before syntax; **MV slice** = IR `services.tool_surface` + runtime enforcement without new surface syntax.

---

## 10. Related documents

| Document | Role |
|----------|------|
| **[`AINL_GRAPH_VOCABULARY.md`](../AINL_GRAPH_VOCABULARY.md)** | Three-graph discipline; avoid confusing repo vs IR vs memory graphs |
| **[`operations/CAPABILITY_GRANT_MODEL.md`](../operations/CAPABILITY_GRANT_MODEL.md)** | Host grants intersect registry membership |
| **[`ARMARAOS_INTEGRATION.md`](../ARMARAOS_INTEGRATION.md)** | Desktop shell integration hub |
| **Sibling: [`TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md)** | Reference control-plane + router semantics |
| **Sibling: [`INFER_SESSION_PROTOCOL_AND_CACHE_PLAN.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/INFER_SESSION_PROTOCOL_AND_CACHE_PLAN.md)** | Session `StaticBundle` carries registry + patches |

---

## 11. Summary

**ToolRegistry** = canonical allowed capabilities for a scope. **ToolPatch** = active subset for this phase (`⊆` registry). **PatchRegistry** = host enforcement. Define terms here so **AINL**, **hosts**, and **control planes** stay aligned; ship wire formats and enforcement in their respective repos without renaming concepts mid-flight.

**Start here** for vocabulary; **implement** in ArmaraOS + ainl-inference-server per their active checklists.
