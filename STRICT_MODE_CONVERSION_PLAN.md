# AI Native Lang (AINL) Strict-Mode Conversion Plan

**Target:** Convert all AINL programs to `strict_mode=True` + `strict_reachability=True` compliance.
**Based on analysis date:** 2026-03-03 (compiler_v2 with grammar_constraint updates)
**Status:** Grammar stable; ready for execution.

---

## Summary of Breaking Changes

1. **If conditions must use precomputed booleans**
   - ❌ `If (core.gt x y) ->L_then ->L_else`
   - ✅ `X _cond (core.gt x y); If _cond ->L_then ->L_else`

2. **Adapter calls must use exactly two tokens: `R group verb`**
   - ❌ `R core.now`, `R email.G`, `R cache.get`, `R queue.Put`, `R db.F`, `R svc caddy` (inside `R` it's two tokens? Actually `R svc caddy` is correct; but combined like `cache.get` as one token must be split.)
   - ✅ `R core now`, `R email G`, `R cache get`, `R queue Put`, `R db F`, `R svc caddy`
   - Note: The grammar expects `adapter` = group name and `target` = verb name. Do not combine group and verb with a dot in the `R` op. The combined forms cause IR `'adapter': '?'` and runtime gate errors.

3. **Parentheses disallowed in many expression contexts**
   - ❌ `(core.concat a b)` in argument position
   - ✅ Either `core.concat a b` directly, or `X tmp (core.concat a b); use tmp`
   - Applies to nested expressions in `Filter`, `Sort`, arithmetic, etc.

4. **Strict reachability**
   - All variables must be defined on all control‑flow paths before use.
   - Add default initializations: `Set var default` early (often at label 0) to satisfy all reads.
   - Ensure every `J` target is reachable and contains exactly one `J` as its entry point.

5. **Label naming**
   - Strict mode expects numeric label IDs only (`L0`, `L1`, …). Friendly names (`L_skip`, `L_healthy`) are not permitted.
   - Convert friendly labels to numeric and update all references consistently.

---

## Conversion Order

**Priority 1:** `demo/monitor_system.strict.lang` (strict version of the production monitor)
**Priority 2:** `examples/openclaw/daily_digest.strict.lang`
**Priority 3:** `examples/openclaw/lead_enrichment.strict.lang`
**Priority 4:** `examples/openclaw/infrastructure_watchdog.strict.lang`
**Priority 5:** `examples/openclaw/webhook_handler.strict.lang`

*Note:* The non‑strict files (`demo/monitor_system.lang` and `examples/openclaw/*.lang`) are already syntactically correct (two‑token `R` steps) and run in production. Strict variants need the additional strict-mode transforms.

---

## Step‑by‑Step Conversion Protocol

For each strict‑target file (`*.strict.lang`):

1. **Parse with strict mode** to generate full error list: `AICodeCompiler(strict_mode=True, strict_reachability=True).compile(code)`.
2. **Split any combined `R` tokens**: convert `R group.verb` into `R group verb`. Also ensure any `R wasm.CALL` becomes `R wasm CALL`.
3. **Extract all inline `If` conditions** into `X` precomputations: `X <var> (expr); If <var> ->L_then ->L_else`.
4. **Remove parentheses in expression arguments**: wherever a nested call like `(core.concat ...)` appears, either flatten or bind to an intermediate `X`.
5. **Add missing variable initializations**: for variables read on some paths (e.g., `needs_notify`, `failed_services`, cond vars), add `Set var default` near the start of the graph (usually label 0).
6. **Rename friendly labels to numeric**: replace `L_skip`, `L_healthy`, `L_done`, `L_notify`, etc. with `L<n>` and update all jumps. Keep a mapping.
7. **Re‑run strict validation** until zero errors.
8. **Verify the non‑strict file still compiles** (optional sanity check).

---

## Adapter Verb Reference (from ADAPTER_REGISTRY.json)

| Adapter | Verbs | Effect | Strict‑mode example |
|---------|-------|--------|---------------------|
| core    | now, add, sub, mul, div, idiv, mod, pow, len, concat, join, stringify, lt, gt, lte, gte, eq, ne | pure‑compute | `R core now`; expressions: `core.sub x y` |
| email   | G | io‑read | `R email G ->emails` |
| calendar| G | io‑read | `R calendar G ->events` |
| social  | G | io‑read | `R social G ->mentions` |
| db      | F (read), P (write) | io‑read / io‑write | `R db F Leads * ->leads`; `R db P Leads data ->result` |
| svc     | caddy, cloudflared, maddy | io‑read | `R svc caddy ->status` |
| cache   | get, set | io‑read / io‑write | `R cache get "key" ->val`; `R cache set "key" val ->_` |
| queue   | Put | io‑write | `R queue Put notify payload ->_` |
| wasm    | CALL | pure‑compute | `R wasm CALL module func args ->result` |

**Important:** In strict mode, the `R` op requires separate tokens for group and verb. Do not use dot‑notation in the `R` op.

---

## Conversion Examples

### If expression with precompute

Before:
```ainl
L7: If (core.gt email_count Config.email_threshold) ->L8 ->L9
```
After:
```ainl
L7: X _cond (core.gt email_count Config.email_threshold)
    If _cond ->L8 ->L9
```

### Adapter token splitting

Before (strict draft):
```ainl
L2: R email.G ->emails
L5: R cache.get "state" "last_email_check" ->last_check
L57: R queue.Put notify {...} ->_
```
After:
```ainl
L2: R email G ->emails
L5: R cache get "state" "last_email_check" ->last_check
L57: R queue Put notify {...} ->_
```

### Numeric labels

Before:
```ainl
L34: If (core.gt stalled_count 0) ->L_skip ->L35
L_skip: Set skipped 1 J L36
```
After:
```ainl
L0: Set skipped 0   # default
...
L34: X cond (core.gt stalled_count 0)
    If cond ->L50 ->L35
L50: Set skipped 1 J L36
```

### Parentheses removal

Before:
```ainl
X digest (core.join "\n\n" [
    (core.concat "📧 " (core.stringify email_count))
])
```
After:
```ainl
X part1 (core.concat "📧 " (core.stringify email_count))
X part2 (core.concat "📅 " (core.stringify cal_count))
X digest (core.join "\n\n" [part1 part2])
```

---

## Specific Files & Action Items

### demo/monitor_system.strict.lang
- Split all `R` ops (`core.now`, `email.G`, `calendar.G`, `social.G`, `cache.get/set`, `db.F`, `queue.Put`, `svc.*` are already two‑token? Monitor non‑strict uses two‑token; the strict draft currently uses combined forms. Update to two‑token.)
- Precompute all `If` conditions with `X`.
- Add default `Set needs_notify 0` and `Set failed_services ""` at entry (label 0) to satisfy reachability.
- Rename any friendly labels (if present) to numeric.
- Ensure every target label contains exactly one `J`.
- Verify bulk‑email filter doesn’t use parentheses around `core.sub` inside `Filter`; either flatten or bind intermediate.

### examples/openclaw/daily_digest.strict.lang
- Convert `R email G`, `calendar G`, `social.G` → `R social G` (some already two‑token? but watch for combined).
- Replace `cache.F` usage with `cache.get` or `cache.set` explicitly.
- Extract `If` in L3 (throttle check) with `X`; convert friendly `L_skip` to numeric.
- Remove parentheses around any `core.concat` inside arrays.
- Add required initializations (e.g., `summary = ""`) if needed.

### examples/openclaw/lead_enrichment.strict.lang
- Fix `If (core.ge i total_leads) ->Label` to precomputed `X`.
- `db.F` is correct verb (`F`); ensure two‑token: `R db F`.
- `social.F` → `R social G`.
- `cache.F` → `R cache get` / `set` as appropriate.
- `queue.F` → `R queue Put`.
- Numeric labels.

### examples/openclaw/infrastructure_watchdog.strict.lang
- Replace friendly labels (`L_healthy`, `L_notify`, `L_send`, `L_skip`) with numeric.
- Transform all `If (expr)` to `X`.
- `queue.PUT` → `R queue Put`.
- `cache.F` → `R cache get`.
- `svc caddy` etc. already two‑token? Should be `R svc caddy` (correct). Ensure no dot syntax.
- Ensure `J` targets singletons.

### examples/openclaw/webhook_handler.strict.lang
- Check endpoint return flow; ensure all paths lead to valid response label.
- `db.F` and `db.P` already two‑token if written `R db F` / `R db P`; if written as `db.F`, split.
- `cache.F` → `cache.get`/`set`.
- `queue.PUT` → `R queue Put`.
- Numeric labels and single `J` per target.

---

## Deliverables After Conversion

- Every `.strict.lang` file compiles in strict mode with zero errors.
- `scripts/run_test_profiles.py --profile openclaw` passes for both strict and non‑strict variants (if strict variant included in profile).
- `agent_reports/AI_CONSULTANT_REPORT_APOLLO.md` updated to reflect strict‑mode compliance and include strict‑mode example snippets.
- `OPENCLAW_AI_AGENT.md` references updated if necessary.

---

## Timing

- Execute conversions in priority order; commit after each file’s strict validation.
- Re-run tests after each conversion.
- Keep non‑strict files unchanged; place strict variants alongside with `.strict.lang` suffix.

---

**Prepared by:** Apollo
**Date:** 2026‑03‑03
**Context:** Two‑token `R` syntax required by compiler; non‑strict monitor already updated and running
