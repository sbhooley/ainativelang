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
  # Tier-0-style signatures only: "_" = all chunks (cap 100); or filter by file path.
  R code_context.GET_SKELETON "_" ->skel_all
  R code_context.GET_SKELETON "adapters/code_context.py" ->skel_file
  # Greedy pack: embedding ranking when embedding_memory is available, else TF–IDF; ~len//4 token estimate.
  R code_context.COMPRESS_CONTEXT "adapter" 4000 ->packed
  # Example chunk id for _tokenize in adapters/code_context.py (see QUERY_CONTEXT or .ainl_code_context.json if this drifts).
  R code_context.GET_DEPENDENCIES "fn:adapters/code_context.py:_tokenize@83:f024a60ce80a" ->deps
  R code_context.GET_IMPACT "fn:adapters/code_context.py:_tokenize@83:f024a60ce80a" ->impact
  # STATS: chunks, store_path, updated_at, plus num_nodes, num_edges, top_pagerank; "_" is a parse placeholder only.
  R code_context.STATS "_" ->stats
  J context
```

## 22. `examples/solana_demo.ainl`
- Primary: `solana_rpc_demo`
- Secondary: `blockhash_pyth_stringify`

```ainl
# examples/solana_demo.ainl
# Solana example — demonstrates R solana.VERB pattern. General blockchain adapters will use similar structure via blockchain_base.py.
# Strict demo: read-only Solana RPC + simulation (install solana+solders for live calls).
#
# Env (typical):
#   export AINL_SOLANA_RPC_URL=https://api.devnet.solana.com   # default if unset
#   export AINL_DRY_RUN=1                                      # safe: no real txs from mutating steps
# Optional caps: AINL_SOLANA_TOKEN_ACCOUNTS_LIMIT, AINL_SOLANA_GET_PROGRAM_ACCOUNTS_LIMIT
# GET_LATEST_BLOCKHASH below: read-only; with AINL_DRY_RUN=1 returns mock blockhash (no RPC).
#
# ainl-validate examples/solana_demo.ainl --strict
# ainl-validate examples/solana_demo.ainl --strict --emit solana-client -o solana_client.py
# cd /path/to/AI_Native_Lang && AINL_DRY_RUN=1 python3 solana_client.py
# AINL_SOLANA_DEMO_PREVIEW=1 AINL_DRY_RUN=1 python3 solana_client.py

L1:
  R solana.GET_ACCOUNT "11111111111111111111111111111111" ->sysprog
  R solana.GET_BALANCE "11111111111111111111111111111111" ->sysbal
  R solana.GET_LATEST_BLOCKHASH _ ->bh   # _ = strict-parse placeholder (no primary arg); use bh + dry-run txs to rehearse flows
  R solana.GET_SIGNATURES_FOR_ADDRESS "Vote111111111111111111111111111111111111111" 3 ->sigs
  R solana.SIMULATE_EVENTS "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA" ->evts
  R core.STRINGIFY sysbal ->sbal
  J sbal
