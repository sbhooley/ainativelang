import argparse
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


JsonObject = Dict[str, Any]

_VALID_NAMESPACES = {"session", "long_term", "daily_log", "workflow"}
_KNOWN_KINDS = {
    "session.context",
    "workflow.token_cost_state",
    "workflow.checkpoint",
    "workflow.monitor_status_snapshot",
    "workflow.advisory_result",
    "long_term.user_preference",
    "long_term.project_fact",
    "daily_log.note",
}


@dataclass
class ValidationIssue:
    kind: str  # "error" or "warning"
    path: str  # e.g. "record_id", "payload.total_cost_usd"
    message: str


def _require_field(
    obj: JsonObject,
    field: str,
    expected_type: Any,
    issues: List[ValidationIssue],
    *,
    kind: str = "error",
    path_prefix: str = "",
) -> None:
    full_path = f"{path_prefix}{field}" if path_prefix else field
    if field not in obj:
        issues.append(
            ValidationIssue(
                kind=kind,
                path=full_path,
                message=f"Missing required field '{field}'.",
            )
        )
        return
    value = obj[field]
    if expected_type is not None and not isinstance(value, expected_type):
        issues.append(
            ValidationIssue(
                kind=kind,
                path=full_path,
                message=f"Field '{field}' expected type {expected_type}, got {type(value).__name__}.",
            )
        )


def validate_memory_record(obj: Any) -> List[ValidationIssue]:
    """
    Validate a single memory record envelope according to the v1 contract.

    Expected envelope shape (conceptual):
    {
      "namespace": "string",
      "record_kind": "string",
      "record_id": "string",
      "created_at": "RFC3339 string",
      "updated_at": "RFC3339 string",
      "ttl_seconds": 3600,
      "payload": {}
    }
    """
    issues: List[ValidationIssue] = []

    if not isinstance(obj, dict):
        issues.append(
            ValidationIssue(
                kind="error",
                path="",
                message=f"Record must be a JSON object, got {type(obj).__name__}.",
            )
        )
        return issues

    # Core key fields
    _require_field(obj, "namespace", str, issues)
    _require_field(obj, "record_kind", str, issues)
    _require_field(obj, "record_id", str, issues)

    ns = obj.get("namespace")
    rk = obj.get("record_kind")

    if isinstance(ns, str) and ns not in _VALID_NAMESPACES:
        issues.append(
            ValidationIssue(
                kind="error",
                path="namespace",
                message=f"Namespace '{ns}' is not allowed in v1 (expected one of {_VALID_NAMESPACES}).",
            )
        )

    # Payload and ttl
    if "payload" not in obj:
        issues.append(
            ValidationIssue(
                kind="error",
                path="payload",
                message="Missing required field 'payload'.",
            )
        )
    else:
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            issues.append(
                ValidationIssue(
                    kind="error",
                    path="payload",
                    message="Payload must be a JSON object.",
                )
            )

    if "ttl_seconds" in obj:
        ttl = obj["ttl_seconds"]
        if ttl is not None and not (isinstance(ttl, int) and not isinstance(ttl, bool)):
            issues.append(
                ValidationIssue(
                    kind="error",
                    path="ttl_seconds",
                    message="ttl_seconds must be an integer or null.",
                )
            )

    # Namespace / kind consistency and light kind checks
    if isinstance(rk, str):
        if rk in _KNOWN_KINDS and isinstance(ns, str):
            if rk.startswith("workflow.") and ns != "workflow":
                issues.append(
                    ValidationIssue(
                        kind="error",
                        path="namespace",
                        message=f"record_kind '{rk}' should use namespace 'workflow', got '{ns}'.",
                    )
                )
            if rk.startswith("long_term.") and ns != "long_term":
                issues.append(
                    ValidationIssue(
                        kind="error",
                        path="namespace",
                        message=f"record_kind '{rk}' should use namespace 'long_term', got '{ns}'.",
                    )
                )
            if rk == "daily_log.note" and ns != "daily_log":
                issues.append(
                    ValidationIssue(
                        kind="error",
                        path="namespace",
                        message="record_kind 'daily_log.note' should use namespace 'daily_log'.",
                    )
                )
            if rk == "session.context" and ns != "session":
                issues.append(
                    ValidationIssue(
                        kind="error",
                        path="namespace",
                        message="record_kind 'session.context' should use namespace 'session'.",
                    )
                )

        # Very light, kind-specific payload checks (warnings, not errors)
        payload = obj.get("payload")
        if isinstance(payload, dict):
            if rk == "workflow.token_cost_state":
                if "total_cost_usd" not in payload and "total_tokens" not in payload:
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="workflow.token_cost_state payload usually includes total_cost_usd or total_tokens.",
                        )
                    )
            elif rk == "workflow.monitor_status_snapshot":
                if "status" not in payload and "monitors" not in payload:
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="workflow.monitor_status_snapshot payload usually includes 'status' or 'monitors'.",
                        )
                    )
            elif rk == "workflow.advisory_result":
                if "summary" not in payload:
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="workflow.advisory_result payload usually includes 'summary'.",
                        )
                    )
            elif rk == "long_term.user_preference":
                if not any(k in payload for k in ("key", "name", "preferences")):
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="long_term.user_preference payload usually includes 'key', 'name', or 'preferences'.",
                        )
                    )
            elif rk == "long_term.project_fact":
                if "fact" not in payload and "text" not in payload:
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="long_term.project_fact payload usually includes 'fact' or 'text'.",
                        )
                    )
            elif rk == "daily_log.note":
                if "entries" not in payload and not any(k in payload for k in ("ts", "text")):
                    issues.append(
                        ValidationIssue(
                            kind="warning",
                            path="payload",
                            message="daily_log.note payload usually includes 'entries' or note fields like 'ts'/'text'.",
                        )
                    )

    return issues


def _format_issues(issues: List[ValidationIssue]) -> str:
    lines: List[str] = []
    for issue in issues:
        prefix = "ERROR" if issue.kind == "error" else "WARN"
        location = issue.path or "<root>"
        lines.append(f"{prefix} [{location}]: {issue.message}")
    return "\n".join(lines)


def validate_records_obj(obj: Any) -> List[ValidationIssue]:
    """
    Validate either a single record or a list of records.
    """
    issues: List[ValidationIssue] = []
    if isinstance(obj, list):
        for idx, rec in enumerate(obj):
            rec_issues = validate_memory_record(rec)
            for i in rec_issues:
                i.path = f"[{idx}].{i.path}" if i.path else f"[{idx}]"
                issues.append(i)
    else:
        issues.extend(validate_memory_record(obj))
    return issues


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate AINL memory records against the v1 memory contract. "
            "Accepts a JSON file containing a single record or an array of records."
        )
    )
    parser.add_argument(
        "--json-file",
        type=str,
        required=True,
        help="Path to a JSON file containing a single record or an array of records.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    with open(args.json_file, "r", encoding="utf-8") as f:
        obj = json.load(f)

    issues = validate_records_obj(obj)

    if args.json:
        payload = {
            "ok": not any(i.kind == "error" for i in issues),
            "issues": [asdict(i) for i in issues],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not issues:
            print("All memory records are valid according to the v1 memory contract.")
        else:
            print(_format_issues(issues))

    return 1 if any(i.kind == "error" for i in issues) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

