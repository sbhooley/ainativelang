# HTTP profile: machine payments & agentic commerce protocols

**Index:** sibling docs in **`docs/integrations/README.md`**.

AINL keeps **one HTTP client** (`SimpleHttpAdapter` in `runtime/adapters/http.py`). **Native “payment profile” code** today targets **HTTP 402 + payment-shaped headers** (primarily **x402** and **MPP**). Everything else in the landscape below is either **ordinary `http` JSON/REST** (same adapter, no special 402 parser) or a **different transport** (call out explicitly so we do not pretend it is `R http.*` magic).

**Honest “can I ship this today?” matrix + backlog:** [`AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md`](./AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md) (end-to-end sufficiency, frame vs host crypto, AGTP gaps).

## Naming collisions (read once)

| Acronym | In *this* doc / commerce context | Confusable with |
|---------|-----------------------------------|------------------|
| **ACP** | **Agentic Commerce Protocol** (checkout / Shared Payment Token flows; Stripe + ecosystem). See Stripe’s “Agentic Commerce Protocol”. | **IBM ACP** (*Agent Communication Protocol* — agent-to-agent **messaging**, converging with **A2A**). Different problem. IBM / LF docs: <https://agentcommunicationprotocol.dev/> |

When someone says “ACP for agents,” confirm whether they mean **checkout commerce** or **agent messaging**.

---

## Protocol landscape (ecosystem map)

The table below is a **practical integration map** for agent builders. **Launch / “Launched”** months are **ecosystem-oriented** (press, vendor docs, draft dates); verify against each project’s canonical site before you hard-code marketing claims.

| Protocol | Focus layer | Crypto support | Fiat / cards | Best for | Typical timeline (ecosystem) | **AINL `http` surface** |
|----------|-------------|----------------|--------------|----------|------------------------------|-------------------------|
| **x402** | Settlement (**HTTP 402** + `PAYMENT-*` headers) | Stablecoins (e.g. USDC; multi-chain in vendor docs) | Generally **no** direct card rails in the core HTTP header flow | Agent-to-agent / agent-to-API **micropaywalled** HTTP resources | ≈ **2025+** (HTTP-native agent payments wave) | **Native profile**: `payment_profile` `auto`/`x402` + `http_payment` merge for `PAYMENT-SIGNATURE`. |
| **MPP** | **Sessions + settlement** (HTTP 402 + `WWW-Authenticate: Payment`; MCP binding exists) | Stablecoins (e.g. **Tempo** method in MPP docs) | **Yes** — e.g. **Stripe** method in MPP payment-methods docs | **Streaming / metered** use cases + HTTP-native challenges | ≈ **2026+** (check `mpp.dev` changelog) | **Native profile**: `payment_profile` `auto`/`mpp` + `http_payment` merge for `Authorization: Payment …`. |
| **AP2** | **Authorization + payment intent** objects (agent commerce); settlement can plug **x402** and other rails | Via **extensions** / rails (x402 called out in ecosystem writeups) | **Yes** when the chosen rail / facilitator supports it | **Delegated user payments** (human principal → agent budget → settlement) | **2026+** (see project FAQ / concepts) | **Mostly generic `http`**: POST/GET JSON to AP2-capable services + parse JSON in graph / host tool. Optional future: small **profile helpers** if a stable **HTTP 402 header dialect** becomes universal for AP2. Primary pointers: <https://ap2-protocol.org/faq/> · concepts mirror: <https://agentpaymentsprotocol.info/docs/concepts/> |
| **ACP** (*Agentic Commerce Protocol*) | **Checkout** (REST session lifecycle; Shared Payment Token) | Not the core story (tokenized / delegated payment) | **Yes** (Stripe rails, merchant integrations) | **Merchant e-commerce** agents (cart, shipping, completion) | **2025+** (Stripe public docs / RFCs in GitHub org) | **Generic `http`**: `POST`/`GET` checkout endpoints + `Authorization: Bearer …`, request signing headers per Stripe spec — **not** the same wire as x402 `PAYMENT-*` on 402. Spec: <https://docs.stripe.com/agentic-commerce/protocol/specification> · RFC-style text: <https://github.com/agentic-commerce-protocol/agentic-commerce-protocol> |
| **AGTP** | **Agent workflows** (intent methods, trust / merchant headers; commerce-related methods in drafts) | **External** (depends on method + counterparty) | **External** | **Trust-tracked purchases**, agent-native verbs beyond raw REST CRUD | **2026+** (IETF Internet-Drafts) | **Not HTTP-402-native**. **What to do:** see **[`AGTP.md`](./AGTP.md)** (HTTP gateway, MCP/daemon, future `agtp` adapter, or `shell_exec`). Draft hub: <https://datatracker.ietf.org/doc/draft-hood-independent-agtp/04/> |

