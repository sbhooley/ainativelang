#!/usr/bin/env python3
"""
Compare two AINL benchmark JSON reports (size or runtime) and fail on regressions.

Regression rules (baseline = old JSON, candidate = new JSON):
  - Size: per (mode, profile, artifact), ``ainl_source_size`` and ``aggregate_generated_output_size``
    must not exceed old × (1 + threshold). Cost dicts must not increase.
  - Runtime: same keying for artifact rows — ``latency_ms.mean_ms``, ``peak_rss_delta_mb``;
    stricter cost dicts; optional reliability success_rate must not drop materially.
  - Baseline groups (runtime only): pure/langgraph latency + RSS; group-level cost dicts.

Non-numeric and missing fields are skipped. Keys only in one report are ignored (no baseline).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ArtifactKey = Tuple[str, str, str]  # (mode_name, profile_name, artifact_path)
BaselineSideKey = Tuple[str, str]  # (group_name, "pure"|"langgraph")


def as_number(value: Any) -> Optional[float]:
    """Coerce to float for comparisons; ignore null, NaN, inf, and common N/A strings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, str):
        s = value.strip().upper()
        if s in ("", "N/A", "NA", "—", "-"):
            return None
        try:
            f = float(s)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except ValueError:
            return None
    return None


def load_report(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a JSON object")
    return data


def report_kind(data: Dict[str, Any]) -> str:
    if data.get("kind") == "runtime":
        return "runtime"
    if "modes" in data and "targets" in data:
        return "size"
    if "modes" in data:
        # Runtime also has modes; kind disambiguates.
        return "runtime"
    raise ValueError("Unrecognized benchmark JSON (expected size or runtime report)")


def iter_mode_profile_artifacts(
    data: Dict[str, Any],
) -> Iterable[Tuple[ArtifactKey, Dict[str, Any]]]:
    modes = data.get("modes") or {}
    if not isinstance(modes, dict):
        return
    for mode_name, mode_payload in modes.items():
        if not isinstance(mode_payload, dict):
            continue
        for prof in mode_payload.get("profiles") or []:
            if not isinstance(prof, dict):
                continue
            pname = str(prof.get("name") or "")
            for art in prof.get("artifacts") or []:
                if not isinstance(art, dict):
                    continue
                rel = art.get("artifact")
                if not rel:
                    continue
                yield (str(mode_name), pname, str(rel)), art


def iter_baseline_sides(
    data: Dict[str, Any],
) -> Iterable[Tuple[BaselineSideKey, Dict[str, Any]]]:
    baselines = data.get("baselines") or {}
    if not isinstance(baselines, dict):
        return
    for g in baselines.get("groups") or []:
        if not isinstance(g, dict):
            continue
        gname = str(g.get("name") or "unknown")
        for side in ("pure", "langgraph"):
            blob = g.get(side)
            if isinstance(blob, dict):
                yield (gname, side), blob


def compare_cost_dicts(
    old_d: Any,
    new_d: Any,
    *,
    path: str,
    failures: List[str],
    verbose: bool,
) -> None:
    if not isinstance(old_d, dict) or not isinstance(new_d, dict):
        return
    for k in old_d:
        if k not in new_d:
            continue
        o = as_number(old_d.get(k))
        n = as_number(new_d.get(k))
        if o is None or n is None:
            continue
        if n > o + 1e-15:
            msg = f"{path} cost[{k}]: old={o:.12g} new={n:.12g} (cost increased)"
            failures.append(msg)
            if verbose:
                print(msg, file=sys.stderr)


def check_worse(
    old_v: Optional[float],
    new_v: Optional[float],
    *,
    path: str,
    label: str,
    threshold: float,
    failures: List[str],
    verbose: bool,
) -> None:
    if old_v is None or new_v is None:
        return
    limit = old_v * (1.0 + threshold)
    if new_v > limit + 1e-15:
        ratio = new_v / old_v if old_v else float("inf")
        msg = (
            f"{path} {label}: old={old_v:.12g} new={new_v:.12g} "
            f"ratio={ratio:.4f} limit={limit:.12g} (threshold={threshold:.0%})"
        )
        failures.append(msg)
        if verbose:
            print(msg, file=sys.stderr)


def check_ok_regression(
    old_row: Dict[str, Any],
    new_row: Dict[str, Any],
    *,
    path: str,
    failures: List[str],
    verbose: bool,
) -> None:
    o_ok = old_row.get("ok")
    n_ok = new_row.get("ok")
    if o_ok is True and n_ok is not True:
        msg = f"{path} ok: old=True new={n_ok!r}"
        failures.append(msg)
        if verbose:
            print(msg, file=sys.stderr)


def check_success_rate(
    old_blob: Dict[str, Any],
    new_blob: Dict[str, Any],
    *,
    path: str,
    field: str,
    failures: List[str],
    verbose: bool,
) -> None:
    o_er = old_blob.get(field)
    n_er = new_blob.get(field)
    if not isinstance(o_er, dict) or not isinstance(n_er, dict):
        return
    o_sr = as_number(o_er.get("success_rate"))
    n_sr = as_number(n_er.get("success_rate"))
    if o_sr is None or n_sr is None:
        return
    if n_sr + 1e-6 < o_sr:
        msg = f"{path} {field}.success_rate: old={o_sr:.6f} new={n_sr:.6f}"
        failures.append(msg)
        if verbose:
            print(msg, file=sys.stderr)


def compare_size_reports(
    old: Dict[str, Any],
    new: Dict[str, Any],
    *,
    threshold: float,
    verbose: bool,
) -> List[str]:
    failures: List[str] = []
    old_map: Dict[ArtifactKey, Dict[str, Any]] = dict(iter_mode_profile_artifacts(old))
    for key, new_art in iter_mode_profile_artifacts(new):
        oa = old_map.get(key)
        if not oa:
            if verbose:
                print(f"[skip] no baseline for size key {key}", file=sys.stderr)
            continue
        path = f"size:{key[0]}/{key[1]}/{key[2]}"

        check_worse(
            as_number(oa.get("ainl_source_size")),
            as_number(new_art.get("ainl_source_size")),
            path=f"{path} ainl_source_size",
            label="tiktokens(source)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        check_worse(
            as_number(oa.get("aggregate_generated_output_size")),
            as_number(new_art.get("aggregate_generated_output_size")),
            path=f"{path} aggregate_generated_output_size",
            label="tiktokens(emit aggregate)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        compare_cost_dicts(
            oa.get("estimated_cost_usd_per_generation"),
            new_art.get("estimated_cost_usd_per_generation"),
            path=path,
            failures=failures,
            verbose=verbose,
        )
        check_success_rate(
            oa,
            new_art,
            path=path,
            field="compile_reliability",
            failures=failures,
            verbose=verbose,
        )
    return failures


def compare_runtime_reports(
    old: Dict[str, Any],
    new: Dict[str, Any],
    *,
    threshold: float,
    verbose: bool,
) -> List[str]:
    failures: List[str] = []
    old_map: Dict[ArtifactKey, Dict[str, Any]] = dict(iter_mode_profile_artifacts(old))
    for key, new_art in iter_mode_profile_artifacts(new):
        oa = old_map.get(key)
        if not oa:
            if verbose:
                print(f"[skip] no baseline for runtime key {key}", file=sys.stderr)
            continue
        path = f"runtime:{key[0]}/{key[1]}/{key[2]}"

        check_ok_regression(oa, new_art, path=path, failures=failures, verbose=verbose)

        old_lat = oa.get("latency_ms") if isinstance(oa.get("latency_ms"), dict) else {}
        new_lat = new_art.get("latency_ms") if isinstance(new_art.get("latency_ms"), dict) else {}
        check_worse(
            as_number(old_lat.get("mean_ms")),
            as_number(new_lat.get("mean_ms")),
            path=f"{path} latency_ms.mean_ms",
            label="mean latency (ms)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        check_worse(
            as_number(oa.get("peak_rss_delta_mb")),
            as_number(new_art.get("peak_rss_delta_mb")),
            path=f"{path} peak_rss_delta_mb",
            label="peak RSS Δ (MB)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        compare_cost_dicts(
            oa.get("estimated_cost_usd_per_run"),
            new_art.get("estimated_cost_usd_per_run"),
            path=path,
            failures=failures,
            verbose=verbose,
        )
        check_success_rate(
            oa,
            new_art,
            path=path,
            field="execution_reliability",
            failures=failures,
            verbose=verbose,
        )

    old_groups = {k: v for k, v in iter_baseline_sides(old)}
    for key, new_blob in iter_baseline_sides(new):
        ob = old_groups.get(key)
        if not ob:
            if verbose:
                print(f"[skip] no baseline for handwritten group {key}", file=sys.stderr)
            continue
        gpath = f"runtime:baseline/{key[0]}/{key[1]}"
        check_ok_regression(ob, new_blob, path=gpath, failures=failures, verbose=verbose)
        o_lat = ob.get("latency_ms") if isinstance(ob.get("latency_ms"), dict) else {}
        n_lat = new_blob.get("latency_ms") if isinstance(new_blob.get("latency_ms"), dict) else {}
        check_worse(
            as_number(o_lat.get("mean_ms")),
            as_number(n_lat.get("mean_ms")),
            path=f"{gpath} latency_ms.mean_ms",
            label="mean latency (ms)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        check_worse(
            as_number(ob.get("peak_rss_delta_mb")),
            as_number(new_blob.get("peak_rss_delta_mb")),
            path=f"{gpath} peak_rss_delta_mb",
            label="peak RSS Δ (MB)",
            threshold=threshold,
            failures=failures,
            verbose=verbose,
        )
        check_success_rate(
            ob,
            new_blob,
            path=gpath,
            field="execution_reliability",
            failures=failures,
            verbose=verbose,
        )

    # Group-level economics (attached to first side dict is wrong); use parent group merge.
    def group_cost_maps(rep: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        baselines = rep.get("baselines") or {}
        if not isinstance(baselines, dict):
            return out
        for g in baselines.get("groups") or []:
            if not isinstance(g, dict):
                continue
            name = str(g.get("name") or "unknown")
            for field in (
                "estimated_cost_usd_per_run_handwritten_stack",
                "estimated_cost_usd_per_run_ainl_reference",
            ):
                d = g.get(field)
                if isinstance(d, dict):
                    out[f"{name}:{field}"] = d
        return out

    old_gc = group_cost_maps(old)
    new_gc = group_cost_maps(new)
    for gkey, old_d in old_gc.items():
        if gkey not in new_gc:
            continue
        compare_cost_dicts(old_d, new_gc[gkey], path=f"runtime:{gkey}", failures=failures, verbose=verbose)

    return failures


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Compare two benchmark JSON files; exit 1 if regressions exceed tolerance."
    )
    ap.add_argument("--old-json", type=Path, required=True, help="Baseline (e.g. from main branch)")
    ap.add_argument("--new-json", type=Path, required=True, help="Candidate report from current run")
    ap.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="Allowed relative increase for size/latency/RSS (default: 0.10 = 10%%)",
    )
    ap.add_argument("--verbose", "-v", action="store_true", help="Print each failure as it is recorded")
    ap.add_argument(
        "--allow-missing-old",
        action="store_true",
        help="If --old-json is missing, exit 0 (for bootstrap before baselines exist in git)",
    )
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.threshold < 0:
        print("--threshold must be >= 0", file=sys.stderr)
        return 2

    if not args.old_json.is_file():
        if args.allow_missing_old:
            print(f"compare_benchmark_json: old JSON missing ({args.old_json}); SKIP (allow-missing-old)")
            return 0
        print(f"compare_benchmark_json: old JSON not found: {args.old_json}", file=sys.stderr)
        return 2
    if not args.new_json.is_file():
        print(f"compare_benchmark_json: new JSON not found: {args.new_json}", file=sys.stderr)
        return 2

    old = load_report(args.old_json)
    new = load_report(args.new_json)
    ko, kn = report_kind(old), report_kind(new)
    if ko != kn:
        print(f"Report kind mismatch: old={ko} new={kn}", file=sys.stderr)
        return 2

    if kn == "size":
        failures = compare_size_reports(old, new, threshold=args.threshold, verbose=args.verbose)
    else:
        failures = compare_runtime_reports(old, new, threshold=args.threshold, verbose=args.verbose)

    if failures:
        print(f"compare_benchmark_json: FAIL ({len(failures)} regression(s))", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(
        f"compare_benchmark_json: PASS ({kn}, threshold={args.threshold:.0%}, "
        f"old={args.old_json} new={args.new_json})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
