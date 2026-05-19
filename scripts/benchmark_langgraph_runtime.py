#!/usr/bin/env python3
"""
LangGraph runtime token benchmark (TODO scaffold — not yet implemented).

PURPOSE
-------
Close the gap identified in the 2026-05 community review: the existing
``benchmark_competitor_baselines.py`` only measures **authoring** tokens
(source-file tiktoken on hand-written LangGraph vs ``.ainl``). It does
*not* measure **runtime** tokens — i.e. what each system actually spends
per execution.

This script is the placeholder. When implemented, it will:

  1. Run a LangGraph agent loop end-to-end on the same workload as the
     committed AINL example (e.g. ``enterprise_monitor.ainl`` / the
     ``enterprise_monitor`` scenario in ``benchmark_compile_once_run_many.py``).
  2. Capture every LLM call the LangGraph agent makes via a token-tracking
     wrapper (likely ``langchain_core.callbacks`` or a model-side counter).
  3. Run the same workload N times in both stacks, with the same trigger
     events (e.g. 90% healthy / 10% incident for the monitor scenario).
  4. Emit a per-stack ``tokens_per_run`` series + aggregate ratio.

WHY THIS MATTERS
----------------
The critic correctly observed that "competitor comparisons are empty" on
the runtime axis. Authoring compactness (≈2× vs LangGraph) does **not**
prove runtime savings; orchestration-token wins only land if LangGraph
re-prompts on every step. This script makes that claim falsifiable.

HONEST SCOPE WHEN IMPLEMENTED
-----------------------------
- Tokens are measured against a *specific* LangGraph implementation
  (hand-written, idiomatic) — not an "average" agent.
- LangGraph users can opt out of routing-LLM calls by hard-coding edges;
  the baseline in this script should be a typical agent-style routing
  graph, NOT a degenerate hard-coded one. Document both versions when
  publishing numbers.
- Runtime parity is NOT proof of feature parity. LangGraph offers
  streaming, human-in-the-loop, etc. that AINL does not yet match.

OUTPUT
------
Writes ``tooling/benchmark_langgraph_runtime.json`` with:
  - ``status``: ``"not_implemented"`` (today) or ``"implemented"`` (later)
  - ``schema_version``
  - ``workloads[].name``
  - ``workloads[].langgraph_tokens_per_run``
  - ``workloads[].ainl_tokens_per_run``
  - ``workloads[].ratio_langgraph_over_ainl``
  - ``methodology``: free-form notes on the LangGraph implementation
    chosen for comparison, plus baseline qualifier (A/B per
    ``WHEN_AINL_DOES_NOT_HELP.md``).

USAGE (future)
--------------
::

    python scripts/benchmark_langgraph_runtime.py
    python scripts/benchmark_langgraph_runtime.py --workload enterprise_monitor
    python scripts/benchmark_langgraph_runtime.py --runs 200

TRACKER
-------
See ``docs/competitive/LONG_TERM_FIXES_TRACKER.md`` row **T2.1**.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_OUT = ROOT / "tooling" / "benchmark_langgraph_runtime.json"
SCHEMA_VERSION = "0.1.0-todo"


def _placeholder_payload() -> dict:
    """Stub output until the benchmark is implemented (Tier 2 work)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "not_implemented",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tracker_row": "T2.1",
        "tracker_doc": "docs/competitive/LONG_TERM_FIXES_TRACKER.md",
        "rationale": (
            "Closes the runtime-side gap in benchmark_competitor_baselines.py "
            "(which only measures authoring tokens). Will produce a per-run "
            "LangGraph vs AINL token comparison on the same workload."
        ),
        "workloads_planned": [
            {
                "name": "enterprise_monitor",
                "source_ainl": "examples/benchmark/enterprise_monitor.ainl",
                "source_langgraph": (
                    "benchmarks/handwritten_baselines/competitive/langgraph/"
                    "enterprise_monitor_langgraph.py"
                ),
                "scenario_notes": (
                    "Health check every 5 min; 90% healthy / 10% incident; "
                    "incident path calls LLM once for alert summary."
                ),
            },
            {
                "name": "support_ticket_router",
                "source_ainl": "examples/workflows/support_ticket_router.ainl",
                "source_langgraph": (
                    "benchmarks/handwritten_baselines/competitive/langgraph/"
                    "support_ticket_router_langgraph.py"
                ),
                "scenario_notes": (
                    "Three-tier triage. LangGraph agentic routing vs AINL IR "
                    "branches. Baseline LangGraph should be agent-style (not "
                    "hard-coded edges) to be a fair representative."
                ),
            },
        ],
        "methodology_notes_when_implemented": [
            "Wrap LangGraph LLM calls with a token-counting callback.",
            "Mock the same LLM provider in both stacks; identical prompts.",
            "Run N=100 invocations per workload; report mean + p95 tokens/run.",
            "Always tag the result with baseline (A/B per WHEN_AINL_DOES_NOT_HELP.md).",
            "Do NOT claim AINL beats LangGraph on streaming/HITL/etc.",
        ],
        "next_action": (
            "Implement LangGraph wrappers + token callback; rerun this "
            "script; replace status with 'implemented'."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help="Path to write JSON output (default: tooling/benchmark_langgraph_runtime.json)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Also print the payload to stdout",
    )
    args = parser.parse_args()

    payload = _placeholder_payload()
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    msg = (
        f"[benchmark_langgraph_runtime] Wrote placeholder to {out_path} "
        f"(status: {payload['status']}; tracker: {payload['tracker_row']})."
    )
    print(msg)
    if args.print:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
