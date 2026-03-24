#!/usr/bin/env python3
"""Segmented, capability-driven size benchmark for AI Native Lang (AINL)."""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tooling.bench_metrics import (
    cost_dict_for_tokens,
    economics_block,
    parse_cost_model_arg,
    tiktoken_count,
)
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

# Modes that run every selected emitter (no minimal capability gating).
_FULL_MULTITARGET_MODES = frozenset({"full_multitarget", "full_multitarget_core"})

TARGET_EMITTERS: Dict[str, str] = {
    "react_ts": "emit_react",
    "python_api": "emit_python_api",
    "prisma": "emit_prisma_schema",
    "mt5": "emit_mt5",
    "scraper": "emit_python_scraper",
    "cron": "emit_cron_stub",
}

# Hybrid emitters live in standalone scripts (not on ``AICodeCompiler``); see ``_emit_selected_targets``.
STANDALONE_BENCH_EMIT_TARGETS = frozenset({"langgraph", "temporal"})


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
    """Delegate to ``tooling.bench_metrics`` so size/runtime share one encoder."""
    try:
        return tiktoken_count(text)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("tiktoken mode requested but tiktoken is not installed") from exc


def metric_counter(metric: str) -> Callable[[str], int]:
    if metric == "approx_chunks":
        return approx_chunks
    if metric == "nonempty_lines":
        return nonempty_lines
    if metric == "tiktoken":
        return tiktoken_chunks
    raise ValueError(f"unsupported metric: {metric}")


def _parallel_tiktoken_bundle(
    *,
    source_text: str,
    rendered_by_target: Dict[str, str],
    included: Sequence[str],
) -> Optional[Dict[str, Any]]:
    """Optional cl100k_base counts alongside a non-tiktoken primary metric."""
    try:
        src_tk = tiktoken_chunks(source_text)
        tmap: Dict[str, Optional[int]] = {t: None for t in TARGET_ORDER}
        agg = 0
        for t in included:
            body = rendered_by_target.get(t) or ""
            n = tiktoken_chunks(body)
            tmap[t] = n
            agg += n
        return {"ainl_source": src_tk, "targets": tmap, "aggregate": agg}
    except Exception:
        return None


def _artifact_row_notes(
    row: Dict[str, Any],
    *,
    mode_name: str,
    profile_name: str,
    report_metric: str,
) -> str:
    parts: List[str] = []
    if mode_name == "minimal_emit" and row.get("fallback_stub"):
        parts.append("fallback stub")
    if profile_name in ("public_mixed", "compatibility_only") and row.get("viable_for_aggregate") is False:
        parts.append("legacy excluded from viable")
    inc = list(row.get("included_targets") or [])

    def _size_tiktoken_for_target(t: str) -> Optional[int]:
        if report_metric == "tiktoken":
            v = (row.get("targets") or {}).get(t, {}).get("size")
            return int(v) if v is not None else None
        pt = row.get("parallel_tiktoken_cl100k")
        if not isinstance(pt, dict):
            return None
        tm = pt.get("targets") or {}
        v = tm.get(t) if isinstance(tm, dict) else None
        return int(v) if v is not None else None

    if "prisma" in inc:
        z = _size_tiktoken_for_target("prisma")
        if z is not None and z < 95:
            parts.append("compacted prisma emitter")
    if "react_ts" in inc:
        z = _size_tiktoken_for_target("react_ts")
        if z is not None and z < 45:
            parts.append("compacted react_ts emitter")
    return "; ".join(parts)


def _format_note_cell(note_semilist: str) -> str:
    if not (note_semilist or "").strip():
        return ""
    parts = [p.strip() for p in note_semilist.split(";") if p.strip()]
    return "; ".join(f"({p})" for p in parts)


def _md_row_tk_bundle(
    row: Dict[str, Any],
    report_metric: str,
) -> Tuple[Optional[int], Dict[str, Optional[int]], Optional[int], Optional[float]]:
    """Markdown-facing sizes: always tiktoken (cl100k_base) when available."""
    if report_metric == "tiktoken":
        src = row.get("ainl_source_size")
        agg = row.get("aggregate_generated_output_size")
        rat = row.get("aggregate_ratio_vs_source")
        tmap: Dict[str, Optional[int]] = {}
        for t in TARGET_ORDER:
            ent = (row.get("targets") or {}).get(t) or {}
            v = ent.get("size")
            tmap[t] = int(v) if v is not None else None
        return (
            int(src) if src is not None else None,
            tmap,
            int(agg) if agg is not None else None,
            float(rat) if rat is not None else None,
        )
    pt = row.get("parallel_tiktoken_cl100k")
    if not isinstance(pt, dict):
        return None, {t: None for t in TARGET_ORDER}, None, None
    src = pt.get("ainl_source")
    agg = pt.get("aggregate")
    tm_raw = pt.get("targets")
    tm: Dict[str, Any] = tm_raw if isinstance(tm_raw, dict) else {}
    tmap = {t: int(tm[t]) if tm.get(t) is not None else None for t in TARGET_ORDER}
    if src is None or agg is None:
        return None, tmap, None, None
    isrc, iagg = int(src), int(agg)
    return isrc, tmap, iagg, _ratio(iagg, isrc)


