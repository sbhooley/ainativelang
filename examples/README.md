# AI Native Lang (AINL) Examples

Examples are intentionally split by compile profile for release safety:

- **Strict-valid canonical examples**: expected to compile with `--strict`
- **Non-strict-only examples**: useful compatibility demos that intentionally do not pass strict mode
- **Legacy compatibility artifacts**: retained for migration/training context

## For AI agents (read this before copying syntax)

Not every file under `examples/` is a safe template. **CI enforces** that every `examples/**/*.ainl` and `examples/**/*.lang` path is listed in `tooling/artifact_profiles.json` with a class (`strict-valid`, `non-strict-only`, or `legacy-compat`).

1. **Prefer `strict-valid` entries** when teaching or generating new AINL. Those paths are checked with `ainl validate <path> --strict` in tests. The full list is in **`tooling/artifact_profiles.json`** → **`examples`** → **`strict-valid`**.
2. **Ground-truth language and adapter rules** live in **`AGENTS.md`** at the repo root (HTTP adapter, `Do NOT`, queue syntax, etc.). Read it before inventing adapters (e.g. there is **no** `regex_find` in this repo).
3. **Classification and tables**: **`docs/EXAMPLE_SUPPORT_MATRIX.md`** explains canonical vs compatibility examples and points to the same JSON files.
4. **`demo/`** is excluded from this contract by design — demos may use experimental syntax; do not treat them as strict references (see **`AGENTS.md`** App Store section).

The machine-readable source of truth is:

- `tooling/artifact_profiles.json`
- `tooling/support_matrix.json`

Quick checks:

```bash
python scripts/validate_ainl.py examples/hello.ainl --strict
python scripts/validate_ainl.py examples/blog.lang
```

**Solana (`R solana.*`):** For `DERIVE_PDA`, pass `seeds_json` as **single-quoted JSON** (recommended), e.g. `'["market","ID"]'`, so inner `"` characters stay inside one token. You can also use one double-quoted string with escaped inner quotes — see `adapters/solana.py` module docstring. **v1.7.1+ onboarding (Solana):** `docs/solana_quickstart.md` (env vars, dry-run, emit flags, prediction-market patterns) and `examples/prediction_market_demo.ainl`.

Canonical strict-valid examples:

- `examples/hello.ainl` — canonical single-label compute + return (`R core.ADD` + `J`).
- `examples/http_get_minimal.ainl` — minimal **`R http.GET`** with URL-only positional args (no `params=` / `timeout=` on the `R` line); see `AGENTS.md` HTTP adapter section.
- `examples/web/basic_web_api.ainl` — canonical web endpoint flow (`S core web`, `E`, label body).
- `examples/crud_api.ainl` — canonical `Set` + `If` branch routing and explicit string literals.
- `examples/scraper/basic_scraper.ainl` — canonical scraper+cron intent (`Sc` + `Cr`) with runtime label flow.
- `examples/rag_pipeline.ainl` — canonical `Call ... ->out` return binding pattern (no `_call_result` compatibility style).
- `examples/retry_error_resilience.ainl` — canonical resilience flow (`R` + `Retry @nX` + `Err @nX` + explicit fallback label).
- `examples/if_call_workflow.ainl` — canonical branching + modular call composition (`If` + `Call ... ->out`).
- `examples/webhook_automation.ainl` — canonical webhook-style automation branch (`validate` -> `accepted/ignored`) plus external action (`R http.POST`).
- `examples/monitor_escalation.ainl` — canonical scheduled monitoring/escalation (`Cr` + condition branch -> `escalate/noop`).
- `examples/monitoring/solana-balance.ainl` — Solana `GET_BALANCE` + budget gate (`core.gt`); no runtime orchestration LLM; see `docs/solana_quickstart.md`.
- `examples/rag/cache-warmer.ainl` — `vector_memory` UPSERT/SEARCH with ops budget gate; run with `--enable-adapter vector_memory`.
- `examples/crm/simple-lead-router.ainl` — `crm_db.P` audit rows + score branch + route budget gate; run with `--enable-adapter crm_db` (`CRM_DB_PATH` optional).
- `examples/status_branching.ainl` — canonical status-branching example (`Set` + `If` -> `ok/alerted`).

Canonical language scope reference:

- `docs/AINL_CANONICAL_CORE.md`
- `docs/EXAMPLE_SUPPORT_MATRIX.md`

Recommended canonical learning order (small-model first):

1. `examples/hello.ainl` (compute + return)
2. `examples/http_get_minimal.ainl` (plain **`R http.GET`** — URL + optional `{}` headers + numeric timeout only; query string in URL)
3. `examples/crud_api.ainl` (Set + If branch)
4. `examples/rag_pipeline.ainl` (Call + bound return)
5. `examples/if_call_workflow.ainl` (If + Call workflow)
6. `examples/retry_error_resilience.ainl` (Retry + Err resilience)
7. `examples/web/basic_web_api.ainl` (endpoint + DB read)
8. `examples/webhook_automation.ainl` (validate/act/reject automation)
9. `examples/scraper/basic_scraper.ainl` (scraper + cron + persistence)
10. `examples/monitor_escalation.ainl` (scheduled monitor escalation)

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

## Adapter Examples

Comprehensive examples for all 42 AINL adapters. See **`ADAPTER_CATALOG.md`** for the complete adapter reference.

### Email Adapter (8 examples)

Full-featured email integration with IMAP/SMTP, HTML, attachments, threading, and drafts:

- `email_send_example.ainl` - Basic email sending
- `email_read_example.ainl` - Read inbox with filters
- `email_autoresponder.ainl` - Auto-responder pattern
- `email_reply_example.ainl` - Reply with threading (In-Reply-To headers)
- `email_draft_example.ainl` - Draft creation and management
- `email_html_example.ainl` - HTML email with plain text fallback
- `email_attachment_example.ainl` - Send files as attachments
- `EMAIL_ADAPTER_README.md` - Complete email adapter documentation

**Features:** ✅ HTML email, ✅ Attachments, ✅ Threading, ✅ Drafts, ✅ Search

### AI & Semantic Adapters (4 examples)

- `embedding_memory_example.ainl` - Vector embeddings for RAG (UPSERT_REF, SEARCH)
- `code_context_example.ainl` - Tiered code chunking (INDEX, QUERY_CONTEXT)
- `langchain_tool_example.ainl` - LangChain tool integration
- `llm_example.ainl` - LLM generation and chat (OpenAI, Anthropic)

### API & Integration (2 examples)

- `github_example.ainl` - GitHub API (repos, issues, PRs)
- `api_example.ainl` - Generic REST API wrapper (GET, POST, PUT, DELETE)

### Configuration

Most adapter examples require environment variables:

```bash
# Email
export EMAIL_USERNAME=your.email@gmail.com
export EMAIL_PASSWORD=app_specific_password

# LLM
export AINL_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# GitHub
export GITHUB_TOKEN=ghp_...

# Adapter Security
export AINL_ALLOW_IR_DECLARED_ADAPTERS=1
```

See individual example headers for specific requirements.

### Quick Start

```bash
# Validate an example
ainl validate examples/email_send_example.ainl --strict

# Run an example (may have side effects!)
ainl run examples/email_send_example.ainl
```

For the complete list of all 42 adapters with targets, configuration, and usage patterns, see **`ADAPTER_CATALOG.md`**.
