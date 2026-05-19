"""Tests for competitor baseline token benchmark script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_competitor_baselines_produces_schema(tmp_path):
    out = tmp_path / "competitor_baseline_tokens.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark_competitor_baselines.py"), "--json-out", str(out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kind"] == "competitor_baseline_tokens"
    assert data["token_counting_method"] == "tiktoken_cl100k_base"
    workloads = {w["id"]: w for w in data["workloads"]}
    assert "enterprise_monitor" in workloads
    assert "support_ticket_router" in workloads
    em = workloads["enterprise_monitor"]["tiktoken_cl100k_base"]
    assert em["ainl"] > 0
    assert em["langgraph"] > em["ainl"]
    assert em["python_hand_optimized"] > em["ainl"]
