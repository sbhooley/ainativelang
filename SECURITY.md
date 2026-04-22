# Security

## Reporting a vulnerability

If you believe you have found a **security issue** in AI_Native_Lang (including the `a2a` adapter, runtime, compiler, or packaged tooling), please report it **privately** so we can address it before public disclosure.

**Preferred:** For **`github.com/sbhooley/ainativelang`**, open a **[private security advisory](https://github.com/sbhooley/ainativelang/security/advisories/new)** (repository **Security** tab → **Report a vulnerability**). Advantages: coordinated disclosure, private thread with maintainers, optional CVE / GitHub advisory once fixed. You need a **GitHub account**; the form accepts description, impact, and repro details.

**Include (when possible):**

- A short description of the issue and its impact
- Steps to reproduce or a proof-of-concept
- Affected version / commit, if known

**Please do not** file public issues for **undisclosed** security bugs until a fix and coordinated disclosure window exist.

## Security-sensitive areas

- **SSRF and outbound HTTP** — HTTP and A2A adapters perform outbound requests; use host allowlists and optional strict DNS checks. See [docs/integrations/A2A_ADAPTER.md](docs/integrations/A2A_ADAPTER.md) for the `a2a` adapter.
- **Untrusted code and prompts** — Treat LLM- or user-supplied URLs and graph inputs with the same care as in any other automation that can reach the network or filesystem.
- **Secrets** — Do not commit API keys, tokens, or private keys. Prefer environment variables and your platform’s secret stores.

## Supported versions

Security fixes are applied to maintained branches as described in project release policy. For production, run a **current** release and follow the changelog when upgrading.
