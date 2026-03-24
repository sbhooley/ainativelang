# Trajectory logging (CLI / RuntimeEngine)

Optional **structured step traces** for `ainl run`: each executed step appends one JSON line to `<source-stem>.trajectory.jsonl` beside the `.ainl` file.

**Enable:** `ainl run path/to/script.ainl --log-trajectory` or `AINL_LOG_TRAJECTORY=1`.

**Example:** `ainl run examples/hello.ainl --log-trajectory --json` → writes `examples/hello.trajectory.jsonl`.

Runner HTTP audit events (`ainl.runner` logger) are separate; see [AUDIT_LOGGING.md](operations/AUDIT_LOGGING.md).
