# Idempotent Webhook Handler Pattern

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
