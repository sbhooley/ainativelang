## AINL Memory Contract (v1, extension-level)

> **OpenClaw (MCP skill):** **[`../OPENCLAW_INTEGRATION.md`](../OPENCLAW_INTEGRATION.md)** — **`skills/openclaw/`**, **`ainl install-mcp --host openclaw`** (alias **`install-openclaw`**), **`ainl-mcp`**; not the bridge **daily markdown** path below.
>
> **ZeroClaw:** **[`../ZEROCLAW_INTEGRATION.md`](../ZEROCLAW_INTEGRATION.md)** — skill + **`ainl install-mcp --host zeroclaw`** (alias **`install-zeroclaw`**), **`ainl-mcp`**; not the OpenClaw **`~/.openclaw/workspace/memory/`** layout described below.

Status: **design + v1 adapter implementation**. This document describes the v1
memory contract as an extension-level adapter. It does **not** change compiler
or core runtime semantics.

See also: [`MEMORY_CONTRACT_V1_1_RFC.md`](MEMORY_CONTRACT_V1_1_RFC.md) for an
additive proposal that keeps deterministic behavior while adding optional query
metadata and filters (no vector semantics, no policy cognition).

**OpenClaw daily markdown (bridge):** Operator workflows that append human-readable logs via `openclaw_memory` typically use **`~/.openclaw/workspace/memory/YYYY-MM-DD.md`** (directory overridable with `OPENCLAW_MEMORY_DIR`). That path is **orthogonal** to the SQLite-backed `memory` adapter contract below; see [`docs/operations/UNIFIED_MONITORING_GUIDE.md`](../operations/UNIFIED_MONITORING_GUIDE.md) for token-budget and related bridge monitoring.

**ArmaraOS JSON graph memory (bridge, separate adapter):** typed nodes/edges in **`~/.armaraos/ainl_graph_memory.json`** (or **`AINL_GRAPH_MEMORY_PATH`**), adapter name **`ainl_graph_memory`**, plus runtime IR ops **`MemoryRecall`** / **`MemorySearch`**, typed **`EdgeType`** relations (structural + epistemic), and label / engine integration for **`persona.update`** — see **[`AINL_GRAPH_MEMORY.md`](AINL_GRAPH_MEMORY.md)**.

**Dotted `memory.*` / `persona.*` on `R` (graph bridge):** tokens such as **`R memory.recall`**, **`R memory.search`**, **`R memory.export_graph`**, **`R memory.store_pattern`**, **`R memory.pattern_recall`**, **`R memory.store`** (alias of **`store_pattern`**), **`R memory.export`** (alias of **`export_graph`**), and **`R persona.{load,get,update}`** compile as **one** adapter slot each and **`RuntimeEngine`** dispatches them to **`ainl_graph_memory`** when that adapter is allowed and registered. This is **not** the split-token SQLite form **`R memory store_pattern …`** / **`R memory recall_pattern …`** (§3.7), which still targets the SQLite **`memory`** adapter.

**SQLite procedural patterns + live merge:** the same **`memory`** adapter also persists **named IR fragments** (partial `labels` maps) in table **`ainl_memory_patterns`**, with a stable **SHA-256 `content_hash`** per row. Use **split-token** **`R memory store_pattern …`** / **`R memory recall_pattern …`** (two adapter tokens, not dotted **`memory.store_pattern`**), and the compiler/runtime step **`memory.merge`** (alias **`MemoryMerge`**) to **re-inject** a stored fragment into the running program’s **`labels`**, execute its entry label, and bind the subgraph exit to a frame variable (default **`mm_result`**). Details: §3.7 below.

