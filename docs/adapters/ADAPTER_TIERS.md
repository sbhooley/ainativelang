# Adapter Tiers — Core and Extended

AINL ships with a two-tier adapter catalog. **Both tiers are fully supported.** This document explains the model, lists every adapter by tier, and describes the import paths and downstream compatibility commitments.

There is **no deprecation, no removal, and no breaking change** associated with the tier model. Every adapter that worked before tiering continues to work via the same import paths and the same `R adapter.verb` syntax in AINL programs.

---

## The model in one paragraph

**Core** adapters are the universal orchestration primitives — language built-ins, HTTP/FS/SQLite/memory/cache/queue, the LLM family, the major databases, audit and tool-registry infrastructure, and repo intelligence. They have dedicated docs, test coverage, strict-valid examples in CI, and are the recommended choice for production deployments.

**Extended** adapters cover narrower domains (web3, social platforms, browser automation, niche interop bridges) or are newer additions still growing test coverage. They are fully supported alongside Core and ship in the same package — they just sit under `adapters/extended/` for namespace clarity rather than implying second-class support.

The split exists so production-grade claims about AINL can be evaluated against a tight, well-defended Core surface, while the broader connector ecosystem remains visible and supported for the use cases that need it. This is the same structure as Postgres (core + extensions), VS Code (built-in + extensions), and AWS (GA + niche services).

---

## Full Core / Extended list

Tier metadata is authoritative in [`ADAPTER_REGISTRY.json`](../../ADAPTER_REGISTRY.json) (`adapters.<name>.tier`). To regenerate this list or change tier assignments, edit `scripts/update_adapter_registry_tiers.py` (`TIER_MAP`) and re-run it.

### Core (29 adapters)

| Adapter | Category |
|---|---|
| `core` | Language primitive (arithmetic, strings, dates) |
| `http` | HTTP client |
| `http_machine_payments` | x402 / MPP / AP2 / ACP machine-payment dialects |
| `fs` | Filesystem |
| `memory` | Key-value memory + procedural patterns |
| `cache` | Cache layer |
| `queue` | Notification queue |
| `sqlite` | SQLite |
| `wasm` | WebAssembly execution |
| `a2a` | Agent-to-Agent protocol |
| `tools` | Tool execution layer |
| `audit_trail` | Hash-chained audit log (regulatory primitive) |
| `ainl_graph_memory` | Graph memory substrate (ArmaraOS bridge) |
| `vector_memory` | Vector memory family |
| `embedding_memory` | Embedding memory family |
| `tool_registry` | ToolPatch / Tool Registry (armaraos integration) |
| `llm` | LLM adapter family (openrouter, anthropic, cohere, ollama, offline) |
| `bridge` | OpenClaw bridge |
| `db` | Generic DB facade |
| `api` | Generic API facade |
| `postgres` | PostgreSQL |
| `mysql` | MySQL |
| `redis` | Redis |
| `dynamodb` | DynamoDB |
| `supabase` | Supabase |
| `airtable` | Airtable |
| `code_context` | Repo indexing / impact analysis |
| `ptc_runner` | Per-task-class runner |
| `svc` | Service control (status, restart, health) |
| `txn` | Transaction primitive |

### Extended (16 adapters)

