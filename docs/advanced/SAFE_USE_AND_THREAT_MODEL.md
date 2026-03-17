## Safe Use and Threat Model (release-facing)

This document explains how to think about AINL and the current
extension/OpenClaw coordination patterns from a **safety and governance**
perspective. It is aimed at non-expert users and authors of
OpenClaw-like agents.

It describes:

- what AINL and the local coordination substrate **assume**,
- what they explicitly **do not** provide today,
- the **threat model and trust assumptions**,
- and which knobs are **enforced** vs **advisory-only**.

This is a **docs-only** description; it does not change compiler/runtime
semantics.

---

## 1. What AINL coordination currently assumes

The current local coordination substrate (the `agent` adapter and associated
examples) makes the following assumptions:

- **Local-first**:
  - Coordination happens via local files under a sandbox root such as
    `AINL_AGENT_ROOT` on the same machine or container.
  - There is no built-in network transport, authentication, or encryption.

- **File-backed**:
  - Tasks are written as JSONL lines (e.g.
    `tasks/openclaw_agent_tasks.jsonl`).
  - Results are single JSON objects (e.g.
    `results/<task_id>.json`).
  - The file layout is a **convention**, not a secure message bus.

- **Sandboxed roots (best-effort)**:
  - Adapters enforce that paths stay under configured roots and reject
    filesystem root as an invalid sandbox.
  - These checks help catch obvious misconfigurations and path traversal, but
    they do not turn the local filesystem into a hardened multi-tenant boundary.

- **External orchestrator for routing and result creation**:
  - AINL/OpenClaw programs:
    - may write `AgentTaskRequest` envelopes using `agent.send_task`,
    - may read `AgentTaskResult` envelopes using `agent.read_result`.
  - An **external orchestrator** (which might be a Cursor-side agent, human
    operator, or other process) is responsible for:
    - consuming task JSONL files,
    - deciding when/how to process tasks,
    - creating and placing result JSON files,
    - enforcing any routing, polling, policy, or approval behavior.

- **Extension/OpenClaw-only and noncanonical for coordination**:
  - The `agent` adapter and the advisory coordination examples
    (`token_cost_advice_*`, `monitor_status_advice_*`) are intentionally
    classified as:
    - `extension_openclaw`,
    - **noncanonical**,
    - **advisory-only**.
  - They are reference patterns for local, file-backed coordination, not
    part of the strict AINL core.

---

## 2. What AINL coordination does *not* currently provide

The current coordination substrate is **not**:

- an authenticated distributed messaging system,
- an encrypted transport layer,
- a multi-tenant isolation boundary,
- a policy or approval enforcement engine,
- a secure remote federation mechanism,
- an autonomous orchestration engine,
- a swarm or recursive multi-agent framework.

In particular:

- Fields such as `approval_required`, `budget_limit`, `policy_context`,
  `trust_domain`, and `allowed_tools` in `AgentTaskRequest` envelopes are:
  - **descriptive/advisory metadata**,
  - only enforced if an external orchestrator chooses to interpret and act
    on them.
- AINL and the `agent` adapter do **not**:
  - authenticate who wrote a task or result file,
  - encrypt those files at rest or in transit,
  - enforce multi-tenant isolation between different agents that share a
    sandbox root.

---

## 3. Threat model and trust assumptions

The current patterns assume:

- **Trusted local environment**:
  - The process running AINL and the code with access to `AINL_AGENT_ROOT`
    and similar roots are under the control of the same operator or trusted
    team.

- **Controlled filesystem access**:
  - Other processes with read/write access to the sandbox roots are trusted
    not to tamper with task/result files in adversarial ways.

- **Disciplined external orchestrator**:
  - The external orchestrator is responsible for:
    - enforcing any safety, approval, budget, or policy rules that matter in
      your environment,
    - deciding when advisory outputs are safe to apply,
    - avoiding silent protocol widening or envelope shape changes that conflict
      with the documented contract.