```

## 23. `examples/prediction_market_demo.ainl`
- Primary: `solana_prediction_market`
- Secondary: `pda_pyth_invoke_payout`

```ainl
# examples/prediction_market_demo.ainl
# AINL v1.3.1 — Solana prediction markets (strict-valid on-ramp)
#
# This file demonstrates a full resolution → conditional payout pattern on Solana: read market state, resolve prices
# with Pyth on-chain (legacy + PriceUpdateV2) and/or Hermes off-chain, then rehearse settlement with INVOKE and
# ComputeBudget priority fees (micro-lamports per CU). Placeholders are compile-only; use real PDAs and feed pubkeys
# on your cluster for production.
#
# Single-quoted JSON for DERIVE_PDA seeds (recommended): R solana.DERIVE_PDA '["market","MY_MARKET"]' "<program_id>" ->pda
# — one lexer token; inner double quotes are literal (see docs/solana_quickstart.md and adapters/solana.py).
#
# Dry-run first: export AINL_DRY_RUN=1 for mock blockhash, Pyth/Hermes-shaped quotes, and simulated INVOKE/TRANSFER
# envelopes without sending transactions or requiring live keypairs for many paths.
#
# Broader guidance (env vars, compile flags, agent-oriented prompts): docs/solana_quickstart.md
#
# Validate / emit standalone client:
#   ainl-validate examples/prediction_market_demo.ainl --strict
#   ainl-validate examples/prediction_market_demo.ainl --strict --emit solana-client -o solana_client.py
#
# More (comment-only; strict graphs — wire labels/If as needed):
#   R solana.DERIVE_PDA '["market","MY_MARKET"]' "YourProgram1111111111111111111111111111111111" ->mkt_pda
#   R solana.GET_PYTH_PRICE "11111111111111111111111111111111" true ->px_v2   # prefer PriceUpdateV2 path
#   R solana.HERMES_FALLBACK ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d ->hq   # SOL/USD (Crypto.SOL/USD) feed id hex
#   # export AINL_PYTH_HERMES_URL=https://hermes.pyth.network   # optional; same default if unset
#   R solana.HERMES_FALLBACK ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d ->hq2   # duplicate example: explicit SOL/USD feed_id_hex

L1:
  R solana.GET_LATEST_BLOCKHASH _ ->bh
  R solana.GET_MARKET_STATE "11111111111111111111111111111111" ->mst
  R solana.GET_PYTH_PRICE "11111111111111111111111111111111" ->px
  # Conditional resolution → payout (strict graphs: use If on px.ok / threshold → label with INVOKE + priority fee):
  #   If px_ok ->Lpayout ->Lskip
  # Lpayout: R solana.INVOKE <program> <settlement_ix_b64> "[]" 5000 ->payout_sig
  # Lskip: J px
  R solana.INVOKE "11111111111111111111111111111111" "AA==" "[]" 5000 ->inv
  R core.STRINGIFY inv ->out
  J out
```

## 24. `examples/compact/hello_compact.ainl`
- Primary: `compute_return_compact`
- Secondary: `compact_syntax`

```ainl
# examples/compact/hello_compact.ainl
# The simplest compact AINL program.
# Equivalent to examples/hello.ainl but in compact syntax.

adder:
  result = core.ADD 2 3
  out result
```

## 25. `examples/compact/classifier_compact.ainl`
- Primary: `if_branching_compact`
- Secondary: `compact_syntax`

```ainl
# examples/compact/classifier_compact.ainl
# Multi-branch classifier in compact syntax.
# Demonstrates if/branching, inputs, and string outputs.

classifier:
  in: level message

  if level == "critical":
    out "ALERT: critical"

  if level == "warning":
    out "WARN: warning"

  out "INFO: logged"
```

## 26. `examples/compact/cache_lookup_compact.ainl`
- Primary: `cache_lookup_compact`
- Secondary: `compact_syntax`

```ainl
# examples/compact/cache_lookup_compact.ainl
# Cache-first pattern: check cache before calling API.

cached_fetch:
  in: url

  cached = cache.get url
  if cached:
    out cached

  fresh = http.GET url
  cache.set url fresh
  out fresh
```

## 27. `examples/rag/cache-warmer.ainl`
- Primary: `rag_cache_warmer`
- Secondary: `memory_and_cache`

```ainl
# examples/rag/cache-warmer.ainl
# RAG cache warmer — upserts fixed chunks into vector_memory, verifies with SEARCH,
# with an explicit ops budget gate (no runtime orchestration LLM).
#
# Run (local vector store):
#   python3 -m cli.main run examples/rag/cache-warmer.ainl --json --enable-adapter vector_memory
# Validate:
#   python3 scripts/validate_ainl.py examples/rag/cache-warmer.ainl --strict

S app core noop

