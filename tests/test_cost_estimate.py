import json
from pathlib import Path

import pytest

from tooling.cost_estimate import (
    DEFAULT_MODEL,
    MODEL_PRICING,
    estimate_file_cost,
    estimate_ir_cost,
    format_estimate_report,
    resolve_model_pricing,
)


def _llm_ir() -> dict:
    return {
        "labels": {
            "L1": {
                "nodes": [
                    {"id": "search", "op": "R", "data": {"adapter": "http", "target": "http.GET", "args": ["https://example.com"]}},
                    {
                        "id": "classify",
                        "op": "R",
                        "data": {"adapter": "llm", "target": "llm.classify", "args": ["classify this text please"]},
                    },
                    {
                        "id": "reply",
                        "op": "R",
                        "data": {"adapter": "openrouter", "target": "llm.call", "args": ["write a short reply"]},
                    },
                ]
            }
        }
    }


def test_empty_ir_warns():
    report = estimate_ir_cost({})
    assert report["totals"]["sum_cost_usd"] == 0.0
    assert any("No labels" in w for w in report["warnings"])


def test_mixed_graph_counts_llm_and_zero_cost_nodes():
    report = estimate_ir_cost(_llm_ir(), pricing_model="gpt-4o")
    assert report["totals"]["node_count"] == 3
    assert report["totals"]["llm_node_count"] == 2
    assert report["totals"]["sum_cost_usd"] > 0
    assert len(report["per_label"]) == 1
    assert report["per_label"][0]["llm_node_count"] == 2


def test_unknown_model_falls_back_with_warning():
    _, _, _, warnings = resolve_model_pricing("nonexistent-model-xyz")
    assert warnings
    report = estimate_ir_cost(_llm_ir(), pricing_model="nonexistent-model-xyz")
    assert report["totals"]["sum_cost_usd"] > 0
    assert report["warnings"]


def test_all_catalog_models_have_pricing():
    for model_name in MODEL_PRICING:
        report = estimate_ir_cost(_llm_ir(), pricing_model=model_name)
        assert report["totals"]["sum_cost_usd"] > 0, model_name


def test_format_table_and_summary_and_json():
    report = estimate_ir_cost(_llm_ir(), pricing_model=DEFAULT_MODEL)
    table = format_estimate_report(report, style="table")
    summary = format_estimate_report(report, style="summary")
    payload = json.loads(format_estimate_report(report, style="json"))
    assert "AINL Graph Cost Estimate" in table
    assert "GRAPH TOTAL" in table
    assert "Estimated cost" in summary
    assert payload["totals"]["llm_node_count"] == 2
    assert "projections" in payload


def test_runs_per_day_projection():
    report = estimate_ir_cost(_llm_ir(), pricing_model="gpt-4o", runs_per_day=20)
    per_run = report["totals"]["sum_cost_usd"]
    assert report["projections"]["runs_per_day"] == 20
    assert report["projections"]["daily_cost_usd"] == pytest.approx(per_run * 20, rel=1e-4)


def test_estimate_file_cost_on_hello_compact(tmp_path: Path) -> None:
    src = Path(__file__).resolve().parents[1] / "examples" / "compact" / "hello_compact.ainl"
    if not src.is_file():
        pytest.skip("hello_compact.ainl missing")
    report = estimate_file_cost(str(src), model="gpt-4o-mini")
    assert "totals" in report
    assert report["totals"]["sum_cost_usd"] >= 0


def test_cli_estimate_json_subprocess() -> None:
    import os
    import subprocess
    import sys

    src = Path(__file__).resolve().parents[1] / "examples" / "compact" / "hello_compact.ainl"
    if not src.is_file():
        pytest.skip("hello_compact.ainl missing")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "estimate", str(src), "--format", "json", "--model", "gpt-4o-mini"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "totals" in data
    assert "projections" in data
