# Idempotent Webhook Handler Pattern

> **ℹ️ TWO SYNTAX STYLES**: This document shows two AINL syntax styles:
> 1. **Compact syntax** (works now) — Python-like, recommended for new code.
>    See `examples/compact/` and `AGENTS.md` for the full reference.
> 2. **Graph block syntax** (`graph { node ... }`) — **DESIGN PREVIEW**, does
>    NOT compile. These blocks are labeled "Design Preview" below.
>
> Use compact syntax for real projects: `ainl validate <file> --strict`


Handle duplicate webhook events safely without double-processing.

---

## Use Case

You receive webhooks from external services (Stripe, SendGrid, GitHub) that may arrive more than once due to:
- Network retries from sender
- Your own retry logic
- Message queue redelivery

You need to ensure processing is idempotent: processing the same event twice has same effect as once.

---

## Implementation

### Real AINL Syntax (v1.8.0 — this compiles)

```ainl
# webhook_processor.ainl — Idempotent webhook handler
# ainl validate webhook_processor.ainl --strict

S app api /webhooks/incoming

L_start:
  R core.GET ctx "body" ->body
  R core.GET body "id" ->event_id
  R core.GET body "type" ->event_type

  # Check idempotency cache
  X cache_key (core.add "webhook:" event_id)
  R cache.get cache_key ->already
  If already ->L_skip ->L_process

L_skip:
  Set result {"status": "already_processed", "skipped": true}
  J result

L_process:
  # Route by event type
  If (core.eq event_type "invoice.paid") ->L_invoice ->L_other

L_invoice:
  R http.POST "https://api.stripe.com/v1/invoices/finalize" body ->resp
  Set result {"status": "processed", "type": "invoice"}
  # Mark as processed
  R cache.set cache_key "processed" ->_
  J result

L_other:
  Set result {"status": "processed", "type": event_type}
  R cache.set cache_key "processed" ->_
  J result
```

### Design Preview Syntax (AINL 2.0 — does NOT compile yet)

```ainl
graph WebhookProcessor {
  input: WebhookEvent = {
    id: string
    type: string
    payload: object
    timestamp: string
  }

  node check_idempotency: Cache("idempotency") {
    key: "webhook:{{input.id}}"
    ttl: 30d
  }
  
  node already_processed: Transform("bool") {
    result: check_idempotency.hit
  }

  node process_event: switch(input.type) {
    case "invoice.paid" -> handle_invoice_paid
    case "customer.created" -> handle_customer_created
  }
  
  node mark_processed: Cache("store") {
    key: "webhook:{{input.id}}"
    value: { status: "processed", ts: now() }
    ttl: 30d
  }

  node route: switch(already_processed.result) {
    case true -> return_duplicate
    case false -> process_and_store
  }
  
  node return_duplicate: Transform("dup") {
    result: { status: "already_processed" }
  }
  
  node process_and_store: sequence(process_event, mark_processed) {
    result: { status: "processed" }
  }

  output: route.result
}
```
