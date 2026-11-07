"""Decision-op contract for the 1.8.2 runtime.

EQ, CONTAINS, TRIM, If, and Loop keep the behavior a strict graph already
shipped with. New names (EQS, HAS, CONTAINS_WORD, Break, core.IF) are the
safe forms. A quoted word does not read the frame.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from runtime.adapters.base import AdapterError, AdapterRegistry, RuntimeAdapter
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.llm_contract import CallbackLlmAdapter
from runtime.bounded_regex import RegexLimitError, regex_contains
from runtime.engine import AinlRuntimeError, RuntimeEngine
from runtime.net_guard import AddressRejected, check_fetch_url


def _run(source: str, frame=None, **kwargs):
    eng = RuntimeEngine.from_code(source, strict=True, trace=False, **kwargs)
    return eng.run_label("1", frame or {})


def test_contains_empty_needle_stays_true():
    out = _run(
        'S app core noop\n\nL1:\n  R core.CONTAINS hay "" ->ok\n  J ok\n',
        {"hay": "Smith"},
    )
    assert out is True


def test_eq_still_coerces_on_r():
    assert _run('S app core noop\n\nL1:\n  R core.EQ "1" 1 ->ok\n  J ok\n') is True
    assert _run(
        "S app core noop\n\nL1:\n  R core.EQ flag 1 ->ok\n  J ok\n",
        {"flag": True},
    ) is True
    assert _run('S app core noop\n\nL1:\n  R core.EQ "yes" "yes" ->ok\n  J ok\n') is True
    assert _run('S app core noop\n\nL1:\n  R core.EQ "yes" 0 ->ok\n  J ok\n') is False


def test_eqs_does_not_coerce_frame_values():
    core = CoreBuiltinAdapter()
    assert core.call("eq", ["1", 1], {}) is True
    assert core.call("eqs", ["1", 1], {}) is False
    assert core.call("eqs", [True, 1], {}) is False
    assert core.call("eqs", [1, 1.0], {}) is True
    assert _run(
        "S app core noop\n\nL1:\n  R core.EQS status 1 ->ok\n  J ok\n",
        {"status": "1"},
    ) is False
    assert _run(
        "S app core noop\n\nL1:\n  R core.EQ status 1 ->ok\n  J ok\n",
        {"status": "1"},
    ) is True


def test_trim_r_collapses_and_x_strips_edges():
    assert _run('S app core noop\n\nL1:\n  R core.TRIM "  a   b  " ->out\n  J out\n') == "a b"
    assert _run('S app core noop\n\nL1:\n  X out (core.trim "  a   b  ")\n  J out\n') == "a   b"


def test_loop_j_does_not_stop_and_after_wins():
    source = """
S app core noop

L1:
  Loop items it ->Lbody ->Lafter
Lbody:
  J it
Lafter:
  J "after"
"""
    assert _run(source, {"items": [1, 2, 3]}) == "after"


def test_if_branch_return_leaves_the_caller():
    source = """
S app core noop

L1:
  Set flag true
  If flag ->Lyes ->Lno
Lyes:
  J "yes"
Lno:
  J "no"
"""
    assert _run(source) == "yes"


def test_quoted_word_does_not_read_the_frame():
    source = """
S app core noop

L1:
  R core.EQ status "yes" ->ok
  J ok
"""
    assert _run(source, {"yes": "no", "status": "yes"}) is True


def test_bare_word_still_reads_the_frame():
    source = """
S app core noop

L1:
  R core.EQ status yes ->ok
  J ok
"""
    assert _run(source, {"yes": "no", "status": "yes"}) is False


def test_bool_ops_use_truthy_rules():
    assert _run(
        'S app core noop\n\nL1:\n  R core.NOT flag ->ok\n  J ok\n',
        {"flag": ""},
    ) is True
    assert _run(
        'S app core noop\n\nL1:\n  R core.NOT flag ->ok\n  J ok\n',
        {"flag": "0"},
    ) is False
    assert _run(
        'S app core noop\n\nL1:\n  R core.AND left right ->ok\n  J ok\n',
        {"left": "0", "right": ""},
    ) is False
    assert _run(
        'S app core noop\n\nL1:\n  R core.OR left right ->ok\n  J ok\n',
        {"left": "0", "right": ""},
    ) is True


def test_break_stops_and_skips_after():
    source = """
