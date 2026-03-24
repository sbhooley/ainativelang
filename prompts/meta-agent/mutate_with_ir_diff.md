Task: Mutate candidate workflow B from baseline A while preserving safety constraints.

Inputs:
- `ainl inspect` output for A and B
- `ainl_ir_diff` JSON
- optional `ainl_fitness_report`

Goals:
- Keep privilege tiers <= baseline unless explicitly allowed.
- Improve fitness score without adding forbidden adapters.
- Emit updated `.ainl` source plus a short rationale tied to diff fields.
