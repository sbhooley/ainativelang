import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import benchmark_size  # type: ignore


class _FakeCompiler:
    def __init__(self, fail_compile: bool = False, fail_emit: str = "", ir_markers=None) -> None:
        self.fail_compile = fail_compile
        self.fail_emit = fail_emit
        self.ir_markers = ir_markers or {}
        self.called_emitters = []

    def compile(self, source: str):
        if self.fail_compile:
            raise RuntimeError("compile failed")
        marker = self.ir_markers.get(source.strip(), {})
        if marker:
            return marker
        return {
            "emit_capabilities": {
                "needs_react_ts": False,
                "needs_python_api": True,
                "needs_prisma": True,
                "needs_mt5": False,
                "needs_scraper": False,
                "needs_cron": False,
            },
            "required_emit_targets": {
                "full_multitarget": list(benchmark_size.TARGET_ORDER),
                "minimal_emit": ["python_api", "prisma"],
            },
        }

    def emit_react(self, ir):
        self.called_emitters.append("react_ts")
        if self.fail_emit == "emit_react":
            raise RuntimeError("react failed")
        return "aa bb cc"

    def emit_python_api(self, ir):
        self.called_emitters.append("python_api")
        return "aa bb"

    def emit_prisma_schema(self, ir):
        self.called_emitters.append("prisma")
        return "aa"

    def emit_mt5(self, ir):
        self.called_emitters.append("mt5")
        return "aa bb cc dd"

    def emit_python_scraper(self, ir):
        self.called_emitters.append("scraper")
        return "aa"

    def emit_cron_stub(self, ir):
        self.called_emitters.append("cron")
        return "aa bb"


def _chunks(text: str) -> int:
    return len(text.split())


def _write_json(path: Path, data: dict) -> None:
    import json
    path.write_text(json.dumps(data), encoding="utf-8")


def _fake_manifests(tmp_path: Path):
    artifact_profiles = {
        "examples": {
            "strict-valid": ["examples/a.ainl"],
            "non-strict-only": ["examples/b.lang"],
            "legacy-compat": ["examples/c.lang"],
        }
    }
    benchmark_manifest = {
        "headline_profile": "canonical_strict_valid",
        "profiles": {
            "canonical_strict_valid": {"artifact_profiles_section": "examples", "classes": ["strict-valid"], "description": "strict"},
            "public_mixed": {"artifact_profiles_section": "examples", "classes": ["strict-valid", "non-strict-only"], "description": "mixed"},
            "compatibility_only": {"artifact_profiles_section": "examples", "classes": ["non-strict-only", "legacy-compat"], "description": "compat"},
        },
        "modes": {
            "full_multitarget": {"description": "all"},
            "full_multitarget_core": {"description": "compiler emitters only"},
            "minimal_emit": {
                "description": "needed",
                "relevance_rules": {
                    "react_ts": {"requires_capability": "needs_react_ts"},
                    "python_api": {"requires_capability": "needs_python_api"},
                    "prisma": {"requires_capability": "needs_prisma"},
                    "cron": {"requires_capability": "needs_cron"},
                    "scraper": {"requires_capability": "needs_scraper"},
                    "mt5": {"requires_capability": "needs_mt5"},
                    "langgraph": {"requires_capability": "needs_langgraph"},
                    "temporal": {"requires_capability": "needs_temporal"},
                },
                "fallback_targets": ["python_api"],
            },
        },
        "handwritten_baselines": {"status": "scaffolded"},
    }
    ap = tmp_path / "artifact_profiles.json"
    bm = tmp_path / "benchmark_manifest.json"
    _write_json(ap, artifact_profiles)
    _write_json(bm, benchmark_manifest)
    return ap, bm, benchmark_manifest


def test_profile_selection_from_manifest(tmp_path: Path):
    ap, bm, _ = _fake_manifests(tmp_path)
    selected, class_map, cfg = benchmark_size.resolve_profile_selection(
        "canonical_strict_valid",
        artifact_profiles_path=ap,
        benchmark_manifest_path=bm,
    )
    assert selected == ["examples/a.ainl"]
    assert class_map["examples/a.ainl"] == "strict-valid"
    assert cfg["artifact_profiles_section"] == "examples"


def test_mode_selection_helper():
    assert benchmark_size._selected_modes("both") == ["full_multitarget", "minimal_emit"]
    assert benchmark_size._selected_modes("wide") == [
        "full_multitarget_core",
        "full_multitarget",
        "minimal_emit",
    ]
    assert benchmark_size._selected_modes("full_multitarget") == ["full_multitarget"]


