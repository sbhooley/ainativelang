#!/usr/bin/env python3
"""Segmented, capability-driven size benchmark for AI Native Lang (AINL)."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tooling.emission_planner import TARGET_ORDER, load_benchmark_manifest, required_emit_targets

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_PROFILES = ROOT / "tooling" / "artifact_profiles.json"
DEFAULT_BENCHMARK_MANIFEST = ROOT / "tooling" / "benchmark_manifest.json"
DEFAULT_JSON_OUT = ROOT / "tooling" / "benchmark_size.json"
DEFAULT_MARKDOWN_OUT = ROOT / "BENCHMARK.md"
DEFAULT_BASELINES_ROOT = ROOT / "benchmarks" / "handwritten_baselines"
PROFILE_CLASSES = ("strict-valid", "non-strict-only", "legacy-compat")

# Keep in sync with scripts/benchmark_runtime.py (AINL path per handwritten group).
BASELINE_AINL_REFERENCE: Dict[str, str] = {
    "token_budget_monitor": "openclaw/bridge/wrappers/token_budget_alert.ainl",
    "basic_scraper": "examples/scraper/basic_scraper.ainl",
    "retry_timeout_wrapper": "examples/retry_error_resilience.ainl",
}

TARGET_EMITTERS: Dict[str, str] = {
    "react_ts": "emit_react",
    "python_api": "emit_python_api",
    "prisma": "emit_prisma_schema",
    "mt5": "emit_mt5",
    "scraper": "emit_python_scraper",
    "cron": "emit_cron_stub",
}


@dataclass
class BenchmarkFailure:
    artifact: str
    stage: str
    detail: str


class BenchmarkError(Exception):
    def __init__(self, failures: Sequence[BenchmarkFailure]) -> None:
        self.failures = list(failures)
        msg = "\n".join(f"- {f.artifact} [{f.stage}]: {f.detail}" for f in self.failures)
        super().__init__(f"benchmark failed with {len(self.failures)} error(s):\n{msg}")


def approx_chunks(text: str) -> int:
    return len(re.findall(r"\S+", text))


def nonempty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def tiktoken_chunks(text: str) -> int:
    try:
        import tiktoken  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("tiktoken mode requested but tiktoken is not installed") from exc
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def metric_counter(metric: str) -> Callable[[str], int]:
    if metric == "approx_chunks":
        return approx_chunks
    if metric == "nonempty_lines":
        return nonempty_lines
    if metric == "tiktoken":
        return tiktoken_chunks
    raise ValueError(f"unsupported metric: {metric}")


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_artifact_class_map(path: Path, *, section: str) -> Dict[str, str]:
    profile = load_json(path)
    sec = profile.get(section)
    if not isinstance(sec, dict):
        raise ValueError(f"missing or invalid section '{section}' in {path}")
    out: Dict[str, str] = {}
    for cls in PROFILE_CLASSES:
        vals = sec.get(cls, [])
        if not isinstance(vals, list):
            raise ValueError(f"invalid class list '{section}.{cls}'")
        for rel in vals:
            out[str(rel)] = cls
    return out


def discover_baseline_groups(baselines_root: Path) -> List[Path]:
    """Subdirs containing both ``pure_async_python.py`` and ``langgraph_version.py``."""
    if not baselines_root.is_dir():
        return []
    out: List[Path] = []
    for p in sorted(baselines_root.iterdir()):
        if not p.is_dir():
            continue
        if (p / "pure_async_python.py").is_file() and (p / "langgraph_version.py").is_file():
            out.append(p)
    return out


def measure_baseline_py_sources(subdir: Path) -> Dict[str, Any]:
    """Nonempty line counts and ``tiktoken`` cl100k_base counts for the two baseline modules."""
    pure_path = subdir / "pure_async_python.py"
    lang_path = subdir / "langgraph_version.py"
    pure_text = pure_path.read_text(encoding="utf-8")
    lang_text = lang_path.read_text(encoding="utf-8")
    out: Dict[str, Any] = {
        "pure_nonempty_lines": nonempty_lines(pure_text),
        "lang_nonempty_lines": nonempty_lines(lang_text),
        "combined_nonempty_lines": nonempty_lines(pure_text) + nonempty_lines(lang_text),
        "pure_tiktoken": None,
        "lang_tiktoken": None,
        "tiktoken_error": None,
    }
    try:
        out["pure_tiktoken"] = tiktoken_chunks(pure_text)
        out["lang_tiktoken"] = tiktoken_chunks(lang_text)
    except Exception as exc:  # pragma: no cover
        out["tiktoken_error"] = str(exc)
    return out


def safe_ainl_aggregate_emit_size(
    rel: str,
    *,
    root: Path,
    mode_name: str,
    benchmark_manifest: Dict,
    compiler: Any,
    count_fn: Callable[[str], int],
) -> Optional[int]:
    """Return aggregate emitted size for *rel* under *mode_name*, or None on failure."""
    src_path = root / rel
    if not src_path.exists():
        return None
    try:
        source_text = src_path.read_text(encoding="utf-8")
        ir = compiler.compile(source_text)
        included = required_emit_targets(
            source_text,
            ir,
            mode=mode_name,
            benchmark_manifest=benchmark_manifest,
        )
        if not included:
            return None
        sizes, _ = _emit_selected_targets(compiler, ir, count_fn, rel, list(included))
        return int(sum(sizes[t] for t in included))
    except Exception:
        return None


def build_handwritten_baseline_size_comparison(
    *,
    baselines_root: Path,
    benchmark_manifest: Dict,
    compiler: Any,
    active_metric_fn: Callable[[str], int],
    active_metric_name: str,
    root: Path = ROOT,
) -> Dict[str, Any]:
    """
    For each handwritten group, measure Python source lines/tokens and AINL emitted aggregates
    per emit mode for the mapped reference artifact.
    """
    groups_dir = discover_baseline_groups(baselines_root)
    names = [p.name for p in groups_dir]
    logger.info(
        "Handwritten baseline size comparison: %d groups (%s)",
        len(names),
        ", ".join(names) or "none",
    )

    tiktoken_fn: Optional[Callable[[str], int]] = None
    try:
        tiktoken_fn = metric_counter("tiktoken")
    except Exception as exc:
        logger.warning("tiktoken unavailable for baseline token ratios: %s", exc)

    groups: List[Dict[str, Any]] = []
    for subdir in groups_dir:
        name = subdir.name
        src_stats = measure_baseline_py_sources(subdir)
        rel = BASELINE_AINL_REFERENCE.get(name)
        g: Dict[str, Any] = {
            "name": name,
            "ainl_reference_artifact": rel,
            "baseline_source": src_stats,
            "modes": {},
        }
        for mode_name in ("minimal_emit", "full_multitarget"):
            ainl_active: Optional[int] = None
            ainl_tik: Optional[int] = None
            if rel:
                ainl_active = safe_ainl_aggregate_emit_size(
                    rel,
                    root=root,
                    mode_name=mode_name,
                    benchmark_manifest=benchmark_manifest,
                    compiler=compiler,
                    count_fn=active_metric_fn,
                )
                if tiktoken_fn is not None:
                    ainl_tik = safe_ainl_aggregate_emit_size(
                        rel,
                        root=root,
                        mode_name=mode_name,
                        benchmark_manifest=benchmark_manifest,
                        compiler=compiler,
                        count_fn=tiktoken_fn,
                    )
            pure_tk = src_stats.get("pure_tiktoken")
            lang_tk = src_stats.get("lang_tiktoken")
            g["modes"][mode_name] = {
                "ainl_aggregate_emit_active_metric": ainl_active,
                "active_metric": active_metric_name,
                "ainl_aggregate_emit_tiktoken": ainl_tik,
                "ratio_ainl_tiktoken_over_pure_py_tiktoken": _ratio_float(ainl_tik, pure_tk),
                "ratio_ainl_tiktoken_over_langgraph_tiktoken": _ratio_float(ainl_tik, lang_tk),
                "ratio_ainl_active_over_pure_tiktoken": _ratio_float(ainl_active, pure_tk),
                "ratio_ainl_active_over_lang_tiktoken": _ratio_float(ainl_active, lang_tk),
            }
        groups.append(g)

    return {
        "groups": groups,
        "baselines_root": str(baselines_root),
        "tiktoken_available": tiktoken_fn is not None,
    }


def _ratio_float(num: Optional[int], den: Optional[Any]) -> Optional[float]:
    if num is None or den is None:
        return None
    try:
        d = float(den)
        if d <= 0:
            return None
        return float(num) / d
    except (TypeError, ValueError):
        return None


def resolve_profile_selection(
    profile_name: str,
    *,
    artifact_profiles_path: Path,
    benchmark_manifest_path: Path,
) -> Tuple[List[str], Dict[str, str], Dict]:
    manifest = load_benchmark_manifest(benchmark_manifest_path)
    profiles = manifest.get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"unknown benchmark profile '{profile_name}'")
    cfg = profiles[profile_name]
    section = cfg["artifact_profiles_section"]
    classes = tuple(cfg["classes"])
    all_map = load_artifact_class_map(artifact_profiles_path, section=section)
    selected = sorted(rel for rel, cls in all_map.items() if cls in classes)
    return selected, {k: all_map[k] for k in selected}, cfg


def _emit_selected_targets(
    compiler,
    ir: Dict,
    count_fn: Callable[[str], int],
    artifact: str,
    selected_targets: Sequence[str],
) -> Tuple[Dict[str, int], Dict[str, str]]:
    out: Dict[str, int] = {}
    rendered_out: Dict[str, str] = {}
    for target in selected_targets:
        emitter_name = TARGET_EMITTERS[target]
        emitter = getattr(compiler, emitter_name, None)
        if emitter is None:
            raise BenchmarkError([BenchmarkFailure(artifact, f"emit:{target}", f"missing emitter {emitter_name}")])
        try:
            rendered = emitter(ir)
        except Exception as exc:
            raise BenchmarkError([BenchmarkFailure(artifact, f"emit:{target}", str(exc))]) from exc
        out[target] = count_fn(rendered)
        rendered_out[target] = rendered
    return out, rendered_out


def _python_line_chunks(lines: List[str], count_fn: Callable[[str], int]) -> int:
    if not lines:
        return 0
    return count_fn("\n".join(lines) + "\n")


def _target_structure_breakdown(
    target: str,
    rendered: str,
    count_fn: Callable[[str], int],
) -> Dict[str, int]:
    lines = [ln.rstrip("\n") for ln in rendered.splitlines()]
    if target == "python_api":
        import_lines = [ln for ln in lines if ln.startswith("from ") or ln.startswith("import ")]
        deco_lines = [ln for ln in lines if ln.startswith("@app.")]
        def_lines = [ln for ln in lines if ln.startswith("def ")]
        return_lines = [ln for ln in lines if "return" in ln]
        return {
            "imports_chunks": _python_line_chunks(import_lines, count_fn),
            "decorator_chunks": _python_line_chunks(deco_lines, count_fn),
            "function_def_chunks": _python_line_chunks(def_lines, count_fn),
            "return_chunks": _python_line_chunks(return_lines, count_fn),
            "total_chunks": count_fn(rendered),
        }
    if target == "scraper":
        import_lines = [ln for ln in lines if ln.startswith("from ") or ln.startswith("import ")]
        def_lines = [ln for ln in lines if ln.startswith("def scrape_")]
        request_lines = [ln for ln in lines if "requests.get(" in ln]
        selector_lines = [ln for ln in lines if "select_one(" in ln]
        return_lines = [ln for ln in lines if "return" in ln]
        return {
            "imports_chunks": _python_line_chunks(import_lines, count_fn),
            "function_def_chunks": _python_line_chunks(def_lines, count_fn),
            "request_call_chunks": _python_line_chunks(request_lines, count_fn),
            "selector_chunks": _python_line_chunks(selector_lines, count_fn),
            "return_chunks": _python_line_chunks(return_lines, count_fn),
            "total_chunks": count_fn(rendered),
        }
    if target == "cron":
        def_lines = [ln for ln in lines if ln.startswith("def run_")]
        comment_lines = [ln for ln in lines if ln.strip().startswith("#")]
        pass_lines = [ln for ln in lines if ln.strip() == "pass"]
        return {
            "function_def_chunks": _python_line_chunks(def_lines, count_fn),
            "schedule_comment_chunks": _python_line_chunks(comment_lines, count_fn),
            "pass_chunks": _python_line_chunks(pass_lines, count_fn),
            "total_chunks": count_fn(rendered),
        }
    return {"total_chunks": count_fn(rendered)}


def run_profile_benchmark(
    source_paths: Sequence[str],
    *,
    class_map: Dict[str, str],
    mode_name: str,
    benchmark_manifest: Dict,
    root: Path,
    count_fn: Callable[[str], int],
    compiler,
) -> Dict:
    failures: List[BenchmarkFailure] = []
    rows: List[Dict] = []
    totals_all = {t: 0 for t in TARGET_ORDER}
    source_total = 0
    aggregate_total = 0
    target_structure_totals: Dict[str, Dict[str, int]] = {}

    for rel in source_paths:
        src_path = root / rel
        if not src_path.exists():
            failures.append(BenchmarkFailure(rel, "source", "file not found"))
            continue
        source_text = src_path.read_text(encoding="utf-8")
        source_size = count_fn(source_text)
        source_total += source_size
        try:
            ir = compiler.compile(source_text)
        except Exception as exc:
            failures.append(BenchmarkFailure(rel, "compile", str(exc)))
            continue
        try:
            included = required_emit_targets(
                source_text,
                ir,
                mode=mode_name,
                benchmark_manifest=benchmark_manifest,
            )
        except Exception as exc:
            failures.append(BenchmarkFailure(rel, "planning", str(exc)))
            continue

        if not included:
            failures.append(BenchmarkFailure(rel, "planning", "no targets selected"))
            continue
        excluded = [t for t in TARGET_ORDER if t not in included]
        try:
            target_sizes, rendered_targets = _emit_selected_targets(compiler, ir, count_fn, rel, included)
        except BenchmarkError as exc:
            failures.extend(exc.failures)
            continue

        target_structure_per_artifact: Dict[str, Dict[str, int]] = {}
        for t in included:
            totals_all[t] += target_sizes[t]
            rendered = rendered_targets[t]
            breakdown = _target_structure_breakdown(t, rendered, count_fn)
            target_structure_per_artifact[t] = breakdown
            aggregate = target_structure_totals.setdefault(t, {})
            for k, v in breakdown.items():
                aggregate[k] = aggregate.get(k, 0) + int(v)

        aggregate = sum(target_sizes[t] for t in included)
        aggregate_total += aggregate
        rows.append(
            {
                "artifact": rel,
                "class": class_map.get(rel, "unclassified"),
                "ainl_source_size": source_size,
                "included_targets": list(included),
                "excluded_targets": excluded,
                "targets": {
                    t: {
                        "size": target_sizes.get(t),
                        "included": t in included,
                        "ratio_vs_source": _ratio(target_sizes[t], source_size) if t in included else None,
                    }
                    for t in TARGET_ORDER
                },
                "aggregate_generated_output_size": aggregate,
                "aggregate_ratio_vs_source": _ratio(aggregate, source_size),
                "target_structure": target_structure_per_artifact,
            }
        )

    if failures:
        raise BenchmarkError(failures)
    return {
        "artifacts": rows,
        "summary": {
            "artifact_count": len(rows),
            "ainl_source_total": source_total,
            "targets_total": totals_all,
            "aggregate_generated_output_total": aggregate_total,
            "aggregate_ratio_vs_source": _ratio(aggregate_total, source_total),
            "target_structure_totals": target_structure_totals,
        },
    }


def _compute_size_drivers(profile_payload: Dict, *, mode_name: str, top_n: int = 3) -> Dict:
    summary = profile_payload.get("summary", {})
    artifacts = profile_payload.get("artifacts", [])
    aggregate_total = int(summary.get("aggregate_generated_output_total", 0) or 0)
    targets_total = summary.get("targets_total", {}) or {}
    target_rows = []
    for target, size in targets_total.items():
        if not size:
            continue
        target_rows.append(
            {
                "target": target,
                "size": int(size),
                "share_of_aggregate": _ratio(int(size), aggregate_total),
            }
        )
    top_targets = sorted(target_rows, key=lambda x: x["size"], reverse=True)[:top_n]

    artifact_rows = sorted(
        [
            {
                "artifact": row.get("artifact"),
                "size": int(row.get("aggregate_generated_output_size", 0) or 0),
                "ratio_vs_source": float(row.get("aggregate_ratio_vs_source", 0.0) or 0.0),
                "included_targets": list(row.get("included_targets", [])),
            }
            for row in artifacts
        ],
        key=lambda x: x["size"],
        reverse=True,
    )[:top_n]
    out = {
        "top_targets": top_targets,
        "top_artifacts": artifact_rows,
    }
    # Residual-overhead audit: structural composition of remaining emitted size.
    structure_totals = summary.get("target_structure_totals", {}) or {}
    by_target = []
    for target_row in top_targets:
        target = target_row["target"]
        struct = structure_totals.get(target, {})
        by_target.append(
            {
                "target": target,
                "total_size": target_row["size"],
                "structure": struct,
            }
        )
    out["residual_overhead_by_target"] = by_target
    if mode_name == "minimal_emit":
        out["top_minimal_emitted_artifacts"] = artifact_rows
        out["top_minimal_emitted_targets"] = top_targets
    return out


def build_report(
    *,
    metric: str,
    mode_request: str,
    profile_request: str,
    benchmark_manifest: Dict,
    mode_payloads: Dict[str, Dict],
    handwritten_baseline_size_comparison: Optional[Dict[str, Any]] = None,
) -> Dict:
    headline_name = benchmark_manifest.get("headline_profile", "canonical_strict_valid")
    # Attach lightweight size-driver diagnostics per profile/mode.
    for mode_name, mode_data in mode_payloads.items():
        for profile in mode_data.get("profiles", []):
            profile["size_drivers"] = _compute_size_drivers(profile, mode_name=mode_name, top_n=3)
    schema_version = "3.1" if handwritten_baseline_size_comparison else "3.0"
    out: Dict[str, Any] = {
        "schema_version": schema_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric": metric,
        "mode_request": mode_request,
        "profile_request": profile_request,
        "headline_profile": headline_name,
        "targets": list(TARGET_ORDER),
        "modes": mode_payloads,
        "handwritten_baselines": benchmark_manifest.get("handwritten_baselines", {}),
    }
    if handwritten_baseline_size_comparison is not None:
        out["handwritten_baseline_size_comparison"] = handwritten_baseline_size_comparison
    return out


def _render_profile_table(profile: Dict) -> List[str]:
    lines = [
        "| Artifact | Class | AINL source | React/TS | Python API | Prisma | MT5 | Scraper | Cron | Aggregate generated output | Aggregate ratio | Included targets |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in profile["artifacts"]:
        t = row["targets"]
        def _fmt_size(val):
            return "-" if val is None else str(val)
        lines.append(
            "| {artifact} | {cls} | {src} | {react} | {api} | {prisma} | {mt5} | {scraper} | {cron} | {agg} | {ratio:.2f}x | {inc} |".format(
                artifact=row["artifact"],
                cls=row["class"],
                src=row["ainl_source_size"],
                react=_fmt_size(t["react_ts"]["size"]),
                api=_fmt_size(t["python_api"]["size"]),
                prisma=_fmt_size(t["prisma"]["size"]),
                mt5=_fmt_size(t["mt5"]["size"]),
                scraper=_fmt_size(t["scraper"]["size"]),
                cron=_fmt_size(t["cron"]["size"]),
                agg=row["aggregate_generated_output_size"],
                ratio=row["aggregate_ratio_vs_source"],
                inc=", ".join(row["included_targets"]),
            )
        )
    return lines


def render_markdown(report: Dict, benchmark_manifest: Dict) -> str:
    lines: List[str] = []
    lines.append("# AI Native Lang Size Benchmark")
    lines.append("")
    lines.append("This benchmark measures AINL source compactness against generated implementation artifacts.")
    lines.append("It is segmented by profile and mode; it is not a universal compactness claim across programming languages.")
    lines.append("")
    lines.append("## Benchmark Profiles")
    lines.append("")
    for name, cfg in benchmark_manifest.get("profiles", {}).items():
        lines.append(f"- `{name}`: {cfg.get('description','')}")
    lines.append("")
    lines.append("## Benchmark Modes")
    lines.append("")
    lines.append("- `full_multitarget`: includes all benchmark targets for each artifact.")
    lines.append("- `minimal_emit`: includes only capability-required targets for each artifact.")
    lines.append("")
    lines.append("## Compiler IR Capability Contract")
    lines.append("")
    lines.append("- `emit_capabilities.needs_python_api`: backend/API execution surface is required.")
    lines.append("- `emit_capabilities.needs_react_ts`: frontend UI output is required.")
    lines.append("- `emit_capabilities.needs_prisma`: schema/data model output is required.")
    lines.append("- `emit_capabilities.needs_mt5`: MT5 strategy output is required.")
    lines.append("- `emit_capabilities.needs_scraper`: scraper output is required.")
    lines.append("- `emit_capabilities.needs_cron`: cron/scheduler output is required.")
    lines.append("- `required_emit_targets.minimal_emit`: compiler-planned minimal target set (planner primary source).")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append(f"- Active metric: `{report['metric']}`.")
    if report["metric"] == "approx_chunks":
        lines.append("- `approx_chunks` is a lexical-size proxy, not tokenizer-accurate pricing.")
    elif report["metric"] == "nonempty_lines":
        lines.append("- `nonempty_lines` measures structural size, not tokenizer-accurate pricing.")
    else:
        lines.append("- `tiktoken` mode depends on optional tokenizer availability.")
    lines.append("")
    lines.append("## How To Read These Results")
    lines.append("")
    lines.append("- Ratio `> 1`: generated output is larger than AINL source.")
    lines.append("- Ratio `~ 1`: near parity.")
    lines.append("- Ratio `< 1`: generated output is smaller than AINL source.")
    lines.append("- `approx_chunks` is a useful lexical proxy, not exact LLM token billing.")
    lines.append("")
    lines.append("## Full Multitarget vs Minimal Emit")
    lines.append("")
    lines.append("- `full_multitarget` shows total downstream expansion potential across all emitters.")
    lines.append("- `minimal_emit` is closer to practical deployment comparison because it emits only required targets.")
    lines.append("")
    lines.append("## Why Some Ratios Got Worse After Truthfulness Fixes")
    lines.append("")
    lines.append("- Ratios can worsen when examples are corrected to express capabilities they were already claiming publicly.")
    lines.append("- This is expected: honest capability accounting increases counted generated output where prior under-emission existed.")
    lines.append("- The result is less flattering but more trustworthy and action-guiding.")
    lines.append("")
    lines.append("## What We Can Honestly Claim")
    lines.append("")
    lines.append("- The benchmark is reproducible, profile-segmented, and mode-segmented.")
    lines.append("- Minimal mode is the better comparison for practical deployment size discussions.")
    lines.append("- Full mode is useful for measuring expansion leverage, not apples-to-apples terseness.")
    lines.append("")
    lines.append("## What These Numbers Are Not")
    lines.append("")
    lines.append("- They are not universal superiority claims over mainstream languages.")
    lines.append("- They are not guaranteed tokenizer-cost or LLM pricing results in `approx_chunks` mode.")
    lines.append("- They are not a proxy for runtime performance or product quality by themselves.")
    lines.append("")

    headline = report["headline_profile"]
    modes = report["modes"]
    full_mode = modes.get("full_multitarget")
    mini_mode = modes.get("minimal_emit")
    lines.append("## Mode Comparison (Headline + Mixed)")
    lines.append("")
    lines.append("| Profile | Full aggregate ratio | Minimal aggregate ratio |")
    lines.append("|---|---:|---:|")
    for pname in (headline, "public_mixed", "compatibility_only"):
        full = (
            next((p for p in full_mode["profiles"] if p["name"] == pname), None) if full_mode else None
        )
        mini = (
            next((p for p in mini_mode["profiles"] if p["name"] == pname), None) if mini_mode else None
        )
        if full and mini:
            lines.append(
                f"| {pname} | {full['summary']['aggregate_ratio_vs_source']:.2f}x | {mini['summary']['aggregate_ratio_vs_source']:.2f}x |"
            )
    lines.append("")
    lines.append(
        "Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline."
    )
    lines.append("")
    lines.append("## Size Drivers (Actionable Diagnosis)")
    lines.append("")
    for mode_name in sorted(modes.keys()):
        mode_payload = modes[mode_name]
        lines.append(f"### {mode_name}")
        for profile in mode_payload["profiles"]:
            drivers = profile.get("size_drivers", {})
            top_targets = drivers.get("top_targets", [])
            top_artifacts = drivers.get("top_artifacts", [])
            targets_txt = ", ".join(f"{t['target']}={t['size']}" for t in top_targets) if top_targets else "none"
            artifacts_txt = ", ".join(f"{a['artifact']}={a['size']}" for a in top_artifacts) if top_artifacts else "none"
            lines.append(f"- `{profile['name']}` top targets: {targets_txt}")
            lines.append(f"- `{profile['name']}` top artifacts: {artifacts_txt}")
        lines.append("")
    lines.append("## Residual Overhead Audit (minimal_emit)")
    lines.append("")
    minimal_profiles = (mini_mode or {}).get("profiles") or []
    for profile in minimal_profiles:
        lines.append(f"### {profile['name']}")
        drivers = profile.get("size_drivers", {})
        for row in drivers.get("residual_overhead_by_target", []):
            target = row["target"]
            total = row["total_size"]
            struct = row.get("structure", {})
            struct_parts = ", ".join(f"{k}={v}" for k, v in sorted(struct.items()))
            lines.append(f"- `{target}` total={total}; structure: {struct_parts or 'none'}")
        lines.append("")

    for mode_name in sorted(modes.keys()):
        mode_payload = modes[mode_name]
        lines.append(f"## Details ({mode_name})")
        lines.append("")
        lines.append("| Profile | Artifact count | AINL source total | Aggregate generated output total | Aggregate ratio |")
        lines.append("|---|---:|---:|---:|---:|")
        for p in mode_payload["profiles"]:
            s = p["summary"]
            lines.append(
                f"| {p['name']} | {s['artifact_count']} | {s['ainl_source_total']} | {s['aggregate_generated_output_total']} | {s['aggregate_ratio_vs_source']:.2f}x |"
            )
        lines.append("")
        for p in mode_payload["profiles"]:
            lines.append(f"### {p['name']}")
            lines.extend(_render_profile_table(p))
            lines.append("")

    hb = report.get("handwritten_baseline_size_comparison")
    if hb:
        lines.extend(_render_handwritten_baseline_size_markdown(hb, report))

    lines.append("## Supported vs Unsupported Claims")
    lines.append("")
    lines.append("- Supported: profile- and mode-scoped compactness comparisons for this benchmark setup.")
    lines.append("- Supported: canonical strict-valid as primary headline profile.")
    lines.append("- Unsupported: universal compactness claims versus Python/TypeScript/Rust/Go.")
    lines.append("- Unsupported: guaranteed pricing impact from default lexical metrics.")
    lines.append("- Note: source-text fallback remains as temporary legacy support for older IRs missing capability metadata.")
    lines.append("")
    lines.append("## Recommended Next Benchmark Improvements")
    lines.append("")
    lines.append(
        "- Handwritten baselines live under `benchmarks/handwritten_baselines/`; use "
        "`--compare-baselines` on size/runtime scripts for tables vs mapped AINL artifacts."
    )
    lines.append("- Add CI trend snapshots for both full and minimal modes.")
    lines.append("- Add tokenizer-metric lane when dependency pinning is available.")
    lines.append("")
    lines.append(
        "Conclusion: strongest current claim is compactness in canonical multi-target examples; "
        "language-surface changes are not required for these benchmark gains."
    )
    lines.append("")
    lines.append("Selection source: `tooling/artifact_profiles.json`; planning source: `tooling/benchmark_manifest.json`.")

    return "\n".join(lines) + "\n"


def _render_handwritten_baseline_size_markdown(hb: Dict[str, Any], report: Dict[str, Any]) -> List[str]:
    """Markdown tables comparing mapped AINL emitted size to handwritten Python sources."""
    lines: List[str] = [
        "",
        "## Handwritten baseline size comparison",
        "",
        f"**AINL emitted** aggregates use the active benchmark metric (`{report.get('metric')}`) and, "
        "when available, **tiktoken** (**cl100k_base**) on the same emitted bundle. "
        "**Pure / Lang** columns count only `pure_async_python.py` / `langgraph_version.py` in each group.",
        "",
    ]
    if not hb.get("tiktoken_available", True):
        lines.append("*Warning:* `tiktoken` is not installed — AINL tiktoken columns and tk ratios may be empty.")
        lines.append("")
    for mode in ("minimal_emit", "full_multitarget"):
        lines.append(f"### Emit mode `{mode}`")
        lines.append("")
        lines.append(
            "| Workflow | AINL reference | AINL emit (active) | AINL emit (tiktoken) | "
            "Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for g in hb.get("groups", []):
            name = g.get("name", "")
            rel = g.get("ainl_reference_artifact") or "—"
            bs = g.get("baseline_source") or {}
            md = (g.get("modes") or {}).get(mode, {})
            def _r(x: Any) -> str:
                if x is None:
                    return "—"
                return f"{float(x):.2f}x"

            lines.append(
                "| {n} | `{r}` | {a} | {t} | {pl} | {ll} | {pt} | {lt} | {rp} | {rl} |".format(
                    n=name,
                    r=rel,
                    a=md.get("ainl_aggregate_emit_active_metric", "—"),
                    t=md.get("ainl_aggregate_emit_tiktoken", "—"),
                    pl=bs.get("pure_nonempty_lines", "—"),
                    ll=bs.get("lang_nonempty_lines", "—"),
                    pt=bs.get("pure_tiktoken", "—"),
                    lt=bs.get("lang_tiktoken", "—"),
                    rp=_r(md.get("ratio_ainl_tiktoken_over_pure_py_tiktoken")),
                    rl=_r(md.get("ratio_ainl_tiktoken_over_langgraph_tiktoken")),
                )
            )
        lines.append("")
    for g in hb.get("groups", []):
        err = (g.get("baseline_source") or {}).get("tiktoken_error")
        if err:
            lines.append(f"*tiktoken error ({g.get('name')}):* `{err}`")
    lines.append("")
    return lines


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Segmented capability-driven AINL benchmark")
    ap.add_argument("--metric", choices=["approx_chunks", "nonempty_lines", "tiktoken"], default="approx_chunks")
    ap.add_argument("--mode", choices=["full_multitarget", "minimal_emit", "both"], default="both")
    ap.add_argument("--profile-name", default="all", help="profile name or 'all'")
    ap.add_argument("--artifact-profiles", default=str(DEFAULT_ARTIFACT_PROFILES))
    ap.add_argument("--benchmark-manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    ap.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    ap.add_argument(
        "--compare-baselines",
        action="store_true",
        help="Include handwritten baseline source size vs mapped AINL emitted aggregates.",
    )
    ap.add_argument(
        "--baselines-root",
        default=str(DEFAULT_BASELINES_ROOT),
        help="Root directory for handwritten baseline groups.",
    )
    return ap.parse_args()


def _selected_profile_names(profile_request: str, benchmark_manifest: Dict) -> List[str]:
    profiles = benchmark_manifest.get("profiles", {})
    if profile_request == "all":
        return list(profiles.keys())
    if profile_request not in profiles:
        raise ValueError(f"unknown profile '{profile_request}'")
    return [profile_request]


def _selected_modes(mode_request: str) -> List[str]:
    if mode_request == "both":
        return ["full_multitarget", "minimal_emit"]
    return [mode_request]


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        from compiler_v2 import AICodeCompiler

        artifact_profiles_path = Path(args.artifact_profiles)
        benchmark_manifest_path = Path(args.benchmark_manifest)
        benchmark_manifest = load_benchmark_manifest(benchmark_manifest_path)
        count_fn = metric_counter(args.metric)
        compiler = AICodeCompiler(strict_mode=False)
        profile_names = _selected_profile_names(args.profile_name, benchmark_manifest)
        mode_names = _selected_modes(args.mode)

        mode_payloads: Dict[str, Dict] = {}
        for mode_name in mode_names:
            if mode_name not in benchmark_manifest.get("modes", {}):
                raise ValueError(f"mode '{mode_name}' missing from benchmark manifest")
            profiles_payload: List[Dict] = []
            for profile_name in profile_names:
                selected, class_map, cfg = resolve_profile_selection(
                    profile_name,
                    artifact_profiles_path=artifact_profiles_path,
                    benchmark_manifest_path=benchmark_manifest_path,
                )
                result = run_profile_benchmark(
                    selected,
                    class_map=class_map,
                    mode_name=mode_name,
                    benchmark_manifest=benchmark_manifest,
                    root=ROOT,
                    count_fn=count_fn,
                    compiler=compiler,
                )
                profiles_payload.append(
                    {
                        "name": profile_name,
                        "description": cfg.get("description", ""),
                        "selection": {
                            "artifact_profiles_section": cfg["artifact_profiles_section"],
                            "classes": cfg["classes"],
                            "artifact_count": len(selected),
                        },
                        "artifacts": result["artifacts"],
                        "summary": result["summary"],
                    }
                )
            mode_payloads[mode_name] = {"profiles": profiles_payload}

        handwritten_cmp: Optional[Dict[str, Any]] = None
        if args.compare_baselines:
            handwritten_cmp = build_handwritten_baseline_size_comparison(
                baselines_root=Path(args.baselines_root),
                benchmark_manifest=benchmark_manifest,
                compiler=compiler,
                active_metric_fn=count_fn,
                active_metric_name=args.metric,
                root=ROOT,
            )

        report = build_report(
            metric=args.metric,
            mode_request=args.mode,
            profile_request=args.profile_name,
            benchmark_manifest=benchmark_manifest,
            mode_payloads=mode_payloads,
            handwritten_baseline_size_comparison=handwritten_cmp,
        )

        json_out = Path(args.json_out)
        md_out = Path(args.markdown_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        md_out.write_text(render_markdown(report, benchmark_manifest), encoding="utf-8")
        print(f"wrote JSON benchmark: {json_out}")
        print(f"wrote markdown benchmark: {md_out}")
        return 0
    except BenchmarkError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
