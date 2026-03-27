import os
import sys
import asyncio
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.supabase import SupabaseAdapter
from runtime.adapters.base import AdapterError


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.content = content
        self.text = str(self._payload)

    def json(self):
        return self._payload


class _FakeHttpClient:
    def request(self, method, url, params=None, json=None, headers=None):
        if "/auth/v1/token" in url:
            return _FakeResponse(200, {"access_token": "tok"})
        if "/auth/v1/user" in url:
            return _FakeResponse(200, {"id": "u1", "email": "a@x.dev"})
        if "/storage/v1/object/list/" in url:
            return _FakeResponse(200, [{"name": "a.txt"}])
        if "/storage/v1/object/" in url and method == "POST":
            return _FakeResponse(200, {"Key": "obj"})
        if "/storage/v1/object/" in url and method == "GET":
            return _FakeResponse(200, {"ok": True}, content=b"hello")
        return _FakeResponse(200, {"ok": True})

    def post(self, url, content=None, headers=None):
        return _FakeResponse(200, {"Key": "obj"})

    def get(self, url, headers=None):
        return _FakeResponse(200, {"ok": True}, content=b"hello")


class _FakePostgres:
    def call(self, target, args, context):
        t = str(target).lower()
        if t == "query":
            return [{"id": 1, "email": "a@x.dev"}]
        return {"rows_affected": 1, "lastrowid": 7}

    async def call_async(self, target, args, context):
        return self.call(target, args, context)


class _FakeWebSocket:
    def __init__(self, messages=None):
        self._messages = list(messages or [])
        self.sent = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if self._messages:
            return self._messages.pop(0)
        await asyncio.sleep(0.01)
        raise asyncio.TimeoutError()

    async def close(self):
        self.closed = True


def _patch_clients(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(Client=lambda **kwargs: _FakeHttpClient()))
    import adapters.supabase.adapter as mod

    monkeypatch.setattr(mod, "PostgresAdapter", lambda **kwargs: _FakePostgres())
    fake_ws = _FakeWebSocket(
        [
            '{"event":"postgres_changes","payload":{"data":{"type":"INSERT","schema":"public","table":"users","record":{"id":1}}}}'
        ]
    )
    async def _connect(*args, **kwargs):
        return fake_ws
    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=_connect))
    return fake_ws


def test_supabase_db_delegation_and_write_gate(monkeypatch):
    _patch_clients(monkeypatch)
    adp = SupabaseAdapter(db_url="postgresql://x", supabase_url="https://x.supabase.co", anon_key="k", allow_write=True, allow_tables=["users"])
    rows = adp.call("select", ["users", {"id": 1}], {})
    assert rows["data"][0]["email"] == "a@x.dev"
    out = adp.call("insert", ["users", {"email": "b@x.dev"}], {})
    assert out["data"]["rows_affected"] == 1
    ro = SupabaseAdapter(db_url="postgresql://x", supabase_url="https://x.supabase.co", anon_key="k", allow_write=False, allow_tables=["users"])
    try:
        ro.call("insert", ["users", {"email": "x"}], {})
        assert False, "expected write block"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allow_write" in str(e)


def test_supabase_auth_storage_realtime_contract(monkeypatch):
    _patch_clients(monkeypatch)
    adp = SupabaseAdapter(
        db_url="postgresql://x",
        supabase_url="https://x.supabase.co",
        anon_key="anon",
        service_role_key="svc",
        allow_write=True,
        allow_tables=["users"],
        allow_buckets=["docs"],
        allow_channels=["chan1"],
    )
    sign_in = adp.call("auth.sign_in_with_password", ["a@x.dev", "pw"], {})
    assert sign_in["ok"] is True
    user = adp.call("auth.get_user", ["tok"], {})
    assert user["ok"] is True
    up = adp.call("storage.upload", ["docs", "a.txt", "hello"], {})
    assert up["ok"] is True
    down = adp.call("storage.download", ["docs", "a.txt"], {})
    assert down["ok"] is True
    sub = adp.call("realtime.subscribe", ["chan1", "INSERT"], {})
    assert sub["ok"] is True
    unsub = adp.call("realtime.unsubscribe", ["chan1"], {})
    assert unsub["ok"] is True


def test_supabase_realtime_async_subscribe_and_broadcast(monkeypatch):
    fake_ws = _patch_clients(monkeypatch)
    adp = SupabaseAdapter(
        db_url="postgresql://x",
        supabase_url="https://x.supabase.co",
        service_role_key="svc",
        allow_write=True,
        allow_tables=["users"],
        allow_channels=["chan1"],
    )
    sub = asyncio.run(adp.call_async("realtime.subscribe", ["chan1", "users", ["INSERT"], None, 0.05, 5], {}))
    assert sub["ok"] is True
    assert sub["result"]["events"]
    evt = sub["result"]["events"][0]
    assert evt["event"] == "INSERT"
    assert evt["table"] == "users"
    assert "sequence" in evt
    assert "timestamp" in evt
    replay = asyncio.run(adp.call_async("realtime.replay", ["chan1", "earliest", 10, 0.01], {}))
    assert replay["ok"] is True
    assert isinstance(replay["result"]["events"], list)
    ack = asyncio.run(adp.call_async("realtime.ack", ["chan1", "cursor-1", "g1", "c1"], {}))
    assert ack["ok"] is True
    cur = asyncio.run(adp.call_async("realtime.get_cursor", ["chan1", "g1", "c1"], {}))
    assert cur["result"]["cursor"]["cursor"] == "cursor-1"
    sub2 = asyncio.run(adp.call_async("realtime.subscribe", ["chan1", "users", ["INSERT"], None, 0.01, 1, "earliest", "g1", "c2"], {}))
    assert sub2["ok"] is True
    assert sub2["result"]["fanout_group"] == "g1"
    assert sub2["result"]["consumer"] == "c2"
    b = asyncio.run(adp.call_async("realtime.broadcast", ["chan1", "ping", {"x": 1}], {}))
    assert b["ok"] is True
    assert any("broadcast" in s for s in fake_ws.sent)
    u = asyncio.run(adp.call_async("realtime.unsubscribe", ["chan1", "g1", "c2"], {}))
    assert u["ok"] is True
