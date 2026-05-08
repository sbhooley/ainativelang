# Canonicalizing ToolRegistry / ToolPatch in AINL (implementation checklist)

**Purpose:** Turn **[`AINL_SPEC.md`](../AINL_SPEC.md) §7** from vocabulary + roadmap into **shipping compiler/runtime behavior**.  
**Prerequisite reading:** [`TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md`](TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md), [`AINL_SPEC.md`](../AINL_SPEC.md) §6 (GraphPatch pattern), §7.

---

## 1. Normative artifacts (machine-readable)

- [x] **JSON Schema** — `schemas/tool_surface_v1.schema.json` for `services.tool_surface`: `registry_ref`, `patch_profile`, `explicit_allow`, `schema_version`, optional `contract_refs`.
- [x] **Validator helper** — `tooling/tool_surface.py` (`validate_tool_surface_shape`, `validate_patch_profile_known`, `effective_tool_surface`).
- [x] **IR documentation** — Unknown `services.*` keys preserved (**lossless compiler** policy); `tool_surface` keys validated when present.

---

## 2. Compiler (`compiler_v2` + compact preprocessor if syntax ships)

- [x] **IR preservation** — `compile(..., preserved_services=…)` merges host `tool_surface`; `_finalize_tool_surface` resolves `patch_profile` via `tooling/patch_profiles.json` (+ optional `AINL_PATCH_PROFILES_JSON`).
- [x] **Static checks (strict)** — `_validate_tool_surface_r_steps`: every static `R` / graph `R` step registry key must be in effective `adapter_allow`.
- [ ] **Opcode / compact syntax (optional phase)** — If promoting §7.3 from **design preview**:
  - [ ] Add opcode mapping (`tool_patch.SetAllowlist`, …) in opcode registry + `STEP_OPS`.
  - [ ] Compact `config tool_surface:` block in preprocessor → fills `services.tool_surface`.
  - [ ] `strict` diagnostics with **`kind` / `suggested_fix`** per project conventions.

---

## 3. Runtime (`runtime/engine.py` + adapter dispatch)

- [x] **Resolve effective patch** — `effective_tool_surface` then intersect IR/host `allowed` adapters with `adapter_allow` (`narrow_allowed_adapters`).
- [x] **Dispatch guard** — `_tool_patch_guard` → **`RUNTIME_TOOL_PATCH_DENY`** before adapter dispatch.
- [x] **Ordering** — Host denylist / allowlist applied first; then `tool_surface` narrowing; then `AdapterRegistry`.

---

## 4. Adapters & effects

- [ ] **Effect tier** — If graph-level mutations to patch are added later, register in `tooling/effect_analysis.py` + `tooling/adapter_manifest.json` (mirror **MemoryPatch** path in §6 notes).
- [ ] **Optional `tool_patch` adapter** — Only if graphs must **mutate** active patch mid-run; otherwise **host-injected `services.tool_surface`** may suffice for v1.

---

## 5. Tooling & CI

- [ ] **Strict-valid corpus** — If new syntax exists: add minimal **`examples/`** + `tooling/artifact_profiles.json` **strict-valid** entry when CI enforces that list.
- [x] **`refresh_repo_stats.py`** / **STATUS.yaml** — Run after compiler/runtime/tooling changes.

---

## 6. Tests

- [x] **IR merge** — `preserved_services` + `patch_profile` coverage in `tests/test_tool_surface_patch.py`.
- [x] **Deny path** — `R http.GET` vs `adapter_allow: ["core"]` → `RUNTIME_TOOL_PATCH_DENY`.
- [x] **Intersect path** — Patch allows `http`, host denylist blocks → host policy wins (`tests/test_tool_surface_patch.py` `test_host_adapter_denylist_wins_over_tool_surface_allowing_http`).

---

## 7. Cross-repo alignment (not blocking AINL merge)

