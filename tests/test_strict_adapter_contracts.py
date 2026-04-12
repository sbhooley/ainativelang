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
        'L1: R postgres.QUERY "SELECT 1" ->out J out\n',
        'L1: R postgres.EXECUTE "UPDATE x SET y = 1" ->out J out\n',
        'L1: R postgres.TRANSACTION [] ->out J out\n',
        'L1: R mysql.QUERY "SELECT 1" ->out J out\n',
        'L1: R mysql.EXECUTE "UPDATE x SET y = 1" ->out J out\n',
        'L1: R mysql.TRANSACTION [] ->out J out\n',
        'L1: R redis.GET "k" ->out J out\n',
        'L1: R redis.SET "k" "v" ->out J out\n',
        'L1: R redis.TRANSACTION [] ->out J out\n',
        'L1: R dynamodb.GET "users" "key" ->out J out\n',
        'L1: R dynamodb.PUT "users" "item" ->out J out\n',
        'L1: R dynamodb.QUERY "users" "pk = :pk" "expr_values" ->out J out\n',
        'L1: R dynamodb.STREAMS_SUBSCRIBE "users" "LATEST" {} 0.2 10 ->out J out\n',
        'L1: R dynamodb.STREAMS_UNSUBSCRIBE "users" ->out J out\n',
        'L1: R airtable.LIST "users" ->out J out\n',
        'L1: R airtable.FIND "users" "formula" ->out J out\n',
        'L1: R airtable.CREATE "users" "record" ->out J out\n',
        'L1: R airtable.ATTACHMENT_UPLOAD "users" "rec1" "Files" "https://files.example.com/a" "a.bin" ->out J out\n',
        'L1: R airtable.WEBHOOK_LIST "users" ->out J out\n',
        'L1: R supabase.SELECT "users" ->out J out\n',
        'L1: R supabase.INSERT "users" "record" ->out J out\n',
        'L1: R supabase.AUTH_SIGN_IN_WITH_PASSWORD "a@x.dev" "pw" ->out J out\n',
        'L1: R supabase.REALTIME_REPLAY "ch" "latest" 10 0.01 ->out J out\n',
        'L1: R supabase.REALTIME_GET_CURSOR "ch" "g1" "c1" ->out J out\n',
        'L1: R supabase.REALTIME_ACK "ch" "cur1" "g1" "c1" ->out J out\n',
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


def test_strict_adapter_effect_includes_memory_persona_graph_ops():
    """Strict keys use uppercased verbs (see strict_adapter_key)."""
    for key in (
        "memory.RECALL",
        "memory.SEARCH",
        "memory.EXPORT_GRAPH",
        "memory.STORE_PATTERN",
        "memory.STORE",
        "persona.UPDATE",
        "persona.GET",
    ):
        assert strict_adapter_effect(key) is not None, key


def test_strict_compile_allows_memory_persona_graph_adapter_verbs():
    """OP_REGISTRY memory.* / persona.* R steps must pass strict graph adapter contract."""
    programs = [
        'L1: R memory.recall * ->out J out\n',
        'L1: R memory.search "q" * ->out J out\n',
        'L1: R memory.export_graph * ->out J out\n',
        'L1: R memory.store_pattern "p" v * ->out J out\n',
        'L1: R memory.store "p" v * ->out J out\n',
        'L1: R persona.update "t" 0.5 * ->out J out\n',
        'L1: R persona.get "t" * ->out J out\n',
    ]
    for code in programs:
        errs = _strict_errors(code)
        assert not errs, f"{code!r} -> {errs!r}"
