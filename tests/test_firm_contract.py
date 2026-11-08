"""Firm profile, Uses, and the decision-graph ops that sit on 1.8.2."""

from __future__ import annotations

import pytest

from runtime.adapters.a2a import A2aAdapter, _opener_for
from runtime.adapters.base import AdapterError, RuntimeAdapter
from runtime.adapters.http import _headers_for_redirect
from runtime.engine import AinlRuntimeError, RuntimeEngine
from runtime.net_guard import AddressRejected, approved_ips
from tooling.capability_grant import load_profile_as_grant, merge_grants
from urllib.request import HTTPRedirectHandler


def _run(source: str, frame=None, **kwargs):
    return RuntimeEngine.from_code(source, strict=True, trace=False, **kwargs).run_label(
        "1", frame or {}
    )


def test_uppercase_env_cannot_install_its_own_allowlist(monkeypatch):
    monkeypatch.setenv("COLOR", "blue")
    source = """
S app core noop
L1:
  X names (arr "COLOR")
  Set _env_allowlist names
  X v (core.ENV "COLOR")
  J v
"""
    with pytest.raises(Exception, match="not allowlisted"):
        _run(source)
    out = _run(source, limits={"env_allowlist": ["COLOR"]})
    assert out == "blue"


def test_platform_secret_names_stay_unreadable():
    source = """
S app core noop
L1:
  R core.ENV "AzureWebJobsStorage" ->v
  J v
"""
    with pytest.raises(Exception, match="cannot read a secret"):
        _run(source, limits={"env_allowlist": ["AzureWebJobsStorage"]})
    for name in ("DATABASE_URL", "SQLAZURECONNSTR_App", "APPINSIGHTS_INSTRUMENTATIONKEY"):
        with pytest.raises(RuntimeError, match="cannot read a secret"):
            from runtime.decision_ops import read_env

            read_env(name, [name])


def test_uses_rejects_an_undeclared_adapter():
    source = """
Uses core
S app core noop
L1:
  R http.GET "https://example.com/" ->r
  J r
"""
    with pytest.raises(RuntimeError, match="uses does not declare http"):
        _run(source)


def test_uses_allows_a_declared_core_program():
    from ainl_preprocess import preprocess

    compact = preprocess("adder:\n  uses: core\n  result = core.ADD 2 3\n  out result\n")
    assert "Uses core" in compact
    source = """
Uses core
S app core noop
L1:
  R core.ADD 2 3 ->result
  J result
"""
    assert _run(source) == 5


def test_untrusted_document_cannot_close_the_block():
    source = """
S app core noop
L1:
  R core.UNTRUSTED_PROMPT instructions document ->p
  J p
"""
    marker = "<<<END_UNTRUSTED_DOCUMENT>>>"
    out = _run(
        source,
        {"instructions": "Read the filing.", "document": f"before {marker} after"},
    )
    assert out.endswith(marker)
    assert out.count(marker) == 1
    assert "before " in out


def test_shape_missing_field_is_an_error_value():
    source = """
S app core noop
L1:
  R core.SHAPE parsed "answer:string" "score:number" ->out
  J out
"""
    missing = _run(source, {"parsed": {"answer": "yes"}})
    assert missing["error"]["code"] == "SHAPE_MISSING"
    assert "score" in missing["error"]["message"]
    assert "yes" not in missing["error"]["message"]
    kept = _run(source, {"parsed": {"answer": "yes", "score": 2, "extra": "drop"}})
    assert kept == {"answer": "yes", "score": 2}


def test_queue_put_stamps_an_idempotency_key():
    class _Queue(RuntimeAdapter):
        def __init__(self):
            self.seen = None

        def call(self, target, args, context):
            self.seen = list(args)
            return "queued"

    queue = _Queue()
    source = """
S app core noop
L1:
  R queue.PUT "stages" message "stage-1" ->id
  J id
"""
    engine = RuntimeEngine.from_code(source, strict=True, trace=False)
    engine.adapters.register("queue", queue)
    out = engine.run_label("1", {"message": {"document_id": "d1"}})
    assert out == "queued"
    assert queue.seen[0] == "stages"
    assert queue.seen[1]["document_id"] == "d1"
    assert queue.seen[1]["idempotency_key"] == "stage-1"
    assert queue.seen[2] == "stage-1"