- [x] **ArmaraOS (partial)** — Native infer/planner path sets `InferRequest.tool_surface` from agent manifest metadata keys **`ainl_tool_surface`** or **`tool_surface`**. Host-side `ainl run` enforcement unchanged.
- [x] **ainl-inference-server** — Same `InferRequest.tool_surface` field (JSON passthrough for future session hydrate).
- [x] **Vocabulary index (ToolPatch layers)** — See **§9** below + **[`TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md`](TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md) §7.2–7.3** (pre-filter vs D-gate vs router; Conversation default; per-turn snap-back vs **opt-in** sticky ceiling — [`STICKY_WORKFLOW_MODE.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/STICKY_WORKFLOW_MODE.md)).

---

## 8. Documentation cleanup when “done”

- [ ] **`AINL_SPEC.md` §7.3** — Remove or tighten **DESIGN PREVIEW** banners for anything that compiles in strict mode.
- [ ] **`STATUS.yaml`** — Note **tool surface** support level (refresh script updates counts; narrative line optional).

---

## 9. Cross-repo vocabulary (pre-filter vs D-gate vs router; snap-back)

**Platform definitions** (normative): **[`TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md`](TOOL_REGISTRY_AND_TOOL_PATCH_PLAN.md) §7.2** — three **distinct** layers (keyword **pre-filter**, infer **D-gate**, optional HTTP **router**). **§7.1** Conversation default; **§7.3** per-turn **snap-back** (default) vs **opt-in sticky workflow ceiling** (host-persisted narrowing until cleared — [`STICKY_WORKFLOW_MODE.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/STICKY_WORKFLOW_MODE.md); product default remains snap-back).

| Layer | Role (short) | Canonical infer-server doc |
|-------|----------------|-----------------------------|
| **Pre-filter (keyword)** | Host / cheap cue → mode & ToolPatch branch | [`TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/TOOL_PATCH_AND_ROUTER_ARCHITECTURE.md) §4.1 |
| **D-gate** | Infer pipeline: signal-only, **never widens**; routes refinement | Same doc §4.2 |
| **Router** | Small-model HTTP tier after D-gate; `RouterOutput` / §5.1 fallbacks | Same doc §5–§5.1 |

**Trust boundary & legacy chat ToolPatch:** [`PLANNER_HOST_BOUNDARIES.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/PLANNER_HOST_BOUNDARIES.md) — **host executes** tools; infer shapes / validates. **Active epic checklist:** [`INFER_SESSION_ACTIVE_TODOS.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/architecture/INFER_SESSION_ACTIVE_TODOS.md) §N (ToolPatch track; sticky **opt-in v1** + product backlog for default-on / A/B).

**Two enforcement surfaces (same §7 vocabulary, different runtime):**

| Surface | What it gates | Mechanism (where to read code) |
|---------|----------------|--------------------------------|
| **Compiled graph (`R adapter.op`)** | Adapter calls in IR | This repo: **`_tool_patch_guard`** → **`RUNTIME_TOOL_PATCH_DENY`** (§3); intersects host grants + `services.tool_surface`. |
| **Agent chat / planner (named tools)** | `file_read`, `mcp_ainl_*`, … | ArmaraOS: **`effective_legacy_tool_allowlist`**, **`compute_native_infer_tool_patch`**, `execute_tool` ∩ allowlist; infer: **`InferRequest.tool_surface`** validation only — [`PLANNER_HOST_BOUNDARIES.md`](https://github.com/sbhooley/ainl-inference-server/blob/main/docs/PLANNER_HOST_BOUNDARIES.md). |

Changing **manifest tool lists**, **`RUNTIME_TOOL_PATCH_DENY`** expectations, or **deny tokens** in IR should be reviewed against **both** rows so compiler/runtime and ArmaraOS stay aligned.

**This repo (AINL):** `services.tool_surface` + runtime **`_tool_patch_guard`** / **`RUNTIME_TOOL_PATCH_DENY`** (§3) implement **ToolPatch ⊆ registry** for **`R` adapter** dispatch. Cross-links do **not** change host vs control-plane authority — see registry plan **§5**.

---

## Minimum viable canonicalization (recommended order)

1. **Schema + IR preserve + runtime deny** — Smallest vertical slice: programs need not use new syntax; host can inject `services.tool_surface`.
2. **Compiler static checks** — Tighten strict mode when patch is static.
3. **Compact / `R tool_patch.*` syntax** — Optional sugar after IR path is proven.

---

_Last updated: 2026-05-08 (§9 dual-surface table + sticky opt-in links; §7 cross-repo row)_
