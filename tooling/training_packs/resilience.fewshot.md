# Canonical Resilience Pack

## 6. `examples/retry_error_resilience.ainl`
- Primary: `retry_error`
- Secondary: `failure_fallback`

```ainl
L1:
  R ext.OP "unstable_task" ->resp
  Retry @n1 2 0
  Err @n1 ->L_fail
  J resp
L_fail:
  Set out "failed_after_retries"
  J out
```

## 8. `examples/webhook_automation.ainl`
- Primary: `webhook_automation`
- Secondary: `validate_act_return`

```ainl
L1:
  Set is_valid true
  R http.POST "https://example.com/automation" "event_webhook" ->resp
  If is_valid ->L2 ->L3
L2:
  Set out "accepted"
  J out
L3:
  Set out "ignored"
  J out
```

## 10. `examples/monitor_escalation.ainl`
- Primary: `monitoring_escalation`
- Secondary: `scheduled_branch`

```ainl
S core cron
Cr L_tick "*/5 * * * *"

L_tick:
  R core.MAX 7 3 ->metric
  If metric ->L_escalate ->L_noop
L_escalate:
  Set out "escalate"
  J out
L_noop:
  Set out "noop"
  J out
```
