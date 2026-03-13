# Golden Examples & Resources for AINL

This directory contains curated materials to help small offline models learn and use AINL effectively for real-world automation.

## Compile profile

`examples/golden/*.ainl` are currently classified as **non-strict-only** in
`tooling/artifact_profiles.json`.

They are intentionally retained for backward-compatible runtime/generation
workflows and model training context, and should not be treated as strict-mode
canonical grammar references.

## Files

| File | Description |
|------|-------------|
| `01_web_server.ainl` | JSON API + static file server (port 8080). Shows routing, cache, fs, core utils. |
| `02_dashboard.ainl` | Auto-refresh dashboard with metrics endpoint. Shows caching, templating, admin stub. |
| `03_scraper.ainl` | Daily scraper with rate limiting and CSV output. Shows HTTP, pattern extraction, fs append. |
| `04_alerting_monitor.ainl` | Service health monitor with throttling. Shows `svc` adapter (OpenClaw extension, operator-only), dedup, queue, WASM integration. |
| `05_file_processor.ainl` | Batch log processing and stats aggregation. Shows fs listing, metadata, state tracking. |
| `CURRICULUM.md` | Progressive learning path for small models: phases 1–6 with deliverables. |
| `ADAPTER_REGISTRY.json` | Machine-readable catalog of all adapters (core, http, sqlite, fs, email, calendar, social, svc, db, cache, queue, wasm). |
| `OPENCLAW_ADAPTER_SPEC.md` | Plan to generalize OpenClaw adapter beyond the monitor for broader agent workflows. |
| `OPENCLAW_KB.md` | Quick reference for using OpenClaw adapters from AINL (email, calendar, CRM, services, notifications). |
| `POLICY_VALIDATOR_SPEC.md` | Spec for a pre-execution validator that enforces allowlists, sandboxing, and resource limits. |
| `FUZZY_SUGGESTIONS.md` | Table of common model hallucinations and how the compiler should auto-correct them tolerantly. |
| `TRAINING_DATA_OUTLINE.json` | Structured plan for ~1300 training examples across buckets (core, adapters, errors, full programs). |

## How to Use

- **For fine-tuning**: Generate training data according to `TRAINING_DATA_OUTLINE.json`. Include positive and negative examples.
- **For prompting**: Provide the golden examples as few-shot context; they are commented and under 300 lines each.
- **For tooling**: Implement the policy validator and fuzzy corrections in `compiler_v2.py` to improve small-model success rate.
- **For integration**: Reference `ADAPTER_REGISTRY.json` in your model's system prompt to make adapter usage discoverable.

## Next Steps

1. Choose a small model (e.g., Phi-3 mini, Gemma 2B, or step-3.5-flash).
2. Generate the actual training set from the outline (I can help draft pairs).
3. Fine-tune or distill the model on the dataset.
4. Build a language server that exposes completions based on the adapter registry.
5. Iterate on the compiler's tolerant mode to capture and fix remaining error patterns.

These artifacts are designed to close the gap between a working compiler/runtime and a model that can reliably use it without being an AINL expert.