### How to read the “AINL `http` surface” column

1. **Native 402 profiles** — implemented helpers in `runtime/adapters/http_machine_payments.py` + `SimpleHttpAdapter` (`payment_profile`, structured `402`, `http_payment` merges).
2. **Generic REST** — still **`R http.GET` / `R http.POST`** with JSON bodies from the **frame** (remember: **no inline dict literals** on `R` lines; build dicts in-frame). This is how **ACP checkout** and many **AP2** HTTP gateways will look in AINL today.
3. **Non-HTTP transports** — **MPP MCP binding**, **pure AGTP**, etc. belong in **MCP clients**, **host runtimes**, or future adapters — not inside `SimpleHttpAdapter` unless we explicitly add them.

---

## Native spec pointers (402 rails)

- **x402** (HTTP 402 + `PAYMENT-*` headers): <https://docs.x402.org/core-concepts/http-402>
- **MPP** (HTTP 402 + `WWW-Authenticate: Payment`): <https://mpp.dev/protocol/>

## Enabling challenge parsing (`payment_profile`)

| `payment_profile` | Behavior on HTTP `402` |
|-------------------|-------------------------|
| `none` (default) | Same as before: `402` is treated like other `4xx` and raises `AdapterError`. |
| `auto` | Detect **x402** vs **MPP** from response headers and return a structured `payment_required` envelope (see below). |
| `x402` | Force x402-oriented challenge summarization. |
| `mpp` | Force MPP-oriented challenge summarization. |

### CLI (`ainl run`)

```bash
ainl run graph.ainl --enable-adapter http --http-allow-host example.com --http-payment-profile auto
```

Flags:

- `--http-payment-profile none|auto|mpp|x402`
- `--http-max-payment-rounds N` (reserved for future multi-hop / facilitator chaining; stored on the adapter)

### Runner service / MCP `ainl_run`

Under `adapters.http`:

```json
{
  "enable": ["http"],
  "http": {
    "allow_hosts": ["api.example.com"],
    "timeout_s": 15,
    "payment_profile": "auto",
    "max_payment_rounds": 2
  }
}
```

### OpenClaw monitor registry (`openclaw_monitor_registry`)

Environment variables (optional):

- `AINL_HTTP_PAYMENT_PROFILE` — `none` (default), `auto`, `mpp`, or `x402`
- `AINL_HTTP_MAX_PAYMENT_ROUNDS` — integer, default `2`

## Structured `402` envelope

When `payment_profile` is not `none` and the server answers `402`, the adapter returns a dict (it does **not** raise) with at least:

- `ok: false`
- `status` / `status_code`: `402`
- `error`: `"payment_required"`
- `headers`: lowercase header map from the response
- `body`: parsed JSON/text when possible
- `payment`: metadata block including `profile`, `kind: "http_402"`, plus dialect-specific fields:
  - **x402**: `payment_required_header` and best-effort decoded `payment_required` (base64 JSON)
  - **MPP**: parsed `www_authenticate` parameters from `WWW-Authenticate: Payment …`

**Security:** Treat `http_payment` values as **secrets**. Do not log them, echo them into chat transcripts, or persist them in plaintext analytics.

## Retrying with proof headers (`http_payment` frame key)

The runtime merges optional payment headers from the **frame** (same dict as `ainl run` / `ainl_run` `frame`) under the key **`http_payment`**. Supported shapes:

1. **Generic extra headers**

```json
{
  "http_payment": {
    "headers": {
      "PAYMENT-SIGNATURE": "<base64 payload from your wallet/facilitator>",
      "Authorization": "Payment <credential>"
    }
  }
}
```

2. **x402 shorthand**

```json
{
  "http_payment": {
    "x402": { "payment_signature": "<value for PAYMENT-SIGNATURE>" }
  }
}
```

3. **MPP shorthand**

```json
{
  "http_payment": {
    "mpp": { "authorization_payment": "<base64url credential token per MPP docs>" }
  }
}
```

Or pass a full header value:

```json
{
  "http_payment": {
    "mpp": { "authorization": "Payment eyJ..." }
  }
}
```

