# Canonical Starter Pack

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
