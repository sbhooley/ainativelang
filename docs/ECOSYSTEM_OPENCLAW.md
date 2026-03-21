# Ecosystem examples & OpenClaw-oriented imports

**Examples in `examples/ecosystem/` are kept fresh via weekly auto-sync from upstream Clawflows & Agency-Agents repos** (GitHub Actions: [`.github/workflows/sync-ecosystem.yml`](../.github/workflows/sync-ecosystem.yml), Monday 04:00 UTC, plus manual **workflow_dispatch**). The job runs `ainl import clawflows` / `ainl import agency-agents` and opens a PR when conversions under `examples/ecosystem/**` change.

## What lives here

- **Curated templates:** [`examples/ecosystem/README.md`](../examples/ecosystem/README.md) — `original.md`, `converted.ainl`, per-folder `README.md`.
- **CLI & flags:** root [`README.md`](../README.md) → *Ecosystem & OpenClaw integration* (`ainl import markdown`, `ainl import clawflows`, `ainl compile`, `--generate-soul`, etc.).
- **MCP (Claude Code / Cursor / Gemini CLI):** [`docs/INTEGRATION_STORY.md`](INTEGRATION_STORY.md) (*Import Clawflows & Agency-Agents via MCP*) and [`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](operations/EXTERNAL_ORCHESTRATION_GUIDE.md) §9.
- **Community PRs:** [`.github/PULL_REQUEST_TEMPLATE/`](../.github/PULL_REQUEST_TEMPLATE/) (workflow / agent submission templates).

Converted graphs often include **cron**, **sequential `Call` steps**, and optional **`memory` / `queue`** hooks for OpenClaw-style bridges (sync workflow uses `--no-openclaw-bridge` for portable samples; re-import locally without that flag when you want bridge ops).

## See also

- **Benchmarks & viable leverage context:** [`docs/benchmarks.md`](benchmarks.md), [`BENCHMARK.md`](../BENCHMARK.md)