You **should not** treat:

- local mailbox files under `AINL_AGENT_ROOT`,
- or the `agent` adapter interface itself,

as a hardened security boundary. They are coordination **conventions**, not a
complete security fabric.

---

## 4. Practical safe-use guidance

For non-expert users and "helpful but undisciplined" agents, we recommend:

- **Keep sandbox roots narrow**:
  - Prefer dedicated directories such as `/tmp/ainl_agents` or an equivalent
    per-deployment path.
  - Avoid pointing `AINL_AGENT_ROOT` or similar roots at:
    - `/` (filesystem root),
    - `$HOME`,
    - shared multi-user mounts,
    - locations where untrusted processes can write.

- **Do not assume advisory outputs are safe to auto-execute**:
  - Treat token-cost and monitor-status advisory examples as:
    - **decision-support**, not auto-remediation,
    - inputs to human or orchestrator review,
    - not direct instructions to change production systems without checks.

- **Do not assume policy fields are enforced by AINL**:
  - `approval_required`, `budget_limit`, `policy_context`, `trust_domain`,
    and similar fields:
    - are not enforced by AINL or the `agent` adapter,
    - must be interpreted and enforced by your orchestrator or workflow system
      if you rely on them.

- **Treat coordination examples as bounded reference patterns**:
  - `token_cost_advice_*` and `monitor_status_advice_*`:
    - demonstrate **one task, one result** advisory loops,
    - are not full agent fabrics or swarm engines,
    - should not be extended into "run arbitrary remediation automatically"
      flows without adding your own safety checks, approvals, and audits.

- **Be conservative about extension adapters**:
  - Adapters classified as `extension_openclaw` and `noncanonical`
    (`agent`, `extras`, `svc`, `tiktok`, etc.):
    - are designed for operator-controlled environments,
    - may not be appropriate to expose directly to untrusted users or
      unreviewed agents without additional safeguards.

---

## 5. Supported safe default use vs advanced/unsupported use

At a high level, you can think about AINL usage in two buckets:

### 5.1 Supported safe default use

These are the patterns the project intends as the **safe default**:

- human-authored or human-reviewed AINL programs,
- canonical / non-extension examples (see `docs/EXAMPLE_SUPPORT_MATRIX.md`),
- controlled local execution of workflows,
- no automatic remediation or infra changes driven directly from advisory
  coordination outputs,
- no unsupervised agent-driven modification of canonical examples or strict
  programs.

Staying in this bucket means:

- you rely on the core compiler/runtime and canonical adapters,
- you treat extension/OpenClaw adapters and coordination as optional,
- you keep humans or well-reviewed code in the loop for high-impact actions.

### 5.2 Advanced / not safe-by-default / unsupported unless operator-controlled

The following patterns are considered **advanced** and **not safe-by-default**.
They should only be used by operators who understand the risks and have added
their own safeguards:

- OpenClaw/extension coordination workflows using the `agent` adapter,
- unsupervised agents generating or mutating AINL programs freely,
- automatically acting on advisory mailbox results (e.g. token-cost or
  monitor-status advisories) without human or policy review,
- using the local coordination substrate as a de-facto orchestration bus for
  production changes,
- configuring broad or shared roots for coordination and observability
  artifacts (e.g. pointing `AINL_AGENT_ROOT` at shared project dirs),
- treating policy or budget fields as if AINL or the adapters enforce them.

These patterns are **possible**, but upstream does **not** present them as safe
default usage and does **not** claim that AINL alone provides sufficient
policy, security, or autonomy safeguards for them.

---

## 6. Advisory vs enforced table (coordination-related)

The table below summarizes which coordination-related knobs are enforced by the
current implementation vs advisory-only.

