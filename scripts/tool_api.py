#!/usr/bin/env python3
"""
Structured tool API CLI for agent loops.

Usage examples:
  echo '{"action":"compile","code":"S core web /api"}' | ainl-tool-api
  ainl-tool-api --request-file request.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
    action = (req.get("action") or "").strip()
    strict = bool(req.get("strict", False))
    compiler = AICodeCompiler(strict_mode=strict)

    if action == "compile":
        code = req.get("code", "")
        ir = compiler.compile(code)
        return {"ok": True, "action": action, "ir": to_jsonable(ir)}

    if action == "validate":
        code = req.get("code", "")
        ir = compiler.compile(code)
        return {"ok": len(ir.get("errors", [])) == 0, "action": action, "errors": ir.get("errors", []), "meta": ir.get("meta", [])}

    if action == "emit":
        code = req.get("code", "")
        target = (req.get("target") or "ir").strip()
        ir = compiler.compile(code)
        if target == "ir":
            out = compiler.emit_ir_json(ir)
        elif target == "server":
            out = compiler.emit_server(ir)
        elif target == "react":
            out = compiler.emit_react(ir)
        elif target == "openapi":
            out = compiler.emit_openapi(ir)
        elif target == "prisma":
            out = compiler.emit_prisma_schema(ir)
        elif target == "sql":
            out = compiler.emit_sql_migrations(ir)
        else:
            return {"ok": False, "action": action, "error": f"Unsupported target: {target}"}
        return {"ok": True, "action": action, "target": target, "output": out, "errors": ir.get("errors", [])}

    if action == "explain_error":
        # Minimal structured helper for local agent loops.
        error = str(req.get("error", "")).strip()
        hint = "Check op arity/scope and label targets."
        if "Unterminated string literal" in error:
            hint = "Close the quoted string before line end. Only \\\" and \\\\ are escapes in AINL 1.0."
        elif "requires at least" in error:
            hint = "Add the missing required slots for this op (see OP_REGISTRY in spec)."
        elif "label-only op" in error:
            hint = "Move this op inside an L<n>: block or convert to a top-level declaration op."
        return {"ok": True, "action": action, "hint": hint}

    return {"ok": False, "error": f"Unsupported action: {action}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="AINL structured tool API CLI")
    ap.add_argument("--request-file", help="Path to JSON request file. If omitted, reads stdin.")
    args = ap.parse_args()

    if args.request_file:
        with open(args.request_file, "r", encoding="utf-8") as f:
            req = json.load(f)
    else:
        raw = sys.stdin.read().strip()
        req = json.loads(raw or "{}")

    try:
        res = handle_request(req)
    except Exception as e:
        res = {"ok": False, "error": str(e)}
    print(json.dumps(to_jsonable(res), indent=2))


if __name__ == "__main__":
    main()