def _md_profile_markdown_tk_summary(
    profile: Dict[str, Any],
    report_metric: str,
    *,
    viable_only: bool,
) -> Optional[Dict[str, Any]]:
    """Re-sum tiktoken across rows for markdown tables (JSON aggregates stay on CLI metric)."""
    arts: List[Dict[str, Any]] = list(profile.get("artifacts") or [])
    if viable_only:
        arts = [r for r in arts if r.get("viable_for_aggregate", True)]
    if arts:
        src_sum = 0
        agg_sum = 0
        for r in arts:
            src_tk, _, agg_tk, _ = _md_row_tk_bundle(r, report_metric)
            if src_tk is None or agg_tk is None:
                return None
            src_sum += src_tk
            agg_sum += agg_tk
        return {
            "artifact_count": len(arts),
            "ainl_source_total": src_sum,
            "aggregate_generated_output_total": agg_sum,
            "aggregate_ratio_vs_source": _ratio(agg_sum, src_sum),
        }
    vs = profile.get("viable_aggregate") if viable_only else None
    if vs is None:
        vs = profile.get("summary")
    if vs and report_metric == "tiktoken":
        st = int(vs.get("ainl_source_total") or 0)
        at = int(vs.get("aggregate_generated_output_total") or 0)
        return {
            "artifact_count": int(vs.get("artifact_count") or 0),
            "ainl_source_total": st,
            "aggregate_generated_output_total": at,
            "aggregate_ratio_vs_source": vs.get("aggregate_ratio_vs_source") or _ratio(at, st),
        }
    return None


def _md_top_targets_display(profile: Dict[str, Any], report_metric: str, top_n: int = 3) -> str:
    if report_metric == "tiktoken":
        drivers = profile.get("size_drivers") or {}
        top_targets = drivers.get("top_targets") or []
        return ", ".join(f"{t['target']}={t['size']}" for t in top_targets) if top_targets else "none"
    totals = {t: 0 for t in TARGET_ORDER}
    arts = list(profile.get("artifacts") or [])
    if profile.get("viable_aggregate") is not None:
        arts = [r for r in arts if r.get("viable_for_aggregate")]
    for r in arts:
        _, tmap, _, _ = _md_row_tk_bundle(r, report_metric)
        for t in TARGET_ORDER:
            v = tmap.get(t)
            if v is not None:
                totals[t] += int(v)
    rows = sorted(((t, v) for t, v in totals.items() if v > 0), key=lambda x: -x[1])[:top_n]
    return ", ".join(f"{t}={v}" for t, v in rows) or "none"


def _md_top_artifacts_display(profile: Dict[str, Any], report_metric: str, top_n: int = 3) -> str:
    if report_metric == "tiktoken":
        drivers = profile.get("size_drivers") or {}
        top_artifacts = drivers.get("top_artifacts") or []
        return ", ".join(f"{a['artifact']}={a['size']}" for a in top_artifacts) if top_artifacts else "none"
    arts = list(profile.get("artifacts") or [])
    if profile.get("viable_aggregate") is not None:
        arts = [r for r in arts if r.get("viable_for_aggregate")]
    scored: List[Tuple[str, int]] = []
    for r in arts:
        _, _, agg_tk, _ = _md_row_tk_bundle(r, report_metric)
        if agg_tk is None:
            continue
        scored.append((str(r.get("artifact", "")), int(agg_tk)))
    scored.sort(key=lambda x: -x[1])
    return ", ".join(f"{a}={s}" for a, s in scored[:top_n]) or "none"


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


def load_viable_for_aggregate_overrides(path: Path) -> Dict[str, bool]:
    """Per-path overrides: True = force viable, False = force excluded from viable subset."""
    profile = load_json(path)
    raw = profile.get("viable_for_aggregate")
    if not isinstance(raw, dict):
        return {}
    return {str(k): bool(v) for k, v in raw.items()}


# Non-strict / legacy rows below this aggregate emit size (active metric) are excluded from viable subset
# unless forced True in artifact_profiles.json (public_mixed / compatibility_only only).
VIABLE_EMIT_AGGREGATE_MIN = 50
# Large sources with very low emit/source ratio (legacy ops shells) skew aggregates downward; exclude unless override True.
VIABLE_SOURCE_LARGE_MIN = 400
VIABLE_EMIT_RATIO_MAX = 0.22


def _row_in_viable_aggregate_subset(
    row: Dict[str, Any],
    *,
    profile_name: str,
    overrides: Dict[str, bool],
) -> bool:
    if profile_name not in ("public_mixed", "compatibility_only"):
        return True
    rel = row["artifact"]
    cls = row.get("class") or ""
    if rel in overrides:
        return overrides[rel]
    if cls == "strict-valid":
        return True
    agg = int(row.get("aggregate_generated_output_size") or 0)
    src = int(row.get("ainl_source_size") or 0)
    rr = row.get("aggregate_ratio_vs_source")
    if (
        isinstance(rr, (int, float))
        and src >= VIABLE_SOURCE_LARGE_MIN
        and float(rr) < VIABLE_EMIT_RATIO_MAX
    ):
        return False
    return agg >= VIABLE_EMIT_AGGREGATE_MIN


def _summarize_artifact_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    totals_all = {t: 0 for t in TARGET_ORDER}
    source_total = 0
    aggregate_total = 0
    target_structure_totals: Dict[str, Dict[str, int]] = {}
    for row in rows:
        source_total += int(row.get("ainl_source_size") or 0)
        aggregate_total += int(row.get("aggregate_generated_output_size") or 0)
        tmap = row.get("targets") or {}
        for t in TARGET_ORDER:
            ent = tmap.get(t) or {}
            sz = ent.get("size")
            if sz is not None:
                totals_all[t] += int(sz)
        for t, struct in (row.get("target_structure") or {}).items():
            agg = target_structure_totals.setdefault(str(t), {})
            for k, v in (struct or {}).items():
                agg[k] = agg.get(k, 0) + int(v)
    return {
        "artifact_count": len(rows),
        "ainl_source_total": source_total,
        "targets_total": totals_all,
        "aggregate_generated_output_total": aggregate_total,
        "aggregate_ratio_vs_source": _ratio(aggregate_total, source_total),
        "target_structure_totals": target_structure_totals,
    }


