# AINL Documentation

This is the primary navigation hub for the `docs/` tree.

AINL docs are organized by user intent and conceptual layer rather than by file creation history. Start here if you want the shortest path to the right section. Use [`DOCS_INDEX.md`](DOCS_INDEX.md) as the exhaustive reference map.

## Sections

- [`overview/`](overview/README.md) — what AINL is, who it is for, and top-level orientation
- [`fundamentals/`](fundamentals/README.md) — why AINL exists and the core conceptual problems it addresses
- [`getting_started/`](getting_started/README.md) — first steps, onboarding, and “start here” implementation paths
- [`architecture/`](architecture/README.md) — system design, canonical IR, and compiler/runtime structure
- [`runtime/`](runtime/README.md) — execution semantics, runtime behavior, and safety boundaries
- [`language/`](language/README.md) — language definition, grammar, and canonical scope
- [`adapters/`](adapters/README.md) — adapters, capabilities, and host integration surfaces
- [`emitters/`](emitters/README.md) — multi-target output surfaces and emitter philosophy
- [`examples/`](examples/README.md) — example support levels, walkthroughs, and example-oriented guidance
- [`case_studies/`](case_studies/README.md) — narrative proof, production lessons, and applied explanations
- [`competitive/`](competitive/README.md) — comparative framing and “AINL vs X” materials
- [`operations/`](operations/README.md) — autonomous ops, monitors, and deployment-style operational docs
- [`advanced/`](advanced/README.md) — operator-only, OpenClaw, and advanced coordination surfaces
- [`reference/`](reference/README.md) — schemas, contracts, indexes, and reference-style maps

## Recommended paths

- New to the project: start with [`overview/`](overview/README.md), then [`getting_started/`](getting_started/README.md)
- Trying to understand the category: read [`fundamentals/`](fundamentals/README.md)
- Implementing or extending AINL: read [`language/`](language/README.md), [`architecture/`](architecture/README.md), and [`runtime/`](runtime/README.md)
- Working with integrations or OpenClaw: read [`adapters/`](adapters/README.md) and [`advanced/`](advanced/README.md)
- Looking for proof and practical examples: read [`case_studies/`](case_studies/README.md) and [`operations/`](operations/README.md)

## Notes

- **Graph diagrams (Mermaid):** root `README.md` → *Visualize your workflow*; details in [`architecture/GRAPH_INTROSPECTION.md`](architecture/GRAPH_INTROSPECTION.md) §7 (`ainl visualize`, `ainl-visualize`).
- `DOCS_INDEX.md` remains in place as the detailed reference map.
- Existing paths will be migrated gradually to avoid breaking relative links and old deep links.
- `case_studies/` is the canonical case-study folder name going forward.
