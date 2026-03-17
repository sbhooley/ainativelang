## Runtime Container Guide

**Status:** Design/docs only. This document does not change compiler or runtime
semantics. It describes how to package and run AINL as a containerized runtime
unit inside any orchestrator or sandbox controller.

---

## 1. Purpose

This guide explains how to deploy the AINL runtime as a **generic, containerized
execution unit** that any orchestrator, sandbox controller, or managed platform
can launch, configure, monitor, and stop.

It is **framework-agnostic**. The patterns described here work with any
container orchestrator (Docker, Kubernetes, Podman, etc.) and any agent host
(NemoClaw, OpenShell, custom orchestrators, CI/CD systems, etc.).

---

## 2. Two deployment modes

### 2.1 Runner service mode (HTTP API)

Run the AINL runtime as a persistent HTTP service that accepts workflow
execution requests via REST.

- **Entrypoint:** `ainl-runner-service` (or `uvicorn scripts.runtime_runner_service:app`)
- **Default port:** 8770
- **Endpoints:**
  - `POST /run` — compile and execute an AINL program (optional `policy` for pre-execution validation)
  - `POST /enqueue` — queue a program for background execution
  - `GET /result/{id}` — retrieve a queued job result
  - `GET /capabilities` — discover adapters, verbs, tiers, and runtime version
  - `GET /health` — liveness probe
  - `GET /ready` — readiness probe
  - `GET /metrics` — runtime metrics

This mode is best when:

- the orchestrator sends workflows via HTTP,
- multiple workflows may execute over the service's lifetime,
- health/readiness monitoring is needed.

### 2.2 CLI mode (one-shot execution)

Run a single AINL program via the `ainl` CLI and exit.

- **Entrypoint:** `ainl run <program> [options]`
- **Exit code:** 0 on success, non-zero on failure

This mode is best when:

- the orchestrator launches a container per workflow,
- execution is one-shot (run once, return result, exit),
- no persistent HTTP service is needed.

---

## 3. Minimal Dockerfile for the runner service

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements-dev.txt ./
COPY compiler_v2.py compiler_grammar.py grammar_priors.py grammar_constraint.py runtime.py ./
COPY runtime/ ./runtime/
COPY adapters/ ./adapters/
COPY tooling/ ./tooling/
COPY scripts/ ./scripts/
COPY cli/ ./cli/

RUN pip install --no-cache-dir -e ".[web]"

EXPOSE 8770

ENV PYTHONUNBUFFERED=1
ENV AINL_AGENT_ROOT=/data/agents
ENV AINL_MEMORY_DB=/data/memory.sqlite3

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8770/health')" || exit 1

CMD ["uvicorn", "scripts.runtime_runner_service:app", "--host", "0.0.0.0", "--port", "8770"]
```

### 3.1 Minimal Dockerfile for CLI mode

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements-dev.txt ./
COPY compiler_v2.py compiler_grammar.py grammar_priors.py grammar_constraint.py runtime.py ./
COPY runtime/ ./runtime/
COPY adapters/ ./adapters/
COPY tooling/ ./tooling/
COPY scripts/ ./scripts/
COPY cli/ ./cli/

RUN pip install --no-cache-dir -e .

ENTRYPOINT ["ainl", "run"]
```

Usage: `docker run ainl-cli program.ainl --max-steps 5000 --strict`

---

## 4. Configuration via environment and request

### 4.1 Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `AINL_AGENT_ROOT` | Sandbox root for agent coordination | `/tmp/ainl_agents` |
| `AINL_MEMORY_DB` | Path to SQLite memory store | `/tmp/ainl_memory.sqlite3` |
| `AINL_SUMMARY_ROOT` | Root for metrics output | (adapter-specific) |

In a containerized deployment, point these at container-local paths (e.g.
`/data/agents`, `/data/memory.sqlite3`). If using ephemeral containers, these
can be temporary.

### 4.2 Runtime configuration via `/run` request

The runner service accepts configuration in the POST body:

```json
{
  "code": "S app api /api\nL1:\nR core.ADD 2 3 ->x\nJ x",
  "strict": true,
  "label": "L1",
  "limits": {
    "max_steps": 5000,
    "max_depth": 50,
    "max_adapter_calls": 500,
    "max_time_ms": 30000
  },
  "allowed_adapters": ["core"],
  "adapters": {
    "enable": ["http"],
    "http": {
      "allow_hosts": ["api.internal.example.com"],
      "timeout_s": 5.0
    }
  }
}
```

Key configuration fields:

- `allowed_adapters` — adapter allowlist (capability gating)
- `limits` — runtime resource limits
- `policy` — optional policy object for pre-execution IR validation (see below)
- `adapters.enable` / `adapters.<name>` — adapter-specific configuration
- `strict` — strict-mode compilation
- `record_calls` / `replay_log` — deterministic recording/replay

---

## 5. Health and readiness probes