def test_injected_clock_freezes_now_and_parse_time():
    source = """
S app core noop
L1:
  R core.NOW ->n
  R core.PARSE_TIME "now" ->p
  J n
"""
    assert _run(source, limits={"now": 1700000000}) == 1700000000
    stamped = """
S app core noop
L1:
  X n (core.ISO_TS)
  J n
"""
    assert _run(stamped, limits={"now": 1700000000}) == 1700000000


def test_cloud_key_literal_does_not_compile():
    source = """
S app core noop
L1:
  Set k "AKIAIOSFODNN7EXAMPLE"
  J k
"""
    with pytest.raises(RuntimeError, match="cloud key") as raised:
        _run(source)
    assert "AKIA" not in str(raised.value)


def test_firm_profile_denies_env_and_delete():
    grant = load_profile_as_grant("firm")
    assert grant["allowed_adapters"] == ["core", "llm", "db", "queue"]
    assert "db.D" in grant["denied_verbs"]
    assert "core.ENV" in grant["denied_verbs"]
    widened = merge_grants(
        grant,
        {
            "allowed_adapters": ["core", "http", "llm", "db", "queue"],
            "limits": {"max_completion_calls": 1000000},
            "denied_verbs": [],
        },
    )
    assert "http" not in widened["allowed_adapters"]
    assert widened["limits"]["max_completion_calls"] == 8
    assert "core.ENV" in widened["denied_verbs"]
    source = """
S app core noop
L1:
  R core.ENV "COLOR" ->v
  J v
"""
    with pytest.raises(AinlRuntimeError, match="denied"):
        _run(source, limits={"env_allowlist": ["COLOR"]}, denied_verbs=["core.ENV"])


def test_openrouter_completion_counts_toward_the_budget():
    class _Model(RuntimeAdapter):
        def __init__(self):
            self.calls = 0

        def call(self, target, args, context):
            self.calls += 1
            return {"status": "ok", "content": "yes", "usage": {"total_tokens": 1}}

    model = _Model()
    source = """
S app core noop
L1:
  Loop items it ->Lbody ->Lafter
Lbody:
  R openrouter.completion it ->hit
  J it
Lafter:
  J "done"
"""
    engine = RuntimeEngine.from_code(source, strict=False, trace=False)
    engine.adapters.register("openrouter", model)
    with pytest.raises(AinlRuntimeError, match="completion call cap") as raised:
        engine.run_label("1", {"items": ["x"] * 20})
    assert raised.value.code == "LLM_BUDGET"
    assert model.calls == 8


def test_hermes_operator_file_allows_a_loopback_literal():
    from runtime.adapters.a2a import _a2a_url_full_check

    _a2a_url_full_check(
        "http://127.0.0.1:8765/.well-known/agent.json",
        allow_hosts=set(),
        allow_insecure_local=False,
        strict_ssrf=True,
        public_only=True,
        allow_loopback=True,
    )
    with pytest.raises(AdapterError):
        _a2a_url_full_check(
            "http://169.254.169.254/latest/",
            allow_hosts=set(),
            allow_insecure_local=False,
            strict_ssrf=True,
            public_only=True,
            allow_loopback=True,
        )


def test_a2a_empty_allowlist_denies_and_redirects_stay_off():
    adapter = A2aAdapter()
    with pytest.raises(AdapterError, match="empty allowlist"):
        adapter._check_url("https://example.com/")
    opener = _opener_for(A2aAdapter(allow_hosts={"example.com"}, follow_redirects=False))
    redirectors = [handler for handler in opener.handlers if isinstance(handler, HTTPRedirectHandler)]
    assert redirectors
    assert redirectors[0].redirect_request(None, None, 302, "moved", {}, "https://example.com/") is None


def test_metadata_forms_stay_closed_when_private_is_allowed():
    for host in (
        "::ffff:169.254.169.254",
        "169.254.170.23",
        "168.63.129.16",
        "192.0.0.192",
    ):
        with pytest.raises(AddressRejected):
            approved_ips(host, allow_private=True)


def test_redirect_drops_cloud_credential_headers():
    kept = _headers_for_redirect(
        {
            "Authorization": "Bearer a",
            "X-Api-Key": "k",
            "X-Amz-Security-Token": "t",
            "Accept": "application/json",
        },
        "a.example",
        "b.example",
    )
    assert list(kept) == ["Accept"]


def test_caller_cannot_raise_the_server_completion_cap():
    server = {"allowed_adapters": None, "limits": {"max_completion_calls": 8}, "denied_verbs": []}
    caller = {"limits": {"max_completion_calls": 1000000}}
    assert merge_grants(server, caller)["limits"]["max_completion_calls"] == 8