L_start:
  # Budget gate: only warm when remaining ops budget allows (tune ops_used / ops_budget per deploy).
  X ops_budget 100
  X ops_used 2
  X within_budget (core.gt ops_budget ops_used)
  If within_budget ->L_warm ->L_skip

L_warm:
  R vector_memory.UPSERT "rag_warm" "chunk" "c1" "placeholder doc body for warming" "{}" ->u1
  R vector_memory.UPSERT "rag_warm" "chunk" "c2" "second chunk for cache priming" "{}" ->u2
  R vector_memory.SEARCH "placeholder" 4 ->hits
  J hits

L_skip:
  Set status "budget_exhausted"
  J status
```

## 28. `examples/crm/simple-lead-router.ainl`
- Primary: `crm_routing`
- Secondary: `http_and_filters`

```ainl
# examples/crm/simple-lead-router.ainl
# CRM lead router — score-based branch, ops budget gate, audit row via crm_db (SQLite).
# No runtime orchestration LLM. Set CRM_DB_PATH or rely on default under OPENCLAW_WORKSPACE/crm/prisma/dev.db.
#
# python3 scripts/validate_ainl.py examples/crm/simple-lead-router.ainl --strict
# python3 -m cli.main run examples/crm/simple-lead-router.ainl --json --enable-adapter crm_db

S app core noop

L_start:
  # Policy: max routing decisions per run (tune with your SLA / cost envelope).
  X route_budget 100
  X routes_used 0
  X policy_ok (core.gt route_budget routes_used)
  If policy_ok ->L_eval ->L_blocked

L_eval:
  # Representative score — in production, bind from CRM row (e.g. parse result_json from R crm_db F).
  # Use lead_score below 70 to exercise the nurture branch on the next run.
  X lead_score 82
  X hot (core.gt lead_score 70)
  If hot ->L_route_hot ->L_route_std

L_route_hot:
  R crm_db.P {"jobName": "lead:router", "status": "routed_hot", "result_json": "{\"score\":82,\"channel\":\"sales\",\"policy\":\"score_gt_70\"}"} ->_p
  Set decision "hot"
  J decision

L_route_std:
  R crm_db.P {"jobName": "lead:router", "status": "routed_std", "result_json": "{\"score\":65,\"channel\":\"nurture\",\"policy\":\"score_lte_70\"}"} ->_p
  Set decision "standard"
  J decision

L_blocked:
  Set decision "policy_block"
  J decision
```

## 29. `examples/enterprise/audit-log-demo.ainl`
- Primary: `audit_logging`
- Secondary: `structured_envelopes`

```ainl
# examples/enterprise/audit-log-demo.ainl
#
# Production-style audit demo: deterministic monitoring slice with explicit policy gates
# and JSONL execution tape suitable for SOC 2–style narratives (illustrative, not certification).
#
# ── CC7.2 (monitoring) — "continuous monitoring and feedback"
#   Each scheduled or on-demand run emits a chronological JSONL tape (node-level steps).
#   Retained tapes give reviewers a replay-oriented trail: what the graph evaluated, which
#   branch executed, and what outcome string was joined — without inferring intent from chat.
#   Pair tape retention, access control, and alerting with your SIEM / log management controls.
#
# ── CC8.1 (change management)
#   The `.ainl` source and `ainl check --strict` output are versionable artifacts; promote
#   the same graph IR through PR review and CI like any other code change.
#
# ── CC6.1 (logical access / capability boundaries)
#   This file uses only the `core` adapter so it runs in restricted sandboxes. In production,
#   you would attach http/email/chain adapters only where policy allows; undeclared effects
#   cannot appear in the compiled graph.
#
# Validate and capture tape (from repo root):
#   uv run ainl check examples/enterprise/audit-log-demo.ainl --strict
#   uv run ainl run examples/enterprise/audit-log-demo.ainl --trace-jsonl audit_demo.tape.jsonl
#
# Replay narrative for auditors: re-run the same binary graph with the same inputs; the tape
# reproduces the branch decision. For investigations, diff tapes across runs or correlate
# timestamps with external telemetry (outside AINL).