Typical graph pattern:

1. `R http.GET url ->res` with `payment_profile: auto` → inspect `res.payment` / `res.error == "payment_required"`.
2. Use an external signer/facilitator (not built into AINL) to mint the proof.
3. Second `ainl run` step (or a new label) with `http_payment` populated → `R http.GET url ->res2`.

AINL **does not** ship wallet private keys, chain clients, or facilitator SDKs; it only performs **HTTP I/O + safe header merging + structured 402 reporting**.

## Successful responses with settlement headers

When `payment_profile` is enabled and the server returns `200`:

- If `PAYMENT-RESPONSE` is present, the adapter adds `payment: { "profile": "x402", "payment_response_header": "..." }`.
- If `Payment-Receipt` / `payment-receipt` is present, the adapter adds `payment: { "profile": "mpp", "payment_receipt_header": "..." }`.

## Where to put other protocols (repository map)

Use this table so new work lands in the **right layer** (docs vs examples vs runtime vs host).

| Protocol / style | Primary wire | **Put documentation** | **Put runnable templates** | **Put Python/runtime code** |
|------------------|--------------|-------------------------|-----------------------------|------------------------------|
| **x402**, **MPP** (HTTP 402 + payment headers) | HTTP | This file (`HTTP_MACHINE_PAYMENTS.md`) + `AGENTS.md` HTTP bullet | `examples/` graphs that only need `http` + `http_payment` frame keys | `runtime/adapters/http.py`, `runtime/adapters/http_machine_payments.py`, tests under `tests/test_http_*` |
| **ACP** (*Agentic Commerce Protocol* checkout), **AP2** HTTP JSON APIs | HTTPS REST + JSON bodies | **New** `docs/integrations/ACP_AGENTIC_COMMERCE.md` / `docs/integrations/AP2.md` (one spec per file keeps search/grep sane) | **New** `examples/...` (strict-valid list in `tooling/artifact_profiles.json` if CI should enforce) | Stay on **`http`** until you have **3+** repeated signing/header flows; then extract **`runtime/adapters/<name>_http.py`** (thin wrapper that builds `Request` + headers) **or** a dedicated **`RuntimeAdapter`** only if the IR needs a new opcode family (`R acp.*`) |
| **AGTP** (native agent transfer), **MPP MCP-only** paths | Not “plain browser HTTP” for the whole lifecycle | `docs/integrations/AGTP.md` (link IETF drafts + deployment notes) | Usually **not** `.ainl`-only unless you have an HTTP gateway; prefer host snippets | **Outside** `SimpleHttpAdapter`: e.g. **MCP tool** in the host, **`armaraos`** bridge, or a **future** `runtime/adapters/agtp.py` / MCP transport adapter — *not* mixed into `http_machine_payments.py` |
| **IBM ACP** (agent messaging) / **A2A** | HTTP JSON-RPC / REST peer | `docs/integrations/A2A_ADAPTER.md` (already) + separate note if IBM REST diverges | Examples that call `R a2a.*` or documented `http` to a gateway | `runtime/adapters/a2a.py` (messaging), **not** `payment_profile` |

**Rule of thumb:** if the protocol’s “happy path” is **`POST` JSON to `/v1/...` with Bearer + signatures**, it belongs in **integration docs + examples + generic `http`**. If the happy path is **`402` + proof headers on the *same* resource URL**, it belongs in **`http_machine_payments.py`**. If the happy path is **a new socket framing or MCP-only**, it belongs in a **host adapter** or a **new runtime adapter name**, not inside the HTTP payment header module.

## Adding a new protocol later

If the industry ships another “HTTP 402 + structured headers” dialect:

1. Extend `runtime/adapters/http_machine_payments.py` with detection + summarization helpers.
2. Wire detection into `resolve_payment_profile` / `build_payment_challenge_envelope`.
3. Document the new `http_payment` merge shape in this file.

If a protocol is **primarily REST checkout** (ACP) or **JSON intent APIs** (AP2 HTTP gateways), follow the **repository map** above: new `docs/integrations/*.md` + `examples/` first; only then consider a thin Python helper or a new `RuntimeAdapter` if graphs truly need `R <brand>.*`.

Non-HTTP transports (for example **MPP’s MCP binding**) are **out of scope** for `SimpleHttpAdapter`; those belong in MCP client tooling or a dedicated adapter, not `R http.*`.
