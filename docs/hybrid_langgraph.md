# Hybrid deployments: AINL inside LangGraph

## What this is

**LangGraph** provides graph-native orchestration for agentic systems: cycles, persistence, human-in-the-loop, and optional LLM nodes. **AINL** provides a **small, deterministic IR** you compile once and execute many times via `RuntimeEngine`—ideal for policy, branching, and adapter calls without paying LLM tokens for orchestration logic.

The **`--emit langgraph`** path in `scripts/validate_ainl.py` generates a **single LangGraph node** (`ainl_core`) that runs the **entire** embedded AINL program in one step. That keeps integration minimal and avoids duplicating control flow in two languages.

## Generate a wrapper

```bash
python3 scripts/validate_ainl.py path/to/workflow.ainl --emit langgraph -o workflow_langgraph.py
```

Default output if `-o` is omitted: `<stem>_langgraph.py` in the current working directory.

## Dependencies

- **Always:** repository `runtime/` (and typically repo root on `PYTHONPATH`).
- **For executing the generated file:** `pip install langgraph` (the emitter wraps `ImportError` with an explicit message).

## State and `run_ainl_graph`

The generated graph uses a small `TypedDict` state (`AinlHybridState`) with:

- **`ainl_frame`** — copied into the AINL runtime frame for the entry label (pass inputs here from upstream LangGraph nodes).
- **`ainl_run`** — populated with the return value of `run_ainl_graph()` from `runtime/wrappers/langgraph_wrapper.py`: `{"ok", "result", "label", "error"}`.

Fields are typed as plain `dict` in the emitted source so **LangGraph**’s internal `get_type_hints` path stays reliable on Python 3.10 (nested generics like `dict[str, Any]` can fail to resolve there).

`run_ainl_graph` accepts either **canonical IR dict**, a **JSON object string**, or **raw `.ainl` source** (see the wrapper docstring). Optional **`adapters=`** mirrors a host that registered CLI adapters.

## Benefits

- **Deterministic core:** branching, adapters, and memory patterns stay in AINL’s graph semantics.
- **Token economics:** the AINL-authored graph does not consume LLM tokens per execution; only optional surrounding LangGraph LLM nodes do.
- **Incremental adoption:** start with one `ainl_core` node; add LangGraph nodes for retrieval, tool choice, or human approval, and **conditional edges** from `build_graph()` comments in the emitted file.

## Example

See `examples/hybrid/langgraph_outer_ainl_core/` for a emitted `*_langgraph.py` plus source `.ainl`.

## Related

- Runtime contract: [`docs/RUNTIME_COMPILER_CONTRACT.md`](RUNTIME_COMPILER_CONTRACT.md)
- Emitters hub: [`docs/emitters/README.md`](emitters/README.md)