S app core noop

L1:
  Loop items it ->Lbody ->Lafter
Lbody:
  R core.EQ it 2 ->stop
  If stop ->Lstop ->Lkeep
Lstop:
  Break "found"
Lkeep:
  J it
Lafter:
  J "exhausted"
"""
    assert _run(source, {"items": [1, 2, 3]}) == "found"
    assert _run(source, {"items": [1, 3]}) == "exhausted"


def test_break_outside_a_loop_is_an_error():
    source = 'S app core noop\n\nL1:\n  Break "nope"\n'
    with pytest.raises(AinlRuntimeError) as caught:
        _run(source)
    assert caught.value.code == "BREAK_OUTSIDE_LOOP"


def test_core_if_selects_a_value_and_continues():
    source = """
S app core noop

L1:
  R core.IF flag "yes" "no" ->picked
  J picked
"""
    assert _run(source, {"flag": "0"}) == "yes"
    assert _run(source, {"flag": ""}) == "no"


def test_has_contains_word_replace_chars_and_in():
    assert _run(
        'S app core noop\n\nL1:\n  R core.HAS hay "" ->ok\n  J ok\n',
        {"hay": "Smith"},
    ) is False
    assert _run(
        'S app core noop\n\nL1:\n  R core.CONTAINS_WORD text "Smith Jones" ->ok\n  J ok\n',
        {"text": "Smith, Jones"},
    ) is True
    assert _run(
        'S app core noop\n\nL1:\n  R core.CONTAINS_WORD text "pre-litigation" ->ok\n  J ok\n',
        {"text": "a pre-litigation memo"},
    ) is True
    assert _run(
        'S app core noop\n\nL1:\n  R core.CONTAINS_WORD text "" ->ok\n  J ok\n',
        {"text": "Smith"},
    ) is False
    assert _run(
        'S app core noop\n\nL1:\n  R core.REPLACE_CHARS text ",." " " ->out\n  J out\n',
        {"text": "Smith,Jones."},
    ) == "Smith Jones "
    assert _run(
        "S app core noop\n\nL1:\n  R core.IN needle items ->ok\n  J ok\n",
        {"needle": "1", "items": [1, 2]},
    ) is False
    assert _run(
        "S app core noop\n\nL1:\n  R core.IN needle items ->ok\n  J ok\n",
        {"needle": "1", "items": ["1", "2"]},
    ) is True


def test_bounded_regex_dates_and_format():
    assert regex_contains("1:26-cv-00412", r"\d+:\d+-cv-\d+") is True
    assert regex_contains("Smith v. Jones", r"v\.") is True
    assert regex_contains("aaab", "a+ab") is True
    assert regex_contains("xx", "x*x") is True
    with pytest.raises(RegexLimitError):
        regex_contains("", "")
    with pytest.raises(RegexLimitError):
        regex_contains("aaaa", r"(a)\1")
    with pytest.raises(RegexLimitError):
        regex_contains("a" * 24 + "!", r"(a+)+$")
    found = _run(
        'S app core noop\n\nL1:\n  R core.REGEX_FINDALL text "\\\\d+:\\\\d+-cv-\\\\d+" ->out\n  J out\n',
        {"text": "see 1:26-cv-00412 now"},
    )
    assert found == ["1:26-cv-00412"]
    nov7 = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
    assert _run(
        'S app core noop\n\nL1:\n  R core.PARSE_TIME "November 7, 2026" ->out\n  J out\n'
    ) == nov7
    assert _run(
        'S app core noop\n\nL1:\n  R core.PARSE_TIME "2026-11-07" ->out\n  J out\n'
    ) == nov7
    later = _run(
        "S app core noop\n\nL1:\n  R core.ADD_DAYS start 14 ->out\n  J out\n",
        {"start": nov7},
    )
    assert later == nov7 + 14 * 86400
    assert _run(
        "S app core noop\n\nL1:\n  R core.BEFORE start later ->ok\n  J ok\n",
        {"start": nov7, "later": later},
    ) is True
    assert _run(
        'S app core noop\n\nL1:\n  R core.FORMAT "{0}" name ->out\n  J out\n',
        {"name": "Ada"},
    ) == "Ada"
    assert _run(
        'S app core noop\n\nL1:\n  R core.FORMAT "{0:plural:day|days}" n ->out\n  J out\n',
        {"n": 2},
    ) == "days"
    with pytest.raises(AinlRuntimeError):
        _run(
            'S app core noop\n\nL1:\n  R core.FORMAT "{0.__class__}" name ->out\n  J out\n',
            {"name": "Ada"},
        )
    assert _run('S app core noop\n\nL1:\n  R core.CASEFOLD "ß" ->out\n  J out\n') == "ss"
    assert _run(
        'S app core noop\n\nL1:\n  R core.HTML_TEXT "<b>Hi</b>" ->out\n  J out\n'
    ) == "Hi"


def test_map_filter_reduce_sort_put_do_not_alias():
    mapped = _run(
        """
