"""Mission substrate MCP helpers — schema load, DAG validation, draft planning, handoff lint."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore

_TOOLING = Path(__file__).resolve().parent
_SCHEMA_FILES = {
    "mission": "mission.schema.json",
    "feature": "feature.schema.json",
    "assertion": "assertion.schema.json",
    "handoff": "handoff.schema.json",
    "progress_event": "progress_event.schema.json",
}


def _load_schema(name: str) -> Dict[str, Any]:
    import json

    path = _TOOLING / _SCHEMA_FILES[name]
    return json.loads(path.read_text(encoding="utf-8"))


def schema_validators() -> Dict[str, Any]:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema is required for mission schema validation")
    out: Dict[str, Any] = {}
    for key in _SCHEMA_FILES:
        out[key] = Draft202012Validator(_load_schema(key))
    return out


def validate_instance(name: str, instance: Any) -> List[str]:
    """Return human-readable schema validation errors (empty if valid)."""
    try:
        validators = schema_validators()
    except RuntimeError as exc:
        return [str(exc)]
    validator = validators[name]
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{name}: {e.message} (at {list(e.path)})" for e in errors]


def _files_overlap(a: str, b: str) -> bool:
    a_norm = a.strip().replace("\\", "/")
    b_norm = b.strip().replace("\\", "/")
    if not a_norm or not b_norm:
        return False
    return a_norm == b_norm or a_norm.startswith(b_norm + "/") or b_norm.startswith(a_norm + "/")


def detect_dag_cycle(features: List[Dict[str, Any]]) -> Optional[List[str]]:
    """Return a cycle path of feature_ids if preconditions form a cycle."""
    ids = {f["feature_id"] for f in features}
    graph: Dict[str, List[str]] = {fid: [] for fid in ids}
    for feat in features:
        fid = feat["feature_id"]
        for pred in feat.get("preconditions") or []:
            if pred in ids:
                graph[fid].append(pred)

    visited: Set[str] = set()
    stack: Set[str] = set()
    path: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        visited.add(node)
        stack.add(node)
        path.append(node)
        for nbr in graph.get(node, []):
            if nbr not in visited:
                found = dfs(nbr)
                if found:
                    return found
            elif nbr in stack:
                idx = path.index(nbr)
                return path[idx:] + [nbr]
        path.pop()
        stack.remove(node)
        return None

    for fid in ids:
        if fid not in visited:
            found = dfs(fid)
            if found:
                return found
    return None


def file_conflict_warnings(features: List[Dict[str, Any]]) -> List[str]:
    """Warn when parallel-ready features share overlapping touches_files prefixes."""
    warnings: List[str] = []
    by_milestone: Dict[str, List[Dict[str, Any]]] = {}
    for feat in features:
        by_milestone.setdefault(feat.get("milestone") or "default", []).append(feat)
    for milestone, group in by_milestone.items():
        for i, a in enumerate(group):
            files_a = a.get("touches_files") or []
            if not files_a:
                continue
            for b in group[i + 1 :]:
                if (a.get("preconditions") or []) and b["feature_id"] in (a.get("preconditions") or []):
                    continue
                if (b.get("preconditions") or []) and a["feature_id"] in (b.get("preconditions") or []):
                    continue
                for fa in files_a:
                    for fb in b.get("touches_files") or []:
                        if _files_overlap(fa, fb):
                            warnings.append(
                                f"file_conflict: features {a['feature_id']} and {b['feature_id']} "
                                f"in milestone {milestone!r} both touch overlapping paths "
                                f"({fa!r}, {fb!r}); scheduler should not run them in parallel."
                            )
    return warnings


def assertion_coverage_errors(
    mission: Dict[str, Any],
    features: List[Dict[str, Any]],
    assertions: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    assertion_ids = {a["assertion_id"] for a in assertions}
    milestone_ids = set(mission.get("milestone_ids") or [])

    for ms in milestone_ids:
        if not any(a.get("milestone") == ms for a in assertions):
            errors.append(f"assertion_coverage: milestone {ms!r} has no assertions")

    for feat in features:
        ms = feat.get("milestone")
        if ms and milestone_ids and ms not in milestone_ids:
            errors.append(
                f"assertion_coverage: feature {feat['feature_id']!r} references unknown milestone {ms!r}"
            )
        for aid in feat.get("fulfills") or []:
            if aid not in assertion_ids:
                errors.append(
                    f"assertion_coverage: feature {feat['feature_id']!r} fulfills unknown assertion {aid!r}"
                )

    uncovered = assertion_ids - {
        aid for feat in features for aid in (feat.get("fulfills") or [])
    }
    if uncovered:
        errors.append(
            "assertion_coverage: assertions never referenced by any feature fulfills: "
            + ", ".join(sorted(uncovered))
        )
    return errors


_MISSION_PROMOTION_SCHEMA_VERSION = "1.0.0"


def compute_validate_checksum(
    objective_md: str,
    mission_id: str,
    features: List[Dict[str, Any]],
    assertions: Optional[List[Dict[str, Any]]] = None,
    *,
    schema_version: str = _MISSION_PROMOTION_SCHEMA_VERSION,
) -> str:
    """Canonical SHA-256 hex digest for POST /api/missions promotion gate (matches ainl-mission Rust)."""
    assertions = assertions or []
    payload = {
        "schema_version": schema_version,
        "objective_md": objective_md.strip(),
        "mission_id": (mission_id or "").strip(),
        "features": sorted(features, key=lambda f: f.get("feature_id") or ""),
        "assertions": sorted(assertions, key=lambda a: a.get("assertion_id") or ""),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_mission_dag(
    mission: Dict[str, Any],
    features: List[Dict[str, Any]],
    assertions: Optional[List[Dict[str, Any]]] = None,
    *,
    validate_worker_ainl: bool = False,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate mission + feature DAG + assertion coverage."""
    assertions = assertions or []
    errors: List[str] = []
    warnings: List[str] = []

    for label, payload in (
        ("mission", mission),
        ("features", features),
    ):
        if label == "features":
            for i, feat in enumerate(features):
                errors.extend(validate_instance("feature", feat))
        else:
            errors.extend(validate_instance("mission", mission))

    for assertion in assertions:
        errors.extend(validate_instance("assertion", assertion))

    feature_ids = {f["feature_id"] for f in features}
    for feat in features:
        for pred in feat.get("preconditions") or []:
            if pred not in feature_ids:
                errors.append(
                    f"dag: feature {feat['feature_id']!r} precondition {pred!r} is not a known feature_id"
                )

    cycle = detect_dag_cycle(features)
    if cycle:
        errors.append("dag: precondition cycle detected: " + " -> ".join(cycle))

    errors.extend(assertion_coverage_errors(mission, features, assertions))
    warnings.extend(file_conflict_warnings(features))

    if validate_worker_ainl and repo_root is not None:
        from compiler_v2 import AICodeCompiler

        compiler = AICodeCompiler()
        for feat in features:
            rel = feat.get("worker_ainl_path")
            if not rel:
                continue
            path = (repo_root / str(rel)).resolve()
            if not path.is_file():
                warnings.append(f"worker_ainl: path not found: {rel}")
                continue
            try:
                source = path.read_text(encoding="utf-8")
                compiler.compile(source, strict_mode=True)
            except Exception as exc:
                errors.append(f"worker_ainl: {rel} strict validate failed: {exc}")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "feature_count": len(features),
        "assertion_count": len(assertions),
        "schema_version": _MISSION_PROMOTION_SCHEMA_VERSION,
        "validate_checksum": compute_validate_checksum(
            str(mission.get("objective_md") or ""),
            str(mission.get("mission_id") or ""),
            features,
            assertions,
        ),
    }


