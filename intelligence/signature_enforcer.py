from __future__ import annotations

import re
import argparse
import json
from typing import Any, Dict, List, Optional, Tuple


_SIG_RE = re.compile(r"#\s*signature\s*:\s*(.+?)\s*$", re.IGNORECASE)
_PAIR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)")


def parse_signature_annotation(line: str) -> Optional[str]:
    m = _SIG_RE.search(line or "")
    if not m:
        return None
    sig = m.group(1).strip()
    return sig or None


def collect_signature_annotations(source: str) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for idx, line in enumerate((source or "").splitlines(), start=1):
        if "signature" not in line.lower():
            continue
        sig = parse_signature_annotation(line)
        if sig:
            out[idx] = sig
    return out


def signature_diagnostics(source: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, line in enumerate((source or "").splitlines(), start=1):
        if "signature" not in line.lower():
            continue
        if "#" not in line:
            continue
        tail = line.split("#", 1)[1]
        if "signature" not in tail.lower():
            continue
        sig = parse_signature_annotation(line)
        if not sig:
            out.append(
                {
                    "code": "AINL_SIGNATURE_METADATA_INVALID",
                    "severity": "warning",
                    "lineno": idx,
                    "message": "Malformed signature metadata; expected '# signature: {field :type}'.",
                }
            )
    return out


def _parse_signature_pairs(signature: str) -> Dict[str, str]:
    s = (signature or "").strip().strip('"').strip("'")
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    pairs = {k: v.lower() for (k, v) in _PAIR_RE.findall(s)}
    return pairs


def _type_ok(value: Any, type_name: str) -> bool:
    t = (type_name or "").lower()
    if t in {"any", "json"}:
        return True
    if t in {"str", "string", "text"}:
        return isinstance(value, str)
    if t in {"int", "integer"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if t in {"float", "number"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t in {"bool", "boolean"}:
        return isinstance(value, bool)
    if t in {"list", "array"}:
        return isinstance(value, list)
    if t in {"obj", "object", "dict"}:
        return isinstance(value, dict)
    return True


def validate_result_against_signature(result: Any, signature: str) -> Tuple[bool, List[str]]:
    expected = _parse_signature_pairs(signature)
    if not expected:
        return True, []
    if not isinstance(result, dict):
        return False, ["result is not an object"]
    errors: List[str] = []
    for field, type_name in expected.items():
        if field not in result:
            errors.append(f"missing field '{field}'")
            continue
        if not _type_ok(result.get(field), type_name):
            errors.append(f"field '{field}' type mismatch: expected {type_name}")
    return len(errors) == 0, errors


def run_with_signature_retry(
    *,
    adapter: Any,
    lisp: str,
    signature: str,
    subagent_budget: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    attempts = max(1, min(int(max_attempts), 3))
    last: Dict[str, Any] = {}
    violations: List[str] = []
    for _ in range(attempts):
        out = adapter.run(
            lisp,
            signature=signature,
            subagent_budget=subagent_budget,
            context=context or {},
        )
        last = dict(out) if isinstance(out, dict) else {"ok": False, "result": out}
        ok, errs = validate_result_against_signature(last.get("result"), signature)
        if ok:
            last["signature_ok"] = True
            last["signature_violations"] = []
            return last
        violations = errs
    last["signature_ok"] = False
    last["signature_violations"] = violations
    return last


def main() -> None:
    ap = argparse.ArgumentParser(description="AINL signature metadata inspector")
    ap.add_argument("file", nargs="?", default="", help="AINL source file to inspect")
    args = ap.parse_args()
    if not args.file:
        print(json.dumps({"ok": True, "message": "signature_enforcer module ready"}, indent=2))
        return
    with open(args.file, "r", encoding="utf-8") as fh:
        src = fh.read()
    print(
        json.dumps(
            {
                "ok": True,
                "annotations": collect_signature_annotations(src),
                "diagnostics": signature_diagnostics(src),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