S app core noop

L1:
  R core.MAP items L2 row ->out
  J out
L2:
  J row
""",
        {"items": ["a", "b"], "row": "shadow"},
    )
    assert mapped == ["a", "b"]
    kept = _run(
        """
S app core noop

L1:
  R core.FILTER items L2 row ->out
  J out
L2:
  R core.EQ row "a" ->ok
  J ok
""",
        {"items": ["a", "b", "a"]},
    )
    assert kept == ["a", "a"]
    total = _run(
        """
S app core noop

L1:
  R core.REDUCE items L2 0 row acc ->out
  J out
L2:
  R core.ADD acc row ->sum
  J sum
""",
        {"items": [1, 2, 3]},
    )
    assert total == 6
    ordered = _run(
        "S app core noop\n\nL1:\n  R core.SORT rows \"name\" ->out\n  J out\n",
        {"rows": [{"name": "b", "n": 1}, {"name": "a", "n": 2}, {"name": "b", "n": 3}]},
    )
    assert [row["n"] for row in ordered] == [2, 1, 3]
    doc = {"id": "1", "title": "secret"}
    out = _run(
        'S app core noop\n\nL1:\n  R core.PUT doc "title" "public" ->out\n  J out\n',
        {"doc": doc},
    )
    assert out["title"] == "public"
    assert doc["title"] == "secret"


def test_effectful_map_is_rejected_unless_the_host_opts_in():
    source = """
S app core noop

L1:
  R core.MAP items L2 row ->out
  J out
L2:
  R core.NOW ->clock
  J clock
"""
    with pytest.raises(AinlRuntimeError) as caught:
        _run(source, {"items": [1]})
    assert caught.value.code == "PURE_VIOLATION"
    out = _run(source, {"items": [1]}, limits={"allow_effectful_map": True})
    assert isinstance(out, list) and len(out) == 1


class _Db(RuntimeAdapter):
    def __init__(self):
        self.queries = []
        self.merged = []

    def call(self, target, args, context):
        verb = str(target or "").upper()
        if verb == "Q":
            self.queries.append(list(args))
            return [{"id": "1"}]
        if verb == "M":
            self.merged.append(list(args))
            doc = {"id": args[1]}
            if isinstance(args[2], dict):
                doc.update(args[2])
            return doc
        raise RuntimeError(f"unsupported {verb}")


def test_db_query_must_be_a_literal_and_merge_is_shallow():
    db = _Db()
    reg = AdapterRegistry(allowed=["core", "db"])
    reg.register("db", db)
    bad = """
S app core noop

L1:
  R db.Q matters query params ->rows
  J rows
"""
    with pytest.raises(RuntimeError, match="db.Q query must be a source literal") as caught:
        _run(bad, {"query": "SELECT secret", "params": {}}, adapters=reg)
    assert "SELECT" not in str(caught.value)
    good = """
S app core noop

L1:
  R db.Q matters "SELECT * FROM c WHERE c.id = @id" params "*" ->rows
  J rows
"""
    rows = _run(good, {"params": {"id": "1"}}, adapters=reg)
    assert rows == [{"id": "1"}]
    assert db.queries[0][1] == "SELECT * FROM c WHERE c.id = @id"
    assert db.queries[0][2] == {"id": "1"}
    assert db.queries[0][3] == "*"
    merged = _run(
        """
S app core noop

L1:
  R db.M matters "doc-1" patch etag ->doc
  J doc
