# Meta-Agent Prompt Library

Few-shot prompts for generating safe, deterministic AINL workflows in self-improving research loops.

- Use strict-friendly ops and explicit `LENTRY` / `LEXIT_*` contracts.
- Prefer adapter calls with explicit outputs (`->var`) and explicit joins (`J var`).
- Keep side effects capability-scoped and observable via trace JSONL.
