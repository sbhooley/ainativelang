#!/usr/bin/env python3
"""Runtime latency and memory benchmark for AINL workflows (compile + RuntimeEngine).

Mirrors ``scripts/benchmark_size.py`` CLI shape (profiles, modes, JSON out) but measures
execution: wall-clock run latency, RSS delta via psutil, and adapter call counts.

Emit *modes* (full_multitarget / minimal_emit) do not change the executed graph; the same
``.ainl`` source is compiled and run. Modes are recorded in the JSON for alignment with
``tooling/benchmark_size.json`` consumers.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tooling.bench_metrics import cost_dict_for_tokens, economics_block, tiktoken_count
from tooling.emission_planner import load_benchmark_manifest

logger = logging.getLogger(__name__)

# Largest **runnable** golden example on default core adapters (see probe in docs string).
DEFAULT_SCALABILITY_ARTIFACT = "examples/golden/04_alerting_monitor.ainl"

DEFAULT_ARTIFACT_PROFILES = ROOT / "tooling" / "artifact_profiles.json"
DEFAULT_BENCHMARK_MANIFEST = ROOT / "tooling" / "benchmark_manifest.json"
DEFAULT_JSON_OUT = ROOT / "tooling" / "benchmark_runtime_results.json"
DEFAULT_MARKDOWN_OUT = ROOT / "BENCHMARK.md"
DEFAULT_BASELINES_ROOT = ROOT / "benchmarks" / "handwritten_baselines"
RUNTIME_SECTION_START = "<!-- RUNTIME_BENCH_START -->"
RUNTIME_SECTION_END = "<!-- RUNTIME_BENCH_END -->"
BASELINE_RUNTIME_SECTION_START = "<!-- BASELINE_RUNTIME_BENCH_START -->"
BASELINE_RUNTIME_SECTION_END = "<!-- BASELINE_RUNTIME_BENCH_END -->"

# Map baseline folder name -> representative AINL path for side-by-side lookup in profile results.
BASELINE_AINL_REFERENCE: Dict[str, str] = {
    "token_budget_monitor": "openclaw/bridge/wrappers/token_budget_alert.ainl",
    "basic_scraper": "examples/scraper/basic_scraper.ainl",
    "retry_timeout_wrapper": "examples/retry_error_resilience.ainl",
}

_SCRAPER_MOCK_HTML = """
<html><body>
  <div class="product-title">Widget A</div><span class="product-price">$10</span>
  <div class="product-title">Widget B</div><span class="product-price">$12</span>
