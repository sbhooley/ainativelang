# AI Native Lang (AINL) targets roadmap — real-world and production

Expanding targets so AI Native Lang is usable in production and for mass adoption. Tiers: **Today** (implemented), **Next** (high priority), **Production** (deploy, observe, scale), **Ecosystem** (other languages and platforms).

---

## Tier 1: Today (implemented)

| Target | Output | Use case |
|--------|--------|----------|
| React (browser) | JSX, hash router, layout, forms, tables, events | Dashboards, SPAs |
| FastAPI + runtime | Python server + ir.json + adapters | API backend |
| Unified web server | API + static mount | Single process for API + frontend |
| Prisma | schema.prisma | DB schema from D |
| MT5 | .mq5 stub | Trading bot skeleton |
| Scraper | Python requests + BeautifulSoup | Scraping jobs |
| Cron | Python stubs | Scheduled jobs |
| Pay / Cache / Queue | Adapters (Stripe, Redis, Bull) | Runtime only |

---

## Tier 2: Next (high priority for adoption)

| Target | Purpose | Ops / IR |
|--------|---------|----------|
| **OpenAPI 3.0** | API docs, codegen, Postman, gateway config | E, D → paths + schemas |
| **Docker + Compose** | One-command run and deploy | S, E, D → Dockerfile + compose |
| **Next.js API routes** | Serverless API + React on Vercel | E, L, R, J → /pages/api/* + React |
| **Vue / Svelte** | Alternative frontend frameworks | Same IR as React (fe, Rt, Lay, etc.) |
| **SQL migrations** | Create/alter tables from D | D → SQL (Postgres/MySQL) |
| **Env + config** | 12-factor env schema from S/C/P | S, C, P → .env.example, config schema |

---

## Tier 3: Production (deploy, observe, scale)

| Target | Purpose | Notes |
|--------|---------|--------|
| **Health + readiness** | /health, /ready in emitted server | From S/core |
| **Structured logging** | Request/response and label logs | ✅ LoggingMiddleware in emit_server |
| **Auth middleware** | JWT or API-key from AINL (A op) | ✅ A op → Depends in emit_server |
| **Rate limit** | Per-client RPM via env | ✅ RateLimitMiddleware; RATE_LIMIT env |
| **Kubernetes** | Deploy manifest (Deployment, Service, Ingress) | ✅ emit_k8s() → k8s.yaml |
| **Native async runtime loop** | Optional async graph/step execution + async adapter path | ✅ `AINL_RUNTIME_ASYNC=1` / `--runtime-async`; redis has full async verb parity, dynamodb supports bounded async streams, and supabase has advanced lightweight fanout/replay/cursor helpers; see `docs/runtime/ASYNC_RUNTIME.md` |
| **Terraform/Pulumi** | DB, queue, cache resources | 🔲 Planned |
| **CI (GitHub Actions)** | Test + build + emit from .lang | ✅ .github/workflows/ci.yml |

---

## Tier 4: Ecosystem (other languages and platforms)

| Target | Purpose |
|--------|---------|
| **Node/Express or Nest** | TypeScript backend; same IR |
| **Java (Spring Boot / Quarkus)** | Enterprise backend |
| **.NET (Minimal API)** | C# backend |
| **Go (Chi / Echo)** | High-performance API |
| **GraphQL** | Schema + resolvers from D, E |
| **gRPC** | Service def from D, E |
| **React Native / Flutter** | Mobile from same fe IR |
| **System scripts** | Shell or Python from Cr, R |
| **Minecraft / game plugins** | Event hooks from S, E, U |

---

## Implementation status

| Target | Status | Emitter / artifact |
|--------|--------|--------------------|
| OpenAPI 3.0 | ✅ Implemented | `emit_openapi()` → openapi.json |
| Docker + Compose | ✅ Implemented | `emit_dockerfile()`, `emit_docker_compose()` |
| Next.js API routes | ✅ Implemented | `emit_next_api_routes()` → next/pages/api/*.ts + health/ready |
| Vue / Svelte | ✅ Implemented | `emit_vue_browser()` → App.vue, `emit_svelte_browser()` → App.svelte |
| SQL migrations | ✅ Implemented | `emit_sql_migrations(ir, dialect)` → migrations/001_initial.sql |
| Env/config | ✅ Implemented | `emit_env_example(ir)` → .env.example |
| Health/readiness | ✅ Implemented | In `emit_server()`: /api/health, /api/ready; in OpenAPI |
| Auth (A op) | ✅ Implemented | A op → `services.auth`; `emit_server()` adds Depends for protected routes |
| Node/Java/.NET/Go | 🔲 Planned | New emitters + adapters |

Adding OpenAPI and Docker to the compiler gives immediate production value: **documented, runnable API** and **one-command deploy** for the current stack.