S app core noop

# Simulated KPIs — replace with adapter reads (HTTP health, chain RPC, queue depth) under your
# capability policy; keep thresholds as data your team reviews in PR.
L_tick:
  Set latency_ms 120
  Set error_rate_bp 15
  Set max_latency_ms 100
  Set max_error_bp 20
  X lat_bad (core.gt latency_ms max_latency_ms)
  If lat_bad ->L_violation ->L_err_check

L_err_check:
  X err_bad (core.gt error_rate_bp max_error_bp)
  If err_bad ->L_violation ->L_ok

L_violation:
  Set out "audit:policy_violation"
  J out

L_ok:
  Set out "audit:within_policy"
  J out
```

## 30. `examples/monitoring/solana-balance.ainl`
- Primary: `monitoring_solana_balance`
- Secondary: `scheduled_branch`

```ainl
# examples/monitoring/solana-balance.ainl
# Solana balance monitor — deterministic read of lamports, budget gate, no runtime LLM.
# Pair with cron or OpenClaw schedule; run with --trace-jsonl for JSONL audit tape.
#
# Env: AINL_SOLANA_RPC_URL (default devnet), AINL_DRY_RUN=1 to rehearse without live RPC pressure.
#
# ainl check examples/monitoring/solana-balance.ainl --strict
# AINL_DRY_RUN=1 ainl run examples/monitoring/solana-balance.ainl --trace-jsonl solana_balance.trace.jsonl

S app core noop

L_start:
  # System program as stable demo pubkey; replace with your wallet / vault to monitor.
  R solana.GET_BALANCE "11111111111111111111111111111111" ->bal
  X lamports get bal lamports
  # Budget gate: alert when balance is below min_lp lamports (tune per environment).
  X min_lp 500000000
  X below (core.gt min_lp lamports)
  If below ->L_alert ->L_ok

L_alert:
  Set status "below_budget"
  J status

L_ok:
  Set status "ok"
  J status
```

## 31. `examples/wishlist/01_cache_and_memory.ainl`
- Primary: `wishlist_cache_memory`
- Secondary: `adapter_cache_memory`

```ainl
# 1) Knowledge caching + structured memory (AINL: cache + memory adapters).
# ArmaraOS: pass session_key from host; set AINL_MEMORY_DB / paths via env policy.
#
# Run (from AI_Native_Lang repo root):
#   AINL_CACHE_JSON=/tmp/w01_cache.json AINL_MEMORY_DB=/tmp/w01_mem.sqlite3 \
#     python -m cli.main run examples/wishlist/01_cache_and_memory.ainl --json \
#     --frame '{"session_key":"sess1","note":"hello memory"}'
# Validate: python -m cli.main validate examples/wishlist/01_cache_and_memory.ainl --strict

wishlist_01_cache_and_memory:
  in: session_key note

  R cache.GET session_key ->cached
  if cached:
    out cached

  R core.concat "{\"note\":\"" note "\"}" ->blob
  R core.parse blob ->payload
  R memory.PUT "workflow" "turn" session_key payload null ->_m
  R cache.SET session_key note ->_
  out note
```

## 32. `examples/wishlist/02_vector_semantic_search.ainl`
- Primary: `wishlist_vector_semantic_search`
- Secondary: `vector_memory_search`

```ainl
# 2) Semantic-ish retrieval via vector_memory (keyword overlap scoring in core repo).
# ArmaraOS: point AINL_VECTOR_MEMORY_PATH at a host-writable file; optional retention policy in host.
#
# Run:
#   AINL_VECTOR_MEMORY_PATH=/tmp/w02_vm.json \
#     python -m cli.main run examples/wishlist/02_vector_semantic_search.ainl --json \
#     --frame '{"namespace":"sessions","doc_id":"d1","text":"asyncio task groups","query":"asyncio"}'
# Validate: python -m cli.main validate examples/wishlist/02_vector_semantic_search.ainl --strict

