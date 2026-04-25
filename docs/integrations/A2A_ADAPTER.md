# A2A adapter — security, wire contract, and operations

The `a2a` runtime adapter calls **ArmaraOS-shaped** A2A endpoints: Agent Card at `GET {base}/.well-known/agent.json` and JSON-RPC 2.0 `tasks/send` and `tasks/get` on the A2A HTTP endpoint. Implementation: [`runtime/adapters/a2a.py`](../../runtime/adapters/a2a.py).

## Wire contract version (compatibility)

| Item | Value |
|------|--------|
| **AINL A2A profile** | `1.0` (documented with this file) |
| **Reference** | [`A2aClient`](https://github.com/sbhooley/armaraos/blob/main/crates/openfang-runtime/src/a2a.rs) in ArmaraOS (JSON-RPC `tasks/send`, `tasks/get`; agent card fields `camelCase`) |
| **JSON-RPC** | `2.0`; methods `tasks/send`, `tasks/get` |
| **Session** | `params.sessionId` optional on `tasks/send` (same as Rust client) |

Peers that use a different A2A binding may need adapter updates. Track breaking upstream changes in release notes.

---

## 1) Threat model and safe defaults (app developers & operators)

**Assumption:** Any URL passed into `R a2a.*` from **user chat**, **untrusted files**, or **LLM output** is **untrusted** unless you validate it out-of-band. The adapter is a **convenience** for vetted programs and configured hosts, not a substitute for a trusted gateway in multi-tenant or user-facing products.

| Default / recommendation | Why |
|----------------------------|-----|
| **Prefer a non-empty `allow_hosts` (or `AINL_A2A_ALLOW_HOSTS`) in production** | Limits outbound DNS/HTTP to known agent hosts. An **empty** allowlist still allows *public* hostnames (only literal loopback/private are blocked when `allow_insecure_local` is off). Wider than many deployments want. |
| **`allow_insecure_local` off in production** | Prevents direct use of `127.0.0.1`, `localhost`, and private/link-local **literals** without an explicit opt-in. |
| **`strict_ssrf` (DNS check) for hostnames** | Resolves the hostname; if any resolved address is loopback/private/link-local, the call fails unless `allow_insecure_local` is on. Reduces some **hostname → private IP** SSRF and DNS-rebinding style issues. **Not a full substitute** for a network firewall or a dedicated SSRF filter (see limitations). |
| **Redirects off by default** | HTTP 3xx are **not** followed unless `follow_redirects` is enabled. When enabled, **each** redirect target is re-validated with the same rules. |

**Environment (lazy registration, e.g. `ainl serve`):**

- `AINL_A2A_ALLOW_HOSTS` — comma-separated hostnames/IPs
- `AINL_A2A_ALLOW_INSECURE_LOCAL` — `1` / `true` to allow private/loopback literals and, with strict, resolved private addresses
- `AINL_A2A_STRICT_SSRF` — `1` / `true` to enable DNS resolution checks
- `AINL_A2A_FOLLOW_REDIRECTS` — `1` / `true` to follow 3xx (re-checked per hop)
- `AINL_A2A_TIMEOUT_S`, `AINL_A2A_MAX_BYTES`

**CLI:** `ainl run … --enable-adapter a2a` with `--a2a-allow-host`, `--a2a-allow-insecure-local`, `--a2a-strict-ssrf`, `--a2a-follow-redirects` (see `ainl run --help`).

**Runner / `ainl_run`:** `adapters.enable: ["a2a"]` and `adapters.a2a: { "allow_hosts": ["…"], "allow_insecure_local": false, "strict_ssrf": true, "follow_redirects": false, … }`.

---

## 2) Agent / MCP hosts (integrators)

- **`ainl_run`:** Pass `adapters` in the tool payload; include `a2a` in `adapters.enable` and configure `adapters.a2a` (see [§1](#1-threat-model-and-safe-defaults-app-developers--operators)).
- **MCP process env:** The same `AINL_A2A_*` variables apply if the host injects them into the MCP server process.
- **Dashboard / ArmaraOS:** The ArmaraOS kernel uses its own Rust A2A path; the Python `a2a` adapter is for AINL-on-PyPI, CLI, and other runtimes. Cross-call behavior is “same wire,” not a second protocol.

Do **not** let end-users paste raw URLs into tools without allowlists in untrusted deployments.

---

## 3) Security review checklist (auditors & reviewers)

**Implemented:**

- `http` / `https` only; other schemes rejected.
- Optional **hostname allowlist** (`allow_hosts`).
- Block **literal** loopback/private/link-local in URL host when `allow_insecure_local` is false.
- **Response size** cap.
- **TLS** via default SSL context (and `certifi` when available).
- **Optional** `strict_ssrf`: `getaddrinfo` and reject if any resolved address is non-public (unless `allow_insecure_local`).
- **No redirects by default**; optional `follow_redirects` with re-check per hop.

**Limitations (document explicitly):**

- **IDNA / Unicode hostnames** — not specially normalized; treat as best-effort same as `urlparse`.
- **TOCTOU / rebinding** — address checked at one point in time; a malicious resolver could still be a risk in pathological cases.
- **Empty `allow_hosts`** — still allows arbitrary **public** DNS names (unless strict resolution catches private resolves). Tighten with non-empty allowlists in sensitive environments.
- **mTLS, pinning, OAuth** — not part of the adapter; use a reverse proxy or a higher trust layer if required.

**Reporting vulnerabilities:** see [SECURITY.md](../../SECURITY.md) at the repository root.

---

## 4) Prompt injection and “agent safety” (LLM-driven setups)

- Treat model-chosen or user-supplied **URLs, hostnames, and task text** as **untrusted** unless a **policy layer** (allowlist, tool firewall, or human approval) enforces which peers may be called.
- **Never** rely on the model alone to decide whether a URL is “safe.”
- Prefer **static** allowlists in configuration over **fully dynamic** URLs in prompts for production.

---

## Hermes local `a2a.json`

When a Hermes-compatible host publishes **`HERMES_HOME/a2a.json`** (default **`~/.hermes/a2a.json`**) with `{"base_url":"http://127.0.0.1:<port>"}` (HTTP **origin** only) and optional **`send_binding`** (`auto` \| `armaraos_jsonrpc` \| `a2a_http`), AINL can call:

- **`R a2a.discover_hermes ->card`** — optional first arg: Hermes root directory string
- **`R a2a.send_hermes message [session] [timeout_s] [hermes_root] ->task`**

**`send_hermes`** tries **ArmaraOS JSON-RPC** `tasks/send` to **`AgentCard.url`** when same-origin with `base_url`, then **Linux Foundation HTTP** `POST …/message:send` (see `skills/hermes/a2a.example.json`). These targets relax literal loopback/private URL checks for URLs implied by that **operator-controlled** file for discovery and HTTP sends.

**Nous Hermes Agent** (`hermes-agent` on GitHub): A2A server mode is **not shipped yet** (open issue **#514**). Stock Hermes will not answer `a2a.json` until upstream implements A2A or you point `base_url` at a bridge. ArmaraOS built-ins: **`hermes_a2a_status`**, **`a2a_discover_hermes`**, **`a2a_send_hermes`**.

---

## Summary

| Audience | Use this doc for |
|----------|------------------|
| **Developers** | Safe defaults, env, CLI, threat model |
| **Integrators** | MCP/runner `adapters.a2a` and env |
| **Reviewers** | What is enforced, what is out of scope |
| **LLM / agent** | Don’t use user URLs as blind SSRF; allowlist peers |

The **wire contract** and **SSRF behavior** are versioned with the **A2A profile `1.0`** above; document breaking changes in the changelog when Armara or AINL behavior diverges.
