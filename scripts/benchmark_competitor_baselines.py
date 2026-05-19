#!/usr/bin/env python3
"""
Measure tiktoken (cl100k_base) authoring sizes for AINL vs hand-written baselines.

Writes tooling/competitor_baseline_tokens.json for docs/competitive/COMPARISON_TABLE.md.

Usage:
  python scripts/benchmark_competitor_baselines.py
  python scripts/benchmark_competitor_baselines.py --json-out tooling/competitor_baseline_tokens.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tooling.bench_metrics import tiktoken_count  # noqa: E402

DEFAULT_JSON = ROOT / "tooling" / "competitor_baseline_tokens.json"

WORKLOADS: List[Dict[str, str]] = [
    {
        "id": "enterprise_monitor",
        "ainl": "examples/benchmark/enterprise_monitor.ainl",
        "python_hand_optimized": "benchmarks/handwritten_baselines/authoring_density/enterprise_monitor.py",
        "langgraph": "benchmarks/handwritten_baselines/competitive/langgraph/enterprise_monitor_langgraph.py",
    },
    {
        "id": "support_ticket_router",
        "ainl": "examples/workflows/support_ticket_router.ainl",
        "python_hand_optimized": "benchmarks/handwritten_baselines/authoring_density/support_ticket_router.py",
        "langgraph": "benchmarks/handwritten_baselines/competitive/langgraph/support_ticket_router_langgraph.py",
    },
]


def _read_rel(path: str) -> str:
    p = ROOT / path
    if not p.is_file():
        raise FileNotFoundError(p)
    return p.read_text(encoding="utf-8")


def measure_workload(spec: Dict[str, str]) -> Dict[str, Any]:
    ainl_text = _read_rel(spec["ainl"])
    py_text = _read_rel(spec["python_hand_optimized"])
    lg_text = _read_rel(spec["langgraph"])
    ainl_tk = tiktoken_count(ainl_text)
    py_tk = tiktoken_count(py_text)
    lg_tk = tiktoken_count(lg_text)

    def ratio(num: int, den: int) -> float | None:
        return round(num / den, 2) if den > 0 else None

    return {
        "id": spec["id"],
        "paths": {
            "ainl": spec["ainl"],
            "python_hand_optimized": spec["python_hand_optimized"],
            "langgraph": spec["langgraph"],
        },
        "tiktoken_cl100k_base": {
            "ainl": ainl_tk,
            "python_hand_optimized": py_tk,
            "langgraph": lg_tk,
        },
        "ratios_vs_ainl": {
            "python_hand_optimized_div_ainl": ratio(py_tk, ainl_tk),
            "langgraph_div_ainl": ratio(lg_tk, ainl_tk),
        },
        "notes": (
            "Authoring token counts on source files. "
            "LangGraph includes StateGraph boilerplate; "
            "python_hand_optimized is baseline B (competent engineer, no compiler)."
        ),
    }


def build_report() -> Dict[str, Any]:
    workloads = [measure_workload(w) for w in WORKLOADS]
    return {
        "schema_version": "1.0",
        "kind": "competitor_baseline_tokens",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "token_counting_method": "tiktoken_cl100k_base",
        "methodology_doc": "docs/competitive/VERSUS_LANGGRAPH_TEMPORAL_BENCHMARKS.md",
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Competitor baseline tiktoken counts")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_JSON,
        help=f"Output JSON path (default: {DEFAULT_JSON})",
    )
    args = parser.parse_args()
    report = build_report()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
