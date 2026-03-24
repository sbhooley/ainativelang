from pathlib import Path

from compiler_v2 import AICodeCompiler
from tooling.bench_metrics import tiktoken_count


ROOT = Path(__file__).resolve().parent.parent


def _compile_file(rel_path: str):
    src = (ROOT / rel_path).read_text(encoding="utf-8")
    return AICodeCompiler(strict_mode=False).compile(src)


def _compile_source(src: str):
    return AICodeCompiler(strict_mode=False).compile(src)


def test_web_api_emit_capabilities():
    ir = _compile_file("examples/web/basic_web_api.ainl")
    caps = ir["emit_capabilities"]
    assert caps["needs_python_api"] is True
    assert caps["needs_cron"] is False
    assert caps["needs_scraper"] is False
    assert caps["needs_langgraph"] is False
    assert caps["needs_temporal"] is False
    assert "python_api" in ir["required_emit_targets"]["minimal_emit"]


def test_full_multitarget_list_matches_tooling_full_order():
    ir = _compile_file("examples/hello.ainl")
    full = ir["required_emit_targets"]["full_multitarget"]
    assert full[-2:] == ["langgraph", "temporal"]
    assert len(full) == 8


def test_crud_emit_capabilities():
    ir = _compile_file("examples/crud_api.ainl")
    caps = ir["emit_capabilities"]
    assert caps["needs_python_api"] is True
    assert ir["required_emit_targets"]["minimal_emit"] == ["python_api"]


def test_scraper_emit_capabilities():
    ir = _compile_file("examples/scraper/basic_scraper.ainl")
    caps = ir["emit_capabilities"]
    assert caps["needs_scraper"] is True
    assert caps["needs_cron"] is True
    assert ir["required_emit_targets"]["minimal_emit"] == ["scraper", "cron"]


def test_cron_monitor_emit_capabilities():
    ir = _compile_file("examples/cron/monitor_and_alert.ainl")
    caps = ir["emit_capabilities"]
    assert caps["needs_cron"] is True
    assert caps["needs_python_api"] is False
    assert ir["required_emit_targets"]["minimal_emit"] == ["cron"]


def test_rag_emit_capabilities():
    ir = _compile_file("examples/rag_pipeline.ainl")
    caps = ir["emit_capabilities"]
    assert caps["needs_python_api"] is True
    assert "python_api" in ir["required_emit_targets"]["minimal_emit"]


def test_openclaw_daily_digest_emit_capabilities():
    ir = _compile_file("examples/openclaw/daily_digest.lang")
    caps = ir["emit_capabilities"]
    assert caps["needs_cron"] is True
    assert "cron" in ir["required_emit_targets"]["minimal_emit"]


def test_mt5_emit_capabilities_from_runtime_steps():
    ir = _compile_source(
        "L1: R mt5.BUY EURUSD 1 ->x J x\n"
    )
    caps = ir["emit_capabilities"]
    assert caps["needs_mt5"] is True
    assert "mt5" in ir["required_emit_targets"]["minimal_emit"]


def test_avm_policy_fragment_emitted_for_adapter_usage():
    ir = _compile_source(
        "L1: R core.ADD 2 3 ->x J x\n"
    )
    frag = ir.get("avm_policy_fragment")
    assert isinstance(frag, dict)
    assert "core" in frag.get("allowed_adapters", [])
    req = ir.get("execution_requirements")
    assert isinstance(req, dict)
    assert req.get("avm_policy_fragment", {}).get("allowed_adapters", []) == frag.get("allowed_adapters", [])


def test_s_hybrid_sets_langgraph_and_temporal_capabilities():
    ir = AICodeCompiler(strict_mode=True).compile(
        "S hybrid langgraph temporal\n"
        "L1:\n"
        "  R core.ADD 1 2 ->x\n"
        "  J x\n"
    )
    assert not ir.get("errors")
    caps = ir["emit_capabilities"]
    assert caps["needs_langgraph"] is True
    assert caps["needs_temporal"] is True
    me = ir["required_emit_targets"]["minimal_emit"]
    assert "langgraph" in me and "temporal" in me


def test_s_hybrid_dedupes_targets_order_preserved():
    ir = AICodeCompiler(strict_mode=True).compile(
        "S hybrid temporal langgraph temporal\n"
        "L1:\n"
        "  R core.ADD 0 0 ->x\n"
        "  J x\n"
    )
    assert not ir.get("errors")
    hy = (ir.get("services") or {}).get("hybrid") or {}
    assert hy.get("emit") == ["temporal", "langgraph"]


def test_s_hybrid_unknown_target_errors_in_strict_mode():
    ir = AICodeCompiler(strict_mode=True).compile("S hybrid crewai\nL1: J x\n")
    assert ir.get("errors")


def test_s_hybrid_langgraph_only_strict():
    ir = AICodeCompiler(strict_mode=True).compile(
        "S hybrid langgraph\n"
        "L1:\n"
        "  R core.ADD 2 3 ->x\n"
        "  J x\n"
    )
    assert not ir.get("errors")
    assert ir["emit_capabilities"]["needs_langgraph"] is True
    assert ir["emit_capabilities"]["needs_temporal"] is False
    assert "langgraph" in ir["required_emit_targets"]["minimal_emit"]
    assert "temporal" not in ir["required_emit_targets"]["minimal_emit"]


def test_core_cron_without_cr_entries_adds_minimal_python_api_fallback():
    ir = _compile_source(
        "S core cron\n"
        "L1:\n"
        "  J x\n"
    )
    assert ir["required_emit_targets"]["minimal_emit"] == ["cron", "python_api"]
    assert ir.get("emit_python_api_fallback_stub") is True
    stub = AICodeCompiler(strict_mode=False).emit_python_api(ir)
    assert "asyncio.run(main())" in stub
    assert "FastAPI" not in stub


def test_compact_prisma_react_emit_smoke_and_token_budget():
    """Compact prisma/react emit: valid shape + materially smaller than pre-compaction baselines."""
    c = AICodeCompiler(strict_mode=False)
    ir = c.compile("D User id:I name:S\nU Dash\nT rows:J\n")
    pr = c.emit_prisma_schema(ir)
    assert 'generator client' in pr and "model User" in pr and "Steven Hooley" in pr
    assert tiktoken_count(pr) < 55

    rx = c.emit_react(ir)
    assert "export const Dash" in rx and "useState" in rx and "Steven Hooley" in rx
    assert tiktoken_count(rx) < 85
