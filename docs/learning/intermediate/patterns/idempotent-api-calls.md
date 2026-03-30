# Idempotent API Calls Pattern

> **ℹ️ TWO SYNTAX STYLES**: This document shows two AINL syntax styles:
> 1. **Compact syntax** (works now) — Python-like, recommended for new code.
>    See `examples/compact/` and `AGENTS.md` for the full reference.
> 2. **Graph block syntax** (`graph { node ... }`) — **DESIGN PREVIEW**, does
>    NOT compile. These blocks are labeled "Design Preview" below.
>
> Use compact syntax for real projects: `ainl validate <file> --strict`


Make external API calls safe to retry without causing duplicates.

---

## Use Case

You're calling external APIs that aren't idempotent by default:
- Creating resources (POST /users)
- Charging credit cards
- Sending emails

Retries could cause duplicates. Need at-most-once execution.

---

## Implementation

### Approach 1: Idempotency Key

```ainl
node create_user: HTTP("api") {
  method: POST
  url: "https://api.example.com/users"
  headers: {
    "Idempotency-Key": "user-create-{{input.user.email | md5}}"
  }
  body: {
    email: input.user.email
    name: input.user.name
  }
}
```

### Approach 2: Database UPSERT

```ainl
node create_with_uuid: Transform("gen-id") {
  external_id: uuid_v4()
}

node upsert: SQL("upsert") {
  query: """
    INSERT INTO external_resources (external_id, data)
    VALUES ({{external_id}}, {{to_json(input.data)}})
    ON CONFLICT (external_id) DO NOTHING
  """
}
```
