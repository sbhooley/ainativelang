# AI Native Lang (AINL) Extensions — Programmers, Ops, Admins, Users, Designers, Architects

**Superseded for structure by [AINL_CORE_AND_MODULES.md](AINL_CORE_AND_MODULES.md).** That doc enforces Core (executable only) vs Modules (metadata), no op overloading, graph-first IR, and Set/Filt/Sort instead of overloading V. The list below is the *raw/historical extension set*; canonical, thesis-aligned behavior is documented in:

- `AINL_SPEC.md`
- `RUNTIME_COMPILER_CONTRACT.md`
- `CONFORMANCE.md`

All new ops and IR keys for control flow, variables, composition, types, config, observability, deploy, secrets, scaling, admin, RBAC, audit, feature flags, i18n/a11y/theme/offline/help, design tokens/components/copy, multi-service, relations/indexes, API rules, NFRs, docs, versioning, testing.

---

## 1. Programmers / developers

### Control flow & branching
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **If** | cond ->Lthen [->Lelse] | label step | Branch: if cond (e.g. var empty) run Lthen else Lelse. cond = var \| var=value \| var? |
| **Err** | [@node_id] ->Lhandler | label step | On error, run Lhandler. Graph: Err @node_id ->Lhandler; step-list bare = immediately preceding node |
| **Retry** | [@node_id] count [backoff_ms] [strategy] | label step | Retry node up to count times. strategy: `fixed` (default) or `exponential` (doubles each attempt, capped at 30s). Graph: Retry @node_id …; step-list bare = immediately preceding node |
| **Call** | Lid [->out] | label step | Call label; result in ctx[out]. If ->out omitted, callee must have exactly one J |

### Variables & expressions
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **V** | name ref | label step | Assign: name = ctx[ref] |
| **V** | name filter ref field op value | label step | Filter array ref by field op value -> name |
| **V** | name sort ref field [asc\|desc] | label step | Sort array ref by field -> name |

`V` forms are historical aliases. Canonical current forms are `Set`, `Filt`, and `Sort`.

### Composition
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Inc** | path/to.spec | top-level | Include another .lang file; merge IR (services, types, labels) |

### Types in the language
- **D** extension: field can be `name:T?` (optional) or `name:T!` (required). Stored in types[name].fields as { f: "T" } and types[name].required = [f] or optional = [f].
- **E** extension: optional return type and description. `E /users G ->L1 ->users A[User]` or `E /users G ->L1 "List users"`. Stored in eps[path].return_type, eps[path].description.
- **Desc** \| path "text" or TypeName "text" \| top-level \| Description for endpoint or type; IR desc.endpoints[path], desc.types[name].

### Testing & debugging
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Tst** | L1 | top-level | Test block: run label L1 (in test runner) |
| **Mock** | adapter key value | inside Tst or top-level | Mock adapter response for tests |

### Versioning & compatibility
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Ver** | 1.0 | top-level | Spec version |
| **Compat** | break \| add | top-level | Change rule: break = breaking change, add = additive |

---

## 2. Administrators / ops / SREs

### Config as code
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Env** | name [required\|optional] [default] | config.env | Env var: name, required/optional, default |
| **Sec** | name ref | config.secrets | Secret ref (e.g. vault path); ref = env var name or path |

### Observability
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **M** | name counter \| histogram | observability.metrics | Metric name and type |
| **Tr** | on \| off | observability.trace | Enable trace IDs in requests |

### Deployment control
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Deploy** | strategy [rolling\|canary] | deploy.strategy | Deployment strategy |
| **EnvT** | staging \| prod | deploy.env_target | Target environment for emit |
| **Flag** | name [default on\|off] | deploy.flags | Feature flag |

### Secrets & security
- **Sec** (above). Emitted config references vault or env for secrets.

### Scaling & limits
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Lim** | path rpm | limits.per_path | Per-path rate limit (requests per minute) |
| **Lim** | tenant rpm | limits.per_tenant | Per-tenant limit (when tenant header present) |

---

## 3. Admins / business operators