def test_full_vs_minimal_mode_behavior(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        benchmark_size,
        "_emit_standalone_bench_target",
        lambda target, ir, artifact: "",
    )
    src = tmp_path / "sample.ainl"
    src.write_text("api-only", encoding="utf-8")
    rel = src.relative_to(tmp_path).as_posix()
    compiler = _FakeCompiler(
        ir_markers={
            "api-only": {
                "emit_capabilities": {
                    "needs_react_ts": False,
                    "needs_python_api": True,
                    "needs_prisma": False,
                    "needs_mt5": False,
                    "needs_scraper": False,
                    "needs_cron": False,
                },
                "required_emit_targets": {
                    "full_multitarget": benchmark_size.TARGET_ORDER,
                    "minimal_emit": ["python_api"],
                },
            }
        }
    )
    _, _, manifest = _fake_manifests(tmp_path)
    full = benchmark_size.run_profile_benchmark(
        [rel],
        class_map={rel: "strict-valid"},
        mode_name="full_multitarget",
        benchmark_manifest=manifest,
        root=tmp_path,
        count_fn=_chunks,
        compiler=compiler,
    )
    minimal = benchmark_size.run_profile_benchmark(
        [rel],
        class_map={rel: "strict-valid"},
        mode_name="minimal_emit",
        benchmark_manifest=manifest,
        root=tmp_path,
        count_fn=_chunks,
        compiler=compiler,
    )
    full_row = full["artifacts"][0]
    min_row = minimal["artifacts"][0]
    assert full_row["included_targets"] == benchmark_size.TARGET_ORDER
    assert min_row["included_targets"] == ["python_api"]
    assert min_row["aggregate_generated_output_size"] < full_row["aggregate_generated_output_size"]


def test_minimal_mode_excludes_irrelevant_targets(tmp_path: Path):
    src = tmp_path / "cron.ainl"
    src.write_text("cron-only", encoding="utf-8")
    rel = src.relative_to(tmp_path).as_posix()
    compiler = _FakeCompiler(
        ir_markers={
            "cron-only": {
                "emit_capabilities": {
                    "needs_react_ts": False,
                    "needs_python_api": False,
                    "needs_prisma": False,
                    "needs_mt5": False,
                    "needs_scraper": False,
                    "needs_cron": True,
                },
                "crons": [{"label": "tick", "expr": "0 * * * *"}],
                "required_emit_targets": {
                    "full_multitarget": benchmark_size.TARGET_ORDER,
                    "minimal_emit": ["cron"],
                },
            }
        }
    )
    _, _, manifest = _fake_manifests(tmp_path)
    result = benchmark_size.run_profile_benchmark(
        [rel],
        class_map={rel: "strict-valid"},
        mode_name="minimal_emit",
        benchmark_manifest=manifest,
        root=tmp_path,
        count_fn=_chunks,
        compiler=compiler,
    )
    row = result["artifacts"][0]
    assert row["included_targets"] == ["cron"]
    assert "react_ts" in row["excluded_targets"]
    assert row["aggregate_generated_output_size"] == row["targets"]["cron"]["size"]
    assert row["targets"]["react_ts"]["size"] is None
    assert compiler.called_emitters == ["cron"]


def test_machine_output_shape_and_math(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        benchmark_size,
        "_emit_standalone_bench_target",
        lambda target, ir, artifact: "",
    )
    src = tmp_path / "x.ainl"
    src.write_text("x y z", encoding="utf-8")
    rel = src.relative_to(tmp_path).as_posix()
    _, _, manifest = _fake_manifests(tmp_path)
    result = benchmark_size.run_profile_benchmark(
        [rel],
        class_map={rel: "strict-valid"},
        mode_name="full_multitarget",
        benchmark_manifest=manifest,
        root=tmp_path,
        count_fn=_chunks,
        compiler=_FakeCompiler(),
    )
    payload = {
        "name": "canonical_strict_valid",
        "description": "strict",
        "selection": {"artifact_profiles_section": "examples", "classes": ["strict-valid"], "artifact_count": 1},
        "artifacts": result["artifacts"],
        "summary": result["summary"],
    }
    report = benchmark_size.build_report(
        metric="approx_chunks",
        mode_request="both",
        profile_request="all",
        benchmark_manifest=manifest,
        mode_payloads={"full_multitarget": {"profiles": [payload]}, "minimal_emit": {"profiles": [payload]}},
    )
    assert report["schema_version"] == "3.5"
    row = report["modes"]["full_multitarget"]["profiles"][0]["artifacts"][0]
    assert row["ainl_source_size"] == 3
    assert row["aggregate_generated_output_size"] == 13
    assert pytest.approx(row["aggregate_ratio_vs_source"], rel=1e-6) == 13 / 3
    drivers = report["modes"]["minimal_emit"]["profiles"][0]["size_drivers"]
    assert "top_targets" in drivers
    assert "top_artifacts" in drivers
    assert "top_minimal_emitted_artifacts" in drivers
    assert "top_minimal_emitted_targets" in drivers
    assert "residual_overhead_by_target" in drivers
    assert isinstance(drivers["residual_overhead_by_target"], list)
    assert drivers["top_targets"]
    assert "target" in drivers["top_targets"][0]
    assert "size" in drivers["top_targets"][0]