</body></html>
""".strip()


def _load_benchmark_size_module() -> Any:
    """Load ``benchmark_size`` as a module (``scripts`` is not a package)."""
    path = ROOT / "scripts" / "benchmark_size.py"
    spec = importlib.util.spec_from_file_location("_ainl_benchmark_size", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Required before exec_module: dataclasses (and typing) expect the module in sys.modules.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_bs = _load_benchmark_size_module()
resolve_profile_selection: Callable[..., Tuple[List[str], Dict[str, str], Dict]] = _bs.resolve_profile_selection
parse_cost_model_cli: Callable[[str], List[str]] = _bs.parse_cost_model_cli


def _require_psutil():
    try:
        import psutil  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "psutil is required for runtime benchmark RSS metrics. "
            "Install with: pip install 'ainativelang[benchmark]' or pip install psutil"
        ) from exc
    return psutil


def _percentile_nearest(sorted_vals: List[float], pct: float) -> float:
    """Nearest-rank style percentile in [0, 100]."""
    if not sorted_vals:
        return 0.0
    xs = sorted(sorted_vals)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    frac = k - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def strict_flag_for_class(class_name: str) -> bool:
    return class_name == "strict-valid"


def count_ir_label_nodes(ir: Dict[str, Any]) -> int:
    """Count IR ``labels[*].nodes`` entries (proxy for workflow graph size)."""
    return sum(len((v or {}).get("nodes") or []) for v in (ir.get("labels") or {}).values())


def _runtime_engine_from_source(
    code: str,
    *,
    strict: bool,
    execution_mode: str,
) -> Tuple[Any, str, Dict[str, Any]]:
    """Compile and construct ``RuntimeEngine``; returns (engine, entry_label, ir)."""
    from compiler_v2 import AICodeCompiler
    from runtime.engine import RuntimeEngine

    compiler = AICodeCompiler(strict_mode=strict, strict_reachability=False)
    ir = compiler.compile(code, emit_graph=True)
    if ir.get("errors"):
        err = "; ".join(str(e) for e in (ir.get("errors") or [])[:3])
        raise RuntimeError(f"compile errors: {err}")
    eng = RuntimeEngine(ir, trace=False, execution_mode=execution_mode)
    return eng, eng.default_entry_label(), ir


def benchmark_execution_reliability(
    rel: str,
    *,
    root: Path,
    artifact_class: str,
    execution_mode: str,
    n_runs: int,
) -> Dict[str, Any]:
    """
    Run ``run_label`` *n_runs* times with a fresh frame (single engine build) for success rate + latency stddev.
    """
    if n_runs <= 0:
        return {}
    src_path = root / rel
    if not src_path.exists():
        return {"ok": False, "error": "file not found", "runs_requested": n_runs}
    code = src_path.read_text(encoding="utf-8")
    strict = strict_flag_for_class(artifact_class)
    try:
        eng, label, _ir = _runtime_engine_from_source(code, strict=strict, execution_mode=execution_mode)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "runs_requested": n_runs,
            "execution_successes": 0,
            "execution_failures": n_runs,
            "success_rate": 0.0,
            "latency_ms_stddev": 0.0,
            "failure_samples": [{"run": 0, "error": str(exc)}],
        }
    latencies: List[float] = []
    failures: List[Dict[str, Any]] = []
    for i in range(n_runs):
        try:
            t0 = time.perf_counter()
            eng.run_label(label, frame={})
            latencies.append((time.perf_counter() - t0) * 1000.0)
        except Exception as exc:
            failures.append({"run": i, "error": str(exc)})
    successes = len(latencies)
    std = float(statistics.pstdev(latencies)) if len(latencies) > 1 else 0.0
    return {
        "ok": successes > 0,
        "runs_requested": n_runs,
        "execution_successes": successes,
        "execution_failures": len(failures),
        "success_rate": float(successes) / float(n_runs) if n_runs else 0.0,
        "latency_ms_stddev": std,
        "failure_samples": failures[:10],
    }


def run_scalability_probe(
    rel: str,
    *,
    root: Path,
    warmup: int,
    timed_runs: int,
    execution_mode: str,
) -> Dict[str, Any]:
    """
    One-shot larger-workflow probe: compile (×3 mean), IR node count, RSS Δ, execution latency.
    """
    src_path = root / rel
    out: Dict[str, Any] = {"artifact": rel, "ok": False}
    if not src_path.exists():
        out["error"] = "file not found"
        return out
    code = src_path.read_text(encoding="utf-8")
    from compiler_v2 import AICodeCompiler

    compiler = AICodeCompiler(strict_mode=False, strict_reachability=False)
    compile_samples: List[float] = []
    ir: Optional[Dict[str, Any]] = None
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            ir = compiler.compile(code, emit_graph=True)
        except Exception as exc:
            out["error"] = f"compile: {exc}"
            return out
        compile_samples.append((time.perf_counter() - t0) * 1000.0)
        if ir.get("errors"):
            out["error"] = "compile returned IR errors"
            out["compile_time_ms_mean"] = float(statistics.mean(compile_samples))
            return out
    assert ir is not None
    out["compile_time_ms_mean"] = float(statistics.mean(compile_samples))
    out["ir_label_node_count"] = count_ir_label_nodes(ir)
    psutil = _require_psutil()
    proc = psutil.Process()
    from runtime.engine import RuntimeEngine

    try:
        eng = RuntimeEngine(ir, trace=False, execution_mode=execution_mode)
    except Exception as exc:
        out["error"] = f"engine: {exc}"
        return out
    label = eng.default_entry_label()
    try:
        for _ in range(max(1, warmup)):
            eng.run_label(label, frame={})
    except Exception as exc:
        out["error"] = f"warmup: {exc}"
        return out
    rss_baseline = proc.memory_info().rss / (1024 * 1024)
    latencies: List[float] = []
    peak_delta_mb = 0.0
    for _ in range(max(1, timed_runs)):
        try:
            t0 = time.perf_counter()
            eng.run_label(label, frame={})
            latencies.append((time.perf_counter() - t0) * 1000.0)
        except Exception as exc:
            out["error"] = f"timed run: {exc}"
            return out
        rss_after = proc.memory_info().rss / (1024 * 1024)
        peak_delta_mb = max(peak_delta_mb, rss_after - rss_baseline)
    out["ok"] = True
    out["latency_mean_ms"] = float(statistics.mean(latencies))
    out["peak_rss_delta_mb"] = float(peak_delta_mb)
    out["ainl_source_tiktoken"] = tiktoken_count(code)
    return out


def enrich_baselines_handwritten_economics(
    baselines: Dict[str, Any],
    *,
    baselines_root: Path,
    cost_models: List[str],
) -> None:
    """Attach tiktoken + estimated $ for combined handwritten ``.py`` sources per group."""
    if not cost_models:
        return
    for g in baselines.get("groups") or []:
        name = str(g.get("name", ""))
        sub = baselines_root / name
        pure_p = sub / "pure_async_python.py"
        lang_p = sub / "langgraph_version.py"
        py = pure_p.read_text(encoding="utf-8") if pure_p.is_file() else ""
        lg = lang_p.read_text(encoding="utf-8") if lang_p.is_file() else ""
        stack_tk = tiktoken_count(py) + tiktoken_count(lg)
        g["handwritten_sources_tiktoken"] = int(stack_tk)
        g["estimated_cost_usd_per_run_handwritten_stack"] = cost_dict_for_tokens(stack_tk, cost_models)
        ar = g.get("ainl_reference_source_tiktoken")
        if ar is not None:
            g["estimated_cost_usd_per_run_ainl_reference"] = cost_dict_for_tokens(int(ar), cost_models)


def discover_baseline_groups(baselines_root: Path) -> List[Path]:
    """Return subdirectories that contain both ``pure_async_python.py`` and ``langgraph_version.py``."""
    if not baselines_root.is_dir():
        return []
    out: List[Path] = []
    for p in sorted(baselines_root.iterdir()):
        if not p.is_dir():
            continue
        if (p / "pure_async_python.py").is_file() and (p / "langgraph_version.py").is_file():
            out.append(p)
    return out


def import_baseline_modules(subdir: Path) -> Tuple[Any, Any]:
    """
    Load ``pure_async_python`` and ``langgraph_version`` from *subdir*.

    Clears cached modules of those names so each group loads the correct files (they share
    module basenames across groups). Temporarily prepends *subdir* to ``sys.path`` so
    ``langgraph_version``'s ``from pure_async_python import ...`` resolves.
    """
    for key in ("pure_async_python", "langgraph_version"):
        sys.modules.pop(key, None)
    path_insert = str(subdir.resolve())
    if path_insert not in sys.path:
        sys.path.insert(0, path_insert)
    try:
        import pure_async_python as pure_mod  # type: ignore
        import langgraph_version as lang_mod  # type: ignore
    finally:
        try:
            sys.path.remove(path_insert)
        except ValueError:
            pass
    return pure_mod, lang_mod


def _baseline_coroutine_factories(name: str, pure_mod: Any, lang_mod: Any) -> Tuple[Callable[[], Awaitable[Any]], Callable[[], Awaitable[Any]]]:
    """
    Return callables that each produce a **fresh** coroutine for timed runs.

    Uses fixed mock inputs so runs are deterministic (no live bridge/HTTP).
    """
    if name == "token_budget_monitor":
        inp = pure_mod.TokenBudgetInput(
            dry_run=False,
            cache_mb=13.5,
            report_already_sent_today=False,
            prune_error=False,
        )

        def pure_coro() -> Awaitable[Any]:
            return pure_mod.run_token_budget_monitor(inp, None)

        def lang_coro() -> Awaitable[Any]:
            return lang_mod.run_via_langgraph(inp, None)

        return pure_coro, lang_coro

    if name == "basic_scraper":

        def pure_coro() -> Awaitable[Any]:
            return pure_mod.run_basic_scrape(mock_html=_SCRAPER_MOCK_HTML, store=pure_mod.ProductStore())

        def lang_coro() -> Awaitable[Any]:
            return lang_mod.run_via_langgraph(mock_html=_SCRAPER_MOCK_HTML, store=lang_mod.ProductStore())

        return pure_coro, lang_coro

    if name == "retry_timeout_wrapper":
        cfg = pure_mod.RetryTimeoutConfig()

        def pure_coro() -> Awaitable[Any]:
            return pure_mod.run_retry_timeout_wrapper(cfg)

        def lang_coro() -> Awaitable[Any]:
            return lang_mod.run_via_langgraph(cfg)

        return pure_coro, lang_coro

    raise ValueError(f"no baseline runner spec for '{name}'")


async def benchmark_async_coroutine_factory(
    label: str,
    factory: Callable[[], Awaitable[Any]],
    *,
    warmup: int,
    timed_runs: int,
) -> Dict[str, Any]:
    """
    Warm up and time *timed_runs* executions of ``await factory()`` (new coroutine each call).

    Records RSS delta (MB) vs post-warmup baseline like ``benchmark_one_artifact``.
    """
    psutil = _require_psutil()
    proc = psutil.Process()
    err: Optional[str] = None
    try:
        for _ in range(warmup):
            await factory()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{label} warmup: {exc}",
            "latency_ms": {},
            "peak_rss_delta_mb": None,
            "adapter_calls_last_run": None,
        }

    rss_baseline = proc.memory_info().rss / (1024 * 1024)
    latencies: List[float] = []
    peak_delta_mb = 0.0

    for _ in range(timed_runs):
        t0 = time.perf_counter()
        try:
            await factory()
        except Exception as exc:
            err = f"{label} timed run: {exc}"
            break
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        rss_after = proc.memory_info().rss / (1024 * 1024)
        peak_delta_mb = max(peak_delta_mb, rss_after - rss_baseline)

    if err:
        return {
            "ok": False,
            "error": err,
            "latency_ms": {},
            "peak_rss_delta_mb": float(peak_delta_mb) if latencies else None,
            "adapter_calls_last_run": None,
        }

    sorted_lat = sorted(latencies)
    latency_summary = {
        "mean_ms": float(statistics.mean(latencies)),
        "p50_ms": _percentile_nearest(sorted_lat, 50),
        "p95_ms": _percentile_nearest(sorted_lat, 95),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "warmup_runs": warmup,
        "timed_runs": timed_runs,
    }
    return {
        "ok": True,
        "error": None,
        "latency_ms": latency_summary,
        "peak_rss_delta_mb": float(peak_delta_mb),
        "adapter_calls_last_run": None,
        "notes": "No RuntimeEngine; adapter_calls N/A for handwritten baselines.",
    }


async def benchmark_async_reliability(
    label: str,
    factory: Callable[[], Awaitable[Any]],
    *,
    n_runs: int,
) -> Dict[str, Any]:
    """Success rate + latency stddev over *n_runs* awaited ``factory()`` calls (no warm-up)."""
    if n_runs <= 0:
        return {}
    latencies: List[float] = []
    failures: List[Dict[str, Any]] = []
    for i in range(n_runs):
        try:
            t0 = time.perf_counter()
            await factory()
            latencies.append((time.perf_counter() - t0) * 1000.0)
        except Exception as exc:
            failures.append({"run": i, "error": str(exc)})
    successes = len(latencies)
    std = float(statistics.pstdev(latencies)) if len(latencies) > 1 else 0.0
    return {
        "ok": successes > 0,
        "runs_requested": n_runs,
        "execution_successes": successes,
        "execution_failures": len(failures),
        "success_rate": float(successes) / float(n_runs) if n_runs else 0.0,
        "latency_ms_stddev": std,
        "failure_samples": failures[:10],
        "label": label,
    }


async def run_handwritten_baselines_benchmark(
    *,
    baselines_root: Path,
    warmup: int,
    timed_runs: int,
    reliability_runs: int = 0,
) -> Dict[str, Any]:
    """Discover and benchmark pure-async then LangGraph implementations per group."""
    groups_dir = discover_baseline_groups(baselines_root)
    names = [p.name for p in groups_dir]
    logger.info("Comparing against %d handwritten baseline groups: %s", len(names), ", ".join(names) or "(none)")
    groups_out: List[Dict[str, Any]] = []
    for subdir in groups_dir:
        name = subdir.name
        gout: Dict[str, Any] = {"name": name, "pure_python": {}, "langgraph": {}}
        try:
            pure_mod, lang_mod = import_baseline_modules(subdir)
            pure_factory, lang_factory = _baseline_coroutine_factories(name, pure_mod, lang_mod)
        except Exception as exc:
            gout["pure_python"] = {"ok": False, "error": f"import/setup: {exc}"}
            gout["langgraph"] = {"ok": False, "error": f"import/setup: {exc}"}
            groups_out.append(gout)
            logger.warning("baseline group %s skipped: %s", name, exc)
            continue

        try:
            gout["pure_python"] = await benchmark_async_coroutine_factory(
                f"{name}/pure", pure_factory, warmup=warmup, timed_runs=timed_runs
            )
        except Exception as exc:
            gout["pure_python"] = {"ok": False, "error": str(exc), "latency_ms": {}, "peak_rss_delta_mb": None}

        try:
            gout["langgraph"] = await benchmark_async_coroutine_factory(
                f"{name}/langgraph", lang_factory, warmup=warmup, timed_runs=timed_runs
            )
        except Exception as exc:
            gout["langgraph"] = {"ok": False, "error": str(exc), "latency_ms": {}, "peak_rss_delta_mb": None}

        if reliability_runs > 0:
            try:
                gout["pure_python"]["execution_reliability"] = await benchmark_async_reliability(
                    f"{name}/pure", pure_factory, n_runs=reliability_runs
                )
            except Exception as exc:
                gout["pure_python"]["execution_reliability"] = {"ok": False, "error": str(exc)}
            try:
                gout["langgraph"]["execution_reliability"] = await benchmark_async_reliability(
                    f"{name}/langgraph", lang_factory, n_runs=reliability_runs
                )
            except Exception as exc:
                gout["langgraph"]["execution_reliability"] = {"ok": False, "error": str(exc)}

        groups_out.append(gout)
    return {"groups": groups_out, "baselines_root": str(baselines_root)}


def _find_ainl_artifact_row(
    mode_payloads: Dict[str, Dict[str, Any]],
    *,
    artifact_rel: str,
    preferred_mode: str = "full_multitarget",
    preferred_profile: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """First matching artifact row across modes/profiles (headline profile first if provided)."""
    modes_order = [preferred_mode, "minimal_emit"] if preferred_mode != "minimal_emit" else ["minimal_emit", "full_multitarget"]
    for mode_name in modes_order:
        mode = mode_payloads.get(mode_name) or {}
        profiles = list(mode.get("profiles") or [])
        if preferred_profile:
            profiles.sort(key=lambda p: 0 if p.get("name") == preferred_profile else 1)
        for prof in profiles:
            for row in prof.get("artifacts") or []:
                if row.get("artifact") == artifact_rel:
                    return row
    return None


@dataclass
class SingleArtifactResult:
    artifact: str
    artifact_class: str
    ok: bool
    error: Optional[str]
    compile_time_ms: Optional[float]
    latency_ms: Dict[str, float]
    peak_rss_delta_mb: Optional[float]
    adapter_calls: Optional[int]
    trace_steps: Optional[int]
    llm_tokens_estimated: int
    llm_calls: int


def _run_once_timed(
    eng: Any,
    label: str,
    frame: Dict[str, Any],
) -> Tuple[float, int, int]:
    """Run ``run_label`` and return (elapsed_ms, adapter_calls, trace_len)."""
    t0 = time.perf_counter()
    eng.run_label(label, frame=frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    calls = int(getattr(eng, "_adapter_calls", 0))
    trace_n = len(getattr(eng, "trace_events", []) or [])
    return elapsed_ms, calls, trace_n


def benchmark_one_artifact(
    rel: str,
    *,
    root: Path,
    artifact_class: str,
    warmup: int,
    timed_runs: int,
    execution_mode: str,
) -> SingleArtifactResult:
    """Compile (timed ×3 mean), build engine from IR once, warm up, then timed runs."""
    psutil = _require_psutil()
    proc = psutil.Process()
    src_path = root / rel
    llm_tokens = 0
    llm_calls = 0
    if not src_path.exists():
        return SingleArtifactResult(
            rel,
            artifact_class,
            False,
            "file not found",
            None,
            {},
            None,
            None,
            None,
            llm_tokens,
            llm_calls,
        )
    code = src_path.read_text(encoding="utf-8")
    strict = strict_flag_for_class(artifact_class)
    from compiler_v2 import AICodeCompiler

    compiler = AICodeCompiler(strict_mode=strict, strict_reachability=False)
    compile_samples: List[float] = []
    ir: Optional[Dict[str, Any]] = None
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            ir = compiler.compile(code, emit_graph=True)
        except Exception as exc:
            return SingleArtifactResult(
                rel,
                artifact_class,
                False,
                f"compile: {exc}",
                None,
                {},
                None,
                None,
                None,
                llm_tokens,
                llm_calls,
            )
        compile_samples.append((time.perf_counter() - t0) * 1000.0)
        if ir.get("errors"):
            err = "; ".join(str(e) for e in (ir.get("errors") or [])[:3])
            return SingleArtifactResult(
                rel,
                artifact_class,
                False,
                f"compile errors: {err}",
                statistics.mean(compile_samples) if compile_samples else None,
                {},
                None,
                None,
                None,
                llm_tokens,
                llm_calls,
            )
    compile_mean_ms = float(statistics.mean(compile_samples))
    assert ir is not None

    from runtime.engine import RuntimeEngine

    try:
        eng = RuntimeEngine(ir, trace=True, execution_mode=execution_mode)
    except Exception as exc:
        return SingleArtifactResult(
            rel,
            artifact_class,
            False,
            f"engine init: {exc}",
            compile_mean_ms,
            {},
            None,
            None,
            None,
            llm_tokens,
            llm_calls,
        )

    label = eng.default_entry_label()

    try:
        for _ in range(warmup):
            eng.run_label(label, frame={})
    except Exception as exc:
        return SingleArtifactResult(
            rel,
            artifact_class,
            False,
            f"warmup run: {exc}",
            compile_mean_ms,
            {},
            None,
            None,
            None,
            llm_tokens,
            llm_calls,
        )

    rss_baseline = proc.memory_info().rss / (1024 * 1024)
    latencies: List[float] = []
    peak_delta_mb = 0.0
    last_calls: Optional[int] = None
    last_trace: Optional[int] = None

    for _ in range(timed_runs):
        try:
            ms, calls, tr = _run_once_timed(eng, label, {})
        except Exception as exc:
            return SingleArtifactResult(
                rel,
                artifact_class,
                False,
                f"timed run: {exc}",
                compile_mean_ms,
                {},
                None,
                None,
                None,
                llm_tokens,
                llm_calls,
            )
        latencies.append(ms)
        rss_after = proc.memory_info().rss / (1024 * 1024)
        peak_delta_mb = max(peak_delta_mb, rss_after - rss_baseline)
        last_calls = calls
        last_trace = tr

    sorted_lat = sorted(latencies)
    latency_summary = {
        "mean_ms": float(statistics.mean(latencies)),
        "p50_ms": _percentile_nearest(sorted_lat, 50),
        "p95_ms": _percentile_nearest(sorted_lat, 95),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "warmup_runs": warmup,
        "timed_runs": timed_runs,
    }

    return SingleArtifactResult(
        rel,
        artifact_class,
        True,
        None,
        compile_mean_ms,
        latency_summary,
        float(peak_delta_mb),
        last_calls,
        last_trace,
        llm_tokens,
        llm_calls,
    )


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


def run_profiles_runtime(
    profile_names: Sequence[str],
    *,
    benchmark_manifest_path: Path,
    artifact_profiles_path: Path,
    root: Path,
    warmup: int,
    timed_runs: int,
    execution_mode: str,
    reliability_runs: int = 0,
    cost_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    benchmark_manifest = load_benchmark_manifest(benchmark_manifest_path)
    profiles_out: List[Dict[str, Any]] = []
    for pname in profile_names:
        selected, class_map, cfg = resolve_profile_selection(
            pname,
            artifact_profiles_path=artifact_profiles_path,
            benchmark_manifest_path=benchmark_manifest_path,
        )
        rows: List[Dict[str, Any]] = []
        failures = 0
        for rel in selected:
            r = benchmark_one_artifact(
                rel,
                root=root,
                artifact_class=class_map.get(rel, "unclassified"),
                warmup=warmup,
                timed_runs=timed_runs,
                execution_mode=execution_mode,
            )
            if not r.ok:
                failures += 1
            src_path = root / rel
            code = src_path.read_text(encoding="utf-8") if src_path.exists() else ""
            ainl_tk = tiktoken_count(code)
            row: Dict[str, Any] = {
                "artifact": r.artifact,
                "class": r.artifact_class,
                "ok": r.ok,
                "error": r.error,
                "compile_time_ms_mean": r.compile_time_ms,
                "latency_ms": r.latency_ms,
                "peak_rss_delta_mb": r.peak_rss_delta_mb,
                "adapter_calls_last_run": r.adapter_calls,
                "trace_events_last_run": r.trace_steps,
                "llm_tokens_estimated": r.llm_tokens_estimated,
                "llm_calls": r.llm_calls,
                "ainl_source_tiktoken": ainl_tk,
                "llm_token_usage": {
                    "adapter_reported_input_tokens": None,
                    "adapter_reported_output_tokens": None,
                    "note": "N/A — runtime does not log LLM adapter tokens in this benchmark.",
                },
            }
            if cost_models:
                row["estimated_cost_usd_per_run"] = cost_dict_for_tokens(ainl_tk, cost_models)
                row["runtime_cost_basis"] = "ainl_source_tiktoken_with_economics_assumptions"
            if reliability_runs > 0:
                row["execution_reliability"] = benchmark_execution_reliability(
                    rel,
                    root=root,
                    artifact_class=class_map.get(rel, "unclassified"),
                    execution_mode=execution_mode,
                    n_runs=reliability_runs,
                )
            rows.append(row)
        ok_rows = [x for x in rows if x["ok"]]
        mean_run_ms = (
            statistics.mean(float(x["latency_ms"]["mean_ms"]) for x in ok_rows) if ok_rows else None
        )
        profiles_out.append(
            {
                "name": pname,
                "description": cfg.get("description", ""),
                "selection": {
                    "artifact_profiles_section": cfg["artifact_profiles_section"],
                    "classes": cfg["classes"],
                    "artifact_count": len(selected),
                },
                "artifacts": rows,
                "summary": {
                    "artifact_count": len(rows),
                    "ok_count": len(ok_rows),
                    "fail_count": failures,
                    "mean_latency_mean_ms_across_ok": mean_run_ms,
                },
            }
        )
    return {"profiles": profiles_out}


def build_runtime_report(
    *,
    mode_request: str,
    profile_request: str,
    warmup: int,
    timed_runs: int,
    execution_mode: str,
    mode_payloads: Dict[str, Dict[str, Any]],
    benchmark_manifest: Dict,
    baselines: Optional[Dict[str, Any]] = None,
    baselines_root: Optional[Path] = None,
    cost_models: Optional[List[str]] = None,
    reliability_runs: int = 0,
    scalability: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headline = benchmark_manifest.get("headline_profile", "canonical_strict_valid")
    schema_version = "1.0"
    if baselines is not None:
        schema_version = "1.1"
    if cost_models or reliability_runs or scalability:
        schema_version = "1.2"
    report: Dict[str, Any] = {
        "schema_version": schema_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "runtime",
        "execution_mode_graph": execution_mode,
        "warmup_runs": warmup,
        "timed_runs": timed_runs,
        "execution_reliability_runs": int(reliability_runs),
        "mode_request": mode_request,
        "profile_request": profile_request,
        "headline_profile": headline,
        "modes_note": (
            "Emit modes mirror benchmark_size.json; each artifact is compiled and executed once per "
            "logical mode entry with identical runtime measurements (emit planning does not change RuntimeEngine IR)."
        ),
        "modes": mode_payloads,
    }
    if cost_models:
        report["economics"] = economics_block(cost_models=cost_models)
    if scalability is not None:
        report["scalability"] = scalability
    if baselines is not None:
        enriched = enrich_baselines_with_ainl_latency(
            baselines,
            mode_payloads=mode_payloads,
            headline_profile=headline,
        )
        if cost_models:
            if baselines_root is not None:
                enrich_baselines_handwritten_economics(
                    enriched,
                    baselines_root=baselines_root,
                    cost_models=cost_models,
                )
            else:
                for g in enriched.get("groups") or []:
                    ar = g.get("ainl_reference_source_tiktoken")
                    if ar is not None:
                        g["estimated_cost_usd_per_run_ainl_reference"] = cost_dict_for_tokens(int(ar), cost_models)
        report["baselines"] = enriched
    return report


def enrich_baselines_with_ainl_latency(
    baselines_payload: Dict[str, Any],
    *,
    mode_payloads: Dict[str, Dict[str, Any]],
    headline_profile: str,
    root: Path = ROOT,
) -> Dict[str, Any]:
    """Attach matching AINL artifact latency (headline profile, full_multitarget first) per baseline group."""
    groups = list(baselines_payload.get("groups") or [])
    for g in groups:
        name = g.get("name", "")
        rel = BASELINE_AINL_REFERENCE.get(name)
        g["ainl_reference_artifact"] = rel
        g["ainl_reference_source_tiktoken"] = None
        if rel:
            p = root / rel
            if p.is_file():
                g["ainl_reference_source_tiktoken"] = tiktoken_count(p.read_text(encoding="utf-8"))
        row = None
        if rel:
            row = _find_ainl_artifact_row(
                mode_payloads,
                artifact_rel=rel,
                preferred_mode="full_multitarget",
                preferred_profile=headline_profile,
            )
        g["ainl_execution_reliability"] = (row.get("execution_reliability") if row else None)
        if row and row.get("ok"):
            lat = row.get("latency_ms") or {}
            g["ainl_latency_mean_ms"] = lat.get("mean_ms")
            g["ainl_peak_rss_delta_mb"] = row.get("peak_rss_delta_mb")
            g["ainl_ok"] = True
        else:
            g["ainl_latency_mean_ms"] = None
            g["ainl_peak_rss_delta_mb"] = None
            g["ainl_ok"] = False
            if rel:
                g["ainl_note"] = "Artifact not in current profile selection or runtime failed."
            else:
                g["ainl_note"] = "No mapped AINL path for this baseline group."
    return {"groups": groups, "baselines_root": baselines_payload.get("baselines_root")}


def _runtime_exec_rel_cell(row: Dict[str, Any]) -> str:
    er = row.get("execution_reliability") or {}
    if not er:
        return "—"
    sr = float(er.get("success_rate", 0.0)) * 100.0
    std = float(er.get("latency_ms_stddev", 0.0))
    return f"{sr:.0f}% σ={std:.2f}ms"


def _runtime_cost_cells(row: Dict[str, Any], cost_models: List[str]) -> List[str]:
    costs = row.get("estimated_cost_usd_per_run") or {}
    return [("—" if costs.get(m) is None else f"{float(costs[m]):.6f}") for m in cost_models]


def render_runtime_markdown_section(report: Dict[str, Any]) -> str:
    econ = report.get("economics") or {}
    cost_models: List[str] = list(econ.get("cost_models_reported") or [])
    rel_n = int(report.get("execution_reliability_runs") or 0)
    lines: List[str] = [
        "## Runtime Performance",
        "",
        "Automated wall-clock and RSS measurements from ``scripts/benchmark_runtime.py`` using "
        "``RuntimeEngine`` (graph-preferred). Latencies are **run_label** only after compile; "
        "compile time is averaged over 3 compiles per artifact.",
        "",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Warm-up runs: **{report['warmup_runs']}**; timed runs per artifact: **{report['timed_runs']}**",
        f"- Graph execution mode: `{report['execution_mode_graph']}`",
        "- **Source tokens:** ``ainl_source_tiktoken`` uses ``tooling/bench_metrics.tiktoken_count`` (**cl100k_base**).",
        "",
        "| Profile | Artifacts | OK | Mean of per-artifact mean latency (ms) |",
        "|---|---:|---:|---:|",
    ]
    for mode_name in ("full_multitarget", "minimal_emit"):
        mode = report["modes"].get(mode_name)
        if not mode:
            continue
        for prof in mode.get("profiles", []):
            s = prof.get("summary", {})
            lines.append(
                f"| {prof['name']} ({mode_name}) | {s.get('artifact_count', 0)} | {s.get('ok_count', 0)} | "
                f"{s.get('mean_latency_mean_ms_across_ok') or '-'} |"
            )
    lines.append("")
    lines.append("### Sample: headline profile artifacts (mean run latency ms)")
    lines.append("")
    cost_h = ""
    if cost_models:
        cost_h = "| " + " | ".join(f"est `{m}` USD/run" for m in cost_models) + " |"
    rel_h = "| Reliability |" if rel_n > 0 else ""
    lines.append(
        "| Artifact | Class | src tk | compile ms (mean×3) | mean | p50 | p95 | min | max | RSS Δ MB | adapter calls |"
        + cost_h
        + rel_h
    )
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|" + ("|---:|" * len(cost_models)) + ("|---|" if rel_n > 0 else "")
    lines.append(sep)
    headline = report["headline_profile"]
    for mode_name in ("full_multitarget", "minimal_emit"):
        mode = report["modes"].get(mode_name)
        if not mode:
            continue
        for prof in mode.get("profiles", []):
            if prof["name"] != headline:
                continue
            for row in prof.get("artifacts", []):
                if not row.get("ok"):
                    continue
                lat = row.get("latency_ms") or {}
                cells: List[str] = [
                    row["artifact"],
                    row["class"],
                    str(row.get("ainl_source_tiktoken", "—")),
                    f"{float(row.get('compile_time_ms_mean') or 0):.2f}",
                    f"{float(lat.get('mean_ms', 0)):.2f}",
                    f"{float(lat.get('p50_ms', 0)):.2f}",
                    f"{float(lat.get('p95_ms', 0)):.2f}",
                    f"{float(lat.get('min_ms', 0)):.2f}",
                    f"{float(lat.get('max_ms', 0)):.2f}",
                    f"{row.get('peak_rss_delta_mb'):.3f}" if row.get("peak_rss_delta_mb") is not None else "-",
                    str(row.get("adapter_calls_last_run", "-")),
                ]
                cells.extend(_runtime_cost_cells(row, cost_models))
                if rel_n > 0:
                    cells.append(_runtime_exec_rel_cell(row))
                lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "**LLM counters:** reserved for future agent/OpenAI adapter lanes; JSON ``llm_token_usage`` is **N/A** unless adapters report usage."
    )
    lines.append("")
    sc = report.get("scalability")
    if sc:
        lines.append("### Scalability probe")
        lines.append("")
        if sc.get("ok"):
            lines.append(
                f"- Artifact ``{sc.get('artifact')}`` — **{sc.get('ir_label_node_count')}** IR label nodes; "
                f"compile **{float(sc.get('compile_time_ms_mean', 0)):.1f} ms** (mean×3); "
                f"mean exec **{float(sc.get('latency_mean_ms', 0)):.2f} ms**; "
                f"peak RSS Δ **{float(sc.get('peak_rss_delta_mb', 0)):.2f} MB**; "
                f"source **{sc.get('ainl_source_tiktoken')}** tiktokens."
            )
        else:
            lines.append(f"- Probe failed: `{sc.get('error', 'unknown')}` (`{sc.get('artifact')}`).")
        lines.append("")
    lines.append("JSON: ``tooling/benchmark_runtime_results.json``")
    lines.append("")
    return "\n".join(lines)


def _fmt_ms(val: Any) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.3f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_mb(val: Any) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.3f}"
    except (TypeError, ValueError):
        return "—"


def _latency_ratio(ainl: Any, other: Any) -> str:
    """AINL mean / other mean; higher means AINL slower than baseline."""
    try:
        a = float(ainl)
        o = float(other)
        if o <= 0:
            return "—"
        return f"{a / o:.2f}x"
    except (TypeError, ValueError):
        return "—"


def _baseline_runtime_markdown_lines(baselines: Dict[str, Any], report: Dict[str, Any]) -> List[str]:
    """Markdown rows for handwritten vs AINL runtime (embedded in the runtime section)."""
    econ = report.get("economics") or {}
    cost_models: List[str] = list(econ.get("cost_models_reported") or [])
    rel_n = int(report.get("execution_reliability_runs") or 0)
    lines: List[str] = [
        "### Handwritten baseline runtime comparison",
        "",
        "Mapped AINL rows use the **headline** profile from ``full_multitarget`` when that artifact "
        "appears in the current ``--profile-name`` selection. Handwritten runs use mocks; "
        "**adapter_calls** are N/A (no ``RuntimeEngine``). Costs use mapped **AINL source** tiktokens / "
        "combined handwritten ``.py`` sources with JSON ``economics`` assumptions.",
        "",
    ]
    header = (
        "| Workflow | AINL src tk | AINL mean (ms) | Pure mean (ms) | Lang mean (ms) | "
        "AINL RSS Δ | Pure RSS Δ | Lang RSS Δ | AINL/Pure | AINL/Lang |"
    )
    for m in cost_models:
        header += f" AINL `{m}` USD | HW `{m}` USD |"
    if rel_n > 0:
        header += " AINL Rel | Pure Rel | Lang Rel |"
    header += " Notes |"
    lines.append(header)
    sep = "|---|" + "---:|" * 9 + ("---:|---:|" * len(cost_models))
    if rel_n > 0:
        sep += "---|" * 3
    sep += "---|"
    lines.append(sep)
    for g in baselines.get("groups") or []:
        name = g.get("name", "")
        ainl_m = g.get("ainl_latency_mean_ms")
        pp = g.get("pure_python") or {}
        lg = g.get("langgraph") or {}
        pm = (pp.get("latency_ms") or {}).get("mean_ms") if pp.get("ok") else None
        lm = (lg.get("latency_ms") or {}).get("mean_ms") if lg.get("ok") else None
        notes: List[str] = []
        if not pp.get("ok"):
            notes.append(f"pure: {pp.get('error', 'fail')}")
        if not lg.get("ok"):
            notes.append(f"lang: {lg.get('error', 'fail')}")
        if not g.get("ainl_ok"):
            notes.append(g.get("ainl_note", "AINL row n/a"))
        note_s = "; ".join(notes) if notes else "—"
        row = "| {w} | {tk} | {a} | {p} | {l} | {ar} | {pr} | {lr} | {rp} | {rl} |".format(
            w=name,
            tk=g.get("ainl_reference_source_tiktoken", "—"),
            a=_fmt_ms(ainl_m),
            p=_fmt_ms(pm),
            l=_fmt_ms(lm),
            ar=_fmt_mb(g.get("ainl_peak_rss_delta_mb")),
            pr=_fmt_mb(pp.get("peak_rss_delta_mb")) if pp.get("ok") else "—",
            lr=_fmt_mb(lg.get("peak_rss_delta_mb")) if lg.get("ok") else "—",
            rp=_latency_ratio(ainl_m, pm),
            rl=_latency_ratio(ainl_m, lm),
        )
        ac = g.get("estimated_cost_usd_per_run_ainl_reference") or {}
        hc = g.get("estimated_cost_usd_per_run_handwritten_stack") or {}
        for m in cost_models:
            av = ac.get(m)
            hv = hc.get(m)
            row += f" {'—' if av is None else f'{float(av):.6f}'} | {'—' if hv is None else f'{float(hv):.6f}'} |"
        if rel_n > 0:
            row += (
                f" {_runtime_exec_rel_cell({'execution_reliability': g.get('ainl_execution_reliability')})} |"
                f" {_runtime_exec_rel_cell(pp)} |"
                f" {_runtime_exec_rel_cell(lg)} |"
            )
        row += " " + note_s.replace("|", "\\|")[:160] + " |"
        lines.append(row)
    lines.append("")
    return lines


def render_baseline_runtime_markdown_section(report: Dict[str, Any]) -> str:
    """Standalone fragment for optional HTML-comment injection (same table as subsection)."""
    b = report.get("baselines")
    if not b:
        return ""
    return "\n".join(_baseline_runtime_markdown_lines(b, report)).rstrip() + "\n"


def inject_runtime_section(markdown_path: Path, section_body: str) -> None:
    """Insert or replace the runtime section in ``BENCHMARK.md`` (between HTML comments)."""
    text = markdown_path.read_text(encoding="utf-8")
    block = f"{RUNTIME_SECTION_START}\n{section_body}{RUNTIME_SECTION_END}\n"
    if RUNTIME_SECTION_START in text and RUNTIME_SECTION_END in text:
        pre, _, rest = text.partition(RUNTIME_SECTION_START)
        _, _, post = rest.partition(RUNTIME_SECTION_END)
        new_text = pre + block + post.lstrip("\n")
    else:
        anchor = "\n## Supported vs Unsupported Claims\n"
        if anchor in text:
            new_text = text.replace(anchor, "\n" + block + anchor.lstrip("\n"), 1)
        else:
            new_text = text.rstrip() + "\n\n" + block
    markdown_path.write_text(new_text, encoding="utf-8")


def inject_baseline_runtime_section(markdown_path: Path, section_body: str) -> None:
    """Insert or replace baseline runtime comparison (between HTML comments)."""
    text = markdown_path.read_text(encoding="utf-8")
    block = f"{BASELINE_RUNTIME_SECTION_START}\n{section_body}{BASELINE_RUNTIME_SECTION_END}\n"
    if BASELINE_RUNTIME_SECTION_START in text and BASELINE_RUNTIME_SECTION_END in text:
        pre, _, rest = text.partition(BASELINE_RUNTIME_SECTION_START)
        _, _, post = rest.partition(BASELINE_RUNTIME_SECTION_END)
        new_text = pre + block + post.lstrip("\n")
    else:
        anchor = "\n## Supported vs Unsupported Claims\n"
        if anchor in text:
            new_text = text.replace(anchor, "\n" + block + anchor.lstrip("\n"), 1)
        else:
            new_text = text.rstrip() + "\n\n" + block
    markdown_path.write_text(new_text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="AINL runtime benchmark (latency, RSS, adapter calls)")
    ap.add_argument(
        "--mode",
        choices=["full_multitarget", "minimal_emit", "both"],
        default="both",
        help="Mirrors size benchmark modes in JSON output (runtime numbers repeat per mode).",
    )
    ap.add_argument(
        "--profile-name",
        default="canonical_strict_valid",
        help="Profile from benchmark_manifest.json, or 'all' (can be very slow).",
    )
    ap.add_argument("--runs", type=int, default=20, help="Timed executions per artifact (after warm-up).")
    ap.add_argument("--warmup", type=int, default=8, help="Warm-up runs per artifact (discarded).")
    ap.add_argument(
        "--execution-mode",
        choices=["graph-preferred", "steps-only", "graph-only"],
        default="graph-preferred",
        help="RuntimeEngine execution_mode for all artifacts.",
    )
    ap.add_argument("--artifact-profiles", default=str(DEFAULT_ARTIFACT_PROFILES))
    ap.add_argument("--benchmark-manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    ap.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    ap.add_argument("--skip-markdown-inject", action="store_true", help="Only write JSON; do not edit BENCHMARK.md")
    ap.add_argument(
        "--compare-baselines",
        action="store_true",
        help="Also benchmark benchmarks/handwritten_baselines/*/ (pure async + LangGraph).",
    )
    ap.add_argument(
        "--baselines-root",
        default=str(DEFAULT_BASELINES_ROOT),
        help="Root directory for handwritten baseline groups (subfolders with pure + LangGraph files).",
    )
    ap.add_argument(
        "--cost-model",
        default="both",
        help="'both', 'none', or comma-separated pricing keys (gpt-4o, claude-3-5-sonnet, …).",
    )
    ap.add_argument(
        "--reliability-runs",
        type=int,
        default=0,
        help="Extra execution-only repetitions per artifact/baseline (0=off) for success %% and latency σ.",
    )
    ap.add_argument(
        "--scalability",
        action="store_true",
        help=f"Run an additional probe on a large golden workflow (default: {DEFAULT_SCALABILITY_ARTIFACT}).",
    )
    ap.add_argument(
        "--scalability-artifact",
        default=DEFAULT_SCALABILITY_ARTIFACT,
        help="Relative path to the scalability probe .ainl (must run on default adapters).",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        artifact_profiles_path = Path(args.artifact_profiles)
        benchmark_manifest_path = Path(args.benchmark_manifest)
        benchmark_manifest = load_benchmark_manifest(benchmark_manifest_path)
        profile_names = _selected_profile_names(args.profile_name, benchmark_manifest)
        mode_names = _selected_modes(args.mode)

        cost_models = parse_cost_model_cli(args.cost_model)

        mode_payloads: Dict[str, Dict[str, Any]] = {}
        for mode_name in mode_names:
            if mode_name not in benchmark_manifest.get("modes", {}):
                raise ValueError(f"mode '{mode_name}' missing from benchmark manifest")
            payload = run_profiles_runtime(
                profile_names,
                benchmark_manifest_path=benchmark_manifest_path,
                artifact_profiles_path=artifact_profiles_path,
                root=ROOT,
                warmup=int(args.warmup),
                timed_runs=int(args.runs),
                execution_mode=args.execution_mode,
                reliability_runs=int(args.reliability_runs),
                cost_models=cost_models or None,
            )
            mode_payloads[mode_name] = payload

        baselines_raw: Optional[Dict[str, Any]] = None
        if args.compare_baselines:
            baselines_root = Path(args.baselines_root)
            baselines_raw = asyncio.run(
                run_handwritten_baselines_benchmark(
                    baselines_root=baselines_root,
                    warmup=int(args.warmup),
                    timed_runs=int(args.runs),
                    reliability_runs=int(args.reliability_runs),
                )
            )

        scalability_out: Optional[Dict[str, Any]] = None
        if args.scalability:
            scalability_out = run_scalability_probe(
                args.scalability_artifact,
                root=ROOT,
                warmup=max(1, int(args.warmup) // 2 or 1),
                timed_runs=max(3, int(args.runs) // 4 or 3),
                execution_mode=args.execution_mode,
            )
            logger.info(
                "Scalability probe %s: nodes=%s ok=%s",
                args.scalability_artifact,
                scalability_out.get("ir_label_node_count"),
                scalability_out.get("ok"),
            )

        report = build_runtime_report(
            mode_request=args.mode,
            profile_request=args.profile_name,
            warmup=int(args.warmup),
            timed_runs=int(args.runs),
            execution_mode=args.execution_mode,
            mode_payloads=mode_payloads,
            benchmark_manifest=benchmark_manifest,
            baselines=baselines_raw,
            baselines_root=Path(args.baselines_root),
            cost_models=cost_models or None,
            reliability_runs=int(args.reliability_runs),
            scalability=scalability_out,
        )

        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        logger.info("wrote %s", json_out)

        if not args.skip_markdown_inject:
            md_path = Path(args.markdown_out)
            section = render_runtime_markdown_section(report)
            inject_runtime_section(md_path, section)
            logger.info("updated runtime section in %s", md_path)
            if report.get("baselines"):
                inject_baseline_runtime_section(md_path, render_baseline_runtime_markdown_section(report))
                logger.info("updated handwritten baseline runtime section in %s", md_path)

        return 0
    except Exception as exc:  # pragma: no cover
        logger.error("benchmark_runtime failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