""",
        {"patch": {"status": "open"}, "etag": "etag-1"},
        adapters=reg,
    )
    assert merged["status"] == "open"
    assert merged["id"] == "doc-1"
    assert db.merged[0][3] == "etag-1"


def test_http_refuses_metadata_and_rechecks_redirects():
    blocked = SimpleHttpAdapter(
        https_only=False,
        allow_hosts=["169.254.169.254", "evil.example"],
    )
    with pytest.raises(AdapterError):
        blocked.call("GET", ["http://169.254.169.254/latest/meta-data/"], {})
    with pytest.raises(AddressRejected):
        check_fetch_url("http://169.254.169.254/", https_only=False, allow_private=True)

    def fake_dns(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    original = socket.getaddrinfo
    socket.getaddrinfo = fake_dns
    try:
        with pytest.raises(AdapterError):
            blocked.call("GET", ["https://evil.example/"], {})
    finally:
        socket.getaddrinfo = original

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/go"):
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/")
                self.end_headers()
                return
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"missing")

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        local = SimpleHttpAdapter(
            allow_hosts=["127.0.0.1"],
            https_only=False,
            allow_insecure_local=True,
            check_redirects=True,
            status_as_value=True,
        )
        with pytest.raises(AdapterError) as caught:
            local.call("GET", [f"http://127.0.0.1:{port}/go"], {})
        assert "169.254.169.254" not in str(caught.value)
        missing = local.call("GET", [f"http://127.0.0.1:{port}/missing"], {})
        assert missing["ok"] is False
        assert missing["status"] == 404
        assert missing["body"] == "missing"
    finally:
        server.shutdown()
        server.server_close()


def test_llm_completion_returns_usage_and_embed():
    def complete(prompt):
        assert "sk-" not in prompt
        return {
            "status": "ok",
            "content": '{"answer":"yes"}',
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        }

    llm = CallbackLlmAdapter(complete, embed=lambda text: [0.1, 0.2])
    reg = AdapterRegistry(allowed=["core", "llm"])
    reg.register("llm", llm)
    out = _run(
        'S app core noop\n\nL1:\n  R llm.COMPLETION "classify" ->out\n  J out\n',
        adapters=reg,
    )
    assert out["status"] == "ok"
    assert out["parsed"]["answer"] == "yes"
    assert out["usage"]["total_tokens"] == 4
    vec = _run(
        'S app core noop\n\nL1:\n  R llm.EMBED "hello" ->out\n  J out\n',
        adapters=reg,
    )
    assert vec == [0.1, 0.2]


def test_env_refuses_secret_shaped_names(monkeypatch):
    monkeypatch.setenv("AINL_API_KEY", "super-secret-value")
    monkeypatch.setenv("SAS_TOKEN", "sas-value")
    monkeypatch.setenv("ACCESS_KEY", "access-value")
    monkeypatch.setenv("ACCOUNT_KEY", "account-value")
    monkeypatch.setenv("CONNECTION_STRING", "connection-value")
    monkeypatch.setenv("KEY", "key-value")
    monkeypatch.setenv("AINL_DECISION_BENIGN", "visible")
    secret_names = [
        "AINL_API_KEY",
        "SAS_TOKEN",
        "ACCESS_KEY",
        "ACCOUNT_KEY",
        "CONNECTION_STRING",
        "KEY",
    ]
    for name in secret_names:
        with pytest.raises(AinlRuntimeError) as caught:
            _run(
                f'S app core noop\n\nL1:\n  R core.ENV "{name}" ->out\n  J out\n',
                limits={"env_allowlist": secret_names},
            )
        assert "value" not in str(caught.value)
    with pytest.raises(AinlRuntimeError, match="not allowlisted"):
        _run('S app core noop\n\nL1:\n  R core.ENV "AINL_DECISION_BENIGN" ->out\n  J out\n')
    assert _run(
        'S app core noop\n\nL1:\n  R core.ENV "AINL_DECISION_BENIGN" ->out\n  J out\n',
        limits={"env_allowlist": ["AINL_DECISION_BENIGN"]},
    ) == "visible"


def test_pure_compile_rejects_env_and_llm():
    with pytest.raises(RuntimeError, match="pure program rejects"):
        RuntimeEngine.from_code(
            'S app core noop\n\nL1:\n  R core.ENV "HOME" ->v\n  J v\n',
            strict=True,
            pure=True,
        )
    with pytest.raises(RuntimeError, match="pure program rejects"):
        RuntimeEngine.from_code(
            'S app core noop\n\nL1:\n  R llm.COMPLETION "hi" ->v\n  J v\n',
            strict=True,
            pure=True,
        )


def test_return_union_and_isolated_call(tmp_path: Path):
    with pytest.raises(RuntimeError, match="outside the declared union"):
        RuntimeEngine.from_code(
            'Returns "yes" | "no"\n\nS app core noop\n\nL1:\n  J "maybe"\n',
            strict=True,
        )
    with pytest.raises(AinlRuntimeError) as caught:
        _run(
            'Returns "yes" | "no"\n\nS app core noop\n\nL1:\n  R core.ECHO status ->status\n  J status\n',
            {"status": "maybe"},
        )
    assert caught.value.code == "RETURN_UNION"
    isolated = """