def test_viable_excludes_large_source_low_ratio_non_strict():
    prof = {
        "artifacts": [
            {
                "artifact": "examples/big.lang",
                "class": "non-strict-only",
                "ainl_source_size": 500,
                "aggregate_generated_output_size": 50,
                "aggregate_ratio_vs_source": 0.1,
                "targets": {t: {"size": None} for t in benchmark_size.TARGET_ORDER},
                "target_structure": {},
            }
        ]
    }
    benchmark_size.apply_viable_aggregate_subset(
        prof,
        profile_name="compatibility_only",
        overrides={},
    )
    assert prof["artifacts"][0]["viable_for_aggregate"] is False


def test_apply_viable_aggregate_subset_public_mixed():
    prof = {
        "artifacts": [
            {
                "artifact": "examples/strict.ainl",
                "class": "strict-valid",
                "ainl_source_size": 100,
                "aggregate_generated_output_size": 10,
                "targets": {t: {"size": None} for t in benchmark_size.TARGET_ORDER},
                "target_structure": {},
            },
            {
                "artifact": "examples/tiny.lang",
                "class": "non-strict-only",
                "ainl_source_size": 200,
                "aggregate_generated_output_size": 30,
                "targets": {t: {"size": None} for t in benchmark_size.TARGET_ORDER},
                "target_structure": {},
            },
            {
                "artifact": "examples/forced.lang",
                "class": "non-strict-only",
                "ainl_source_size": 50,
                "aggregate_generated_output_size": 30,
                "targets": {t: {"size": None} for t in benchmark_size.TARGET_ORDER},
                "target_structure": {},
            },
        ]
    }
    benchmark_size.apply_viable_aggregate_subset(
        prof,
        profile_name="public_mixed",
        overrides={"examples/forced.lang": True},
    )
    flags = [r["viable_for_aggregate"] for r in prof["artifacts"]]
    assert flags == [True, False, True]
    assert prof["excluded_legacy_count"] == 1
    assert prof["viable_aggregate"]["artifact_count"] == 2
    assert prof["viable_aggregate"]["ainl_source_total"] == 150


def test_explicit_failure_on_compile_error(tmp_path: Path):
    src = tmp_path / "bad.ainl"
    src.write_text("bad", encoding="utf-8")
    rel = src.relative_to(tmp_path).as_posix()
    _, _, manifest = _fake_manifests(tmp_path)
    with pytest.raises(benchmark_size.BenchmarkError) as exc:
        benchmark_size.run_profile_benchmark(
            [rel],
            class_map={rel: "strict-valid"},
            mode_name="full_multitarget",
            benchmark_manifest=manifest,
            root=tmp_path,
            count_fn=_chunks,
            compiler=_FakeCompiler(fail_compile=True),
        )
    assert exc.value.failures[0].stage == "compile"


def test_explicit_failure_on_emit_error(tmp_path: Path):
    src = tmp_path / "bademit.ainl"
    src.write_text("bademit", encoding="utf-8")
    rel = src.relative_to(tmp_path).as_posix()
    _, _, manifest = _fake_manifests(tmp_path)
    with pytest.raises(benchmark_size.BenchmarkError) as exc:
        benchmark_size.run_profile_benchmark(
            [rel],
            class_map={rel: "strict-valid"},
            mode_name="full_multitarget",
            benchmark_manifest=manifest,
            root=tmp_path,
            count_fn=_chunks,
            compiler=_FakeCompiler(fail_emit="emit_react"),
        )
    stages = [f.stage for f in exc.value.failures]
    assert "emit:react_ts" in stages
