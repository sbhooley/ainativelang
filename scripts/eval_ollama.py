#!/usr/bin/env python3
"""
Evaluate a local Ollama model on AINL generation quality.

Input format (JSONL):
  {"id":"crud_users","prompt":"Generate AINL for users CRUD dashboard"}

Usage:
  ainl-ollama-eval --model qwen2.5:7b --prompts data/evals/ollama_prompts.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


SYSTEM_PROMPT = (
    "You are generating AINL 1.0 source only.\n"
    "Output ONLY raw AINL code, no markdown fences, no explanations.\n"
    "Prefer compact valid programs with S/D/E/L/R/J and optional UI declarations.\n"
)


def ollama_generate(host: str, model: str, prompt: str, timeout_s: int = 120) -> str:
    payload = {
        "model": model,
        "prompt": SYSTEM_PROMPT + "\n\nTask:\n" + prompt + "\n",
        "stream": False,
        "options": {"temperature": 0.2},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{host.rstrip('/')}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return (body.get("response") or "").strip()


def load_prompts(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate local Ollama model on AINL generation")
    ap.add_argument("--model", required=True, help="Ollama model name, e.g. qwen2.5:7b")
    ap.add_argument("--prompts", default="data/evals/ollama_prompts.jsonl", help="JSONL prompts file")
    ap.add_argument("--host", default="http://127.0.0.1:11434", help="Ollama host URL")
    ap.add_argument("--out", default="data/evals/ollama_eval_report.json", help="Output JSON report")
    args = ap.parse_args()

    prompts = load_prompts(args.prompts)
    compiler = AICodeCompiler(strict_mode=True)
    rows: List[Dict[str, Any]] = []
    t0 = time.time()

    for i, item in enumerate(prompts, 1):
        pid = item.get("id", f"case_{i}")
        prompt = item.get("prompt", "")
        row: Dict[str, Any] = {"id": pid, "ok": False, "error_count": 0}
        try:
            gen = ollama_generate(args.host, args.model, prompt)
            ir = compiler.compile(gen)
            errs = ir.get("errors", [])
            row.update(
                {
                    "ok": len(errs) == 0,
                    "error_count": len(errs),
                    "errors": errs[:5],
                    "generated_chars": len(gen),
                    "stats": ir.get("stats", {}),
                }
            )
        except Exception as e:
            row.update({"ok": False, "error_count": 1, "errors": [str(e)]})
        rows.append(row)

    elapsed = time.time() - t0
    passed = sum(1 for r in rows if r["ok"])
    report = {
        "model": args.model,
        "host": args.host,
        "cases": len(rows),
        "passed": passed,
        "pass_rate": (passed / len(rows)) if rows else 0.0,
        "elapsed_s": round(elapsed, 3),
        "results": rows,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
