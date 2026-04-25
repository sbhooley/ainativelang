# Agentic protocols — practitioner readiness in AINL (today vs gaps)

This document answers: **can someone program AINL graphs today to use x402, MPP, AP2, ACP (commerce), and AGTP “sufficiently”**—and if not, **what is missing** (mapped backlog).

Operational details for HTTP 402 profiles live in **`HTTP_MACHINE_PAYMENTS.md`**. Placement rules live in the **“Where to put other protocols”** section there.

---

## Executive answer

**No — not uniformly, and not end-to-end inside the graph alone.**

- **x402 / MPP (HTTP 402 rails):** A practitioner can **observe challenges and attach proofs** using `http` + `payment_profile` + the `http_payment` frame key, **provided** something **outside** the graph mints signatures / credentials (host, MCP tool, `shell_exec` script, wallet). AINL does **not** ship wallets, facilitators, or chain SDKs.
- **AP2 / ACP (commerce):** A practitioner can **call documented HTTPS JSON endpoints** with `R http.POST` / `R http.GET` **if** they build request bodies and auth headers via the **frame** (no inline dict literals on `R` lines). There are **no first-class `R ap2.*` / `R acp.*` verbs**, no built-in request-signing helpers, and **no curated strict-valid examples** in-repo for these stacks yet (see gaps).
- **AGTP (native):** **Not** sufficiently supported from pure `http` unless the operator exposes an **HTTP gateway** that fronts AGTP. Otherwise this needs **host code** or a **future dedicated adapter**.

So: **all protocols are “reachable” in some architecture**, but **only x402/MPP get specialized HTTP-402 support** today; the rest rely on **generic HTTP + external signing/state**, which is **powerful but not turnkey**.

---

## Capability matrix (what “sufficiently” means in practice)

Legend:

- **Graph-only** — feasible with `core` + `http` (+ other already-registered adapters), no `shell_exec`, assuming URLs/hosts are allowlisted.
- **Frame-fed** — graph is fine if the **runner injects** secrets / pre-signed blobs / checkout JSON into `frame` (e.g. `http_payment`, bodies, bearer tokens).
- **Host script** — needs `shell_exec` or a non-AINL process (wallet, facilitator, Stripe signing SDK).
- **Not today** — missing adapter, transport, or in-repo examples.

| Protocol | Discover / parse server intent | Retry / prove payment | Full autonomous pay (no host crypto) | In-repo examples / CI strict-valid | Primary gap |
|----------|-------------------------------|------------------------|--------------------------------------|--------------------------------------|-------------|
| **x402** | **Yes** (`payment_profile` → structured `402`) | **Yes** if frame supplies `PAYMENT-SIGNATURE` / `http_payment` | **No** (signing off-graph) | **Partial** — generic HTTP examples exist; **no** dedicated x402 strict-valid recipe in `tooling/artifact_profiles.json` yet | Example graphs + optional thin signer bridge docs |
| **MPP** | **Yes** (WWW-Authenticate parse + `402` envelope) | **Yes** if frame supplies `Authorization: Payment …` pieces | **No** (method-specific settlement off-graph) | **Partial** — same as x402 | Same + MPP **MCP binding** not in `http` adapter |
| **AP2** | **Generic `http`** (JSON responses) | **Generic `http`** | **No** (intent / rails-specific) | **No** first-class | `docs/integrations/AP2.md` + minimal `examples/` + host frame contract |
| **ACP** (*Agentic Commerce*) | **Generic `http`** | **Generic `http`** | **No** (SPT + Stripe signing) | **No** first-class | `docs/integrations/ACP_AGENTIC_COMMERCE.md` + frame patterns for Bearer + signed POSTs |
| **AGTP** | **Only via HTTP gateway** | Same | **No** | **No** | Dedicated adapter **or** documented gateway + **honest “not native AGTP”** note |

---

## What a practitioner can do **today** (concrete checklist)