wishlist_02_vector_semantic_search:
  in: namespace doc_id text query

  R vector_memory.UPSERT namespace "chunk" doc_id text "{}" ->_u
  R vector_memory.SEARCH query 8 0.1 ->raw_hits
  R core.filter_high_score raw_hits 0.1 ->hits
  out hits
```

## 33. `examples/wishlist/03_parallel_fanout.ainl`
- Primary: `wishlist_fanout_parallel`
- Secondary: `fanout_adapter_plans`

```ainl
# 3) Parallel tool execution — fanout.ALL over adapter plans (thread pool).
# ArmaraOS: optional AINL_FANOUT_MAX_WORKERS / AINL_FANOUT_DISABLE for host policy.
#
# Run:
#   python -m cli.main run examples/wishlist/03_parallel_fanout.ainl --json
# Validate: python -m cli.main validate examples/wishlist/03_parallel_fanout.ainl --strict

wishlist_03_parallel_fanout:
  in:

  fan_json = "[[\"core\",\"add\",2,3],[\"core\",\"mul\",4,5],[\"core\",\"concat\",\"a\",\"b\"]]"
  R fanout.ALL fan_json ->results
  out results
```

## 34. `examples/wishlist/04_validate_with_ext.ainl`
- Primary: `wishlist_ext_validate`
- Secondary: `optional_ext_adapter`

```ainl
# 4) Automated validation — ext.EXEC runs a subprocess (e.g. py_compile).
# AINL: graph + ext adapter (env-gated). ArmaraOS: never pass user-controlled argv; set cwd + allowlist.
#
# Run (repo root; requires AINL_EXT_ALLOW_EXEC=1):
#   AINL_EXT_ALLOW_EXEC=1 python -m cli.main run examples/wishlist/04_validate_with_ext.ainl --json \
#     --enable-adapter ext \
#     --frame '{"py_file":"examples/wishlist/fixtures/syntax_ok.py"}'
# Validate: python -m cli.main validate examples/wishlist/04_validate_with_ext.ainl --strict

wishlist_04_validate_with_ext:
  in: py_file

  R ext.EXEC python3 -m py_compile py_file ->ex
  out ex
```

## 35. `examples/wishlist/05_route_then_llm_mock.ainl`
- Primary: `wishlist_llm_query_routing`
- Secondary: `llm_query_branch`

```ainl
# 5) Multi-model orchestration — route by keyword, then llm_query (mock or real bridge).
# Prefer unified llm + config.yaml: see 05b_unified_llm_offline_config.ainl + fixtures/llm_offline.yaml (docs/LLM_ADAPTER_USAGE.md).
# AINL: routing graph + llm_query.QUERY. ArmaraOS: API keys, AINL_LLM_QUERY_URL, and model policy live on the host.
#
# Run (deterministic mock; no network):
#   AINL_ENABLE_LLM_QUERY=true AINL_LLM_QUERY_MOCK=true \
#     python -m cli.main run examples/wishlist/05_route_then_llm_mock.ainl --json \
#     --enable-adapter llm_query \
#     --frame '{"user_query":"debug my rust borrow checker error"}'
# Validate: python -m cli.main validate examples/wishlist/05_route_then_llm_mock.ainl --strict

wishlist_05_route_then_llm_mock:
  in: user_query

  is_rust = core.contains user_query "rust"
  if is_rust:
    R llm_query.QUERY user_query "rust-expert" 256 ->out
    out out
  R llm_query.QUERY user_query "general-assistant" 256 ->out
  out out