| Adapter | Category |
|---|---|
| `solana` | Blockchain — Solana RPC, PDAs, Pyth, INVOKE/TRANSFER_SPL |
| `tiktok` | Social — TikTok CRM read adapter (see [layered config](#extended-adapter-config-pattern)) |
| `social` | Social — generic social platform layer |
| `calendar` | Calendar adapter |
| `email` | Email adapter |
| `github` | GitHub adapter |
| `crm` | CRM operations |
| `web` | Web search / fetch / scrape |
| `langchain_tool` | Interop bridge — LangChain tools |
| `llm_query` | Specialized LLM query helper |
| `ext` | Generic extension hook |
| `fanout` | Multicast helper |
| `pggraph` | PostgreSQL graph hybrid (Evokoa pgGraph) |
| `auth` | Authentication primitive (abstract base) |
| `agent` | Agent backend scaffolding (abstract base) |
| `extras` | Generic helper utilities |

---

## Import paths

Both import paths are **permanent, supported, and produce no warnings**. Use whichever you prefer:

```python
from adapters.solana import SolanaAdapter            # stable alias
from adapters.extended.solana import SolanaAdapter   # canonical path

from adapters.tiktok import TiktokAdapter, TiktokAdapterConfigError
from adapters.extended.tiktok import TiktokAdapter, TiktokAdapterConfigError
```

The string-name registry that AINL programs use is unchanged: `R solana.GET_BALANCE ...` and `R tiktok.recent ...` resolve through the same `AdapterRegistry` lookup as before.

The shims at `adapters/solana.py` and `adapters/tiktok.py` are thin re-exports — see those files for the one-screen contract.

---

## Extended adapter config pattern

Extended adapters that need external resources (e.g. `tiktok` needs a SQLite path) follow a layered configuration pattern:

1. **Explicit constructor argument** — `TiktokAdapter(db_path="...")`
2. **Environment variable** — `AINL_TIKTOK_DB=/path/to/db.sqlite` (also settable via profile in `tooling/ainl_profiles.json`)
3. **Legacy default** — back-compat path with a one-time `UserWarning` (silenced by setting an env var or passing the arg)
4. **Fail fast** — `TiktokAdapterConfigError` at construction time, not at first query, with an actionable message

This pattern is the recommended shape for any new Extended adapter that wires to host-specific resources.

---

## Downstream compatibility commitments

| Downstream | Compatibility |
|---|---|
| **ArmaraOS** (`sbhooley/armaraos`) | No impact. ArmaraOS resolves adapters by string name through the `AdapterRegistry` and via MCP, not by Python module path. Both runtime and CLI bridges continue to work without changes. |
| **ainl-inference-server** (`sbhooley/ainl-inference-server`) | No impact. Rust workspace; does not import Python adapter modules. |
| **ainl-cortex** (`sbhooley/ainl-cortex`) | No breaking change. Any `from adapters.<name> import ...` in `ainl-cortex` continues to work via the stable alias shims. Tier classification is metadata-only on the AINL side; `ainl-cortex` is unaffected. |
| **ainativelangweb** (`sbhooley/ainativelangweb`) | No impact (static Next.js site). |
| **OpenClaw integration scripts** | No impact. The live `R tiktok.*` runtime path is wired through `adapters.openclaw_integration.TiktokAdapter`, which is unchanged. |
| **Any external Python consumer** | No breaking change. Both `from adapters.X import ...` (stable alias) and `from adapters.extended.X import ...` (canonical) work identically. |

---

## Promotion policy

Adapters can move between tiers as the project matures. The checklist for **Extended → Core** promotion:

- Dedicated documentation page under `docs/adapters/`
- Contract or integration test coverage in `tests/`
- At least one strict-valid example under `examples/` referenced by `tooling/artifact_profiles.json` (strict-valid set)
- Production use story we are willing to defend publicly
- No outstanding hardcoded paths, secrets, or environment-specific defaults

The reverse direction (**Core → Extended**) requires a documented reason in `LONG_TERM_FIXES_TRACKER.md` and a release-note callout. The default expectation is that Core adapters stay Core.

A promotion is a JSON edit in `scripts/update_adapter_registry_tiers.py` + a `CHANGELOG.md` entry — no file moves are required.

---

## Why this model exists (one-paragraph history)

This split was introduced in v1.9.0 as part of the post-2026-05 honest-positioning pass ([`LONG_TERM_FIXES_TRACKER.md`](../competitive/LONG_TERM_FIXES_TRACKER.md) T3.1–T3.4). The original feedback was that AINL appeared to spread its production claims across too many domain-specific adapters. The fix is *not* to retire adapters — the catalog is a real strength — but to be explicit about which adapters carry the production-grade SLA and which are part of the broader supported catalog. The model is permanent; nothing is being walked back.