1. **Enable `http`** with a real **`allow_hosts`** allowlist (CLI, runner JSON, or MCP `adapters` payload).
2. Set **`payment_profile`** to `auto` / `x402` / `mpp` when talking to **402-native** paywalled HTTP APIs.
3. Put **JSON bodies, bearer tokens, and `http_payment` proofs** in the **`frame`** passed to `ainl run` / `ainl_run` (graphs reference variables; they do not embed wallet keys).
4. Use **`R a2a.*`** for **agent delegation** (separate from commerce checkout — see `A2A_ADAPTER.md`).
5. For anything harder (Stripe request signing, wallet ECDSA, facilitator polling): **call out** to **`shell_exec`** (if enabled in your host) or run a **sidecar** your operator trusts.

---

## Mapped gaps (backlog — ordered by leverage)

These are the **missing pieces** between “protocol exists in the industry” and “any practitioner can ship safely in AINL without reading Python.”

| ID | Gap | Affects | Suggested fix (repo) |
|----|-----|---------|----------------------|
| G1 | **No strict-valid worked examples** for x402 / MPP happy-path + frame-injected proof | x402, MPP | Add `examples/integrations/x402_paywalled_get.ainl` (or similar) + optional MPP twin; promote paths in `tooling/artifact_profiles.json` → `strict-valid` **only after** `ainl validate --strict` passes. |
| G2 | **No integration guide** for AP2 HTTP gateways (URLs, auth, typical JSON shapes) | AP2 | New `docs/integrations/AP2.md` + one minimal example using frame-held JSON + `R http.POST`. |
| G3 | **No integration guide** for Stripe **Agentic Commerce Protocol** (ACP) checkout | ACP commerce | New `docs/integrations/ACP_AGENTIC_COMMERCE.md` + document signing requirements explicitly (“host must sign”). |
| G4 | **AGTP not native in `http`** (needs gateway, host tool, or dedicated adapter) | AGTP | **Done (docs):** `docs/integrations/AGTP.md` — options A–D (HTTP gateway, MCP/daemon, `agtp` adapter when gated, `shell_exec`), IETF links, **core repo next steps**. Remaining: **product choice** (ship gateway vs ArmaraOS MCP tool vs AINL `agtp` adapter). |
| G5 | **No optional Python helper** for repeated HMAC / canonical string builders (Stripe, generic “sign this dict”) | AP2, ACP | Add `runtime/adapters/` helper module **only** when **3+** internal callsites exist; until then keep in host SDK. |
| G6 | **MPP MCP transport** not exposed to graphs | MPP | Host MCP server or new adapter `mcp_payment` — **out of scope** for `SimpleHttpAdapter` (see `HTTP_MACHINE_PAYMENTS.md`). |
| G7 | **Education**: one-page “**where secrets live**” (never in `.ainl` literals; always frame/host) | All | Short section in `AGENTS.md` or link here from HTTP doc intro. |

---

## Related files (ground truth)

- `runtime/adapters/http.py` — HTTP client + `payment_profile` / `http_payment`.
- `runtime/adapters/http_machine_payments.py` — x402 / MPP 402 header helpers.
- `docs/integrations/HTTP_MACHINE_PAYMENTS.md` — wire formats + repo placement table.
- `docs/integrations/A2A_ADAPTER.md` — delegation (not checkout).
- `docs/integrations/AGTP.md` — how to address AGTP without pretending it is plain `http`.
- `tooling/artifact_profiles.json` — which `examples/*` paths are **CI strict-valid** (do not assume every new example is on the list until added).

---

## Summary sentence you can quote

**AINL is sufficient today for HTTP-402-native rails (x402/MPP) at the “transport + envelope + header merge” layer; AP2/ACP are sufficient only at the “generic signed REST” layer if the host supplies crypto/signing; native AGTP is not productized in-repo yet—gateway or future adapter.**
