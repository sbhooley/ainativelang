# Post-Release Roadmap (Immediate)

This roadmap captures immediate engineering priorities following the first public GitHub release.
It is intentionally narrow and contract-driven.

GitHub-ready issue draft stubs for this roadmap live in `docs/issues/`.
The operator-grade sequencing and breakage-control plan lives in `docs/NO_BREAK_MIGRATION_PLAN.md`.

## Recently shipped (through **v1.8.0** — keep docs/tests aligned)

Use this as the **done** baseline when opening new work; do not re-plan these without an explicit new requirement.

| Area | Shipped | Pointers |
|------|---------|----------|
| **Release line** | **PyPI / runtime `ainativelang` 1.8.0** (`pyproject.toml`, **`RUNTIME_VERSION`**, **`CITATION.cff`**) — see **`docs/RELEASE_NOTES.md`** / **`docs/CHANGELOG.md`** | `docs/RELEASING.md` |
| **GraphPatch (runtime + bridge)** — **✅ complete (v1.6.0)** | **`R memory.patch`** / graph **`memory.patch`** → **`adapters.call("ainl_graph_memory", "graph_patch", …)`**; **`OverwriteGuardError`**; **`StrictModeError`**; **`_reinstall_patches`** on boot; fitness EMA; engine dispatch for **`patch`** | `runtime/engine.py`, **`tests/test_graph_patch_op.py`**, `armaraos/bridge/ainl_graph_memory.py`, `compiler_v2.py`, `tooling/effect_analysis.py` |
| **Graph memory (bridge + runtime)** | IR **`MemoryRecall`/`MemorySearch`** → **`ainl_graph_memory`**; JSON store + ArmaraOS **`armaraos/bridge/`**; **`docs/adapters/AINL_GRAPH_MEMORY.md`**; demos **`demo/procedural_roundtrip_demo.py`**, **`demo/ainl_graph_memory_demo.py`** | `runtime/engine.py`, `tests/test_memory_recall_op.py`, **`tests/test_memory_search_op.py`**, `armaraos/bridge/ainl_graph_memory.py` |
| **Hybrid interop + `S hybrid`** | LangGraph / Temporal wrappers, **`validate_ainl.py --emit langgraph|temporal`**, **`langchain_tool`** adapter, **`S hybrid langgraph|temporal`** for **`minimal_emit`** / planners | `docs/HYBRID_GUIDE.md`, `docs/AINL_SPEC.md` §2.3.1, `runtime/wrappers/`, `examples/hybrid/`, `docs/hybrid/OPERATOR_RUNBOOK.md`, `docs/PACKAGING_AND_INTEROP.md` |
| **CI benchmark regression** | **`benchmark-regression`** prefers committed **`tooling/benchmark_*_ci.json`** on baseline SHA; **Python 3.10** jobs; **`make benchmark-ci`** echoes **`PYTHON`** | `.github/workflows/ci.yml`, `BENCHMARK.md` § *CI regression baselines*, `docs/benchmarks.md` § CI |
| **Runtime label resolution (includes + graph)** | Bare subgraph targets in **If** / **Loop** / **While** / **Call** are qualified with the **`alias/`** prefix from the runtime stack when **`labels`** keys are merged as **`alias/child`** | `runtime/engine.py` (`_resolve_label_key`), `tests/test_demo_enforcer.py` (`test_graph_mode_nested_if_resolves_bare_child_labels`) |
| **Access-aware memory (opt-in)** | **`modules/common/access_aware_memory.ainl`**: **`LACCESS_READ`**, **`LACCESS_WRITE`**, **`LACCESS_LIST`**, **`LACCESS_LIST_SAFE`**; module header documents graph-mode caveats for **`LACCESS_LIST`** (ForEach IR) vs graph-safe **`LACCESS_LIST_SAFE`** | `modules/common/access_aware_memory.ainl`, `modules/common/README.md`, `docs/RELEASE_NOTES.md` § **v1.2.4** (current release **v1.8.0**) |
| **Compile-time `include`** | Merge included `.ainl` into parent IR under **`alias/LABEL`** ids; strict **ENTRY / EXIT_*** contracts; path resolution + cycle checks | `tests/test_includes.py`, `modules/common/retry.ainl`, `modules/common/timeout.ainl`, root README *Includes & modules*, `docs/WHAT_IS_AINL.md` |
| **Structured diagnostics (Phase 3 core)** | Native **`Diagnostic`** + **`CompilerContext`**; merge **dedup** (native wins); CLI **`--diagnostics-format`** (`auto` / `plain` / `rich` / `json`); optional **rich** stderr | `compiler_diagnostics.py`, `ainl-validate`, `docs/INSTALL.md`, `tests/test_diagnostics.py` |
| **OpenClaw intelligence + ops (v1.2.8–v1.8.0)** | **`run_intelligence.py`** (context, summarizer, consolidation, **`auto_tune_ainl_caps`**), **`tooling/intelligence_budget_hydrate.py`**, profiles + env templates, **`OPENCLAW_AINL_GOLD_STANDARD.md`** / **`OPENCLAW_HOST_AINL_1_2_8.md`**, embedding pilot + startup token clamps, graph-safe intelligence fixes | `scripts/run_intelligence.py`, `intelligence/`, `docs/operations/OPENCLAW_*.md`, **`WHITEPAPERDRAFT.md`** §10.5 / §13.5 |
| **Graph visualizer CLI** | **`ainl visualize`** / **`ainl-visualize`** → **Mermaid** from **`ir["labels"]`**; subgraph clusters per include alias; synthetic **`Call →` entry** edges + `%%` comment | `scripts/visualize_ainl.py`, `docs/architecture/GRAPH_INTROSPECTION.md` §7, root README *Visualize your workflow* |
| **Strict literal / dataflow** | Quoted string literals in read positions where required; **`J "payload"`** style for strict dataflow | `docs/RUNTIME_COMPILER_CONTRACT.md`, `docs/CONFORMANCE.md`, canonical lint / strict tests |

