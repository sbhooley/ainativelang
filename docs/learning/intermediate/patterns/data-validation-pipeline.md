# Data Validation Pipeline Pattern

> **⚠️ DESIGN PREVIEW**: The `graph { node ... }` syntax shown in this document
> is a **design preview for AINL 2.0** and does not compile with the current
> AINL compiler (v1.3.3). The current working syntax uses single-character
> opcodes (`S`, `R`, `X`, `J`, `If`, `Set`). See `examples/hello.ainl` or
> `AGENTS.md` in the repo root for real, compilable syntax.


Multi-stage data validation with LLM + deterministic checks.

---

## Use Case

Ingesting data from external sources that may contain:
- Missing fields
- Wrong types
- Business logic violations
- Format errors

Need validation before processing.

---

## Implementation

### Real AINL Syntax (v1.3.3 — this compiles)

```ainl
# validation_pipeline.ainl — Multi-stage data validation
# ainl validate validation_pipeline.ainl --strict

S app core noop

L_start:
  R core.GET ctx "data" ->data
  R core.GET ctx "source" ->source

  # Stage 1: Check required fields
  R core.GET data "id" ->id
  R core.GET data "email" ->email
  R core.GET data "amount" ->amount
  If (core.eq id null) ->L_reject_schema ->L_check_email

L_check_email:
  If (core.eq email null) ->L_reject_schema ->L_check_amount

L_check_amount:
  If (core.lt amount 0) ->L_reject_business ->L_accept

L_reject_schema:
  Set result {"valid": false, "errors": ["missing required field"]}
  J result

L_reject_business:
  Set result {"valid": false, "errors": ["amount must be >= 0"]}
  J result

L_accept:
  Set result {"valid": true, "errors": [], "data": data}
  J result
```

### Design Preview Syntax (AINL 2.0 — does NOT compile yet)

```ainl
graph ValidationPipeline {
  input: Record = { data: object, source: string }

  node validate_schema: ValidateSchema("schema-check") {
    schema: {
      type: object
      required: ["id", "email", "amount"]
      properties: {
        id: { type: "string" }
        email: { type: "string", format: "email" }
        amount: { type: "number", minimum: 0 }
      }
    }
    data: input.data
  }

  node validate_business: Transform("rules") {
    errors: []
    if input.data.amount < 0:
      errors.append("Amount must be >= 0")
    result: { valid: len(errors)==0, errors: errors }
  }

  node aggregate: Transform("combine") {
    is_valid: validate_business.valid
    errors: validate_business.errors
    result: { valid: is_valid, errors: errors, data: input.data if is_valid else null }
  }

  node route: switch(aggregate.result.valid) {
    case true -> accept
    case false -> reject
  }

  node accept: WriteFile("accepted") {
    path: "./data/accepted.jsonl"
    content: serialize_json(aggregate.result.data)
    mode: append
  }
  
  node reject: WriteFile("rejected") {
    path: "./data/rejected.jsonl"
    content: serialize_json({
      source: input.source,
      data: input.data,
      errors: aggregate.result.errors,
      ts: now()
    })
    mode: append
  }

  output: aggregate.result
}
```