```

## 36. `examples/wishlist/05b_unified_llm_offline_config.ainl`
- Primary: `wishlist_unified_llm_offline`
- Secondary: `llm_completion_fallback`

```ainl
# 5b) Same routing as 05 — unified `llm` adapter + config.yaml (see docs/LLM_ADAPTER_USAGE.md).
# Compare: `05_route_then_llm_mock.ainl` uses deprecated `llm_query` + mock env.
#
# Run (offline deterministic; no API keys):
#   python -m cli.main run examples/wishlist/05b_unified_llm_offline_config.ainl --json \
#     --config examples/wishlist/fixtures/llm_offline.yaml \
#     --frame-json '{"user_query":"debug my rust borrow checker error"}'
# Or:  export AINL_CONFIG=examples/wishlist/fixtures/llm_offline.yaml   (same command without --config)
# Live providers: copy fixtures/llm_openrouter.example.yaml or llm_ollama.example.yaml, set AINL_CONFIG, then run as above.
# Validate: python -m cli.main validate examples/wishlist/05b_unified_llm_offline_config.ainl --strict

wishlist_05b_unified_llm_offline_config:
  in: user_query

  is_rust = core.contains user_query "rust"
  if is_rust:
    R llm.COMPLETION user_query 256 ->resp_r
    R core.GET resp_r "content" ->out
    out out
  R llm.COMPLETION user_query 256 ->resp_g
  R core.GET resp_g "content" ->out
  out out
```

## 37. `examples/wishlist/06_feedback_memory.ainl`
- Primary: `wishlist_feedback_memory`
- Secondary: `memory_feedback_loop`

```ainl
# 6) Persistent learning loop — memory.APPEND for corrections; memory.GET reads prior turn payload.
# AINL: memory adapter. ArmaraOS: retention, encryption, and which namespaces are allowed for which agent.
#
# Run:
#   AINL_MEMORY_DB=/tmp/w06_mem.sqlite3 \
#     python -m cli.main run examples/wishlist/06_feedback_memory.ainl --json \
#     --frame '{"session_id":"u1","correction":"use pathlib instead of os.path"}'
# Validate: python -m cli.main validate examples/wishlist/06_feedback_memory.ainl --strict

wishlist_06_feedback_memory:
  in: session_id correction

  R core.concat "{\"correction\":\"" correction "\"}" ->blob
  R core.parse blob ->entry
  R memory.APPEND "workflow" "feedback" session_id entry null ->_a
  R memory.GET "workflow" "turn" session_id ->prior
  out prior
```

## 38. `examples/wishlist/07_parallel_http.ainl`
- Primary: `wishlist_fanout_http`
- Secondary: `fanout_http_get`

```ainl
# 7) Real-time data enrichment — parallel HTTP GET via fanout (independent I/O).
# AINL: http + fanout. ArmaraOS: HTTP allowlists, timeouts, and egress policy.
#
# This file uses opcode lines for the JSON plan string so URLs with ":" are not misparsed by compact.
#
# Run (needs network; from repo root):
#   python -m cli.main run examples/wishlist/07_parallel_http.ainl --json --enable-adapter http
# Validate: python -m cli.main validate examples/wishlist/07_parallel_http.ainl --strict

S app core noop

L1:
  Set fan_json "[[\"http\",\"GET\",\"http://example.com/\"],[\"http\",\"GET\",\"http://example.com/\"]]"
  R fanout.ALL fan_json ->bundle
  J bundle
```

## 39. `examples/wishlist/08_code_review_context.ainl`
- Primary: `wishlist_code_review_context`
- Secondary: `code_context_pack`

```ainl
# 8) Code-review style context pack — INDEX then QUERY + COMPRESS (sequential; code_context is not fanout-safe).
# For parallel *pure* fanout patterns see 03; for HTTP see 07.
# AINL: code_context + core. ArmaraOS: workspace root, adapter allowlist, optional llm keys for review.
#
# Run (from AI_Native_Lang repo root; enable code_context):
#   python -m cli.main run examples/wishlist/08_code_review_context.ainl --json \
#     --enable-adapter code_context
# Validate: python -m cli.main validate examples/wishlist/08_code_review_context.ainl --strict