---

## GraphPatch follow-ups (next)

1. **`MemoryExecute` verb** — close the executable memory loop (invoke stored procedural graphs with explicit budgets); align compiler, **`ADAPTER_EFFECT`**, and runtime dispatch with **`memory.patch`** lessons learned.
2. **GraphPatch whitepaper section** — add a **`WHITEPAPERDRAFT.md`** subsection covering promotion, fitness EMA, boot reinstall, and operator safety (**`OverwriteGuardError`** / **`StrictModeError`**).
3. **Cross-agent patch sharing** — policy + storage for exporting/importing **`PatchRecord`** / procedural nodes across **`agent_id`** scopes (tenant isolation defaults).
4. **Fitness decay / TTL policy** — age out or down-rank stale patches beyond EMA alone (session caps, graph-store GC hooks).

---

## Active priorities (next)

### 1) Canonical strict surface expansion (contract-first)

- Expand strict-valid surface only through explicit, compiler-owned contracts.
- Any strict expansion must be reflected in:
  - `tooling/effect_analysis.py` (adapter/effect contract)
  - `tooling/artifact_profiles.json` (artifact expectations)
  - conformance/runtime tests
- No wildcard strict allowances.

### 2) Legacy and non-strict artifact migration

- Reduce non-strict-only and legacy-compat artifacts over time via intentional migration.
- Promote artifacts to `strict-valid` only after:
  - strict compile pass
  - runtime behavior validation
  - docs/profile updates
- Keep compatibility artifacts explicitly labeled while migration is incomplete.

### 3) Compiler-structured diagnostics — remaining scope

**Status:** **Core path shipped** (validator, visualizer, merge dedup, CLI format flags). **Remaining (optional):** additional strict diagnostic sites, language-server polish, regression tests that lock span precision for new sites.

- Increase structured diagnostic coverage where gaps remain (`span`, `lineno`, `label_id`, `node_id`, etc.).
- Keep language server diagnostic heuristics strictly as backward-compat fallback.
- Add tests that prevent diagnostic location regressions and fake precision.

### 4) Compatibility-path retirement (incremental)

- Continue reducing compatibility-only execution paths where canonical behavior already exists.
- Maintain backward compatibility wrappers during transition but avoid adding new semantics there.
- Require explicit deprecation notes before removing compatibility paths.

## Guardrails

- No semantic changes without corresponding contract docs and tests.
- Preserve canonical ownership boundaries:
  - compiler semantics: `compiler_v2.py`
  - runtime semantics: `runtime/engine.py`
  - compatibility wrappers: `runtime/compat.py`, `runtime.py`
