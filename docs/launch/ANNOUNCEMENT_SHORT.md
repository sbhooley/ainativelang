# AINL v1.1.0 — Short-Form Announcement Drafts

Use these for X/Twitter, LinkedIn, Hacker News, Reddit, or similar.

---

## X / Twitter (short)

AINL v1.1.0 is live — an open language for deterministic AI workflows.

Compile structured workflows to graph IR. Execute through a deterministic runtime. Three integration paths: CLI, HTTP runner, or MCP for AI coding agents.

Python 3.10+. Apache 2.0 core. 403 tests green.

github.com/sbhooley/ainativelang

---

## LinkedIn / longer post

**AINL v1.1.0 — First Public Release**

AINL (AI Native Lang) is an open-core programming system for building deterministic AI workflows. Instead of relying on ever-growing prompt loops, AINL compiles structured workflows to canonical graph IR and executes them through a runtime with adapter-based side effects, policy-gated execution, and multi-target emission.

**What's in this release:**

- Python 3.10+ baseline with CI on 3.10 and 3.11
- MCP v1 server for Gemini CLI, Claude Code, Codex, and other MCP hosts
- HTTP runner service with policy-gated execution and capability discovery
- Security/operator surfaces: privilege tiers, named security profiles, policy validation
- Docs reorganized by user intent with three clear getting-started paths

**Who it's for:**

- AI engineers building multi-step, stateful agent workflows
- Platform/ops teams that need governed, repeatable AI execution
- Anyone integrating AI workflows into sandboxed or operator-controlled environments

**Start here:** Three paths — CLI, HTTP runner, or MCP host. One canonical example works across all three.

Apache 2.0 core. Contributions welcome.

github.com/sbhooley/ainativelang

---

## Hacker News / Reddit title + body

**Title:** AINL v1.1.0 – Open language for deterministic AI workflows (graph IR, MCP, policy-gated execution)

**Body:**

AINL compiles structured AI workflows to canonical graph IR and runs them deterministically. The idea: move orchestration out of prompt loops and into a compiled, validated, repeatable execution layer.

v1.1.0 ships with:
- A compiler + runtime that produces canonical graph IR from a compact DSL
- An MCP v1 server (stdio) so AI coding agents (Gemini CLI, Claude Code, Codex) can validate/compile/run workflows natively
- An HTTP runner service with policy-gated execution and capability discovery
- Security surfaces: privilege tiers per adapter, named security profiles, pre-execution policy validation
- 403 core tests green on Python 3.10+

Three ways to try it: CLI (`ainl-validate`), HTTP runner (`/run`), or MCP (`ainl-mcp`). Same example works across all three.

Apache 2.0 core. Open to contributions and feedback.

https://github.com/sbhooley/ainativelang
