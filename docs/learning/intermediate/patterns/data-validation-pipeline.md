# Data Validation Pipeline Pattern

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