def apply_viable_aggregate_subset(
    profile_payload: Dict[str, Any],
    *,
    profile_name: str,
    overrides: Dict[str, bool],
) -> None:
    """Mutates profile_payload: per-row viable_for_aggregate, viable_aggregate, excluded_legacy_count."""
    rows: List[Dict[str, Any]] = list(profile_payload.get("artifacts") or [])
    viable_rows: List[Dict[str, Any]] = []
    for row in rows:
        ok = _row_in_viable_aggregate_subset(row, profile_name=profile_name, overrides=overrides)
        row["viable_for_aggregate"] = ok
        if ok:
            viable_rows.append(row)
    profile_payload["viable_aggregate"] = _summarize_artifact_rows(viable_rows)
    profile_payload["excluded_legacy_count"] = int(len(rows) - len(viable_rows))


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
        if mode_name in _FULL_MULTITARGET_MODES:
            ir.pop("emit_python_api_fallback_stub", None)
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
    cost_models: Optional[List[str]] = None,
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
        for mode_name in ("minimal_emit", "full_multitarget_core", "full_multitarget"):
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
            mode_payload: Dict[str, Any] = {
                "ainl_aggregate_emit_active_metric": ainl_active,
                "active_metric": active_metric_name,
                "ainl_aggregate_emit_tiktoken": ainl_tik,
                "ratio_ainl_tiktoken_over_pure_py_tiktoken": _ratio_float(ainl_tik, pure_tk),
                "ratio_ainl_tiktoken_over_langgraph_tiktoken": _ratio_float(ainl_tik, lang_tk),
                "ratio_ainl_active_over_pure_tiktoken": _ratio_float(ainl_active, pure_tk),
                "ratio_ainl_active_over_lang_tiktoken": _ratio_float(ainl_active, lang_tk),
            }
            if cost_models and ainl_tik is not None:
                mode_payload["estimated_cost_usd_ainl_emit_tiktoken"] = cost_dict_for_tokens(int(ainl_tik), cost_models)
            if cost_models and pure_tk is not None and lang_tk is not None:
                stack_tk = int(pure_tk) + int(lang_tk)
                mode_payload["estimated_cost_usd_handwritten_sources_tiktoken"] = cost_dict_for_tokens(
                    stack_tk, cost_models
                )
            g["modes"][mode_name] = mode_payload
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


def _emit_standalone_bench_target(target: str, ir: Dict, artifact: str) -> str:
    """LangGraph / Temporal wrappers are emitted by ``scripts/emit_*.py``, not ``compiler_v2``."""
    stem = Path(artifact).stem
    if target == "langgraph":
        from scripts.emit_langgraph import emit_langgraph_source

        return emit_langgraph_source(ir, source_stem=stem)
    if target == "temporal":
        import tempfile

        from scripts.emit_temporal import emit_temporal_pair

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            act_path, wf_path = emit_temporal_pair(ir, output_dir=out_dir, source_stem=stem)
            return act_path.read_text(encoding="utf-8") + "\n" + wf_path.read_text(encoding="utf-8")
    raise BenchmarkError([BenchmarkFailure(artifact, f"emit:{target}", "unknown standalone emitter")])


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
        if target in STANDALONE_BENCH_EMIT_TARGETS:
            try:
                rendered = _emit_standalone_bench_target(target, ir, artifact)
            except BenchmarkError:
                raise
            except Exception as exc:
                raise BenchmarkError([BenchmarkFailure(artifact, f"emit:{target}", str(exc))]) from exc
        else:
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