wishlist_08_code_review_context:
  in:

  R code_context.INDEX "examples/wishlist" ->_idx
  R code_context.QUERY_CONTEXT "syntax" 1 6 ->ctx
  R code_context.COMPRESS_CONTEXT "syntax" 1200 ->packed
  R core.concat ctx "\n---\n" packed ->bundle
  out bundle
```

## 40. `examples/api_only.lang`
- Primary: `api_only_rest`
- Secondary: `rest_api_definitions`

```ainl
# API-only: no frontend, core service and types
S core web /api

D User id:I name:S email:S
D Session id:I userId:I token:S expires:D

E /users G ->L1 ->users
E /users P ->L2 ->user
E /sessions G ->L3 ->sessions

L1:
  R db.F User * ->users
  J users
L2:
  R db.P User * ->user
  J user
L3:
  R db.F Session * ->sessions
  J sessions
```

## 41. `examples/blog.lang`
- Primary: `blog_web_app`
- Secondary: `content_management`

```ainl
# Blog: posts and comments, full stack
S core web /api
S fe web /

D Post id:I title:S body:S created:D author:S
D Comment id:I postId:I body:S author:S created:D

E /posts G ->L1 ->posts
E /posts P ->L2 ->post
E /comments G ->L3 ->comments
E /comments P ->L4 ->comment

Rt / PostList
Rt /posts PostList
Rt /post PostDetail
Rt /comments CommentList
Lay Shell Sidebar Main

U PostList posts
T posts:A[Post]
U PostDetail post
T post:Post
U CommentList comments
T comments:A[Comment]
Fm CommentForm Comment body author
Tbl PostList Post id title author created
Tbl CommentList Comment id body author created

C cache postList 3600

L1:
  R db.F Post * ->posts
  J posts
L2:
  R db.P Post * ->post
  J post
L3:
  R db.F Comment * ->comments
  J comments
L4:
  R db.P Comment * ->comment
  J comment
```

## 42. `examples/ecom.lang`
- Primary: `ecom_storefront`
- Secondary: `ecommerce_workflow`

```ainl
# Ecom dashboard + Stripe pay (explicit E binding + routes, layout, forms, tables, events)
S core web /api
S fe web /

D Product id:I name:S price:F sku:S
D Order id:I uid:I total:F status:E[Pending,Paid,Shipped]

E /products G ->L1 ->products
E /orders G ->L2 ->orders
E /checkout P ->L3

Rt / Dashboard
Rt /products ProductList
Rt /orders OrderTable
Lay Shell Sidebar Main

U Dashboard
T products:A[Product]
T orders:A[Order]
U ProductList products
U OrderTable orders
U CheckoutBtn

Fm OrderForm Order id uid total status
Tbl OrderTable Order id uid total status
Tbl ProductList Product id name price sku

Ev CheckoutBtn click /checkout

P checkout 1999 usd "Order payment"

C cart sessionId 3600

L1:
  R db.F Product * ->products
  J products
L2:
  R db.F Order * ->orders
  J orders
L3:
  R db.F Order * ->ord
  J ord
```

## 43. `examples/internal_tool.lang`
- Primary: `internal_tool`
- Secondary: `admin_crud`

```ainl
# Internal tool: tasks and users (API + minimal frontend)
S core web /api
S fe web /

D Task id:I title:S assignee:I status:E[Todo,InProgress,Done] due:D
D User id:I name:S email:S role:E[Admin,User]

E /tasks G ->L1 ->tasks
E /tasks P ->L2 ->task
E /users G ->L3 ->users

Rt / TaskBoard
Rt /tasks TaskList
Rt /users UserList
Lay Shell Sidebar Main

U TaskBoard tasks
T tasks:A[Task]
U TaskList tasks
T tasks:A[Task]
U UserList users
T users:A[User]
Fm TaskForm Task title assignee status due
Tbl TaskList Task id title assignee status due
Tbl UserList User id name email role

Cr L1 */15 * * * *

L1:
  R db.F Task * ->tasks
  J tasks
L2:
  R db.P Task * ->task
  J task
L3:
  R db.F User * ->users
  J users