S app core noop

L1:
  Set text "caller"
  Call L9 isolate text ->res
  J text
L9:
  Set text "callee"
  J text
"""
    assert _run(isolated) == "caller"
    callee = tmp_path / "callee.ainl"
    callee.write_text(
        "S app core noop\n\nL1:\n  R core.ECHO text ->text\n  J text\n",
        encoding="utf-8",
    )
    caller = tmp_path / "caller.ainl"
    caller.write_text(
        'S app core noop\n\nL1:\n  Call "callee.ainl" L1 isolate text ->out\n  J out\n',
        encoding="utf-8",
    )
    eng = RuntimeEngine.from_code(
        caller.read_text(encoding="utf-8"),
        strict=True,
        source_path=str(caller),
    )
    assert eng.run_label("1", {"text": "hello", "secret": "nope"}) == "hello"
    caller.write_text(
        'S app core noop\n\nL1:\n  Call "../callee.ainl" L1 isolate text ->out\n  J out\n',
        encoding="utf-8",
    )
    eng = RuntimeEngine.from_code(
        caller.read_text(encoding="utf-8"),
        strict=True,
        source_path=str(caller),
    )
    with pytest.raises(AinlRuntimeError):
        eng.run_label("1", {"text": "hello"})


def test_safe_trace_drops_frame_values(tmp_path: Path):
    log = tmp_path / "trace.jsonl"
    source = 'S app core noop\n\nL1:\n  R core.ECHO text ->text\n  J text\n'
    eng = RuntimeEngine.from_code(
        source,
        strict=True,
        trace=True,
        safe_trace=True,
        trajectory_log_path=str(log),
    )
    assert eng.run_label("1", {"text": "SECRET-DOCUMENT"}) == "SECRET-DOCUMENT"
    dumped = json.dumps(eng.get_trace())
    assert "SECRET-DOCUMENT" not in dumped
    assert "out" not in eng.get_trace()[-1]
    if log.exists():
        assert "SECRET-DOCUMENT" not in log.read_text(encoding="utf-8")
    default = RuntimeEngine.from_code(source, strict=True, trace=True)
    assert default.safe_trace is True
    assert default.run_label("1", {"text": "SECRET-DOCUMENT"}) == "SECRET-DOCUMENT"
    assert "SECRET-DOCUMENT" not in json.dumps(default.get_trace())
    opened = RuntimeEngine.from_code(source, strict=True, trace=True, safe_trace=False)
    opened.run_label("1", {"text": "SECRET-DOCUMENT"})
    assert "out" in opened.get_trace()[-1]


def test_eqs_source_literal_number_is_coerced_before_the_op():
    """R core.EQS "1" 1 is true because a quoted number is coerced during resolve.

    EQS is strict only after resolve, when one side is already a frame string.
    """
    assert _run('S app core noop\n\nL1:\n  R core.EQS "1" 1 ->ok\n  J ok\n') is True
    assert _run(
        "S app core noop\n\nL1:\n  R core.EQS status 1 ->ok\n  J ok\n",
        {"status": "1"},
    ) is False
    assert _run(
        "S app core noop\n\nL1:\n  R core.EQ status 1 ->ok\n  J ok\n",
        {"status": "1"},
    ) is True


def test_x_decision_ops_call_the_same_functions():
    assert _run(
        """
S app core noop

L1:
  X a (core.eqs status 1)
  J a
""",
        {"status": "1"},
    ) is False
    assert _run(
        """
S app core noop

