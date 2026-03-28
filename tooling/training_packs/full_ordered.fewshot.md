# Canonical Full Ordered Pack

## 1. `examples/hello.ainl`
- Primary: `compute_return`
- Secondary: `none`

```ainl
# examples/hello.ainl
# The simplest possible AINL program — a good starting point.
#
# AINL programs are compiled graphs. Each "label" (L1:, L2:, END) is a node.
# Control flow is explicit: every node ends with a J (join/return) that passes
# a value to the runtime, or an If (...) that branches to another label.
#
# Syntax cheat-sheet:
#   S <scope> <adapter> <path>     — header: declares the program surface
#   X <var> <literal>              — assign a literal to a variable
#   R <adapter>.<op> [args] -><v>  — Request: call an adapter operation
#   J <var>                        — Join: return the value and finish this node
#   If (<expr>) -><then> -><else>  — conditional branch
#
# Run this file:
#   ainl check examples/hello.ainl --strict
#   ainl run   examples/hello.ainl
#   ainl visualize examples/hello.ainl --output -   # Mermaid diagram

S app core noop

L1:
  # Use the built-in core.ADD operation to add two numbers.
  # The result is bound to the variable `sum`.
  R core.ADD 2 3 ->sum
  J sum
```

## 2. `examples/crud_api.ainl`
- Primary: `if_branching`
- Secondary: `set_literals`

```ainl
L1: Set flag true If flag ->L2 ->L3
L2: Set out "ok" J out
L3: Set out "bad" J out
```

## 3. `examples/rag_pipeline.ainl`
- Primary: `call_return`
- Secondary: `label_modularity`

```ainl
L1: Call L9 ->out J out
L9:
  R core.ADD 40 2 ->v
  J v
```

## 4. `examples/if_call_workflow.ainl`
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

## 5. `examples/retry_error_resilience.ainl`
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

## 6. `examples/web/basic_web_api.ainl`
- Primary: `web_endpoint`
- Secondary: `db_read`

```ainl
S core web /api
E /users G ->L_users ->users

L_users:
  R db.F User * ->users
  J users
```

## 7. `examples/webhook_automation.ainl`
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

## 8. `examples/scraper/basic_scraper.ainl`
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

## 9. `examples/monitor_escalation.ainl`
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

## 10. `examples/cron/monitor_and_alert.ainl`
- Primary: `cron_db_metric_branch`
- Secondary: `scheduled_branch`

```ainl
S core cron
Cr L_monitor "*/5 * * * *"   # every 5 minutes

L_monitor:
  R db.F Metric * ->metrics
  If metrics ->L_alert ->L_ok

L_alert:
  R http.Post "https://hook.example.com/alert" metrics ->ack
  J ack

L_ok:
  J metrics
```

## 11. `examples/status_branching.ainl`
- Primary: `status_branching`
- Secondary: `if_branching`

```ainl
L1:
  Set status "ok"
  If status=ok ->L2 ->L3
L2:
  Set out "ok"
  J out
L3:
  Set out "alerted"
  J out
```

## 12. `examples/timeout_demo.ainl`
- Primary: `include_timeout_call`
- Secondary: `subgraph_entry`

```ainl
# timeout_demo.ainl
# Minimal include-based timeout demo using the strict-safe timeout starter module.

include "modules/common/timeout.ainl" as timeout

L1:
  Call timeout/ENTRY ->out
  J out
```

## 13. `examples/timeout_memory_prune_demo.ainl`
- Primary: `timeout_memory_workflow`
- Secondary: `memory_put_list_prune`

```ainl
# examples/timeout_memory_prune_demo.ainl
# Strict-safe demo: timeout starter + workflow memory put/list/prune.
# Good graph for visualizer PNG export, e.g.:
#   ainl visualize examples/timeout_memory_prune_demo.ainl --png docs/assets/timeout_memory_prune_flow.png

include "modules/common/timeout.ainl" as timeout

L1:
  Call timeout/ENTRY ->out
  R core.parse "{\"source\":\"timeout_memory_demo\",\"confidence\":1.0,\"tags\":[\"demo\"],\"valid_at\":\"2026-01-01T00:00:00Z\"}" ->memory_meta
  R core.parse "{\"tags_any\":[\"demo\"],\"source\":\"timeout_memory_demo\",\"limit\":10}" ->memory_filters
  R core.parse "{\"step\":\"timeout_demo\"}" ->record_payload
  R memory put "workflow" "demo_flow" "after_timeout" record_payload 3600 memory_meta ->_w
  R memory list "workflow" "demo_flow" "after" "1970-01-01T00:00:00Z" memory_filters ->hist
  R memory prune "workflow" ->_pr
  J out
```

## 14. `examples/hybrid/langchain_tool_demo.ainl`
- Primary: `langchain_tool_adapter`
- Secondary: `dotted_adapter_call`

