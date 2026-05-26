#!/usr/bin/env python3
"""
Benchmark: constrained vs unconstrained AINL decoding.

Measures turns-to-valid-AINL and tokens-to-valid-AINL with and without
grammar-constrained decoding. Requires:
  - `ainl serve` running (POST /validate, POST /grammar)
  - A local llama.cpp server (POST /completion) or OpenAI-compat endpoint

Usage:
    # Start prerequisites:
    ainl serve --port 8765 &
    llama-server --model <model.gguf> --port 9999 &

    # Run benchmark:
    python scripts/benchmark_constrained_decode.py \\
        --ainl-url http://127.0.0.1:8765 \\
        --llm-url  http://127.0.0.1:9999 \\
        --output   benchmark_constrained_decode_results.json

    # Or with default URLs:
    python scripts/benchmark_constrained_decode.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

AINL_URL = os.getenv("AINL_SERVE_URL", "http://127.0.0.1:8765")
LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:9999")

PROMPTS = [
    "Write a compact AINL workflow that fetches a URL via http.GET and writes the result to a file via fs.write.",
    "Write a compact AINL workflow that monitors a health endpoint every 15 minutes using cron and caches the result.",
    "Write a compact AINL workflow that reads from cache, falls back to HTTP if cache miss, and stores in cache.",
    "Write a compact AINL workflow with branching: if status is 200, output success, else output failure.",
    "Write a compact AINL workflow that concatenates strings to build a CSV row and writes it to disk.",
    "Write a compact AINL workflow that fetches two APIs in sequence and merges the results.",
    "Write a compact AINL workflow that checks an environment variable and branches based on its value.",
    "Write a compact AINL workflow that takes frame inputs for url and output_path, fetches and saves.",
    "Write a compact AINL workflow that uses core.NOW and core.ISO to timestamp an output file.",
    "Write a compact AINL workflow that stores a value in SQLite after fetching from HTTP.",
]


def fetch_grammar(ainl_url: str, fmt: str = "gbnf") -> Optional[str]:
    try:
        resp = requests.post(f"{ainl_url}/grammar", json={"format": fmt}, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return data.get("gbnf") or data.get("ebnf")
    except Exception as e:
        print(f"[warn] Failed to fetch grammar: {e}", file=sys.stderr)
    return None


def validate_ainl(ainl_url: str, source: str) -> bool:
    try:
        resp = requests.post(f"{ainl_url}/validate", json={"source": source, "strict": True}, timeout=10)
        data = resp.json()
        return bool(data.get("ok"))
    except Exception:
        return False


def generate_unconstrained(llm_url: str, prompt: str, max_tokens: int = 512) -> Dict[str, Any]:
    payload = {
        "prompt": f"You are an expert AINL programmer. {prompt}\n\nRespond with ONLY the AINL code, no explanation:\n\n",
        "n_predict": max_tokens,
        "temperature": 0.3,
        "stop": ["\n\n\n"],
    }
    t0 = time.time()
    resp = requests.post(f"{llm_url}/completion", json=payload, timeout=60)
    elapsed = time.time() - t0
    data = resp.json()
    return {
        "text": data.get("content", ""),
        "tokens": data.get("tokens_predicted", 0),
        "elapsed_s": elapsed,
    }


def generate_constrained(llm_url: str, prompt: str, grammar: str, max_tokens: int = 512) -> Dict[str, Any]:
    payload = {
        "prompt": f"You are an expert AINL programmer. {prompt}\n\nRespond with ONLY the AINL code, no explanation:\n\n",
        "n_predict": max_tokens,
        "temperature": 0.3,
        "stop": ["\n\n\n"],
        "grammar": grammar,
    }
    t0 = time.time()
    resp = requests.post(f"{llm_url}/completion", json=payload, timeout=120)
    elapsed = time.time() - t0
    data = resp.json()
    return {
        "text": data.get("content", ""),
        "tokens": data.get("tokens_predicted", 0),
        "elapsed_s": elapsed,
    }


def run_benchmark(ainl_url: str, llm_url: str, max_retries: int = 3) -> Dict[str, Any]:
    grammar = fetch_grammar(ainl_url)
    if not grammar:
        print("[error] Could not fetch GBNF grammar from ainl serve", file=sys.stderr)
        return {"error": "grammar_unavailable"}

    results: List[Dict[str, Any]] = []

    for i, prompt in enumerate(PROMPTS):
        print(f"\n[{i+1}/{len(PROMPTS)}] {prompt[:60]}...")
        entry: Dict[str, Any] = {"prompt": prompt}

        # Unconstrained
        unc_valid = False
        unc_turns = 0
        unc_total_tokens = 0
        for attempt in range(max_retries):
            unc_turns += 1
            gen = generate_unconstrained(llm_url, prompt)
            unc_total_tokens += gen["tokens"]
            if validate_ainl(ainl_url, gen["text"]):
                unc_valid = True
                break
        entry["unconstrained"] = {
            "valid": unc_valid,
            "turns": unc_turns,
            "total_tokens": unc_total_tokens,
        }
        print(f"  unconstrained: valid={unc_valid} turns={unc_turns} tokens={unc_total_tokens}")

        # Constrained
        con_valid = False
        con_turns = 0
        con_total_tokens = 0
        for attempt in range(max_retries):
            con_turns += 1
            gen = generate_constrained(llm_url, prompt, grammar)
            con_total_tokens += gen["tokens"]
            if validate_ainl(ainl_url, gen["text"]):
                con_valid = True
                break
        entry["constrained"] = {
            "valid": con_valid,
            "turns": con_turns,
            "total_tokens": con_total_tokens,
        }
        print(f"  constrained:   valid={con_valid} turns={con_turns} tokens={con_total_tokens}")

        results.append(entry)

    unc_first_try = sum(1 for r in results if r["unconstrained"]["valid"] and r["unconstrained"]["turns"] == 1)
    con_first_try = sum(1 for r in results if r["constrained"]["valid"] and r["constrained"]["turns"] == 1)
    unc_total_tokens = sum(r["unconstrained"]["total_tokens"] for r in results)
    con_total_tokens = sum(r["constrained"]["total_tokens"] for r in results)

    summary = {
        "total_prompts": len(PROMPTS),
        "unconstrained_first_try_valid": unc_first_try,
        "constrained_first_try_valid": con_first_try,
        "unconstrained_total_tokens": unc_total_tokens,
        "constrained_total_tokens": con_total_tokens,
        "token_savings_pct": round((1 - con_total_tokens / max(unc_total_tokens, 1)) * 100, 1),
        "first_try_improvement": con_first_try - unc_first_try,
    }

    return {"summary": summary, "results": results, "grammar_length": len(grammar)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark constrained vs unconstrained AINL decode")
    parser.add_argument("--ainl-url", default=AINL_URL)
    parser.add_argument("--llm-url", default=LLM_URL)
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    report = run_benchmark(args.ainl_url, args.llm_url)

    output = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"\nResults written to {args.output}")
    else:
        print(output)

    if "summary" in report:
        s = report["summary"]
        print(f"\n--- Summary ---")
        print(f"First-try valid: unconstrained={s['unconstrained_first_try_valid']}/{s['total_prompts']}, "
              f"constrained={s['constrained_first_try_valid']}/{s['total_prompts']}")
        print(f"Total tokens: unconstrained={s['unconstrained_total_tokens']}, "
              f"constrained={s['constrained_total_tokens']} ({s['token_savings_pct']}% savings)")


if __name__ == "__main__":
    main()
