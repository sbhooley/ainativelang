# Canonical Workflow Pack

## 4. `examples/rag_pipeline.ainl`
- Primary: `call_return`
- Secondary: `label_modularity`

```ainl
L1: Call L9 ->out J out
L9:
  R core.ADD 40 2 ->v
  J v
```

## 5. `examples/if_call_workflow.ainl`
- Primary: `if_call_workflow`
- Secondary: `bound_call_result`

```ainl
L1:
  Call L8 ->has_payload
  If has_payload ->L2 ->L3
L8:
  Set v true
  J v
L2:
  Call L9 ->out
  J out
L3:
  Set out "missing_payload"
  J out
L9:
  R core.CONCAT "task_" "ready" ->res
  J res
```

## 7. `examples/web/basic_web_api.ainl`
- Primary: `web_endpoint`
- Secondary: `db_read`

```ainl
S core web /api
E /users G ->L_users ->users

L_users:
  R db.F User * ->users
  J users
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

## 9. `examples/scraper/basic_scraper.ainl`
- Primary: `scraper_cron`
- Secondary: `http_to_storage`

```ainl
S core cron
Sc products "https://example.com/products" title=.product-title price=.product-price
Cr L_scrape "0 * * * *"   # hourly

L_scrape:
  R http.GET "https://example.com/products" ->resp
  R db.C Product * ->stored
  J stored
```
