# AGTP (Agent Transfer Protocol) — options for AINL practitioners

**Problem:** AGTP is **not** “one URL + `GET`/`POST` + optional HTTP 402” in the same way as x402/MPP. Treating it as if it were plain `https://` traffic will mislead authors. Today, **pure `.ainl` + `R http.*` alone** is only realistic if an operator puts an **HTTP façade** in front of AGTP, or you add **non-graph glue** (host tool, MCP, `shell_exec`, or a future **dedicated adapter**).

This page lists **what you can do about that**, in order of **engineering leverage vs commitment**.

---

## 0) Grounding links (read before you design)

- IETF draft hub (revision moves): <https://datatracker.ietf.org/doc/draft-hood-independent-agtp/>
- Related methods / commerce-oriented drafts (check current filenames): see datatracker for `draft-hood-agtp-*`

**Reality check:** Internet-Drafts change. Any gateway or adapter you ship should **pin a draft revision** in config and plan for **wire upgrades**.

---

## Option A — **HTTP gateway** (recommended near-term for “graphs only”)

**Idea:** Run a small **trusted service** that speaks **native AGTP** on one side and exposes a **stable REST (or minimal JSON-RPC) API** on the other. AINL graphs use only `R http.*` against `https://gateway.internal/...` with normal `allow_hosts`.

**What to specify at the gateway boundary (contract sketch):**

| Concern | Gateway responsibility | AINL graph responsibility |
|--------|-------------------------|---------------------------|
| Identity / Agent-ID / scopes | Validate, map to internal AGTP identities | Pass opaque tokens **via frame** (never hard-code secrets in `.ainl`) |
| Framing / TLS / replay | Full AGTP semantics | None |
| Business verbs (e.g. PURCHASE, QUOTE) | Translate REST JSON ↔ AGTP methods | `R http.POST` JSON body built from **frame variables** |
| Errors | Map AGTP failures to HTTP 4xx/5xx + JSON body | Branch on `http` envelope `status` / `body` |

**Pros:** No new AINL opcode surface; reuse `http` allowlists, timeouts, observability you already have.  
**Cons:** You must **build and operate** the gateway; it is a **trust pivot** (compromise = full AGTP power).

---

## Option B — **Host MCP tool** or **daemon RPC** (recommended for ArmaraOS / OpenFang)

**Idea:** Expose `agtp_call` (or similar) as a **tool** the agent loop invokes; implementation uses whatever AGTP library your host language has.

**Pros:** Natural place for **long-lived connections**, retries, and vendor SDK churn **outside** the AINL compiler/runtime.  
**Cons:** Graphs are no longer “AINL-only”; they depend on **host capabilities** (same as wallets for x402).

**Where it lives:** product repo (e.g. **ArmaraOS** `tool_runner.rs` + config), not necessarily `AI_Native_Lang`.

---

## Option C — **Dedicated `agtp` runtime adapter** in AINL (heavy, only when justified)

**Idea:** Register `RuntimeAdapter` `agtp` with verbs like `agtp.QUERY`, `agtp.PURCHASE`, … implemented in Python against a pinned draft.

**Gate before you start (all should be true):**

1. **Stable wire profile** you are willing to support for a release cycle (pin draft + test vectors).
2. **Security model** agreed: SSRF rules, identity storage, max bytes, logging redaction (no raw purchase proofs in traces).
3. **3+ internal use cases** that are painful through a gateway (otherwise Option A wins).
4. **Test strategy**: mock server or recorded sessions in `tests/`.

**Where code would go:** `runtime/adapters/agtp.py` (+ `docs/integrations/AGTP_ADAPTER.md`, `ADAPTER_REGISTRY.json`, CLI `--enable-adapter agtp`, MCP runner wiring, strict contract tests).

**Cons:** Ongoing maintenance as drafts evolve; risk of **half-implemented** AGTP that confuses users.

---

## Option D — **`shell_exec` bridge** (pragmatic hack, operator-beware)

**Idea:** Ship a CLI/SDK wrapper (`agtp-cli …`) and call it from graphs where your host enables `shell_exec`.

**Pros:** Fastest path when an **official CLI** exists and you trust the machine.  
**Cons:** Weakest security story; hardest to reason about in multi-tenant or chat-driven deployments.

---

## What the AINL **core** repo should do next (actionable)

1. **Keep AGTP out of `http_machine_payments.py`** — that module is for **HTTP-402 payment headers**, not AGTP framing.
2. **Prefer documenting Option A** in customer deployments until Option C’s gates are met.
3. If the project commits to **Option C**, open a **tracking issue** with: pinned draft, verb list, threat model, and “gateway remains supported for users who do not enable `agtp`.”

For **readiness / backlog cross-links**, see `AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md` (item **G4**).