L1:
  X a (core.eqs status 1)
  R core.EQS status 1 ->b
  R core.EQ a b ->same
  J same
""",
        {"status": "1"},
    ) is True


def test_x_env_uses_the_allowlist(monkeypatch):
    monkeypatch.setenv("SAS_TOKEN", "sas-value")
    with pytest.raises(Exception) as caught:
        _run(
            """
S app core noop

L1:
  X v (core.env "SAS_TOKEN" "fallback")
  J v
""",
            limits={"env_allowlist": ["SAS_TOKEN"]},
        )
    assert "sas-value" not in str(caught.value)


def test_parse_time_offset_fraction_and_abbreviation():
    from runtime.decision_ops import add_days, parse_time

    off = parse_time("2026-11-07T15:30:45.123456-05:00")
    expect = int(datetime(2026, 11, 7, 20, 30, 45, tzinfo=timezone.utc).timestamp())
    assert off == expect
    frac = parse_time("2026-11-07T00:00:00.9Z")
    midnight = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
    assert frac == midnight
    assert parse_time("Nov 7, 2026") == parse_time("November 7, 2026") == midnight
    assert add_days(off, 14) == off + 14 * 86400


def test_html_text_is_not_a_sanitizer():
    from runtime.decision_ops import html_text

    out = html_text("<scr<script>ipt>alert(1)</scr<script>ipt>")
    assert "alert(1)" in out


def test_regex_size_limit_is_an_error_value():
    out = _run(
        'S app core noop\n\nL1:\n  R core.REGEX_CONTAINS text "a+" ->out\n  J out\n',
        {"text": "a" * 100_001},
    )
    assert out["error"]["code"] == "REGEX_INPUT_LIMIT"
    assert "aaa" not in json.dumps(out)
    limited = _run(
        'S app core noop\n\nL1:\n  R core.REGEX_CONTAINS text "(a+)+$" ->out\n  J out\n',
        {"text": "a" * 24 + "!"},
    )
    assert limited["error"]["code"] == "REGEX_STEP_LIMIT"
    docket = json.dumps(
        r"\b(?:\d{1,2}:\d{2}-(?:cv|cr|mc|md)-\d{3,6}|No\.\s*\d{2,4}-[A-Za-z0-9\-]{2,12})\b"
    )
    assert _run(
        f'S app core noop\n\nL1:\n  R core.REGEX_CONTAINS text {docket} "i" ->ok\n  J ok\n',
        {"text": "see 1:26-CV-00412 now"},
    ) is True


def test_db_query_is_bound_capped_and_merge_needs_an_etag():
    db = _Db()
    reg = AdapterRegistry(allowed=["core", "db"])
    reg.register("db", db)
    with pytest.raises(AinlRuntimeError) as unbound:
        _run(
            """
S app core noop

L1:
  R db.Q matters "SELECT * FROM c WHERE c.id = @id" params "*" ->rows
  J rows
""",
            {"params": {}},
            adapters=reg,
        )
    assert unbound.value.code == "DB_QUERY_PARAMS"
    assert not db.queries
    with pytest.raises(AinlRuntimeError) as star:
        _run(
            """
S app core noop

L1:
  R db.Q matters "SELECT * FROM c WHERE c.id = @id" params star ->rows
  J rows
""",
            {"params": {"id": "1"}, "star": "*"},
            adapters=reg,
        )
    assert star.value.code == "DB_QUERY_PARTITION"
    wide = _Db()

    def too_many(target, args, context):
        return [{"id": str(i), "body": "FILING-TEXT"} for i in range(26)]

    wide.call = too_many
    reg.register("db", wide)
    capped = _run(
        """
S app core noop

L1:
  R db.Q matters "SELECT * FROM c WHERE c.id = @id" params "*" ->rows
  J rows
""",
        {"params": {"id": "1"}},
        adapters=reg,
    )
    assert capped["error"]["code"] == "DB_QUERY_CAP"
    assert "FILING-TEXT" not in json.dumps(capped)
    with pytest.raises(RuntimeError, match="db.M requires an etag"):
        _run(
            """
S app core noop

L1:
  R db.M matters "doc-1" patch ->doc
  J doc
