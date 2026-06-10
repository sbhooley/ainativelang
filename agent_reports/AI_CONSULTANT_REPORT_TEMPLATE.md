# AI Consultant Report Template

**Date:** YYYY-MM-DD
**Session:** <session-id>
**Role:** Consultant & Developer — AINL <integration/analysis topic>

---

## Executive Summary

[One paragraph: What did you analyze? What are your top 2-3 recommendations? Is the project healthy?]

---

## 1. Project Health & Maturity

### Current State
- **Version**: X.Y (stable/beta/alpha)
- **Spec**: [Link to spec file] — completeness status
- **Compiler**: `compiler_v2.py` — [characterize maturity]
- **Runtime**: `runtime/engine.py` — [graph-first or step-based?]
- **Adapters**: List known adapters and their status
- **Fine-tuning**: [Model status, constrained decoding support]
- **Testing**: [Conformance suite, integration tests, coverage]
- **Emitters**: [List available targets]

### Quality Metrics (from `corpus/curated/`)
- Summary of latest eval reports
- Strict AINL rate, runtime compile rate, nonempty rate
- Regression detection status
- CI health

### AI Development Context
- Is the project AI-co-developed? Mention AI's role in architecture/implementation
- Reference `docs/PROJECT_ORIGIN_AND_ATTRIBUTION.md` if applicable

---

## 2. Deep Dive: Architecture & Design Principles

**Core Invariant** (quote the key invariant from `docs/AINL_SPEC.md`):
> Canonical IR = nodes/edges; everything else is serialization.

### Design Principles (paraphrase from spec)
1. [Principle 1 — what it means]
2. [Principle 2]
3. ...

### Execution Model (how programs run)
- Services (`S`): [...]
- Types (`D`): [...]
- Endpoints (`E`): [...]
- Labels (`L`): [...]
- Adapters (`R group verb`): [...]
- Frontend (`U`, `T`, `Rt`, ...): [...]
- Metadata (`P`, `C`, `Q`, ...): [...]

### Strict Mode Guarantees (safety)
- List the guarantees enforced in `--strict` mode
- Why they matter for AI-generated code

---

## 3. Concrete Usage: End-to-End Examples

[Pick 2-3 representative examples from `examples/` and show full code. For each:]

### Example N: [Title]
```ainl
<full .lang code>
```

**Key features demonstrated**:
- [Feature 1]
- [Feature 2]
- ...

**Emits**:
- [List emitted artifacts]

---

## 4. My Use Case & Reasoning

### Why AINL for [Your Integration]?
1. **Agent-native** — [explain]
2. **Single source of truth** — [explain]
3. **Deterministic & verifiable** — [explain]
4. **Pluggable adapters** — [explain]
5. **Existing ecosystem** — [explain]

### Proposed Integration: [Integration Name]

[Describe what you're adding, e.g., new adapter namespace, new emitter, new example]

**Design**:
```text
R group verb args ->out
```

**Benefits**:
- ...

### Implementation Plan
1. [Step 1 — concrete action]
2. [Step 2]
3. [Step 3]

---

## 5. Developer Guide for AI Agents (How to Work with AINL)

### Quick Start Checklist (Every Session)
1. Read core docs in order: `README.md`, `docs/DOCS_INDEX.md`, `docs/AINL_SPEC.md`, `SEMANTICS.md`, `docs/TRAINING_ALIGNMENT_RUNBOOK.md`
2. Inspect current state: `ls corpus/curated/`, check trends, health
3. Run core validation: `pytest tests/test_conformance.py -v` or `.venv/bin/python scripts/run_test_profiles.py --profile core`
4. Validate a program: `ainl-validate myprog.lang --strict`
5. Emit and inspect: `python scripts/validate_ainl.py myprog.lang --emit server`
6. Run test profile: `.venv/bin/python scripts/run_test_profiles.py --profile integration`

### Tool API for Agent Loops
```bash
# Compile
echo '{"action":"compile","code":"S core web /api"}' | ainl-tool-api

# Emit
echo '{"action":"emit","target":"openapi","code":"..."}' | ainl-tool-api

# Validate
echo '{"action":"validate","code":"...", "strict":true}' | ainl-tool-api

# Delta planning
echo '{"action":"plan_delta","base_ir":{...},"code":"..."}' | ainl-tool-api
```

### Common Patterns for AI Agents

#### Pattern 1: New endpoint + frontend
```ainl
S core web /api
S fe web /
D Thing id:I name:S
E /things G ->L1 ->things
L1: R db F Thing * ->things J things
Rt / Things
U ThingsList things
T things:A[Thing]
Tbl ThingsList Thing id name
```

#### Pattern 2: Cron job
```ainl
S core cron "0 9 * * *"
E /run G ->L1
L1: ... J ok
```

#### Pattern 3: Conditional
```ainl
L10: If (condition) ->L_then ->L_else
```

#### Pattern 4: Error handling
```ainl
L1: R ... ->data
L2: Retry 3 1000
L3: Err ->L_handler
```

### Testing Workflow
1. Validate strictly: `ainl-validate myprog.lang --strict`
2. Check IR shape: ensure `labels[id].nodes` and `edges` exist
3. Test runtime: `ainl-test-runtime myprog.lang`
4. Verify emits: `--emit server|react|openapi|prisma|sql`
5. Run full profile: `.venv/bin/python scripts/run_test_profiles.py --profile integration`

### Fine-Tuning Alignment (if training)
- Dataset: `corpus/curated/pos.jsonl` + `neg.jsonl`
- Training: `scripts/finetune_ainl.py --profile fast`
- Eval: `scripts/eval_finetuned_model.py` with repair
- Gates: `strict_ainl_rate`, `runtime_compile_rate`, `nonempty_rate`
- Runbook: `docs/TRAINING_ALIGNMENT_RUNBOOK.md`

---

## 6. Recommendations & Next Steps

### Immediate Actions
1. [Concrete task 1]
2. [Task 2]
3. [Task 3]

### Medium-Term Improvements
- [Improvement 1]
- [Improvement 2]

### For Future AI Consultants
When analyzing AINL for a new integration:
1. Read the spec and understand the invariant
2. Check health in `corpus/curated/`
3. Identify required adapters; follow `OPENCLAW_AI_AGENT.md` pattern
4. Write an example program exercising the workflow
5. Validate strictly, test runtime, verify emits
6. Document your adapter schema and usage patterns
7. **Update this template** with your findings for the next agent

---

## 7. Conclusion

[Summarize your overall assessment and expected impact of your recommendations.]

---

## Appendix: Reference

**Key Files:**
- Spec: `docs/AINL_SPEC.md`
- Compiler: `compiler_v2.py`
- Runtime: `runtime/engine.py`
- Adapters: `adapters/`
- Examples: `examples/`
- Tests: `tests/`
- Tooling: `tooling/`
- Emitted: `tests/emits/`
- Models: `models/`
- Registry: `ADAPTER_REGISTRY.json`

**Tooling Commands:**
- `ainl-validate`, `ainl-test-runtime`, `ainl-tool-api`, `.venv/bin/python scripts/run_test_profiles.py --profile <name>`
- `python scripts/validate_ainl.py`, `python scripts/run_tests_and_emit.py`
- `pytest`, `uvicorn` for validator web UI

**Quality Gates** (see `docs/TRAINING_ALIGNMENT_RUNBOOK.md`):
- `strict_ainl_rate` >= threshold
- `runtime_compile_rate` >= threshold
- `nonempty_rate` >= threshold
- No regression across length buckets

---

**Consultant:** <Your Name/ID>
**Timestamp:** <ISO 8601>
