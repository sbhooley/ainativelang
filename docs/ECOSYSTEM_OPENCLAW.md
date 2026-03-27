# Ecosystem examples & OpenClaw- / ZeroClaw- / Hermes-oriented imports

**Examples in `examples/ecosystem/` are kept fresh via weekly auto-sync from upstream Clawflows & Agency-Agents repos** (GitHub Actions: [`.github/workflows/sync-ecosystem.yml`](../.github/workflows/sync-ecosystem.yml), Monday 04:00 UTC, plus manual **workflow_dispatch**). The job runs `ainl import clawflows` / `ainl import agency-agents` and opens a PR when conversions under `examples/ecosystem/**` change.

## Recommended production stack: AINL graphs + AVM or general agent sandboxes

AINL provides deterministic graphs and declared capabilities; pair with AVM or other sandbox runtimes (microVM/container/agent-sandbox) for isolation. Integration remains additive and optional via `execution_requirements`, `ainl generate-sandbox-config`, and unified sandbox shim hooks.

### Sync workflow & upstream ownership

We **do not** need admin access to [Clawflows](https://github.com/nikilster/clawflows) or [Agency-Agents](https://github.com/msitarzewski/agency-agents). The job only **downloads public raw Markdown** (same URLs as the CLI importer) and commits changes **in this repository**.

Some GitHub orgs **block the default `GITHUB_TOKEN` from creating pull requests**. If the sync job fails with *“GitHub Actions is not permitted to create or approve pull requests”*:

1. Create a **fine-grained** or **classic** PAT for a bot or maintainer account with **`contents: read/write`** and **`pull requests: read/write`** on **this repo only** (classic: `repo` scope for a private repo, or public-repo `public_repo` if applicable).
2. Add it as an Actions secret named **`GH_PAT`** (Settings → Secrets and variables → Actions).
3. Re-run the workflow — [`.github/workflows/sync-ecosystem.yml`](../.github/workflows/sync-ecosystem.yml) uses `secrets.GH_PAT` when set, otherwise `github.token`, for both **`peter-evans/create-pull-request`** and the **`gh label create`** step.

Never commit the PAT; rotate it if leaked.

## What lives here

- **Curated templates:** [`examples/ecosystem/README.md`](../examples/ecosystem/README.md) — `original.md`, `converted.ainl`, per-folder `README.md`.
- **CLI & flags:** root [`README.md`](../README.md) → *Ecosystem & agent hosts* (`ainl import markdown`, `ainl import clawflows`, `ainl compile`, `--generate-soul`, etc.). When parsing fails, the importer may emit a **minimal_emit fallback stub** so graphs still compile for review.
- **MCP (Claude Code / Cursor / Gemini CLI / OpenClaw / ZeroClaw / Hermes):** [`docs/INTEGRATION_STORY.md`](INTEGRATION_STORY.md) (*Import Clawflows & Agency-Agents via MCP*) and [`docs/operations/EXTERNAL_ORCHESTRATION_GUIDE.md`](operations/EXTERNAL_ORCHESTRATION_GUIDE.md) §9 — tools **`ainl_list_ecosystem`**, **`ainl_import_clawflow`**, **`ainl_import_agency_agent`**, **`ainl_import_markdown`**. **OpenClaw skill + bootstrap:** [`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md) · **ZeroClaw skill:** [`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md) · **Hermes:** [`docs/HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md) · **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**.
- **Community PRs:** [`.github/PULL_REQUEST_TEMPLATE/`](../.github/PULL_REQUEST_TEMPLATE/) (workflow / agent submission templates).

Converted graphs often include **cron**, **sequential `Call` steps**, and optional **`memory` / `queue`** hooks for **OpenClaw**-style bridges (sync workflow uses `--no-openclaw-bridge` for portable samples; re-import locally without that flag when you want bridge ops). **OpenClaw** users wire the same importer and MCP tools via **[`skills/openclaw/`](../skills/openclaw/)** and **`ainl install-openclaw`** (`~/.openclaw/openclaw.json`, **`ainl-mcp`**); see **[`OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)**. **ZeroClaw** users consume the same surface via the **[ZeroClaw skill](ZEROCLAW_INTEGRATION.md)** and **`ainl install-zeroclaw`** (`~/.zeroclaw/mcp.json`, **`ainl-mcp`**). **Hermes Agent** users compile to skill bundles and run via **`ainl_run`**: **[`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md)**, **[`skills/hermes/`](../skills/hermes/)**, **`ainl install-mcp --host hermes`**, upstream **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**.

## See also

- **OpenClaw skill & bootstrap:** [`docs/OPENCLAW_INTEGRATION.md`](OPENCLAW_INTEGRATION.md)
- **ZeroClaw skill & bootstrap:** [`docs/ZEROCLAW_INTEGRATION.md`](ZEROCLAW_INTEGRATION.md)
- **Hermes Agent & bootstrap:** [`docs/HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md) · **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**
- **Benchmarks & viable leverage context:** [`docs/benchmarks.md`](benchmarks.md), [`BENCHMARK.md`](../BENCHMARK.md)