```ainl
# examples/hybrid/langchain_tool_demo.ainl
# Hybrid LangChain interop: call a tool by name through the langchain_tool adapter.
#
# Run (from repo root):
#   python3 -m cli.main run examples/hybrid/langchain_tool_demo.ainl --json \
#     --enable-adapter langchain_tool
#
# Strict validate:
#   python3 scripts/validate_ainl.py examples/hybrid/langchain_tool_demo.ainl --strict
#
# The bundled demo registers a stub for tool name "my_search_tool" inside the adapter.
# For real LangChain tools, use register_langchain_tool("name", tool) in Python before run.

L1:
  # Dotted verb = tool name (strict allowlist includes MY_SEARCH_TOOL for this demo).
  # Use a frame var for multi-word text (spaces break R-slot tokenization).
  Set q "example query"
  # Tokenization: use `->result` (no space) so the output slot is not parsed as extra args.
  R langchain_tool.my_search_tool q ->result
  J result
```

## 15. `examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl`
- Primary: `langgraph_ainl_core_slice`
- Secondary: `metric_threshold_summary`

```ainl
# examples/hybrid/langgraph_outer_ainl_core/monitoring_escalation.ainl
# Deterministic "monitoring slice": compare metric vs threshold and stringify for handoff.
# Wrapped by monitoring_escalation_langgraph.py (emit with validate_ainl --emit langgraph).

L1:
  Set metric_value 42
  Set threshold 40
  R core.sub metric_value threshold ->diff
  R core.stringify diff ->summary
  J summary
```

## 16. `examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl`
- Primary: `temporal_ainl_activity_slice`
- Secondary: `metric_threshold_summary`

```ainl
# examples/hybrid/temporal_durable_ainl/monitoring_durable.ainl
# Compact deterministic slice: metric vs threshold → summary string.
# Compiled IR is embedded in emitted *_activities.py for Temporal workers.

L1:
  Set metric_value 42
  Set threshold 40
  R core.sub metric_value threshold ->diff
  R core.stringify diff ->summary
  J summary
```

## 17. `examples/hyperspace_demo.ainl`
- Primary: `hyperspace_multi_adapter_modules`
- Secondary: `includes_vector_tool_registry`

```ainl
# examples/hyperspace_demo.ainl
# Demo: common modules + local vector_memory / tool_registry (strict-safe dotted verbs).
#
# ainl-validate examples/hyperspace_demo.ainl --strict
# ainl run examples/hyperspace_demo.ainl --enable-adapter vector_memory --enable-adapter tool_registry --log-trajectory --json
# ainl-validate examples/hyperspace_demo.ainl --strict --emit hyperspace -o demo_agent.py
# cd /path/to/AI_Native_Lang && AINL_LOG_TRAJECTORY=1 python3 demo_agent.py

include "modules/common/guard.ainl" as guard
include "modules/common/session_budget.ainl" as sb

L1:
  Set guard_skip false
  Set guard_tokens_used 0
  Set guard_max_tokens 500
  Set guard_elapsed_sec 0
  Set guard_max_duration_sec 3600
  Set guard_condition_ok true
  Set guard_audit false
  Call guard/ENTRY ->g_out
  Set budget_tokens_start 0
  Set budget_tokens_delta 1
  Set budget_max_tokens 10000
  Set budget_time_start 0
  Set budget_time_delta_sec 0
  Set budget_max_duration_sec 86400
  Set budget_log_memory false
  Call sb/ENTRY ->b_out
  R vector_memory.UPSERT "demo" "note" "n1" "hyperspace demo vector text" "{}" ->vm_u
  R vector_memory.SEARCH "vector" 3 ->vm_hits
  R tool_registry.REGISTER "demo_tool" "Hyperspace demo capability" "{}" ->tr_reg
  R tool_registry.LIST "." ->tr_list
  R tool_registry.DISCOVER "." ->tr_disc
  R core.STRINGIFY vm_hits ->s_hits
  R core.STRINGIFY tr_list ->s_list
  R core.STRINGIFY tr_disc ->s_disc
  R core.concat g_out " | " ->p1
  R core.concat p1 b_out ->p2
  R core.concat p2 " | " ->p3
  R core.concat p3 s_hits ->p4
  R core.concat p4 " | " ->p5
  R core.concat p5 s_list ->p6
  R core.concat p6 " | " ->p7
  R core.concat p7 s_disc ->out
  J out
```

## 18. `examples/test_adapters_full.ainl`
- Primary: `vector_tool_registry_adapters`
- Secondary: `stringify_concat_summary`