### Admin UI
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Adm** | UIName [entities...] | admin | Admin view UIName with CRUD over entities |

### Feature flags
- **Flag** (above).

### Audit & compliance
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Aud** | event retention_days | audit | Audit event type and retention (e.g. 90) |

---

## 4. Users (end users)

### Access control
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Role** | name | roles | Define role |
| **Allow** | role path method | allow | Role can call path with method |
| **Allow** | role UI | allow | Role can see UI |

### Localization & a11y
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **i18n** | key text | fe.i18n | Translation key and default text |
| **A11y** | role label \| component aria-label | fe.a11y | Accessibility: role/label for component or UI |
| **Theme** | dark \| light \| system | fe.theme | Default theme |

### Offline / resilience
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Off** | path [ttl] | fe.offline | Cache response at path for offline (ttl seconds) |
| **Retry** | count backoff_ms | fe.retry | Client retry: count and backoff (for fetch) |

### Onboarding & help
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Help** | UI content_key | fe.help | Help content key for UI |
| **Wiz** | UIName step1 step2 ... | fe.wizard | Wizard flow: UI and steps |

---

## 5. Designers / product

### Layout & styling
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Tok** | name value | fe.tokens | Design token (e.g. color.primary #333) |
| **Brk** | name value | fe.breakpoints | Breakpoint (e.g. sm 640) |
| **Sp** | name value | fe.spacing | Spacing (e.g. md 1rem) |

### Components & patterns
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Comp** | Name slot1 slot2 ... | fe.components | Design-system component and slots |

### Content & copy
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Copy** | key text | fe.copy | Copy string key and default text |

---

## 6. Architects / tech leads

### Multi-service
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Svc** | name [path_prefix] | services.boundaries | Service boundary; optional path prefix |
| **Contract** | path method [response_type] | services.contracts | Contract: path, method, optional response type |

### Data model
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Rel** | Type1 hasMany Type2 [fk] | types[].relations | Relation: Type1 has many Type2; optional fk field |
| **Rel** | Type1 belongsTo Type2 [fk] | types[].relations | Type1 belongs to Type2 |
| **Idx** | Type field1 field2 ... | types[].indexes | Index on Type (fields) |

### API design
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **API** | rest \| graphql [version_prefix] | api.style | API style and version prefix (e.g. v1) |
| **Dep** | path at version | api.deprecate | Deprecate path at version |

### Non-functional requirements
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **SLA** | path p99_ms availability | api.sla | SLA: P99 latency (ms), availability (e.g. 0.999) |

### Documentation
| Op | Slots | IR | Purpose |
|----|-------|-----|--------|
| **Desc** | path "text" | desc.endpoints | Endpoint description |
| **Desc** | TypeName "text" | desc.types | Type description |
| **Run** | name step1 step2 ... | runbooks | Runbook name and steps |

---

## IR summary (new keys)

- **labels[].legacy.steps**: R, J, If, Err, Retry, Call, Set, Filt, Sort (legacy serialization; canonical semantics are graph nodes/edges)
- **config**: { env: [...], secrets: [...] }
- **observability**: { metrics: [...], trace: true }
- **deploy**: { strategy, env_target, flags: [...] }
- **limits**: { per_path: { path: rpm }, per_tenant: rpm }
- **roles**: [ names ]
- **allow**: [ { role, path?, method?, ui? } ]
- **audit**: { event, retention_days }
- **admin**: { ui, entities: [...] }
- **fe**: i18n, a11y, theme, offline, help, wizard, tokens, breakpoints, spacing, components, copy, retry
- **types[].relations**: [ { type, kind: hasMany\|belongsTo, target, fk? } ]
- **types[].indexes**: [ [ fields ] ]
- **services.boundaries**: { name: path_prefix }
- **services.contracts**: [ { path, method, response_type? } ]
- **api**: { style, version_prefix, deprecate: [...], sla: {} }
- **desc**: { endpoints: {}, types: {} }
- **runbooks**: { name: [ steps ] }
- **ver**: string
- **compat**: break \| add
- **tests**: [ { label, mocks: [...] } ]