def _compile_time_mean_three_ms(source_text: str, compiler: Any) -> Dict[str, Any]:
    """Wall-clock compile latency: mean of three timed ``compile(..., emit_graph=True)`` calls.

    Runs after the primary compile path succeeds; uses the same emit_graph flag as the
    reliability probe so numbers are comparable. Failures still advance the loop but do
    not contribute to the mean.
    """
    times_ms: List[float] = []
    failures = 0
    for _ in range(3):
        try:
            t0 = time.perf_counter()
            ir = compiler.compile(source_text, emit_graph=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if ir.get("errors"):
                failures += 1
            else:
                times_ms.append(elapsed_ms)
        except Exception:
            failures += 1
    mean = float(statistics.mean(times_ms)) if times_ms else None
    return {
        "compile_time_ms_mean": mean,
        "compile_time_ms_samples": 3,
        "compile_time_ms_failures_in_probe": failures,
    }


def _compile_reliability_probe(source_text: str, compiler: Any, n_runs: int) -> Dict[str, Any]:
    """Repeat compile *n_runs* times for stability (same artifact, cold-ish compiler path)."""
    times_ms: List[float] = []
    failures: List[Dict[str, Any]] = []
    for i in range(n_runs):
        try:
            t0 = time.perf_counter()
            ir = compiler.compile(source_text, emit_graph=True)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if ir.get("errors"):
                failures.append({"run": i, "error": "compile returned IR errors"})
            else:
                times_ms.append(elapsed)
        except Exception as exc:
            failures.append({"run": i, "error": str(exc)})
    successes = len(times_ms)
    std = float(statistics.pstdev(times_ms)) if len(times_ms) > 1 else 0.0
    return {
        "runs_requested": n_runs,
        "compile_successes": successes,
        "compile_failures": len(failures),
        "success_rate": float(successes) / float(n_runs) if n_runs else 0.0,
        "compile_time_ms_stddev": std,
        "failure_samples": failures[:8],
    }


def run_profile_benchmark(
    source_paths: Sequence[str],
    *,
    class_map: Dict[str, str],
    mode_name: str,
    benchmark_manifest: Dict,
    root: Path,
    count_fn: Callable[[str], int],
    compiler,
    metric_name: str = "tiktoken",
    cost_models: Optional[List[str]] = None,
    compile_reliability_runs: int = 0,
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
        if mode_name in _FULL_MULTITARGET_MODES:
            # compile() may set emit_python_api_fallback_stub for minimal_emit; full mode must use real API emit.
            ir.pop("emit_python_api_fallback_stub", None)
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
        compile_timing = _compile_time_mean_three_ms(source_text, compiler)
        row: Dict[str, Any] = {
            "artifact": rel,
            "class": class_map.get(rel, "unclassified"),
            "ainl_source_size": source_size,
            **compile_timing,
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
        if cost_models:
            basis_tokens = aggregate if metric_name == "tiktoken" else tiktoken_count(source_text)
            row["cost_estimation_basis_tokens"] = int(basis_tokens)
            row["cost_estimation_method"] = (
                "aggregate_emitted_tiktoken" if metric_name == "tiktoken" else "ainl_source_tiktoken_fallback"
            )
            row["estimated_cost_usd_per_generation"] = cost_dict_for_tokens(int(basis_tokens), cost_models)
        if compile_reliability_runs > 0:
            row["compile_reliability"] = _compile_reliability_probe(source_text, compiler, compile_reliability_runs)
        if mode_name == "minimal_emit" and ir.get("emit_python_api_fallback_stub"):
            row["fallback_stub"] = True
        row["ainl_source_nonempty_lines"] = nonempty_lines(source_text)
        if metric_name != "tiktoken":
            row["parallel_tiktoken_cl100k"] = _parallel_tiktoken_bundle(
                source_text=source_text,
                rendered_by_target=rendered_targets,
                included=included,
            )
        rows.append(row)

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
    summary = profile_payload.get("viable_aggregate") or profile_payload.get("summary", {})
    artifacts = list(profile_payload.get("artifacts", []))
    if "viable_aggregate" in profile_payload:
        artifacts = [r for r in artifacts if r.get("viable_for_aggregate")]
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
    cost_models: Optional[List[str]] = None,
    compile_reliability_runs: int = 0,
    strict_compiler_mode: bool = False,
) -> Dict:
    headline_name = benchmark_manifest.get("headline_profile", "canonical_strict_valid")
    # Attach lightweight size-driver diagnostics per profile/mode.
    for mode_name, mode_data in mode_payloads.items():
        for profile in mode_data.get("profiles", []):
            profile["size_drivers"] = _compute_size_drivers(profile, mode_name=mode_name, top_n=3)
    # 3.5: transparency fields + parallel tiktoken when --metric != tiktoken.
    schema_version = "3.5"
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
        "compile_reliability_runs": int(compile_reliability_runs),
        "strict_compiler_mode": bool(strict_compiler_mode),
        "primary_size_encoding": "tiktoken_cl100k_base",
        "size_benchmark_transparency": {
            "default_cli_metric": "tiktoken",
            "tiktoken_encoding": "cl100k_base",
            "approx_chunks_deprecated": True,
            "nonempty_lines_secondary": True,
            "compacted_emitters_note": "prisma and react_ts stubs compacted Mar 2026 for benchmark efficiency",
            "minimal_emit_fallback_note": "python_api async stub when no selected target emits code",
            "viable_subset_note": "public_mixed / compatibility_only headline ratios use viable_aggregate",
        },
    }
    if handwritten_baseline_size_comparison is not None:
        out["handwritten_baseline_size_comparison"] = handwritten_baseline_size_comparison
    if cost_models:
        out["economics"] = economics_block(cost_models=cost_models)
    return out


def _cost_cells(row: Dict[str, Any], cost_models: List[str]) -> List[str]:
    costs = row.get("estimated_cost_usd_per_generation") or {}
    cells: List[str] = []
    for m in cost_models:
        v = costs.get(m)
        cells.append("—" if v is None else f"{float(v):.6f}")
    return cells


def _reliability_cell(row: Dict[str, Any]) -> str:
    rel = row.get("compile_reliability")
    if not rel:
        return "—"
    sr = float(rel.get("success_rate", 0.0)) * 100.0
    std = float(rel.get("compile_time_ms_stddev", 0.0))
    return f"{sr:.0f}% σ={std:.3f}ms"


def _compile_time_cell(row: Dict[str, Any]) -> str:
    m = row.get("compile_time_ms_mean")
    if m is None:
        return "—"
    fails = int(row.get("compile_time_ms_failures_in_probe") or 0)
    base = f"{float(m):.3f}"
    if fails:
        return f"{base} ({fails}/3 failed)"
    return base


def _render_profile_table(
    profile: Dict,
    cost_models: List[str],
    compile_rel_runs: int,
    *,
    mode_name: str = "full_multitarget",
    profile_name: str = "",
    report_metric: str = "tiktoken",
) -> List[str]:
    cost_h = ""
    if cost_models:
        labels = []
        for m in cost_models:
            short = m.replace("claude-3-5-", "C-").replace("gpt-4o", "4o").replace("sonnet", "Son").replace("haiku", "Hk")
            labels.append(f"est ${short} (USD)")
        cost_h = "| " + " | ".join(labels) + " |"
    rel_h = "| Compile reliability |" if compile_rel_runs > 0 else ""
    legacy_h = ""
    legacy_sep = ""
    if report_metric == "approx_chunks":
        legacy_h = "| Src (legacy ≈chunks) | Agg (legacy ≈chunks) |"
        legacy_sep = "|---:|---:|"
    lines_h = ""
    lines_sep = ""
    if report_metric == "nonempty_lines":
        lines_h = "| AINL ∅ lines |"
        lines_sep = "|---:|"
    lines = [
        "| Artifact | Class | AINL source (tk) | Compile ms (mean×3) | "
        "React/TS (tk) | Python API (tk) | Prisma (tk) | MT5 (tk) | Scraper (tk) | Cron (tk) | "
        "Aggregate Σ (tk) | Ratio (tk) | Included targets | Notes |"
        + legacy_h
        + lines_h
        + cost_h
        + rel_h,
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"
        + legacy_sep
        + lines_sep
        + ("|---:|" * len(cost_models) if cost_models else "")
        + ("|---|" if compile_rel_runs > 0 else ""),
    ]
    for row in profile["artifacts"]:
        src_tk, tmap, agg_tk, r_tk = _md_row_tk_bundle(row, report_metric)

        def _fmt_tk(val: Optional[int]) -> str:
            return "—" if val is None else str(int(val))

        notes_raw = _artifact_row_notes(
            row,
            mode_name=mode_name,
            profile_name=profile_name,
            report_metric=report_metric,
        )
        notes_cell = _format_note_cell(notes_raw)
        cells: List[str] = [
            row["artifact"],
            row["class"],
            _fmt_tk(src_tk),
            _compile_time_cell(row),
            _fmt_tk(tmap["react_ts"]),
            _fmt_tk(tmap["python_api"]),
            _fmt_tk(tmap["prisma"]),
            _fmt_tk(tmap["mt5"]),
            _fmt_tk(tmap["scraper"]),
            _fmt_tk(tmap["cron"]),
            _fmt_tk(agg_tk),
            "—" if r_tk is None else f"{float(r_tk):.2f}x",
            ", ".join(row["included_targets"]),
            notes_cell,
        ]
        if report_metric == "approx_chunks":
            cells.append(str(row.get("ainl_source_size")))
            cells.append(str(row.get("aggregate_generated_output_size")))
        if report_metric == "nonempty_lines":
            cells.append(str(row.get("ainl_source_nonempty_lines", "—")))
        cells.extend(_cost_cells(row, cost_models))
        if compile_rel_runs > 0:
            cells.append(_reliability_cell(row))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_markdown(report: Dict, benchmark_manifest: Dict) -> str:
    lines: List[str] = []
    lines.append("# AI Native Lang Size Benchmark")
    lines.append("")
    lines.append("This benchmark measures AINL source compactness against generated implementation artifacts.")
    lines.append("It is segmented by profile and mode; it is not a universal compactness claim across programming languages.")
    lines.append("")
    lines.append(
        "> **Sizing:** All markdown tables foreground **tiktoken** **cl100k_base** token counts "
        "(billing-accurate for GPT-4o-class models). JSON numeric fields still use the CLI `--metric`."
    )
    lines.append(
        "> **Emitters:** `prisma` and `react_ts` benchmark stubs were **compacted (Mar 2026)** for benchmark efficiency."
    )
    lines.append(
        "> **minimal_emit:** includes a tiny **python_api** async **fallback stub** when no selected target emits code."
    )
    lines.append(
        "> **Headline ratios:** **viable** subset for `public_mixed` / `compatibility_only` (legacy / pure-cron focus); "
        "**full legacy-inclusive** totals appear [below](#including-legacy-artifacts)."
    )
    lines.append("")
    if report["metric"] == "approx_chunks":
        lines.append(
            "> **Deprecated metric:** This run uses `--metric=approx_chunks`. Markdown still shows **tiktoken** in "
            "artifact tables; optional **legacy ≈chunks** columns are for regression comparison only — do not use for pricing."
        )
        lines.append("")
    if report.get("strict_compiler_mode"):
        lines.append(
            "> **Strict compiler mode:** ``AICodeCompiler(strict_mode=True, strict_reachability=True)`` "
            "(``--strict-mode`` with ``--profile-name=canonical_strict_valid`` only)."
        )
        lines.append("")
    lines.append("## Benchmark Profiles")
    lines.append("")
    for name, cfg in benchmark_manifest.get("profiles", {}).items():
        lines.append(f"- `{name}`: {cfg.get('description','')}")
    lines.append("")
    lines.append("## Benchmark Modes")
    lines.append("")
    lines.append("- `full_multitarget`: includes all benchmark targets for each artifact (compiler emitters + hybrid wrappers).")
    lines.append(
        "- `full_multitarget_core`: six compiler-backed emitters only (matches historical multitarget headline before hybrid wrappers)."
    )
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
    lines.append(
        "- `emit_capabilities.needs_langgraph` / `needs_temporal`: opt-in hybrid wrapper targets (default **false** in the compiler)."
    )
    lines.append("- `required_emit_targets.minimal_emit`: compiler-planned minimal target set (planner primary source).")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append(
        f"- **Default / recommended:** `tiktoken` (**cl100k_base**) via `tooling/bench_metrics.py` (shared with runtime benchmarks)."
    )
    lines.append(
        f"- **Active CLI metric (JSON):** `{report['metric']}` — drives raw JSON sizes, economics basis, and viable-threshold "
        "comparisons where noted; markdown artifact tables still list **(tk)** for readability."
    )
    if report["metric"] == "approx_chunks":
        lines.append(
            "- `approx_chunks` is **deprecated** (word-count proxy). It is omitted from markdown except optional legacy columns "
            "when explicitly selected."
        )
    elif report["metric"] == "nonempty_lines":
        lines.append("- `nonempty_lines` is structural; markdown adds an **AINL ∅ lines** column when this metric is active.")
    lines.append(
        "- **Compile ms (mean×3):** mean wall time of three ``compile(..., emit_graph=True)`` calls per artifact "
        "(see JSON ``compile_time_ms_mean``); unrelated to optional compile-reliability batches."
    )
    econ = report.get("economics") or {}
    if econ:
        lines.append("- **Economics:** estimated LLM $/run from token budgets (see JSON `economics`).")
    lines.append("")
    lines.append("## How To Read These Results")
    lines.append("")
    lines.append("- Ratio `> 1`: generated output is larger than AINL source.")
    lines.append("- Ratio `~ 1`: near parity.")
    lines.append("- Ratio `< 1`: generated output is smaller than AINL source.")
    lines.append(
        "- Summary and mode-comparison ratios in this document use **tiktoken** sums unless labeled otherwise; "
        "match them to the **(tk)** columns in detail tables."
    )
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
    lines.append(
        "- They are not a substitute for measuring your own prompts: tiktoken counts are reproducible for this repo’s emitted text, "
        "but vendor tokenizers may differ slightly."
    )
    lines.append("- They are not a proxy for runtime performance or product quality by themselves.")
    lines.append("")
    lines.append(
        "> **Viable subset (`public_mixed` / `compatibility_only`):** selection rules use the **CLI metric** "
        f"(`{report['metric']}`) on JSON row fields — aggregate emit &lt; {VIABLE_EMIT_AGGREGATE_MIN} "
        f"({report['metric']} units), large-source low-ratio heuristic (source ≥ {VIABLE_SOURCE_LARGE_MIN}, "
        f"ratio &lt; {VIABLE_EMIT_RATIO_MAX}), plus `viable_for_aggregate` overrides in `tooling/artifact_profiles.json`. "
        "**Markdown** headline ratios are recomputed in **tiktoken** for the same viable rows. Strict-valid rows in "
        "`public_mixed` stay viable. **Legacy-inclusive** totals: [Including Legacy Artifacts](#including-legacy-artifacts)."
    )
    lines.append("")

    headline = report["headline_profile"]
    modes = report["modes"]
    full_mode = modes.get("full_multitarget")
    core_mode = modes.get("full_multitarget_core")
    mini_mode = modes.get("minimal_emit")

    def _md_viable_aggregate(prof: Dict[str, Any]) -> Dict[str, Any]:
        return prof.get("viable_aggregate") or prof.get("summary") or {}

    lines.append("## Mode Comparison (Headline + Mixed)")
    lines.append("")
    lines.append(
        "| Profile | Full core ratio (viable, tk) | Full+hybrid ratio (viable, tk) | Minimal ratio (viable, tk) | Viable artifacts |"
    )
    lines.append("|---|---:|---:|---:|---|")
    rm = report["metric"]
    for pname in (headline, "public_mixed", "compatibility_only"):
        full = (
            next((p for p in full_mode["profiles"] if p["name"] == pname), None) if full_mode else None
        )
        core = (
            next((p for p in core_mode["profiles"] if p["name"] == pname), None) if core_mode else None
        )
        mini = (
            next((p for p in mini_mode["profiles"] if p["name"] == pname), None) if mini_mode else None
        )
        if full and mini:
            fs = _md_viable_aggregate(full)
            ftk = _md_profile_markdown_tk_summary(full, rm, viable_only=True)
            mtk = _md_profile_markdown_tk_summary(mini, rm, viable_only=True)
            fr = ftk.get("aggregate_ratio_vs_source") if ftk else None
            mr = mtk.get("aggregate_ratio_vs_source") if mtk else None
            fr_s = f"{float(fr):.2f}x" if fr is not None else "—"
            mr_s = f"{float(mr):.2f}x" if mr is not None else "—"
            cr_s = "—"
            if core:
                ctk = _md_profile_markdown_tk_summary(core, rm, viable_only=True)
                cr = ctk.get("aggregate_ratio_vs_source") if ctk else None
                if cr is not None:
                    cr_s = f"{float(cr):.2f}x"
            n_full = int(fs.get("artifact_count") or 0)
            n_all = len(full.get("artifacts") or [])
            via = f"{n_full}/{n_all}" if n_all else str(n_full)
            lines.append(f"| {pname} | {cr_s} | {fr_s} | {mr_s} | {via} |")
    lines.append("")
    lines.append(
        "Compatibility/non-strict artifacts are segmented and not used as the primary benchmark headline."
    )
    lines.append("")
    lines.append("## Size Drivers (Actionable Diagnosis)")
    lines.append("")
    lines.append(
        f"- Values below are **tiktoken (tk)** on the same **viable** subset as headline drivers when applicable "
        f"(CLI metric: `{report['metric']}`)."
    )
    lines.append("")
    for mode_name in sorted(modes.keys()):
        mode_payload = modes[mode_name]
        lines.append(f"### {mode_name}")
        for profile in mode_payload["profiles"]:
            targets_txt = _md_top_targets_display(profile, rm)
            artifacts_txt = _md_top_artifacts_display(profile, rm)
            lines.append(f"- `{profile['name']}` top targets (tk): {targets_txt}")
            lines.append(f"- `{profile['name']}` top artifacts (tk): {artifacts_txt}")
        lines.append("")
    lines.append("## Residual Overhead Audit (minimal_emit)")
    lines.append("")
    if report["metric"] != "tiktoken":
        lines.append(
            f"> Residual **structure** keys below are counted in **`{report['metric']}`** (CLI metric), not tiktoken. "
            "Compare magnitudes to the **tk** driver lines above."
        )
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
        lines.append(
            "| Profile | Viable artifacts | AINL source Σ (tk, viable) | Aggregate Σ (tk, viable) | Ratio (tk, viable) | Excluded legacy |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|")
        for p in mode_payload["profiles"]:
            vs = p.get("viable_aggregate") or p["summary"]
            ex = int(p.get("excluded_legacy_count") or 0)
            tk = _md_profile_markdown_tk_summary(p, rm, viable_only=True)
            n_via = int(vs.get("artifact_count") or 0)
            if tk:
                r_s = f"{float(tk['aggregate_ratio_vs_source']):.2f}x"
                lines.append(
                    f"| {p['name']} | {n_via} | {tk['ainl_source_total']} | "
                    f"{tk['aggregate_generated_output_total']} | {r_s} | {ex} |"
                )
            else:
                lines.append(f"| {p['name']} | {n_via} | — | — | — | {ex} |")
        lines.append("")
        for p in mode_payload["profiles"]:
            lines.append(f"### {p['name']}")
            cm = (report.get("economics") or {}).get("cost_models_reported") or []
            cr = int(report.get("compile_reliability_runs") or 0)
            lines.extend(
                _render_profile_table(
                    p,
                    cm,
                    cr,
                    mode_name=mode_name,
                    profile_name=p["name"],
                    report_metric=rm,
                )
            )
            lines.append("")
            lines.append(
                "*Token counts via tiktoken **cl100k_base**. Minimal_emit **fallback** stubs are typically ~20–30 tk.*"
            )
            lines.append("")

    hb = report.get("handwritten_baseline_size_comparison")
    if hb:
        lines.extend(_render_handwritten_baseline_size_markdown(hb, report))

    lines.append("## Including Legacy Artifacts")
    lines.append("")
    lines.append(
        "Legacy files (pure-cron shells, OpenClaw micro-wrappers, aggregate emit below the viable threshold, "
        f"or paths marked `viable_for_aggregate: false`) are **still compiled and listed** in the per-artifact "
        "tables; they are **excluded only** from the **viable** summary rows above for `public_mixed` and "
        "`compatibility_only`. Canonical strict-valid profile totals are unchanged (all viable)."
    )
    lines.append("")
    for mode_name in sorted(modes.keys()):
        mode_payload = modes[mode_name]
        lines.append(f"### {mode_name} — legacy-inclusive totals")
        lines.append("")
        lines.append(
            "| Profile | Artifact count | AINL source total (tk) | Aggregate total (tk) | Ratio (tk) |"
        )
        lines.append("|---|---:|---:|---:|---:|")
        for p in mode_payload["profiles"]:
            s = p["summary"]
            tk_all = _md_profile_markdown_tk_summary(p, rm, viable_only=False)
            n_art = int(s.get("artifact_count") or 0)
            if tk_all:
                r_s = f"{float(tk_all['aggregate_ratio_vs_source']):.2f}x"
                lines.append(
                    f"| {p['name']} | {n_art} | {tk_all['ainl_source_total']} | "
                    f"{tk_all['aggregate_generated_output_total']} | {r_s} |"
                )
            else:
                lines.append(f"| {p['name']} | {n_art} | — | — | — |")
        lines.append("")
        lines.append("*Legacy-inclusive totals above: all artifacts in profile, **tiktoken** sums.*")
        lines.append("")

    lines.append("## Supported vs Unsupported Claims")
    lines.append("")
    lines.append("- Supported: profile- and mode-scoped compactness comparisons for this benchmark setup.")
    lines.append("- Supported: canonical strict-valid as primary headline profile.")
    lines.append("- Unsupported: universal compactness claims versus Python/TypeScript/Rust/Go.")
    lines.append(
        "- Unsupported: treating **approx_chunks** or **nonempty_lines** JSON runs as exact OpenAI billing without "
        "cross-checking tiktoken."
    )
    lines.append("- Note: source-text fallback remains as temporary legacy support for older IRs missing capability metadata.")
    lines.append("")
    lines.append("## Recommended Next Benchmark Improvements")
    lines.append("")
    lines.append(
        "- Handwritten baselines live under `benchmarks/handwritten_baselines/`; use "
        "`--compare-baselines` on size/runtime scripts for tables vs mapped AINL artifacts."
    )
    lines.append("- Add CI trend snapshots for both full and minimal modes.")
    lines.append("- Optional: snapshot secondary `--metric` lanes (e.g. `nonempty_lines`) for structure-only regressions.")
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
    econ = report.get("economics") or {}
    cm = list(econ.get("cost_models_reported") or [])
    for mode in ("minimal_emit", "full_multitarget_core", "full_multitarget"):
        lines.append(f"### Emit mode `{mode}`")
        lines.append("")
        hdr = (
            "| Workflow | AINL reference | Compile ms (mean×3) | AINL emit (active) | AINL emit (tiktoken) | "
            "Pure lines | Lang lines | Pure tk | Lang tk | AINL tk ÷ Pure tk | AINL tk ÷ Lang tk |"
        )
        sep = "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
        for mname in cm:
            hdr += f" AINL `{mname}` USD | HW `{mname}` USD |"
            sep += "---:|---:|"
        lines.append(hdr + "|")
        lines.append(sep + "|")
        for g in hb.get("groups", []):
            name = g.get("name", "")
            rel = g.get("ainl_reference_artifact") or "—"
            bs = g.get("baseline_source") or {}
            md = (g.get("modes") or {}).get(mode, {})

            def _r(x: Any) -> str:
                if x is None:
                    return "—"
                return f"{float(x):.2f}x"

            row_cells = [
                name,
                f"`{rel}`",
                "—",
                str(md.get("ainl_aggregate_emit_active_metric", "—")),
                str(md.get("ainl_aggregate_emit_tiktoken", "—")),
                str(bs.get("pure_nonempty_lines", "—")),
                str(bs.get("lang_nonempty_lines", "—")),
                str(bs.get("pure_tiktoken", "—")),
                str(bs.get("lang_tiktoken", "—")),
                _r(md.get("ratio_ainl_tiktoken_over_pure_py_tiktoken")),
                _r(md.get("ratio_ainl_tiktoken_over_langgraph_tiktoken")),
            ]
            ea = md.get("estimated_cost_usd_ainl_emit_tiktoken") or {}
            eh = md.get("estimated_cost_usd_handwritten_sources_tiktoken") or {}
            for m in cm:
                av = ea.get(m)
                hv = eh.get(m)
                row_cells.append("—" if av is None else f"{float(av):.6f}")
                row_cells.append("—" if hv is None else f"{float(hv):.6f}")
            lines.append("| " + " | ".join(row_cells) + " |")
        lines.append("")
    for g in hb.get("groups", []):
        err = (g.get("baseline_source") or {}).get("tiktoken_error")
        if err:
            lines.append(f"*tiktoken error ({g.get('name')}):* `{err}`")
    lines.append("")
    return lines


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Segmented capability-driven AINL benchmark")
    ap.add_argument(
        "--metric",
        choices=["tiktoken", "approx_chunks", "nonempty_lines"],
        default="tiktoken",
        help="Token/size metric for emitted artifacts (default: tiktoken cl100k_base).",
    )
    ap.add_argument(
        "--mode",
        choices=["full_multitarget", "full_multitarget_core", "minimal_emit", "both", "wide"],
        default="both",
        help=(
            "Benchmark emit planning mode. "
            "`wide` = full_multitarget_core + full_multitarget + minimal_emit (recommended for `BENCHMARK.md`). "
            "`both` = full_multitarget + minimal_emit only."
        ),
    )
    ap.add_argument("--profile-name", default="all", help="profile name or 'all'")
    ap.add_argument("--artifact-profiles", default=str(DEFAULT_ARTIFACT_PROFILES))
    ap.add_argument("--benchmark-manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    ap.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    ap.add_argument(
        "--skip-markdown-inject",
        action="store_true",
        help="Only write JSON; skip markdown generation (CI / regression checks).",
    )
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
    ap.add_argument(
        "--cost-model",
        default="both",
        help="Comma-separated keys or 'both' (gpt-4o+claude-3-5-sonnet), 'none' to skip $ columns.",
    )
    ap.add_argument(
        "--compile-reliability-runs",
        type=int,
        default=0,
        help="Repeat compile N times per artifact (0=off); reports success %% and compile-time stddev.",
    )
    ap.add_argument(
        "--strict-mode",
        action="store_true",
        help=(
            "Use AICodeCompiler(strict_mode=True, strict_reachability=True). "
            "Only honored when --profile-name=canonical_strict_valid (otherwise warned and ignored)."
        ),
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
    if mode_request == "wide":
        return ["full_multitarget_core", "full_multitarget", "minimal_emit"]
    return [mode_request]


def parse_cost_model_cli(s: str) -> List[str]:
    """Parse ``--cost-model`` (``both``, ``none``, or comma-separated pricing keys)."""
    raw = (s or "").strip().lower()
    if raw in ("none", "off", ""):
        return []
    if raw == "both":
        return parse_cost_model_arg("both")
    keys: List[str] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        keys.extend(parse_cost_model_arg(p))
    # de-dupe preserving order
    seen: Dict[str, None] = {}
    out: List[str] = []
    for k in keys:
        if k not in seen:
            seen[k] = None
            out.append(k)
    return out


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        from compiler_v2 import AICodeCompiler

        artifact_profiles_path = Path(args.artifact_profiles)
        benchmark_manifest_path = Path(args.benchmark_manifest)
        benchmark_manifest = load_benchmark_manifest(benchmark_manifest_path)
        viable_overrides = load_viable_for_aggregate_overrides(artifact_profiles_path)
        if args.metric == "approx_chunks":
            logger.warning(
                "DEPRECATED --metric=approx_chunks: JSON uses this unit; BENCHMARK.md foregrounds tiktoken (cl100k_base). "
                "Prefer default tiktoken for billing-aligned sizing."
            )
        count_fn = metric_counter(args.metric)
        strict_compiler_active = False
        if args.strict_mode:
            if args.profile_name != "canonical_strict_valid":
                logger.warning(
                    "--strict-mode only applies when --profile-name=canonical_strict_valid; "
                    "ignoring (current --profile-name=%r).",
                    args.profile_name,
                )
            else:
                strict_compiler_active = True
                logger.info("Strict compiler mode: strict_mode=True, strict_reachability=True")
        compiler = AICodeCompiler(
            strict_mode=strict_compiler_active,
            strict_reachability=strict_compiler_active,
        )
        cost_models = parse_cost_model_cli(args.cost_model)
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
                    metric_name=args.metric,
                    cost_models=cost_models or None,
                    compile_reliability_runs=int(args.compile_reliability_runs),
                )
                prof = {
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
                apply_viable_aggregate_subset(
                    prof,
                    profile_name=profile_name,
                    overrides=viable_overrides,
                )
                profiles_payload.append(prof)
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
                cost_models=cost_models or None,
            )

        report = build_report(
            metric=args.metric,
            mode_request=args.mode,
            profile_request=args.profile_name,
            benchmark_manifest=benchmark_manifest,
            mode_payloads=mode_payloads,
            handwritten_baseline_size_comparison=handwritten_cmp,
            cost_models=cost_models or None,
            compile_reliability_runs=int(args.compile_reliability_runs),
            strict_compiler_mode=strict_compiler_active,
        )

        json_out = Path(args.json_out)
        md_out = Path(args.markdown_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote JSON benchmark: {json_out}")
        if not args.skip_markdown_inject:
            md_out.parent.mkdir(parents=True, exist_ok=True)
            md_out.write_text(render_markdown(report, benchmark_manifest), encoding="utf-8")
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