```

## 44. `examples/ticketing.lang`
- Primary: `ticketing_system`
- Secondary: `issue_tracking`

```ainl
# Ticketing: events and tickets
S core web /api
S fe web /
A jwt Authorization

D Event id:I name:S venue:S date:D capacity:I
D Ticket id:I eventId:I uid:I status:E[Reserved,Paid,Cancelled]

E /events G ->L1 ->events
E /events P ->L2 ->event
E /tickets G ->L3 ->tickets
E /tickets P ->L4 ->ticket
E /my-tickets G ->L5 ->tickets

Rt / Dashboard
Rt /events EventList
Rt /event EventDetail
Rt /my-tickets MyTickets
Lay Shell Nav Main

U Dashboard
U EventList events
T events:A[Event]
U EventDetail event
T event:Event
U MyTickets tickets
T tickets:A[Ticket]
Tbl EventList Event id name venue date capacity
Tbl MyTickets Ticket id eventId status
Fm TicketForm Ticket eventId uid status

P reserve 999 usd "Ticket reservation"

L1:
  R db.F Event * ->events
  J events
L2:
  R db.P Event * ->event
  J event
L3:
  R db.F Ticket * ->tickets
  J tickets
L4:
  R db.P Ticket * ->ticket
  J ticket
L5:
  R db.F Ticket * ->tickets
  J tickets
```

## 45. `examples/openclaw/daily_lead_summary.lang`
- Primary: `daily_lead_summary`
- Secondary: `crm_digest`

```ainl
# Daily Lead Summary (simplified)
# Reports number of leads created in the last day.
S core cron "0 7 * * *"

D Config lookback_days:N
D State last_run:T

L0:
    R core now ->ts
    R cache get "state" "last_run" ->last_run
    R core sub ts 86400 ->cutoff
    R db F ->rows
    X total len rows
    R core stringify total ->s_total
    R core concat "Leads: " s_total ->summary
    X notify_payload obj text summary
    R queue Put notify notify_payload ->_
    R cache set "state" "last_run" ts ->_
```

## 46. `examples/openclaw_full_unification.ainl`
- Primary: `openclaw_full_unification`
- Secondary: `workspace_unification`

```ainl
# Meta-supervisor sample — polls health endpoint and writes a status log entry.
# Runs every 15 minutes via cron.
S core cron "*/15 * * * *"

L0:
  R http.GET "http://localhost:4200/api/health" ->st
  R core.concat "supervisor status=" st ->line
  R memory.put "ops" "supervisor" "status" line 86400 {} ->_
  J st
```

## 47. `examples/test_if_var.ainl`
- Primary: `if_var_branch`
- Secondary: `conditional_branch`

```ainl
S app core noop

L0:
  R core.sub 100 85 ->x
  If x ->L2 ->L3

L2:
  J "true"

L3:
  J "false"
```

## 48. `examples/test_mul.ainl`
- Primary: `multiply_ops`
- Secondary: `arithmetic_mul`

```ainl
S app core noop

L0:
  R core.sub 100 85 ->x
  R core.mul x 2 ->y
  J y
```

## 49. `examples/test_X_sub.ainl`
- Primary: `subtract_expr`
- Secondary: `arithmetic_sub`

```ainl
S app core noop

L0:
  X diff (core.sub 100 85)
  X out (core.mul diff 2)
  J out
```

## 50. `examples/compact/openclaw_learning_handoff.ainl`
- Primary: `openclaw_learning_handoff`
- Secondary: `learning_digest`

```ainl
# OpenClaw ↔ AINL pipeline handoff (template).
# ClawHub skills capture into ~/.openclaw/workspace/.learnings/; export script
# promotes a digest into memory/. This graph is the slot where a host passes
# promoted text or JSON into AINL as inputs — replace with real ops as needed.

openclaw_handoff:
  in: digest_summary
  merged = core.CONCAT "openclaw_stage=ainl_ingest " digest_summary
  out merged
```