def lint_handoff(
    handoff: Dict[str, Any],
    *,
    features: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Validate handoff JSON and optional cross-checks against features."""
    errors = validate_instance("handoff", handoff)
    warnings: List[str] = []

    feature_by_id: Dict[str, Dict[str, Any]] = {}
    if features:
        feature_by_id = {f["feature_id"]: f for f in features}

    fid = handoff.get("feature_id")
    feat = feature_by_id.get(fid) if fid else None
    if features and fid and feat is None:
        errors.append(f"handoff: feature_id {fid!r} not found in supplied features list")

    if feat:
        expected = (feat.get("expected_behavior") or "").strip()
        implemented = (handoff.get("what_was_implemented_md") or "").strip()
        if expected and not implemented:
            warnings.append(
                f"handoff: feature {fid!r} has expected_behavior but what_was_implemented_md is empty"
            )
        fulfills = set(feat.get("fulfills") or [])
        if fulfills and handoff.get("verification", {}).get("status") == "failed":
            warnings.append(
                f"handoff: verification failed but feature {fid!r} claims fulfills assertions: "
                + ", ".join(sorted(fulfills))
            )

    for issue in handoff.get("discovered_issues") or []:
        if not (issue.get("summary") or "").strip():
            errors.append("handoff: discovered_issues entry missing summary")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def _slug(text: str, max_len: int = 32) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug[:max_len] or "mission").rstrip("-")


def mission_plan(
    objective: str,
    *,
    repo_intel: Optional[Dict[str, Any]] = None,
    mission_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft a Mission + Feature + Assertion DAG from a natural-language objective."""
    objective = (objective or "").strip()
    if not objective:
        return {"ok": False, "error": "missing required argument: objective", "tool_call_error": True}

    repo_intel = repo_intel or {}
    now = datetime.now(timezone.utc).isoformat()
    mission_id = f"mission-{_slug(objective, 24)}-{uuid.uuid4().hex[:8]}"
    milestone = "m1-ship"
    root = mission_root or repo_intel.get("mission_root") or "."

    mission: Dict[str, Any] = {
        "mission_id": mission_id,
        "objective_md": objective,
        "state": "AwaitingInput",
        "milestone_ids": [milestone],
        "mission_root": root,
        "created_at": now,
        "capability_flags": {
            "mission_enabled": True,
            "coding_domain": bool(repo_intel.get("coding_domain", True)),
            "git_snapshot": bool(repo_intel.get("git_snapshot", True)),
        },
    }

    touches = list(repo_intel.get("touches_files") or ["src/", "tests/"])
    if isinstance(touches, str):
        touches = [touches]

    features: List[Dict[str, Any]] = [
        {
            "feature_id": "feat-scaffold",
            "description": "Scaffold mission worker artifacts and validation hooks.",
            "status": "pending",
            "milestone": milestone,
            "skill_name": "mission-worker",
            "touches_files": [touches[0]] if touches else [],
            "preconditions": [],
            "expected_behavior": "Mission worker examples and schemas are present and strict-valid.",
            "verification_steps": ["ainl validate examples/mission_workers/*.ainl --strict"],
            "fulfills": ["assert-schemas"],
            "worker_ainl_path": "examples/mission_workers/handoff_emitter_worker.ainl",
        },
        {
            "feature_id": "feat-implement",
            "description": "Implement the core objective changes described in objective_md.",
            "status": "pending",
            "milestone": milestone,
            "skill_name": "coding-agent",
            "touches_files": touches,
            "preconditions": ["feat-scaffold"],
            "expected_behavior": "Primary user objective is satisfied with tests passing.",
            "verification_steps": [
                "Run targeted unit tests for touched modules",
                "Run ainl_mission_validate on updated DAG",
            ],
            "fulfills": ["assert-objective"],
            "worker_ainl_path": "examples/mission_workers/assertion_check_worker.ainl",
        },
        {
            "feature_id": "feat-review",
            "description": "Scrutiny review and improvement proposals for discovered issues.",
            "status": "pending",
            "milestone": milestone,
            "skill_name": "code-reviewer",
            "touches_files": [],
            "preconditions": ["feat-implement"],
            "expected_behavior": "Review completes; blocking issues become fix features or proposals.",
            "verification_steps": ["Run scrutiny_reviewer_worker.ainl frame checks"],
            "fulfills": ["assert-review"],
            "worker_ainl_path": "examples/mission_workers/scrutiny_reviewer_worker.ainl",
        },
    ]

    assertions: List[Dict[str, Any]] = [
        {
            "assertion_id": "assert-schemas",
            "description": "Mission JSON schemas and conformance tests pass.",
            "verification_steps": ["pytest tests/test_mission_schema_conformance.py -q"],
            "state": "Pending",
            "milestone": milestone,
            "failed_count": 0,
        },
        {
            "assertion_id": "assert-objective",
            "description": "Objective acceptance criteria met.",
            "verification_steps": ["Operator sign-off on objective_md"],
            "state": "Pending",
            "milestone": milestone,
            "failed_count": 0,
        },
        {
            "assertion_id": "assert-review",
            "description": "Scrutiny review recorded with no unresolved critical issues.",
            "verification_steps": ["handoff_lint on scrutiny handoff JSON"],
            "state": "Pending",
            "milestone": milestone,
            "failed_count": 0,
        },
    ]

    validation = validate_mission_dag(mission, features, assertions)
    return {
        "ok": validation["ok"],
        "schema_version": "1.0.0",
        "mission": mission,
        "features": features,
        "assertions": assertions,
        "validation": validation,
        "recommended_next_tools": ["ainl_mission_validate", "ainl_handoff_lint", "ainl_validate"],
        "recommended_resources": [
            "ainl://mission-authoring-cheatsheet",
            "ainl://mission-worker-examples",
        ],
    }


MISSION_AUTHORING_CHEATSHEET = """# Mission authoring — MCP cheatsheet

**Golden path:** `ainl_mission_plan` (objective + optional repo_intel) → `ainl_mission_validate` (DAG + assertions) → dispatch workers in ArmaraOS → `ainl_handoff_lint` on each Handoff JSON.

## Schemas (tooling/*.schema.json)
- `mission.schema.json` — Mission graph root
- `feature.schema.json` — Feature nodes with preconditions / fulfills
- `assertion.schema.json` — Milestone assertions
- `handoff.schema.json` — Worker handoff payload
- `progress_event.schema.json` — MissionEvent variants for SSE / ledger

## Host tools (ArmaraOS; contracts in ADAPTER_CONTRACTS)
- `mission_dispatch` — spawn worker for a feature (write / approval-gated)
- `mission_handoff_record` — persist Handoff node (write)
- `mission_assertion_check` — run verification_steps (write)
- `git_snapshot` / `git_rollback` — lazy stash snapshot (write; rollback approval-gated)
- `ask_user` — read-only question vs write vs approval-gated side effects

## Strict-valid workers
See `ainl://mission-worker-examples` and `examples/mission_workers/*.ainl`. Workers use `fs` + `core` in AINL; host binds mission_* tools at runtime.

## Avoid
- Cycles in Feature `preconditions` (validate will fail)
- Assertions with no Feature `fulfills` reference
- Overlapping `touches_files` on parallel features without preconditions ordering
"""
