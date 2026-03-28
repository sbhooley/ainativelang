# Bot onboarding (AINL / OpenClaw / ZeroClaw repo)

Short entrypoint for bots (and other agents) newly exposed to this repo. Use this to orient quickly and to follow the expected implementation discipline.

---

## Where to start

1. **Machine-readable bootstrap** — `tooling/bot_bootstrap.json`
   Points to onboarding doc, preflight doc, and key safe vs advanced docs. Use it to discover paths programmatically. For **OpenClaw + AINL** install/upgrade posture: **`openclaw_ainl_gold_standard`** → **`docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md`**; for **v1.2.8 host obligations** (what ships vs what OpenClaw wires): **`openclaw_host_ainl_1_2_8`** → **`docs/operations/OPENCLAW_HOST_AINL_1_2_8.md`**. For **optional tiered repo context** (`code_context`): **`code_context_adapter_doc`** → **`docs/adapters/CODE_CONTEXT.md`** (graphs that call `R code_context.*` need **`--enable-adapter code_context`** on **`ainl run`**; MCP install alone does not enable it).

2. **Docs index** — `docs/DOCS_INDEX.md`
   Top-level map of documentation (core, advanced, training, contributor path). Prefer this over guessing doc names.

3. **This onboarding doc** — `docs/BOT_ONBOARDING.md`
   You are here. Read the next sections, then the preflight doc before any implementation work.

---

## Which docs matter first

- **Core / safe-default:**
  `docs/AINL_SPEC.md`, `docs/AINL_CANONICAL_CORE.md`, `docs/EXAMPLE_SUPPORT_MATRIX.md`, `docs/RUNTIME_COMPILER_CONTRACT.md`.
  These describe the main language, runtime, and which examples are canonical vs compatible.

- **Advanced / operator-only:**
  `docs/adapters/OPENCLAW_ADAPTERS.md`, `docs/adapters/MEMORY_CONTRACT.md`, `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`, `docs/CAPABILITY_REGISTRY.md`.
  Extension adapters, memory, and operator-only capabilities are documented here. Do not assume all adapters or examples are safe-default; check the support matrix and capability metadata.

- **Implementation discipline:**
  **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`** — required reading before implementing. It defines the preflight steps and output structure you must produce before coding.

---

## Preflight is required before implementation work

Before writing code, tests, or implementation-oriented docs:

- Read **`docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md`**.
- Complete the **required preflight steps** (inspect files, confirm not duplicate, verify adapter semantics from code, etc.).
- Emit the **required output structure** (chosen task, why not duplicate, files inspected, current behavior, verified semantics, assumptions, smallest viable implementation, validation plan).
- Then implement.

Skipping the preflight increases the risk of duplicate work, wrong assumptions, and misuse of adapter/API semantics.

---

## Safe-default vs advanced / operator-only

- **Safe-default** — Canonical compiler/runtime, core adapters, strict-valid examples, graph/IR tooling. Documented in the “Core / safe-default” section of `docs/DOCS_INDEX.md` and in `docs/AINL_CANONICAL_CORE.md`. Safe for general use and unsupervised agents within the stated scope.

- **Advanced / operator-only** — Extension adapters (memory, svc, extras, agent, etc.), OpenClaw monitors, coordination, and operator-only capability tags. Documented in “Advanced / operator-only” in `docs/DOCS_INDEX.md`, `docs/adapters/OPENCLAW_ADAPTERS.md`, `docs/CAPABILITY_REGISTRY.md`, and `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md`. Intended for operators and controlled environments; not the default entry path for new users or unsupervised agents.

When proposing or implementing work that touches adapters or examples, check the support matrix and capability registry to see whether the surface is safe-default or advanced/operator-only, and document that in your preflight output.

---

## Quick reference

| Need | Doc or file |
|------|------------------|
| Bootstrap pointers | `tooling/bot_bootstrap.json` |
| Full doc map | `docs/DOCS_INDEX.md` |
| Implementation preflight (required) | `docs/OPENCLAW_IMPLEMENTATION_PREFLIGHT.md` |
| Canonical language / core | `docs/AINL_CANONICAL_CORE.md`, `docs/AINL_SPEC.md` |
| Example classification | `docs/EXAMPLE_SUPPORT_MATRIX.md` |
| Adapters / capabilities | `docs/CAPABILITY_REGISTRY.md`, `tooling/capabilities.json` |
| Memory contract | `docs/adapters/MEMORY_CONTRACT.md` |
| Safe use / threat model | `docs/advanced/SAFE_USE_AND_THREAT_MODEL.md` |
| OpenClaw / AI agent quickstart | `AI_AGENT_QUICKSTART_OPENCLAW.md` (see also `OPENCLAW_AI_AGENT.md`) |
| OpenClaw skill + MCP bootstrap | `docs/OPENCLAW_INTEGRATION.md` (`skills/openclaw/`, `ainl install-openclaw`, `~/.openclaw/openclaw.json`) |
| ZeroClaw skill + MCP bootstrap | `docs/ZEROCLAW_INTEGRATION.md` (`ainl install-zeroclaw`, `~/.zeroclaw/`) |
| Optional **`code_context`** (repo index, deps, impact, `COMPRESS_CONTEXT`) | `docs/adapters/CODE_CONTEXT.md` — enable **`--enable-adapter code_context`** on **`ainl run`** / host **`ainl-run`** shims; optional **`AINL_CODE_CONTEXT_STORE`**; demo **`examples/code_context_demo.ainl`** |
| OpenClaw bridge monitoring (token budget, weekly trends, daily memory path) | `docs/operations/UNIFIED_MONITORING_GUIDE.md` (also `docs/ainl_openclaw_unified_integration.md`, `openclaw/bridge/README.md`) — not used for ZeroClaw daily memory |

---

This is documentation and discoverability only. No auto-execution, policy engine, or planner is implied. Follow the preflight, then implement.