| Item | Description | Enforced by AINL / adapters? | External/orchestrator responsibility? |
|------|-------------|------------------------------|----------------------------------------|
| `approval_required` | Indicates if human approval is needed for a task | **No** (descriptive only) | **Yes** — orchestrator must enforce any approval workflow |
| `budget_limit` | Token/monetary budget hints for a task | **No** (descriptive only) | **Yes** — orchestrator must track and enforce budgets |
| `policy_context` | Environment / change window / policy hints | **No** (descriptive only) | **Yes** — policy engines / workflows must interpret this |
| `trust_domain` | Logical trust grouping for an agent | **No** (descriptive only) | **Yes** — system design and deployment boundaries |
| `allowed_tools` | Tools the agent is expected to use | **No** (descriptive only) | **Yes** — orchestrator must restrict tool access if required |
| `task_id` format | Identifier used to derive result file name | **Partially** — `agent.read_result` rejects ids with path separators / `..` | **Yes** — choosing non-sensitive ids and mapping to real workflows |
| `AINL_AGENT_ROOT` sandbox checks | Root must not be `/`; paths must stay under root | **Yes** — adapters enforce root and path containment | **Yes** — choosing a safe root location is operator’s responsibility |
| `AgentTaskResult` object-only JSON | Result must parse to a JSON object | **Yes** — non-object JSON is rejected | **Yes** — orchestrator must ensure result shape is correct and safe |
| Coordination protocol surface (`send_task` / `read_result`) | Only accepted shared verbs for local mailbox coordination | **Yes** — tests and docs lock this surface | **Yes** — additional verbs in forks must not be treated as shared protocol |
| Result creation and routing | How tasks are scheduled, routed, and converted into results | **No** — AINL does not perform routing or scheduling | **Yes** — orchestrator must implement routing, retries, escalation, etc. |

If a field is marked "descriptive only", you should assume **nothing** happens
unless your own orchestrator or workflow system is written to act on it.

For advanced deployments that use the local mailbox substrate heavily, you can
run:

- `python -m scripts.validate_coordination_mailbox --tasks-jsonl path/to/tasks.jsonl`
- `python -m scripts.validate_coordination_mailbox --result-json path/to/result.json`

to check whether envelopes still conform to the upstream coordination schema.
This validator is **optional** and **extension-only**; it is provided to help
keep empowered usage on upstream rails, not to enforce policy or change core
AINL behavior.

---

## 7. Sandboxed and containerized deployments

AINL is designed to function as a **workflow execution layer** inside sandboxed,
containerized, or operator-controlled environments. In this model:

- The **hosting environment** (container orchestrator, sandbox controller, or
  managed agent platform) provides:
  - process isolation, filesystem restrictions, and network policy,
  - resource limits (CPU, memory, wall-clock timeout),
  - policy enforcement and approval workflows.

- The **AINL runtime** provides:
  - adapter capability gating via an explicit allowlist,
  - runtime resource limits (`max_steps`, `max_depth`, `max_time_ms`, etc.),
  - adapter-level path containment and host restriction,
  - a policy validation tool (`tooling/policy_validator.py`) that can serve
    as a pre-execution gate on compiled IR,
  - optional policy-gated execution at the `/run` endpoint (HTTP 403 on
    violations),
  - capability discovery via `GET /capabilities` (adapters, verbs, tiers,
    runtime version).

AINL does **not** claim to be a sandbox or security layer. The adapter
allowlist and runtime limits are **defense-in-depth mechanisms**, not a
substitute for container-level or OS-level isolation.

For operators deploying AINL inside sandboxed environments:

- **External orchestration guide** (capability discovery, policy-gated
  execution, integration checklist):
  `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- **Sandbox execution profiles** (adapter allowlists, runtime limits,
  environment configuration): `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- **Runtime container guide** (Dockerfiles, probe configuration, integration
  patterns): `docs/operations/RUNTIME_CONTAINER_GUIDE.md`

These guides are **framework-agnostic** and apply to any container
orchestrator or agent host.