The runner service exposes standard probe endpoints:

| Endpoint | Purpose | Healthy response |
|----------|---------|-----------------|
| `GET /health` | Liveness probe | `{"status": "ok"}` (200) |
| `GET /ready` | Readiness probe | `{"status": "ready"}` (200) |
| `GET /metrics` | Runtime metrics | JSON with run counts, durations, adapter stats |

### 5.1 Kubernetes probe configuration

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8770
  initialDelaySeconds: 5
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8770
  initialDelaySeconds: 3
  periodSeconds: 10
```

### 5.2 Docker Compose health check

```yaml
services:
  ainl-runner:
    build: .
    ports:
      - "8770:8770"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8770/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

---

## 6. Graceful shutdown

The runner service uses uvicorn, which handles `SIGTERM` for graceful shutdown.
Container orchestrators that send `SIGTERM` before `SIGKILL` (standard
Kubernetes behavior with a default 30-second grace period) will get clean
shutdown.

For long-running enqueued jobs, the orchestrator should:

- check `/result/{id}` before stopping the container,
- or accept that in-flight jobs may be lost on container stop.

---

## 7. Resource constraints

### 7.1 Container-level constraints (orchestrator-enforced)

Set these in your container orchestrator:

- **CPU limit:** 0.5–2 cores (depends on workflow complexity)
- **Memory limit:** 256MB–1GB (depends on workflow data size)
- **Wall-clock timeout:** match your SLA (the runner service does not enforce
  a global timeout; use container-level timeouts as the outer boundary)

### 7.2 AINL-level constraints (runtime-enforced)

Set these in the `/run` request or CLI flags:

- `max_steps`, `max_depth`, `max_adapter_calls`, `max_time_ms`,
  `max_frame_bytes`, `max_loop_iters`

See `docs/operations/SANDBOX_EXECUTION_PROFILE.md` for recommended limit
profiles.

These two layers provide defense-in-depth: AINL limits catch runaway workflows
within the runtime, and container limits catch anything that escapes the
runtime.

---

## 8. Sandboxed execution checklist

Before deploying AINL in a sandboxed or restricted environment:

- [ ] Choose an adapter allowlist profile from
  `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- [ ] Set runtime limits appropriate for your workload
- [ ] Configure environment variables to use container-local paths
- [ ] Set container-level resource constraints (CPU, memory, timeout)
- [ ] If using `http` adapter, configure `allow_hosts` to restrict egress
- [ ] If using `fs` adapter, configure `sandbox_root` to restrict filesystem access
- [ ] If the orchestrator needs pre-execution policy checks, include a
  `policy` object in the `/run` request (the runner validates IR against the
  policy before execution and returns HTTP 403 on violations)
- [ ] Verify health/readiness probes work in your orchestrator
- [ ] Review `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` for trust model

---

## 9. Integration patterns

### 9.1 Orchestrator submits pre-compiled IR

If the orchestrator pre-compiles AINL to IR (using the compiler separately),
it can submit IR directly to the runner service. This separates the compile
step (which can be done in a trusted environment) from the execution step
(which happens in the sandbox).

### 9.2 Orchestrator submits source code

The runner service can compile and execute in one step via `POST /run` with
`code` in the body. The runner compiles to IR, caches the result, and
executes.

### 9.3 One-shot container execution

For orchestrators that launch a container per workflow:

```bash
docker run --rm \
  -e AINL_AGENT_ROOT=/data/agents \
  ainl-cli program.ainl \
  --strict \
  --max-steps 5000 \
  --enable-adapter core \
  --json
```

The container runs the workflow, prints JSON output, and exits.

### 9.4 Sidecar pattern

The AINL runner can run as a sidecar container alongside an agent process.
The agent sends workflows to `localhost:8770/run` and receives results.
The orchestrator manages both containers as a pod.

---

## 10. What AINL does not provide in containerized deployments

The AINL runtime is the **workflow execution layer**. It does not provide:

- container orchestration or scheduling,
- secret management (do not pass secrets in AINL source or adapter args),
- log aggregation (the runner emits structured JSON logs to stdout; pipe to
  your logging system),
- TLS termination (place behind a reverse proxy or ingress controller),
- multi-tenant isolation (one runtime instance per tenant, or enforce at the
  orchestrator level).

---

## 11. Relationship to other docs

- **External orchestration guide:**
  `docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`
- **Sandbox profiles and adapter allowlists:**
  `docs/operations/SANDBOX_EXECUTION_PROFILE.md`
- **Trust model and safe use:**
  `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`
- **Agent coordination:**
  `docs/advanced/AGENT_COORDINATION_CONTRACT.md`
- **Adapter registry:**
  `docs/reference/ADAPTER_REGISTRY.md`
- **Runner service source:**
  `scripts/runtime_runner_service.py`
- **Emitted server Dockerfile (application mode):**
  `tests/emits/server/Dockerfile`
