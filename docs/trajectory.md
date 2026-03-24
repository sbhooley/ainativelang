# Trajectory logging (CLI / RuntimeEngine)

Optional **structured step traces** for `ainl run`: each executed step appends one JSON line to `<source-stem>.trajectory.jsonl` beside the `.ainl` file (same directory as the source path passed to the CLI).

## Enable

- **Flag:** `ainl run path/to/script.ainl --log-trajectory`
- **Environment:** `AINL_LOG_TRAJECTORY=1` (or `true` / `yes` / `on`, case-insensitive after trim)

Works with **`--json`** and other normal `ainl run` flags.

## Examples

```bash
ainl run examples/hello.ainl --log-trajectory --json
# creates examples/hello.trajectory.jsonl
```

**Hyperspace emitted agents:** `python3 scripts/validate_ainl.py … --emit hyperspace -o agent.py` embeds IR and uses `RuntimeEngine`; trajectory files are written relative to the **process current working directory**, using the stem of the original `.ainl` source. Set `AINL_LOG_TRAJECTORY` when running the emitted script if you do not pass CLI flags through a wrapper.

## Relation to other logging

- **Runner HTTP audit** (`ainl.runner` logger, `/run` on the runner service) is separate; see [AUDIT_LOGGING.md](operations/AUDIT_LOGGING.md).
- **Runtime / compiler contract:** optional trace is an implementation surface on `RuntimeEngine`; it does not change graph semantics. See [RUNTIME_COMPILER_CONTRACT.md](RUNTIME_COMPILER_CONTRACT.md).

## See also

- **`modules/common`:** `guard.ainl`, `session_budget.ainl`, `reflect.ainl` — optional gates that pair well with traced runs ([modules/common/README.md](../modules/common/README.md)).
- **Hyperspace emitter:** [emitters/README.md](emitters/README.md) — `--emit hyperspace`, `examples/hyperspace_demo.ainl`, root `README.md` (*Emitters* / happy path).
