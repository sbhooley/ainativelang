#!/usr/bin/env python3
"""
Temporal authoring-token benchmark (TODO scaffold — not yet implemented).

PURPOSE
-------
Close the Temporal-side gap identified in the 2026-05 community review.
``docs/competitive/COMPARISON_TABLE.md`` §A explicitly leaves
"Temporal SDK hand-written baselines remain **TBD**". This script is the
placeholder that, when implemented, will fill that cell.

SCOPE — AUTHORING ONLY (deliberate)
-----------------------------------
We do **not** attempt to benchmark Temporal *runtime* against AINL.
Temporal's value proposition is durability and worker history, not
per-step latency. A runtime race would be the wrong comparison and would
mislead reviewers. AINL ``--emit temporal`` produces a Temporal workflow
from an ``.ainl`` source; the right comparison is **how many tokens of
source code did the human (or LLM) have to write** to express the same
workload.

This is symmetric with ``benchmark_competitor_baselines.py`` which
measures the same axis vs LangGraph and hand-optimized Python.

WHAT IT MEASURES (when implemented)
-----------------------------------
For each reference workload:

  - ``.ainl`` source token count (tiktoken cl100k_base)
  - Hand-written Temporal worker source token count (same workload,
    idiomatic ``@workflow.defn`` + activities)
  - Ratio ``temporal_div_ainl``

PLUS the qualitative axes that matter for "lift to Temporal":

  - Activity boundary count (Temporal forces you to think about these;
    AINL emits them from IR adapter calls)
  - Determinism gotchas in hand-written Temporal (random IDs, time-of-day
    branching) that the AINL emit path handles by construction

WORKLOADS PLANNED
-----------------
1. ``enterprise_monitor`` — same as ``benchmark_competitor_baselines.py``
2. ``support_ticket_router`` — same
3. (Stretch) ``data_pipeline`` — file-heavy workload that exercises
   activity boundaries

OUTPUT
------
Writes ``tooling/temporal_authoring_tokens.json``. Schema mirrors
``competitor_baseline_tokens.json`` so downstream tooling (the
``COMPARISON_TABLE.md`` regenerator, eventually) can consume both.

USAGE (future)
--------------
::

    python scripts/benchmark_temporal_authoring.py
    python scripts/benchmark_temporal_authoring.py --workload enterprise_monitor

TRACKER
-------
See ``docs/competitive/LONG_TERM_FIXES_TRACKER.md`` row **T2.2**.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_OUT = ROOT / "tooling" / "temporal_authoring_tokens.json"
SCHEMA_VERSION = "0.1.0-todo"


def _placeholder_payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "not_implemented",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tracker_row": "T2.2",
        "tracker_doc": "docs/competitive/LONG_TERM_FIXES_TRACKER.md",
        "scope": "authoring_tokens_only",
        "explicitly_not_claiming": (
            "Runtime parity with Temporal. Temporal's value is durability "
            "and worker history. AINL emits TO Temporal; it does not "
            "compete with the durability layer."
        ),
        "tokenizer": "tiktoken cl100k_base",
        "workloads_planned": [
            {
                "name": "enterprise_monitor",
                "source_ainl": "examples/benchmark/enterprise_monitor.ainl",
                "source_temporal_planned": (
                    "benchmarks/handwritten_baselines/competitive/temporal/"
                    "enterprise_monitor_temporal.py"
                ),
                "notes": "Hand-written Temporal worker, idiomatic activities + workflow.",
            },
            {
                "name": "support_ticket_router",
                "source_ainl": "examples/workflows/support_ticket_router.ainl",
                "source_temporal_planned": (
                    "benchmarks/handwritten_baselines/competitive/temporal/"
                    "support_ticket_router_temporal.py"
                ),
                "notes": "Activities per integration (Zendesk/Stripe/Clearbit), workflow for orchestration.",
            },
        ],
        "qualitative_axes_when_implemented": [
            "activity_boundary_count",
            "determinism_gotchas_avoided_by_emit",
            "lift_from_ainl_emit_to_running_worker_loc",
        ],
        "next_action": (
            "Hand-write Temporal workers for the two workloads above; "
            "count source tokens; commit JSON; update COMPARISON_TABLE.md §A."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help="Path to write JSON output (default: tooling/temporal_authoring_tokens.json)",
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
        f"[benchmark_temporal_authoring] Wrote placeholder to {out_path} "
        f"(status: {payload['status']}; tracker: {payload['tracker_row']})."
    )
    print(msg)
    if args.print:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