```ainl
# examples/test_adapters_full.ainl
# Phase 3+ consolidation: vector_memory + tool_registry (strict-safe dotted R verbs).
#
# Validate:
#   python3 scripts/validate_ainl.py examples/test_adapters_full.ainl --strict
# Run:
#   python3 -m cli.main run examples/test_adapters_full.ainl --json \
#     --enable-adapter vector_memory --enable-adapter tool_registry
# Emit Hyperspace wrapper:
#   python3 scripts/validate_ainl.py examples/test_adapters_full.ainl --emit hyperspace -o /tmp/full_agent.py
#   cd /path/to/AI_Native_Lang && AINL_LOG_TRAJECTORY=1 python3 /tmp/full_agent.py
#   (writes test_adapters_full.trajectory.jsonl in cwd when env set)

L1:
  R vector_memory.UPSERT "demo_ns" "chunk" "doc1" "hello semantic adapter test" "{}" ->vm_u
  R vector_memory.SEARCH "semantic" 5 ->vm_hits
  R tool_registry.REGISTER "demo_tool" "Demonstration tool" "{}" ->tr_reg
  R tool_registry.LIST "." ->tr_list
  R tool_registry.DISCOVER "." ->tr_disc
  R tool_registry.GET "demo_tool" ->tr_get
  R core.STRINGIFY vm_hits ->s_hits
  R core.STRINGIFY tr_list ->s_list
  R core.STRINGIFY tr_disc ->s_disc
  R core.STRINGIFY tr_get ->s_get
  R core.concat s_hits "\n" ->a1
  R core.concat a1 s_list ->a2
  R core.concat a2 "\n" ->a3
  R core.concat a3 s_disc ->a4
  R core.concat a4 "\n" ->a5
  R core.concat a5 s_get ->summary
  J summary
```

## 19. `examples/test_nested.ainl`
- Primary: `nested_expr_arithmetic`
- Secondary: `core_mul_sub`

```ainl
L0: R core.mul (core.sub 100 85) 2 ->y J y
```

## 20. `examples/test_phase2_common_modules.ainl`
- Primary: `common_modules_guard_budget_reflect`
- Secondary: `sequential_module_calls`

```ainl
# examples/test_phase2_common_modules.ainl
# Phase 2 smoke: guard, session_budget, reflect (strict-safe frame bindings).
# Run: python3 scripts/validate_ainl.py --strict --strict-reachability examples/test_phase2_common_modules.ainl
#      python3 -m cli.main run examples/test_phase2_common_modules.ainl --log-trajectory --json --enable-adapter api --enable-adapter memory

include "modules/common/guard.ainl" as guard
include "modules/common/session_budget.ainl" as sb
include "modules/common/reflect.ainl" as reflect

L1:
  Set guard_skip false
  Set guard_tokens_used 5
  Set guard_max_tokens 100
  Set guard_elapsed_sec 1
  Set guard_max_duration_sec 3600
  Set guard_condition_ok true
  Set guard_audit false
  Call guard/ENTRY ->g_out

  Set budget_tokens_start 10
  Set budget_tokens_delta 5
  Set budget_max_tokens 100
  Set budget_time_start 0
  Set budget_time_delta_sec 1
  Set budget_max_duration_sec 9999
  Set budget_log_memory false
  Call sb/ENTRY ->b_out

  Set reflect_trajectory_text ""
  Set reflect_traj_nonempty 0
  Set reflect_has_fail_pattern false
  Set reflect_abort false
  Call reflect/ENTRY ->r_ok

  Set reflect_trajectory_text "{\"outcome\": \"fail\"}"
  Set reflect_traj_nonempty 1
  Set reflect_has_fail_pattern true
  Set reflect_abort false
  Call reflect/ENTRY ->r_adj

  Set guard_skip false
  Set guard_tokens_used 500
  Set guard_max_tokens 10
  Set guard_elapsed_sec 1
  Set guard_max_duration_sec 3600
  Set guard_condition_ok true
  Set guard_audit false
  Call guard/ENTRY ->g_viol

  R core.ECHO "done" ->done
  J done
```

## 21. `examples/code_context_demo.ainl`
- Primary: `code_context_adapter`
- Secondary: `none`

```ainl
# examples/code_context_demo.ainl
# Tiered code index demo (ctxzip-style) via the optional code_context adapter.
# Also exercises forgeindex-inspired dependency / impact / COMPRESS_CONTEXT (see docs).
#
# Run from repo root (indexes "." — this repository):
#   python3 -m cli.main run examples/code_context_demo.ainl --json \
#     --enable-adapter code_context
#
# Strict validate:
#   python3 scripts/validate_ainl.py examples/code_context_demo.ainl --strict
#
# Credits: BradyD2003/ctxzip (Brady Drexler); chrismicah/forgeindex (Chris Micah) — see docs/adapters/CODE_CONTEXT.md.

S app core noop

L1:
  # Build / refresh the JSON store (default: .ainl_code_context.json in cwd).
  R code_context.INDEX "." ->_idx
  # Tier 1: TF–IDF-ranked signatures + one-line summaries (limit 5 chunks).
  R code_context.QUERY_CONTEXT "adapter" 1 5 ->context
  # Greedy pack: TF–IDF order, stop when estimated tokens exceed budget (~len//4).
  R code_context.COMPRESS_CONTEXT "adapter" 4000 ->packed
  # Example chunk id for _tokenize in adapters/code_context.py (see QUERY_CONTEXT or .ainl_code_context.json if this drifts).
  R code_context.GET_DEPENDENCIES "fn:adapters/code_context.py:_tokenize@83:f024a60ce80a" ->deps
  R code_context.GET_IMPACT "fn:adapters/code_context.py:_tokenize@83:f024a60ce80a" ->impact
  # STATS has no logical args; "_" is a parse placeholder only (adapter ignores it).
  R code_context.STATS "_" ->stats
  J context
```