""",
            {"patch": {"status": "open"}},
            adapters=reg,
        )


def test_completion_calls_have_a_default_cap():
    calls = {"n": 0}

    def complete(prompt):
        calls["n"] += 1
        return {"status": "ok", "content": "yes", "usage": {"total_tokens": 4}}

    reg = AdapterRegistry(allowed=["core", "llm"])
    reg.register("llm", CallbackLlmAdapter(complete))
    source = """
S app core noop

L1:
  Loop items it ->Lbody ->Lafter
Lbody:
  R llm.COMPLETION "hi" ->out
  J it
Lafter:
  J "done"
"""
    with pytest.raises(AinlRuntimeError) as caught:
        _run(source, {"items": list(range(20))}, adapters=reg)
    assert caught.value.code == "LLM_BUDGET"
    assert calls["n"] == 8
    calls["n"] = 0
    with pytest.raises(AinlRuntimeError) as tokens:
        _run(
            source,
            {"items": list(range(5))},
            adapters=reg,
            limits={"max_completion_calls": 20, "max_completion_tokens": 10},
        )
    assert tokens.value.code == "LLM_BUDGET"
    assert calls["n"] == 3


def test_token_cap_reads_only_the_return_usage():
    """A host that still stores tokens on the adapter object does not trip the cap."""

    class _ObjectUsage(RuntimeAdapter):
        def __init__(self):
            self.calls = 0
            self.tokens = 0

        def call(self, target, args, context):
            self.calls += 1
            self.tokens += 50_000
            return {"status": "ok", "content": "yes"}

    adapter = _ObjectUsage()
    reg = AdapterRegistry(allowed=["core", "llm"])
    reg.register("llm", adapter)
    source = """
S app core noop

L1:
  Loop items it ->Lbody ->Lafter
Lbody:
  R llm.COMPLETION "hi" ->out
  J it
Lafter:
  J "done"
"""
    assert _run(
        source,
        {"items": [1, 2, 3]},
        adapters=reg,
        limits={"max_completion_tokens": 10},
    ) == "done"
    assert adapter.tokens == 150_000
    with pytest.raises(AinlRuntimeError) as caught:
        _run(source, {"items": list(range(20))}, adapters=reg)
    assert caught.value.code == "LLM_BUDGET"


def test_pure_follows_a_cross_file_call(tmp_path: Path):
    impure = tmp_path / "impure.ainl"
    impure.write_text(
        'S app core noop\n\nL1:\n  R core.ENV "HOME" ->v\n  J v\n',
        encoding="utf-8",
    )
    pure_child = tmp_path / "pure_child.ainl"
    pure_child.write_text(
        "S app core noop\n\nL1:\n  R core.ADD 1 2 ->n\n  J n\n",
        encoding="utf-8",
    )
    bad = tmp_path / "bad.ainl"
    bad.write_text(
        'S app core noop\n\nL1:\n  Call "impure.ainl" L1 ->out\n  J out\n',
        encoding="utf-8",
    )
    eng = RuntimeEngine.from_code(
        bad.read_text(encoding="utf-8"),
        strict=True,
        pure=True,
        source_path=str(bad),
    )
    with pytest.raises(RuntimeError, match="pure program rejects"):
        eng.run_label("1", {})
    good = tmp_path / "good.ainl"
    good.write_text(
        'S app core noop\n\nL1:\n  Call "pure_child.ainl" L1 ->out\n  J out\n',
        encoding="utf-8",
    )
    child = RuntimeEngine.from_code(
        good.read_text(encoding="utf-8"),
        strict=True,
        pure=True,
        source_path=str(good),
    )
    assert child.run_label("1", {}) == 3


def test_http_constructor_is_deny_by_default():
    from runtime.adapters.http import _headers_for_redirect

    with pytest.raises(AdapterError):
        SimpleHttpAdapter().call("GET", ["https://example.com/"], {})
    for hosts in (["*"], ["*.example.com"]):
        with pytest.raises(AdapterError, match="allowlist"):
            SimpleHttpAdapter(allow_hosts=hosts).call("GET", ["https://example.com/"], {})
    assert "Authorization" in _headers_for_redirect(
        {"Authorization": "Bearer x"}, "a.example", "a.example"
    )
    stripped = _headers_for_redirect(
        {"Authorization": "Bearer x", "Accept": "text/plain"},
        "a.example",
        "b.example",
    )
    assert "Authorization" not in stripped
    assert stripped["Accept"] == "text/plain"
