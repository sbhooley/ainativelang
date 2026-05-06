"""Verify JSONL lines produced by the audit_trail adapter (event_hash field).

Trajectory JSONL lines (per-step execution) do not use event_hash; they are
skipped unless you extend this module. See docs/enterprise/EVIDENCE_BUNDLE_RECIPE.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _audit_trail_expected_hash(rec: Dict[str, Any]) -> str:
    base = {k: v for k, v in rec.items() if k != "event_hash"}
    blob = json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def verify_jsonl_lines(lines: List[str]) -> Tuple[int, int, int, List[str]]:
    """Return (verified_hashed_count, skipped_other_count, line_no_of_first_error_or_0, error_messages)."""
    errors: List[str] = []
    verified = 0
    skipped = 0
    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: invalid JSON ({e})")
            return verified, skipped, i, errors
        if not isinstance(rec, dict):
            errors.append(f"line {i}: expected object, got {type(rec).__name__}")
            return verified, skipped, i, errors
        if "event_hash" not in rec:
            skipped += 1
            continue
        got = rec.get("event_hash")
        exp = _audit_trail_expected_hash(rec)
        if got != exp:
            errors.append(f"line {i}: event_hash mismatch (expected {exp!r}, got {got!r})")
            return verified, skipped, i, errors
        verified += 1
    return verified, skipped, 0, errors


def verify_jsonl_file(path: Path, *, verbose: bool = False) -> int:
    import sys

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    verified, skipped, _bad_line, errors = verify_jsonl_lines(lines)
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1
    if verified == 0 and skipped:
        print(
            f"warning: no lines with event_hash in {path} ({skipped} other JSON object line(s) skipped)",
            file=sys.stderr,
        )
    if verbose:
        print(
            f"OK: verified {verified} audit_trail line(s); skipped {skipped} non-audit line(s) in {path}"
        )
    else:
        print(f"OK: verified {verified} audit_trail line(s); skipped {skipped}")
    return 0
