# Debugging AINL graphs with enhanced diagnostics and the visualizer

> v1.3.4 feature guide. All commands use `ainl` (or `python -m cli.main`).

## Overview

Two new flags make it much easier to understand why a graph fails strict validation:

| Flag | Command | What it does |
|------|---------|--------------|
| `--enhanced-diagnostics` | `ainl check`, `ainl validate`, `scripts/validate_ainl.py` | Attaches `graph_context` (human description of where the error sits) and `mermaid_snippet` (1-hop Mermaid fragment) to each diagnostic |
| `--highlight-errors` | `ainl visualize` | Post-processes Mermaid output to style error nodes in red |

Both are **additive and default-off**. `--enhanced-diagnostics` auto-enables when `--strict` is set.

---

## Step 1 — Reproduce a strict compile error

Create a file with an unreachable node:

```ainl
# bad_graph.ainl
S app core noop

L1:
  R core.ADD 2 3 ->result
  J result
  R core.SUB 9 1 ->dead   # unreachable after J
```

Run strict validation:

```bash
ainl check bad_graph.ainl --strict
```

You'll see a structured error. The exit code will be 1.

---

## Step 2 — Add `--enhanced-diagnostics` for richer output

```bash
ainl check bad_graph.ainl --strict --enhanced-diagnostics
```

The JSON output now includes two new fields in each diagnostic object:

```json
{
  "kind": "unreachable_node",
  "message": "...",
  "label_id": "L1",
  "node_id": "n3",
  "graph_context": "unreachable node 'n3' in label 'L1' (node appears after a terminal join — dead code path)",
  "mermaid_snippet": "graph TD\n    L1_n2[...] --> L1_n3[...]\n"
}
```

For machine-readable output, add `--diagnostics-format json`:

```bash
ainl check bad_graph.ainl --strict --enhanced-diagnostics --diagnostics-format json \
  | python3 -m json.tool
```

Via `scripts/validate_ainl.py` directly (same behavior):

```bash
python scripts/validate_ainl.py bad_graph.ainl --strict --enhanced-diagnostics \
  --diagnostics-format json
```

---

## Step 3 — Visualize with error highlighting

`--highlight-errors` only applies when the compiled IR includes `structured_diagnostics` (the visualizer reads them from the IR and then post-processes the Mermaid).

Important caveat: if the file **fails strict compilation** (for example, a missing `include`), `ainl visualize` exits non-zero and prints structured diagnostics **instead of Mermaid**. That is correct behavior.

```bash
ainl visualize bad_graph.ainl --highlight-errors --output - > /tmp/bad_graph.mmd
```

The generated Mermaid file will contain lines like:

```
classDef errorstyle fill:#ffcccc,stroke:#f00
class L1_n3 errorstyle
```

---

## Step 4 — Render a screenshot (optional)

If you have the `mmdc` CLI from `@mermaid-js/mermaid-cli`:

```bash
mmdc -i /tmp/bad_graph.mmd -o /tmp/bad_graph.png
```

Or render directly via AINL’s built-in image export (requires the local renderer dependencies used by `ainl visualize` in your environment):

```bash
ainl visualize bad_graph.ainl --output /tmp/bad_graph.png
```

Or paste the Mermaid output into [mermaid.live](https://mermaid.live) to view it interactively. Error nodes will be highlighted in pink/red.

---

## Tips

- `--enhanced-diagnostics` is automatically active when `--strict` or `--strict-reachability` is used, so you get graph context by default in strict mode.
- The `mermaid_snippet` field is a self-contained `graph TD` block showing the failing node plus its immediate predecessors/successors — paste it into any Mermaid renderer.
- For CI, combine with `--diagnostics-format json` to parse `graph_context` in your error reporter.
- If the secondary non-strict compile also fails (e.g. deeply broken source), `graph_context` and `mermaid_snippet` stay `null` — the primary diagnostic is still complete.

---

## Related

- [Production: Estimates & Audit Trail](production_with_estimates_and_audit.md)
- [AINL visualize command](../../AGENTS.md) — `ainl visualize <file> --output -` for Mermaid stdout
- `ainl check --help` for all flags
