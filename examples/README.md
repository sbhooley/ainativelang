# AI Native Lang (AINL) Examples

Examples are intentionally split by compile profile for release safety:

- **Strict-valid canonical examples**: expected to compile with `--strict`
- **Non-strict-only examples**: useful compatibility demos that intentionally do not pass strict mode
- **Legacy compatibility artifacts**: retained for migration/training context

The machine-readable source of truth is:

- `tooling/artifact_profiles.json`
- `tooling/support_matrix.json`

Quick checks:

```bash
python scripts/validate_ainl.py examples/hello.ainl --strict
python scripts/validate_ainl.py examples/blog.lang
```

**Solana (`R solana.*`):** For `DERIVE_PDA`, pass `seeds_json` as **single-quoted JSON** (recommended), e.g. `'["market","ID"]'`, so inner `"` characters stay inside one token. You can also use one double-quoted string with escaped inner quotes — see `adapters/solana.py` module docstring. **v1.3.3 onboarding:** `docs/solana_quickstart.md` (env vars, dry-run, emit flags, prediction-market patterns) and `examples/prediction_market_demo.ainl`.

Canonical strict-valid examples:

- `examples/hello.ainl` — canonical single-label compute + return (`R core.ADD` + `J`).
- `examples/web/basic_web_api.ainl` — canonical web endpoint flow (`S core web`, `E`, label body).
- `examples/crud_api.ainl` — canonical `Set` + `If` branch routing and explicit string literals.
- `examples/scraper/basic_scraper.ainl` — canonical scraper+cron intent (`Sc` + `Cr`) with runtime label flow.
- `examples/rag_pipeline.ainl` — canonical `Call ... ->out` return binding pattern (no `_call_result` compatibility style).
- `examples/retry_error_resilience.ainl` — canonical resilience flow (`R` + `Retry @nX` + `Err @nX` + explicit fallback label).
- `examples/if_call_workflow.ainl` — canonical branching + modular call composition (`If` + `Call ... ->out`).
- `examples/webhook_automation.ainl` — canonical webhook-style automation branch (`validate` -> `accepted/ignored`) plus external action (`R http.POST`).
- `examples/monitor_escalation.ainl` — canonical scheduled monitoring/escalation (`Cr` + condition branch -> `escalate/noop`).
- `examples/status_branching.ainl` — canonical status-branching example (`Set` + `If` -> `ok/alerted`).

Canonical language scope reference:

- `docs/AINL_CANONICAL_CORE.md`
- `docs/EXAMPLE_SUPPORT_MATRIX.md`

Recommended canonical learning order (small-model first):

1. `examples/hello.ainl` (compute + return)
2. `examples/crud_api.ainl` (Set + If branch)
3. `examples/rag_pipeline.ainl` (Call + bound return)
4. `examples/if_call_workflow.ainl` (If + Call workflow)
5. `examples/retry_error_resilience.ainl` (Retry + Err resilience)
6. `examples/web/basic_web_api.ainl` (endpoint + DB read)
7. `examples/webhook_automation.ainl` (validate/act/reject automation)
8. `examples/scraper/basic_scraper.ainl` (scraper + cron + persistence)
9. `examples/monitor_escalation.ainl` (scheduled monitor escalation)

Machine-readable curriculum source:

- `tooling/canonical_curriculum.json`

Non-strict-only examples (intentional compatibility surface):

- `examples/api_only.lang`
- `examples/blog.lang`
- `examples/ecom.lang`
- `examples/internal_tool.lang`
- `examples/ticketing.lang`
- `examples/cron/monitor_and_alert.ainl`
- `examples/openclaw/*.lang`
- `examples/autonomous_ops/*.lang`
- `examples/golden/*.ainl`

Use non-strict examples for runtime/backward-compat demonstrations, not as strict language conformance references.

Canonical guidance for small-model reliability:

- Prefer uppercase adapter verbs in strict-valid examples (e.g., `core.ADD`, `http.GET`).
- Prefer explicit `Call ... ->out` return binding over compatibility fallback (`_call_result`) in canonical examples.
