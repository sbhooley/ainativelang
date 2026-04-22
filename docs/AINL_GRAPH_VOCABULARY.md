# AINL graph vocabulary (three “graphs”)

This repository uses **three distinct graph concepts**. Confusing them causes incorrect mental models for agents and operators.

| Concept | What it is | Primary artifact |
|--------|------------|------------------|
| **Code / repo graph** | Static analysis of source (symbols, calls, routes, processes). *GitNexus-class MCP tools operate here.* | External indexer / MCP (`query`, `context`, `impact`, …). |
| **AINL execution graph (IR)** | Compiled workflow: nodes, edges, adapter calls. Produced by `ainl compile`. | IR JSON from `compiler_v2` |
| **Agent / memory graph** | Conversation and procedural memory (e.g. SQLite graph memory in ArmaraOS). | Runtime stores — not a full code index |

**Rule of thumb:** *Repo intelligence MCP* answers “where in the codebase?” — AINL answers “what does this workflow *do* when run?”

See also: [`CONTEXT_FRESHNESS.md`](CONTEXT_FRESHNESS.md). ArmaraOS policy boundaries: sibling repo `armaraos/docs/POLICY_BOUNDARIES.md`.
