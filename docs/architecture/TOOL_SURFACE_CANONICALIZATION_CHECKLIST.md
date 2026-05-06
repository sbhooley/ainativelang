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
- [ ] **Intersect path** — Patch allows `http`, host denylist blocks → host policy wins (document expected behavior).

---

## 7. Cross-repo alignment (not blocking AINL merge)

- [x] **ArmaraOS (partial)** — Native infer/planner path sets `InferRequest.tool_surface` from agent manifest metadata keys **`ainl_tool_surface`** or **`tool_surface`**. Host-side `ainl run` enforcement unchanged.
- [x] **ainl-inference-server** — Same `InferRequest.tool_surface` field (JSON passthrough for future session hydrate).

---

## 8. Documentation cleanup when “done”

- [ ] **`AINL_SPEC.md` §7.3** — Remove or tighten **DESIGN PREVIEW** banners for anything that compiles in strict mode.
- [ ] **`STATUS.yaml`** — Note **tool surface** support level (refresh script updates counts; narrative line optional).

---

## Minimum viable canonicalization (recommended order)

1. **Schema + IR preserve + runtime deny** — Smallest vertical slice: programs need not use new syntax; host can inject `services.tool_surface`.
2. **Compiler static checks** — Tighten strict mode when patch is static.
3. **Compact / `R tool_patch.*` syntax** — Optional sugar after IR path is proven.

---

_Last updated: 2026-05-06_
