---
title: Validation Deep Dive
description: Reachability analysis, strict diagnostics, and JSONL execution tape for transparent workflow validation.
order: 16
---

# Validation Deep Dive

AINL validation exists to catch workflow defects before runtime and to make failures inspectable when they do occur. This page explains the practical safety model and how to use it in daily development.

## What validation checks

### Reachability analysis

The compiler validates graph connectivity and control-flow reachability so dead labels and impossible branches are caught early. This reduces hidden branches that only fail under edge input at runtime.

### Strict mode diagnostics

`ainl check --strict` enforces the strongest guarantees currently available in the public compiler/runtime lane:

- no undeclared references
- no unknown adapter operations
- duplicate/unreachable node detection
- call/return shape consistency
- controlled exits and graph integrity

Diagnostics are structured and actionable. They are available in human-readable output and machine-readable JSON.

### JSONL execution tape

When you execute with tracing enabled, AINL can emit a JSONL execution tape for audit and replay analysis. This records step-level behavior with deterministic runtime context, so incident review is based on observed execution rather than prompt transcript reconstruction.

## Example: strict check on a broken workflow

Broken `broken.ainl`:

```ainl
S app api /api
L1:
  R core.ADD 2 3 ->sum
  J L9
```

Run:

```bash
ainl check broken.ainl --strict
```

Representative output shape:

```text
error: jump target 'L9' is not declared
 --> broken.ainl:4
suggestion: declare L9 or return a value directly from L1
```

Suggested repair:

```ainl
S app api /api
L1:
  R core.ADD 2 3 ->sum
  J sum
```

Re-run:

```bash
ainl check broken.ainl --strict
```

Then execute with tape:

```bash
ainl run broken.ainl --trace-jsonl run.trace.jsonl
```

## What the compiler catches that prompt loops miss

Prompt loops can produce plausible text while silently drifting in control flow. The compiler catches classes of defects that are easy to miss in prompt-only orchestration:

- invalid or missing branch targets
- unreachable workflow branches
- undeclared state references
- adapter contract mismatches
- malformed graph exits

This is the core difference between "the model seems right in chat" and "the workflow is valid, repeatable, and auditable in production."

## Enterprise and SOC 2 mapping

For teams mapping validation, policy gates, and execution tape to audit narratives (e.g., logical access and monitoring), see **[`docs/enterprise/SOC2_CHECKLIST.md`](enterprise/SOC2_CHECKLIST.md)**. It is guidance only, not legal advice — pair with your GRC process and counsel.
