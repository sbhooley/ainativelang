# AI Native Lang (AINL) Glossary

## AINL
AI Native Lang. A language designed for AI-first authoring and execution workflows.

## Canonical AINL
The strict, line-oriented AINL form used for validation, training targets, and evaluation.

## IR (Intermediate Representation)
The compiler output graph/step structure used by runtimes and emitters.

## Graph-First Runtime
Execution mode that prioritizes graph semantics and uses step fallback only when needed.

## Adapter
A runtime integration surface for external capabilities (HTTP, DB, files, tools, etc.).

## LoRA
Low-Rank Adaptation fine-tuning strategy used to adapt base models efficiently.

## Strict AINL Rate
Share of prompts where output is non-empty, AINL-like, and passes strict compile checks.

## Runtime Compile Rate
Share of outputs that pass runtime (non-strict) compile validation.

## Nonempty Rate
Share of prompts producing non-empty output.

## Constraint Diagnostics
Telemetry emitted during constrained decoding (allowed/rejected tokens, fallback, EOS gating).

## Failure Family
A normalized category of generation failure (timeout, shape mismatch, compile failure, etc.).

## Prompt-Length Bucket
Grouping prompts by rendered token length to improve shape stability and analysis granularity.

## Checkpoint Sweep
Evaluating checkpoints and ranking them by task metrics instead of raw eval loss.

## Trend Gate
Cross-run quality gate enforcing minimum rates and maximum allowed regressions.

## Run Health Report
Machine-readable pass/fail summary artifact for automation:
`corpus/curated/alignment_run_health.json`.

## Distill Mix
Training-data composition strategy mixing gold examples and repair/check-rewrite supervision.

## Failure Boost Dataset
Targeted dataset generated from failing prompt IDs to improve weak families.

## OpenClaw
An extension and operator-focused surface area built on top of canonical AINL, used for advanced adapters, orchestration, and multi-agent workflows.

## Adapter Registry
The catalog of available runtime adapters, their identifiers, and supported capabilities as defined in `docs/ADAPTER_REGISTRY.md`.

## Memory Adapter
An adapter responsible for durable memory operations (read, write, list, delete) over structured memory records, specified in `docs/MEMORY_CONTRACT.md`.

## Memory Record
A structured, schema-validated unit of persisted memory (with fields such as id, kind, timestamps, and content) managed by the memory adapter.

## Conformance Profile
A named set of behavioral and surface-area expectations (e.g., `AINL_V0_9_PROFILE`) that a runtime, compiler, or adapter must meet to be considered compatible.

## Language Lanes and Extensions
The division between canonical AINL and additional extension lanes (including OpenClaw-focused extensions) described in `docs/AINL_CANONICAL_CORE.md` and `docs/AINL_EXTENSIONS.md`.

## Runtime Specification
The formal description of how compiled IR and language constructs must behave at runtime, complementing the human-readable semantics; see `docs/ainl_runtime_spec.md` and `SEMANTICS.md`.

## Targets Roadmap
The forward-looking map of officially supported runtimes, adapters, and deployment targets, documented in `docs/TARGETS_ROADMAP.md`.
