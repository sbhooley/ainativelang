# RFC: Memory Contract v1.1 (Deterministic Query Metadata)

Status: **Draft proposal (additive, backward-compatible)**  
Scope: `memory` adapter contract only  
Non-goals: compiler semantics, runtime graph semantics, vector retrieval, policy cognition

---

## 1) Why this RFC exists

AINL memory v1 is intentionally explicit and non-magical: deterministic keys,
simple envelopes, and narrow verbs. That foundation is strong, but operators and
workflow authors still need better deterministic filtering when records grow.

This RFC proposes a small v1.1 contract extension that improves operational
queryability without changing execution semantics or introducing plugin-style
intelligence layers.

---

## 2) Design constraints

- **Additive only**: all v1 payloads and verb calls remain valid.
- **Deterministic only**: no semantic/vector/fuzzy behavior.
- **Portable only**: keep backend-agnostic contract shape.
- **No implicit behavior**: no auto-recall, auto-linking, or policy inference.

---

## 3) Proposed envelope additions

v1 envelope (unchanged fields omitted):

```json
{
  "namespace": "workflow",
  "record_kind": "workflow.checkpoint",
  "record_id": "cp-42",
  "created_at": "2026-03-20T10:00:00+00:00",
  "updated_at": "2026-03-20T10:01:00+00:00",
  "ttl_seconds": null,
  "payload": {},
  "metadata": {
    "source": "ainl.workflow.runner",
    "confidence": 0.95,
    "tags": ["checkpoint", "billing"],
    "valid_at": "2026-03-20T10:00:00+00:00"
  }
}
```

### New optional `metadata` object

- `source: string` - producer identifier (`ainl.workflow.runner`, `import.markdown`, etc.)
- `confidence: number|null` - advisory confidence in `[0.0, 1.0]`
- `tags: string[]` - deterministic labels for filtering
- `valid_at: RFC3339 string|null` - business validity timestamp (distinct from created/updated)
- `last_accessed: RFC3339 string|null` - **caller-maintained only**; last time the record was explicitly treated as “accessed” by workflow/agent code (never auto-updated by `memory.get` / `memory.list`)
- `access_count: int|null` - **caller-maintained only**; non-negative integer incremented only when workflow/agent code explicitly updates it (never auto-incremented by the adapter)

All fields are optional. Missing `metadata` is valid.

`last_accessed` and `access_count` exist solely for **opt-in, auditable** usage (for example via shared helpers that perform a follow-up `memory.put` after a read). They MUST NOT be written or mutated by the adapter on `get` or `list`.

---

## 4) Proposed verb changes (additive)

### 4.1 `memory.put(...)`

Current v1 shape stays valid.  
v1.1 allows optional metadata via either:

- `payload` convention key (`_metadata`) for compatibility bridges, or
- explicit adapter argument in hosts that support named params.

Contract requirement: metadata, when present, must normalize to envelope
`metadata` on read/export.

### 4.2 `memory.get(...)`

Return shape unchanged except optional `record.metadata`.

### 4.3 `memory.list(namespace, record_kind?, record_id_prefix?, updated_since?, filters?)`

v1 positional parameters stay valid.

v1.1 adds optional deterministic filters:

- `tags_any: string[]` - record has at least one of the tags
- `tags_all: string[]` - record contains all tags
- `created_after: RFC3339`
- `created_before: RFC3339`
- `valid_at_after: RFC3339`
- `valid_at_before: RFC3339`
- `since_last_accessed: RFC3339` - include only records whose stored `metadata.last_accessed` is present and lexically / chronologically `>=` the given timestamp (same comparison style as other RFC3339 window filters). Records with no `last_accessed` in metadata are excluded.
- `source: string`
- `limit: int` (bounded; implementation-defined max)
- `offset: int`

No free-form query language is introduced.

---

## 5) Determinism and ordering

For the same store state and same parameters:

- result membership must be stable,
- ordering remains deterministic (`record_kind`, `record_id` ascending unless explicitly documented otherwise),
- pagination over a stable store must be reproducible.

---

## 6) Retention defaults (optional, host-configurable)

This RFC permits optional namespace-level retention defaults:

- `default_ttl_by_namespace: { [namespace]: int|null }`
- `prune_strategy_by_namespace: { [namespace]: "ttl_only" | "none" }`

These defaults must not alter explicit per-record TTL values.

---

## 7) Capability advertisement

Hosts may declare memory profile via capability metadata:

- `memory_profile: "v1"` or `"v1.1-deterministic-metadata"`

Workflows/orchestrators can branch on capability without guessing support.

---

## 8) Explicit non-goals

The following remain out of scope for AINL core memory contract and belong to
plugin/skill/service layers:

- vector embeddings and semantic retrieval,
- fuzzy entity matching and autonomous recall,
- alignment scoring/correction loops,
- multi-store autonomous memory governance.

---

## 9) Migration and compatibility

- Existing v1 records are valid as-is.
- Existing v1 calls are valid as-is.
- Bridges (`memory_bridge.py`, markdown import/export) can progressively include
  `metadata` without breaking v1 consumers.
- Validator updates should be additive and gated by profile.

---

## 10) Proposed rollout plan

1. **Docs + contract update** (this RFC and `MEMORY_CONTRACT.md` note).
2. **Validator additive support** for `metadata` and list-filter arguments.
3. **Adapter support** for deterministic list filters and optional metadata storage.
4. **Conformance additions** for deterministic pagination/filter behavior.
5. **Capability metadata** surfaced in tooling/docs.