**Public article (tiers, hosts, bridge vs adapter):** [AINL, structured memory, and OpenClaw-style agents](https://ainativelang.com/blog/ainl-structured-memory-openclaw-agents).

**Implementation note (v1.1 additive):** the current adapter now supports
optional deterministic metadata (`source`, `confidence`, `tags`, `valid_at`)
plus bounded list filters (`tags_any`, `tags_all`, created/updated ranges,
`limit`, `offset`), namespace-level retention hooks, operational counters in
responses, and capability-advertised memory profile hints. These are additive
extensions; existing v1 call shapes remain valid.

**AINL syntax (callers):** When filling namespace / kind / record id in the execution frame before `R memory put` or module `Call`s, use **`Set memory_namespace "…"`** (not `X memory_namespace "…"`). The `X` op is `X dst fn args…`; a line like `X memory_namespace "workflow"` is parsed as `fn = workflow` and fails at runtime. See **`docs/AINL_SPEC.md`** (note after the **`X`** op in §2.3).

> **Positioning note.** Memory is classified as `extension_openclaw` in the
> adapter support tier, but it is the **recommended durable state mechanism**
> for any workflow that needs persistence beyond a single run. The extension
> classification reflects packaging origin, not importance. Any stateful
> workflow — OpenClaw, NemoClaw, or custom-host — that needs to remember
> facts, session context, or workflow checkpoints across runs should use the
> memory adapter. See `docs/architecture/STATE_DISCIPLINE.md` for where
> memory fits in the tiered state model.

Memory in AINL v1 is:

- **adapter-level** — implemented as a `memory` adapter,
- **execution-facing** — used explicitly from workflows, not implicitly injected,
- **backend-agnostic** — v1 uses SQLite by default but the contract is portable,
- **typed** by `namespace` and `record_kind`,
- **validator-friendly** — records have a simple canonical envelope,
- **non-magical** — no vector search, auto-recall, or policy semantics in v1.

---

## 1. Canonical identity model

Every memory record is uniquely identified by the triple:

- `namespace: string`
- `record_kind: string`
- `record_id: string`

All three are **required** in v1. There is no shorthand that omits
`record_kind`.

Conceptually:

- `namespace` encodes **lifetime/scope**,
- `record_kind` encodes the **logical type** of the record,
- `record_id` is the **instance key** within that kind.

The canonical envelope for a record is:

```json
{
  "namespace": "string",
  "record_kind": "string",
  "record_id": "string",
  "created_at": "RFC3339 string",
  "updated_at": "RFC3339 string",
  "ttl_seconds": 3600,
  "payload": {}
}
```

The `payload` field is always a JSON object in v1.

---

## 2. Namespaces and record kinds (v1)

### 2.1 Namespaces (v1 whitelist)

- `session` — short-lived per-session/interaction context.
- `long_term` — durable multi-session facts/preferences.
- `daily_log` — timestamped notes and logs, roughly per day.
- `workflow` — per-workflow or per-pipeline state and checkpoints.
- `ops` — operational metrics, monitor state, and infrastructure health records for autonomous ops monitors.

### 2.2 Recommended record kinds (v1)

The following record kinds are recommended in v1:

- `session.context`
- `workflow.token_cost_state`
- `workflow.checkpoint`
- `workflow.monitor_status_snapshot`
- `workflow.advisory_result`
- `long_term.user_preference`
- `long_term.project_fact`
- `daily_log.note`

These kinds are advisory; AINL does not enforce a full schema per kind in v1,
but validators and tooling can use them for light shape checks.

---

## 3. Verbs (v1)

The `memory` adapter exposes the six **namespace** v1 verbs below (§3.1–3.6), plus **pattern** helpers in §3.7. The **`memory.merge`** / **`MemoryMerge`** step is implemented in **`RuntimeEngine`** (not an adapter `call` verb) but requires a registered **`memory`** adapter for **`recall_pattern`**.

### 3.1 `memory.put(namespace, record_kind, record_id, payload, ttl_seconds?)`

- Creates or overwrites a record at `(namespace, record_kind, record_id)`.
- `payload` must be a JSON object.
- `ttl_seconds` is optional and advisory (see below).

Returns a small envelope such as:

```json
{
  "ok": true,
  "created": true,
  "updated_at": "2026-03-09T01:23:45Z"
}
```

### 3.2 `memory.get(namespace, record_kind, record_id)`

- Loads a record by its canonical identity.
- Backends may treat TTL-expired records as not found.

Returns:

```json
{
  "found": true,
  "record": {
    "namespace": "workflow",
    "record_kind": "workflow.checkpoint",
    "record_id": "cp-1",
    "created_at": "2026-03-09T01:00:00Z",
    "updated_at": "2026-03-09T01:00:00Z",
    "ttl_seconds": 3600,
    "payload": { "step": 1 }
  }
}
```

If not found (or treated as expired), `found` is `false` and `record` is `null`.

### 3.3 `memory.append(namespace, record_kind, record_id, entry, ttl_seconds?)`

- Appends an `entry` object to a **log-like** record.
- Intended primarily for log-style kinds such as:
  - `daily_log.note`,
  - log views of `workflow.advisory_result`,
  - log views of `workflow.monitor_status_snapshot`.
- Not a general-purpose mutation primitive for arbitrary JSON records.

Behavior:

- If no record exists at `(namespace, record_kind, record_id)`:
  - create a new record with a log-shaped payload, e.g. `{ "entries": [entry] }`.
- If a record exists:
  - payload must be a JSON object with an `entries` list; otherwise an error is raised.
  - the new `entry` is appended to that list.

Returns:

```json
{
  "ok": true,
  "updated_at": "2026-03-09T02:00:00Z"
}
```

### 3.4 `memory.list(namespace, record_kind?, record_id_prefix?, updated_since?)`

`memory.list` provides a **narrow, structured enumeration** capability for
discovering existing memory records without reading full payloads.

- `namespace` (required): must be one of the v1 namespaces.
- `record_kind` (optional): when provided, filters to that kind.
- `record_id_prefix` (optional): when provided (non-null, non-empty string), filters to records whose
  `record_id` starts with this prefix. In AINL, pass JSON **`null`** to omit the prefix; a literal empty string **`""`** is still “provided” and is **rejected** by the runtime adapter.
- `updated_since` (optional): an ISO-8601 timestamp string; when provided,
  filters to records whose `updated_at` is greater than or equal to this
  timestamp (string comparison on the stored ISO form).

It does **not**:

- scan or inspect `payload` contents,
- implement full-text search,
- implement semantic retrieval or vector/RAG,
- accept arbitrary predicates or a query language.

Return shape:

```json
{
  "items": [
    {
      "record_kind": "workflow.checkpoint",
      "record_id": "cp-1",
      "created_at": "2026-03-09T01:00:00Z",
      "updated_at": "2026-03-09T02:00:00Z",
      "ttl_seconds": 3600
    }
  ]
}
```

Results are ordered deterministically by `record_kind` then `record_id`
ascending within the given namespace, regardless of `updated_since`.

Typical usage patterns:

- enumerate all records in a namespace:

  ```text
  R memory.list "workflow"
  ```

- enumerate only workflow checkpoints:

  ```text
  R memory.list "workflow" "workflow.checkpoint"
  ```

- enumerate only token cost state records with an ID prefix:

  ```text
  R memory.list "workflow" "workflow.token_cost_state" "token-"
  ```

- enumerate only records updated recently (no `record_id_prefix` filter):

  ```text
  R memory.list "workflow" "workflow.checkpoint" null "2026-03-10T00:00:00+00:00"
  ```

`memory.list` is intended as:

- a lightweight discovery tool,
- a structured way to locate record IDs,
- an aid for humans and bots when combined with `memory.get`.

It is **not** meant to replace bridge tooling or future search/index layers.

### 3.5 `memory.delete(namespace, record_kind, record_id)`

`memory.delete` provides a **narrow, exact-key lifecycle primitive**:

- deletes at most one record identified by `(namespace, record_kind, record_id)`,
- does not support bulk deletion, wildcards, or predicates,
- does not change TTL behavior or pruning semantics.

Return shape:

```json
{
  "ok": true,
  "deleted": true
}
```

- `deleted: true` — a record existed and was removed.
- `deleted: false` — no record existed at that exact key; the call is still ok.

`memory.delete` is intended for:

- operator- or workflow-triggered cleanup of known keys,
- small lifecycle hygiene (e.g. removing obsolete checkpoints or facts),
- providing a clear conceptual base for future admin-only pruning tools.

It is **not**:

- a general mutation surface for arbitrary payload rewriting,
- a bulk or pattern-based delete API,
- a replacement for possible future `memory.prune` tooling that might clean up
  expired records or apply policy-based retention.

### 3.6 `memory.prune(namespace?)`

`memory.prune` is an **admin/operator-oriented** helper that removes expired
records based on TTL metadata:

- only affects records with non-null `ttl_seconds`,
- treats a record as expired when:
  - `ttl_seconds is not null`, **and**
  - `now > created_at + ttl_seconds` (using the same best-effort behavior as
    `memory.get`),
- never deletes records that do not meet the expiration condition.

Arguments:

- `namespace` (optional):
  - when provided: only prune expired records in that namespace,
  - when omitted: prune expired records across all namespaces.

Return shape:

```json
{
  "ok": true,
  "pruned": 3
}
```

- `pruned` is the number of records actually removed.

`memory.prune` is:

- **explicit and one-shot** (manual call, no scheduler or background worker),
- **TTL-only** (no arbitrary predicates, no payload-based deletion),
- intended for small lifecycle hygiene and admin tools that want to clean up
  expired rows before running reports or migrations.

In practice, operators should consider running `memory.prune` periodically as
part of their own maintenance or cron tooling (at a cadence appropriate for
their environment), especially in deployments that make heavy use of TTLs.

It does **not**:

- provide bulk deletion by pattern or arbitrary query,
- change TTL semantics beyond what's already in `memory.get`,
- act as a general-purpose retention or archival system.

### 3.7 Procedural patterns (`store_pattern` / `recall_pattern`) and engine **`memory.merge`**

These features use the **same SQLite file** as v1 namespace records but a **dedicated table** `ainl_memory_patterns` (`name` primary key, `content_hash`, `ir_json`, `updated_at`). They do **not** use the `(namespace, record_kind, record_id)` triple.

| Surface | Role |
|--------|------|
| **`MemoryAdapter.store_pattern(name, ir_fragment)`** | Validates `ir_fragment` is a dict with a non-empty **`labels`** map; writes JSON + **SHA-256** content hash; upserts by **`name`**. |
| **`MemoryAdapter.recall_pattern(name)`** | Returns a **normalized** partial IR `{"labels": {…}}` with each label body containing **`legacy.steps`**, **`nodes`**, **`edges`**, or **`None`** if missing/invalid. |
| **`R memory store_pattern …` / `recall_pattern`** | Adapter dispatch mirrors the methods (see `runtime/adapters/memory.py`). |
| **`memory.merge`** / **`MemoryMerge`** (label step) | **`RuntimeEngine`** (`_exec_memory_merge`): **`deepcopy`** of the fragment, new label keys **`_mm_{seq}_<originalLabel>`**, **`_steps_to_graph`** + **`normalize_labels`** on merged labels, run merged **entry** (or optional **override** label id from the step), write return value to **`out`** (default **`mm_result`**). Missing or invalid pattern: **warning**, no exception. |

**Authoring (opcode / compact body):**

```text
memory.merge my_pattern ->out_var
MemoryMerge my_pattern L2 ->out_var
```

Optional middle slot: **entry label id** inside the recalled fragment (override auto-picked entry). Grammar / slot classes: **`compiler_v2.OP_GRAMMAR["memory.merge"]`** (STRING pattern, optional LABEL_REF, optional OUT_VAR).

**Recall vs merge:** **`MemoryRecall`** (graph adapter) loads a **single graph node** into the frame for inspection. **`memory.merge`** turns a **stored procedural `labels` fragment** back into **live** engine labels and **runs** that subgraph — see **[`AINL_GRAPH_MEMORY.md`](AINL_GRAPH_MEMORY.md)** (section **MemoryMerge vs graph recall**).

**Tests:** `tests/test_memory_merge.py`.

---

## 4. TTL semantics

The `ttl_seconds` field is:

- **advisory** and **best-effort**,
- not a hard guarantee of expiration time,
- not a precise scheduler.

Backends may:

- treat a TTL-expired record as not found on read, and/or
- periodically clean up expired records.

The spec does **not** require strict TTL enforcement in v1.

---

## 5. Backend strategy (v1: SQLite)

The initial v1 adapter uses a local SQLite database, conceptually:

```sql
CREATE TABLE memory_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  namespace TEXT NOT NULL,
  record_kind TEXT NOT NULL,
  record_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  ttl_seconds INTEGER NULL,
  payload_json TEXT NOT NULL
);

CREATE INDEX idx_memory_ns_kind_id
ON memory_records(namespace, record_kind, record_id);
```

The default path is taken from `AINL_MEMORY_DB`, falling back to
`/tmp/ainl_memory.sqlite3`.

Future backends (filesystem, Obsidian, vector/RAG systems) can map the same
canonical identity and envelope onto different storage forms without changing
the `memory` adapter contract.

---

## 6. Validation expectations

Validators and tooling for v1 should, at minimum:

- enforce the namespace whitelist,
- require `record_kind` and `record_id` as non-empty strings,
- require `payload` to be a top-level JSON object,
- ensure `ttl_seconds` is integer-or-null when present,
- perform light checks for known record kinds:
  - e.g. `workflow.*` kinds are used under the `workflow` namespace,
  - `daily_log.note` payloads contain `entries` or note fields, etc.

---

## 7. Validator and CLI

An extension-only validator is provided to help keep memory usage on the v1
contract rails:

- `tooling/memory_validator.py`
- `scripts/validate_memory_records.py`

Usage examples:

- Validate a single record or an array of records from a JSON file:

  ```bash
  python -m scripts.validate_memory_records --json-file path/to/records.json
  ```

- For machine-readable output:

  ```bash
  python -m scripts.validate_memory_records --json-file path/to/records.json --json
  ```

The validator checks:

- core identity fields (`namespace`, `record_kind`, `record_id`),
- namespace whitelist,
- payload object shape,
- `ttl_seconds` type (integer-or-null),
- basic namespace/record_kind consistency,
- and emits light warnings when recognized record kinds lack common fields.

It is **governance/tooling only**; it does **not** change runtime semantics.

---

## 8. Export/import tooling (interoperability)

On top of the canonical `memory` contract, JSON/JSONL export/import tools are
provided for advanced users and bots, plus small markdown bridges for humans:

- `tooling/memory_bridge.py`
- `scripts/export_memory_records.py`
- `scripts/import_memory_records.py`
- `tooling/memory_markdown_bridge.py`
- `scripts/export_memory_daily_log_markdown.py`
- `tooling/memory_markdown_import.py`
- `scripts/import_memory_markdown.py`
- `tooling/memory_migrate.py`
- `scripts/migrate_memory_legacy.py`
- `scripts/memory_retention_report.py` — read-only retention and TTL hygiene report (see below).

These tools:

- treat the SQLite-backed `memory_records` table as the source of truth,
- export records into canonical JSON/JSONL envelopes including:
  - `namespace`, `record_kind`, `record_id`,
  - `created_at`, `updated_at`, `ttl_seconds`,
  - `payload`,
  - `provenance` (e.g. `source_system`, `authored_by`, `origin_uri`),
  - `flags` (`authoritative`, `curated`, `ephemeral`),
- and import such envelopes back into the memory store with:
  - validation via `tooling/memory_validator.py`,
  - provenance/flags preserved inside `payload` under reserved keys
    (`_provenance`, `_flags`) without changing core adapter behavior.

On top of this machine-facing foundation, a **one-way, explicit, markdown
export** exists for a single v1 kind:

- `namespace = daily_log`
- `record_kind = daily_log.note`

This bridge:

- renders each `daily_log.note` record into a markdown file at:
  - `memory/daily_log/<YYYY>/<YYYY-MM-DD>.md`
  - where `<YYYY-MM-DD>` is the `record_id`,
- includes a small frontmatter block with:
  - `ainl_namespace`,
  - `ainl_record_kind`,
  - `ainl_record_id`,
  - `exported_from: ainl.memory`,
- and formats note entries deterministically as bullet points:
  - `- [<ts>] <text>` when `ts` is present,
  - `- <text>` otherwise,
  - sorted by `ts` when available.

### 8.1 Memory retention report (operator visibility)

The **memory retention report** is a read-only script that inspects the SQLite
memory store and summarizes record counts, TTL coverage, age distribution, and
records that are expiring soon or already expired (but still on disk until
`memory.prune` runs). It is intended for operator hygiene and visibility only;
it does not modify the store or change runtime/schema.

- **Script:** `scripts/memory_retention_report.py`
- **Data source:** The same SQLite backing store as the memory adapter
  (`AINL_MEMORY_DB` or `/tmp/ainl_memory.sqlite3`).
- **Output:** Plain-text summary by default; `--json` for machine-readable
  output. Optional filters: `--namespace <ns>`, `--record-kind <kind>`.
- **Expiring soon:** By default, records whose expiry time
  (`created_at + ttl_seconds`) falls within the next 24 hours are reported;
  use `--expire-soon-seconds` to change the window.

Example commands:

- Full report (plain text):
  - `python3 scripts/memory_retention_report.py`

- JSON output:
  - `python3 scripts/memory_retention_report.py --json`

- Filter by namespace or record kind:
  - `python3 scripts/memory_retention_report.py --namespace workflow`
  - `python3 scripts/memory_retention_report.py --record-kind workflow.monitor_check`

The report helps answer: what is filling memory, where TTLs are missing, what
will expire soon, and whether expired rows are accumulating before prune. It
is **read-only** and does not invoke the compiler or runtime.

### 8.2 Operator runbook: weekly memory hygiene

This section describes a **lightweight, manual** workflow for checking memory
growth and performing routine TTL cleanup using the existing retention report
and `memory.prune`. No scheduler, daemon, or new tool is required.

**When to care**

- You use the memory adapter (monitors, workflow state, session or daily_log).
- You want to avoid unbounded growth and confirm TTLs are effective.
- You run `memory.prune` on a schedule (e.g. daily via the `memory_prune`
  monitor) but want to **inspect** state and **decide** when to prune or
  re-check after pruning.

**What “expired but still present” means**

- Records with a TTL are treated as “not found” by `memory.get` once
  `created_at + ttl_seconds` has passed. They are **not** removed from the
  SQLite store until something explicitly deletes them.
- `memory.prune` is that explicit action: it physically deletes expired
  rows. Until you run prune, expired rows remain on disk and are reported
  by the retention report as “expired but still present.”
- A non-zero expired count is **normal** between prune runs. React if the
  count grows without bound or if you never run prune.

**What not to overreact to**

- **Some records without TTL** — `long_term` and some `session`/`daily_log`
  usage intentionally omit TTL. Focus on namespaces/kinds that should have
  TTLs (e.g. `workflow.monitor_check`, `workflow.token_cost_state`).
- **Expiring soon** — informational; no action required unless you want to
  anticipate churn.
- **Small expired count** — expected between weekly or daily prune runs.

**Step 1: Run the memory retention report**

```bash
python3 scripts/memory_retention_report.py
```

Inspect:

- **Overall totals** — total records, with/without TTL.
- **By namespace / by record kind** — where growth is coming from.
- **TTL coverage** — whether critical kinds have TTLs.
- **Expired but still present** — count and sample; expect some if prune
  has not run recently.
- **Expiring within 24h** — optional; use to anticipate turnover.

Filter by namespace or record kind if you care about a subset:

```bash
python3 scripts/memory_retention_report.py --namespace workflow
python3 scripts/memory_retention_report.py --record-kind workflow.monitor_check
```

Machine-readable output:

```bash
python3 scripts/memory_retention_report.py --json
```

**Step 2: Interpret the report**

- **Totals and distribution** — identify namespaces or kinds that dominate
  growth. Confirm they use TTLs where appropriate.
- **Missing TTLs** — if many records have no TTL and they are short-lived
  by design, consider adding TTLs in the writing workflow or accept the
  growth and prune less often.
- **Expired count** — if it is large or growing and you do not run prune
  regularly, plan to run prune (see Step 4).

**Step 3: (Optional) Inspect expired / expiring soon**

- Use the “Expired but still present” sample to confirm they are
  expected (e.g. old `workflow.monitor_check` or `workflow.token_cost_state`
  rows). No need to act on every expired row; prune removes them in bulk.
- “Expiring within 24h” is for awareness only.

**Step 4: Run prune if needed**

- Prune is **explicit and operator-triggered**. The memory adapter does not
  prune automatically.
- To prune **all** namespaces: run the AINL program that calls
  `memory.prune` with no namespace argument, e.g. execute
  `demo/memory_prune.lang` or `examples/autonomous_ops/memory_prune.lang`
  via your usual AINL runner (e.g. `python3 run_ainl.py demo/memory_prune.lang`
  if that runner is available).
- To prune a **single** namespace only: use a program or one-off invocation
  that calls `memory.prune(namespace)` with the desired namespace (e.g.
  `workflow`). The contract supports an optional namespace filter.
- Prune is idempotent and safe to run regularly (e.g. daily or weekly).

**Step 5: Re-run the report to confirm**

```bash
python3 scripts/memory_retention_report.py
```

- **Expired (in DB)** should drop to zero or a small number after prune.
- **Total records** will decrease by the number of expired rows that were
  removed.

**Suggested cadence**

- **Weekly:** Run the retention report; run prune if expired count is high or
  you want to keep the store lean.
- **After adding new monitors or workflow state:** Run the report once to
  establish a baseline and confirm TTLs are set where expected.

The markdown daily-log export is:

- **export-only** (one-way, no import),
- **tooling-only** (no runtime/compiler semantic change),
- **not** a live mirror, sync engine, or Obsidian integration,
- intended purely to let humans browse `daily_log.note` content in a normal
  filesystem/note workflow.

In the other direction, a **curated, frontmatter-based markdown import**
exists for a small set of long-term kinds:

- `namespace = long_term`, `record_kind = long_term.project_fact`
- `namespace = long_term`, `record_kind = long_term.user_preference`

This bridge:

- only imports markdown files that explicitly opt in via frontmatter:
  - `ainl_namespace`
  - `ainl_record_kind`
  - `ainl_record_id`
- maps the markdown body into `payload.text` (trimmed),
- for `long_term.user_preference`, additionally maps:
  - `preference_key` / `key` -> `payload.key`
  - `preference_value` / `value` -> `payload.value`,
- attaches provenance and flags using the established bridge-layer convention:
  - `provenance` (e.g. `source_system`, `origin_uri`, `authored_by`) and
    `flags` (`authoritative`, `curated`, `ephemeral`) are passed to
    `tooling.memory_bridge.import_records` and end up stored under
    `payload._provenance` / `payload._flags`.

Markdown import is:

- **explicit and one-shot** (CLI-triggered, not watched or auto-synced),
- **curated/human-authored only** (no semantic extraction from arbitrary notes),
- **limited** to the two long-term kinds above,
- validated via the same `tooling/memory_validator.py` contract as JSON/JSONL
  import,
- intended for small, structured facts and preferences, not bulk note
  ingestion, indexing, or RAG/vector search.

Finally, a **narrow legacy migration helper** exists to help bootstrap the
SQLite-backed store from older note patterns:

- `MEMORY.md` -> `long_term.project_fact` records
- `memory/YYYY-MM-DD.md` -> `daily_log.note` records

This migration:

- is implemented by `tooling/memory_migrate.py` and
  `scripts/migrate_memory_legacy.py`,
- treats each `##` section in `MEMORY.md` with non-empty body as a separate
  `long_term.project_fact` (record IDs derived from a slugified heading, e.g.
  `memory_md.ainl_knowledge_base`),
- treats each `memory/YYYY-MM-DD.md` file as a single `daily_log.note` record
  with:
  - `namespace = daily_log`,
  - `record_kind = daily_log.note`,
  - `record_id = YYYY-MM-DD`,
  - `payload.entries` built from non-empty lines in the file (best-effort
    detection of `[timestamp] text` patterns, but no semantic analysis),
- attaches provenance/flags as:
  - `source_system: legacy_markdown`,
  - `origin_uri`: original file path,
  - `authored_by: human`,
  - conservative flags (`authoritative=False`, `curated=False`).

The migration tool is:

- **explicit and one-shot** (CLI-triggered, not watched or auto-synced),
- **conservative** (skips ambiguous content rather than guessing),
- **limited** to `MEMORY.md` and `memory/YYYY-MM-DD.md` patterns,
- validated via the same JSON envelope import/validator path as other bridges,
- intended for bootstrapping from legacy habits, not as a general markdown
  ingestion pipeline.

Example CLI usage:

```bash
# Export workflow advisory results to JSONL
python -m scripts.export_memory_records \
  --namespace workflow \
  --record-kind workflow.advisory_result \
  --output advisory_results.jsonl \
  --jsonl

# Import curated long_term facts from JSON
python -m scripts.import_memory_records \
  --json-file long_term_facts.json
```

These tools are **one-shot, explicit bridges**; they do **not** implement live
sync, watchers, or vector/RAG semantics.

---

## 9. Out of scope for v1

Memory v1 explicitly does **not** provide:

- implicit recall into prompts,
- automatic context injection,
- vector or semantic search semantics,
- policy or approval enforcement,
- cross-agent synchronization or multi-tenant guarantees,
- secret storage.

These concerns belong to higher-level orchestrators, policy engines, or
specialized storage systems layered on top of the v1 contract.
