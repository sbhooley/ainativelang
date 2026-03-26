import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.effect_analysis import strict_adapter_effect, strict_adapter_key, strict_adapter_key_for_step


def _strict_errors(code: str):
    return list(AICodeCompiler(strict_mode=True).compile(code, emit_graph=True).get("errors", []))


def test_strict_allows_explicit_runtime_supported_adapter_verbs():
    programs = [
        'L1: R core.ADD 1 2 ->out J out\n',
        'L1: R db.G User "1" ->out J out\n',
        'L1: R api.POST /x "{}" ->out J out\n',
        'L1: R http.GET "https://example.com" ->out J out\n',
        'L1: R sqlite.QUERY "SELECT 1" ->out J out\n',
        'L1: R fs.READ "note.txt" ->out J out\n',
        'L1: R tools.CALL "ping" ->out J out\n',
        'L1: R memory prune ->out J out\n',
        'L1: R ptc_runner run "(+ 1 2)" "{total :float}" 5 ->out J out\n',
        'L1: R ptc_runner.RUN "(+ 1 2)" "{total :float}" 5 ->out J out\n',
        'L1: R llm_query query "hello" "gpt" 64 ->out J out\n',
        'L1: R llm_query.QUERY "hello" "gpt" 64 ->out J out\n',
    ]
    for code in programs:
        errs = _strict_errors(code)
        assert not errs, f"strict compile unexpectedly failed for: {code!r} -> {errs!r}"


def test_strict_unknown_adapter_verb_fails_by_design():
    errs = _strict_errors('L1: R http.BOGUS "https://example.com" ->out J out\n')
    assert any("unknown adapter.verb" in e for e in errs), errs


def test_strict_core_allowlist_is_explicit():
    allowed = _strict_errors("L1: R core.ADD 2 3 ->out J out\n")
    assert not allowed, allowed

    blocked = _strict_errors("L1: R core.MAGIC 2 3 ->out J out\n")
    assert any("unknown adapter.verb 'core.MAGIC'" in e for e in blocked), blocked


def test_legacy_surface_does_not_widen_strict_contract():
    allowed = _strict_errors('L1: R ext.OP /x 1 ->out J out\n')
    assert not allowed, allowed

    blocked = _strict_errors('L1: R ext.UNKNOWN /x 1 ->out J out\n')
    assert any("unknown adapter.verb 'ext.UNKNOWN'" in e for e in blocked), blocked


def test_strict_adapter_helpers_are_deterministic_and_compiler_owned():
    key_a = strict_adapter_key("core.add", "")
    key_b = strict_adapter_key_for_step({"adapter": "core.add"})
    key_c = strict_adapter_key_for_step({"src": "core", "req_op": "add"})
    assert key_a == "core.ADD"
    assert key_b == "core.ADD"
    assert key_c == "core.ADD"
    assert strict_adapter_effect(key_a) is not None
