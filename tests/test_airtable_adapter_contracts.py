import os
import sys
import asyncio
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.airtable import AirtableAdapter
from runtime.adapters.base import AdapterError


class _FakeResponse:
    def __init__(self, status_code, payload, content=None):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)
        self.content = content if content is not None else (str(payload).encode("utf-8") if payload is not None else b"")

    def json(self):
        return self._payload


class _FakeHttpxClient:
    def __init__(self, **kwargs):
        self.records = {}
        self.seq = 0

    def request(self, method, url, params=None, json=None, content=None):
        if url.startswith("https://files.example.com/"):
            return _FakeResponse(200, {"ok": True}, content=b"file-bytes")
        if "/webhooks" in url:
            if method == "POST":
                return _FakeResponse(
                    200,
                    {
                        "id": "wh_1",
                        "expirationTime": "2026-04-01T00:00:00.000Z",
                        "macSecretBase64": "abc",
                        "specification": (json or {}).get("specification", {}),
                    },
                )
            if method == "GET":
                return _FakeResponse(200, {"webhooks": [{"id": "wh_1"}]})
            if method == "DELETE":
                return _FakeResponse(200, {"id": "wh_1", "deleted": True})
        if "/meta/bases" in url:
            if url.endswith("/tables"):
                return _FakeResponse(200, {"tables": [{"id": "tbl1", "name": "users"}]})
            return _FakeResponse(200, {"bases": [{"id": "app1"}]})
        if "/v0/" in url:
            if url.endswith("/uploadAttachment") and method == "POST":
                return _FakeResponse(200, {"id": "att1", "url": "https://files.example.com/a.bin", "filename": (json or {}).get("filename")})
            if method == "GET":
                recs = list(self.records.values())
                return _FakeResponse(200, {"records": recs})
            if method == "POST":
                if isinstance(json, dict) and "records" in json:
                    out = []
                    for r in json["records"]:
                        self.seq += 1
                        rid = f"rec{self.seq}"
                        rec = {"id": rid, "fields": r.get("fields", {}), "createdTime": "t"}
                        self.records[rid] = rec
                        out.append(rec)
                    return _FakeResponse(200, {"records": out})
                self.seq += 1
                rid = f"rec{self.seq}"
                rec = {"id": rid, "fields": (json or {}).get("fields", {}), "createdTime": "t"}
                self.records[rid] = rec
                return _FakeResponse(200, rec)
            if method == "PATCH":
                if isinstance(json, dict) and "records" in json:
                    out = []
                    for r in json["records"]:
                        rid = r["id"]
                        self.records[rid] = {"id": rid, "fields": r.get("fields", {}), "createdTime": "t"}
                        out.append(self.records[rid])
                    return _FakeResponse(200, {"records": out})
                rid = url.rsplit("/", 1)[-1]
                self.records[rid] = {"id": rid, "fields": (json or {}).get("fields", {}), "createdTime": "t"}
                return _FakeResponse(200, self.records[rid])
            if method == "DELETE":
                rid = url.rsplit("/", 1)[-1]
                if "records[]" in url:
                    return _FakeResponse(200, {"records": []})
                self.records.pop(rid, None)
                return _FakeResponse(200, {"id": rid, "deleted": True})
        return _FakeResponse(404, {"error": "not found"})


class _FakeHttpxAsyncClient(_FakeHttpxClient):
    async def request(self, method, url, params=None, json=None, content=None):
        return super().request(method, url, params=params, json=json, content=content)


def _install_fake_httpx(monkeypatch):
    fake_module = SimpleNamespace(
        Client=lambda **kwargs: _FakeHttpxClient(**kwargs),
        AsyncClient=lambda **kwargs: _FakeHttpxAsyncClient(**kwargs),
    )
    monkeypatch.setitem(sys.modules, "httpx", fake_module)


def test_airtable_read_write_contract(monkeypatch):
    _install_fake_httpx(monkeypatch)
    adp = AirtableAdapter(api_key="k", base_id="app1", allow_write=True, allow_tables=["users"])
    created = adp.call("create", ["users", {"name": "alice"}], {})
    assert created["id"]
    listed = adp.call("list", ["users"], {})
    assert isinstance(listed["records"], list)
    found = adp.call("find", ["users", {"field": "name", "value": "alice"}], {})
    assert isinstance(found["records"], list)
    upd = adp.call("update", ["users", {"id": created["id"], "fields": {"name": "bob"}}], {})
    assert upd["fields"]["name"] == "bob"
    deleted = adp.call("delete", ["users", created["id"]], {})
    assert deleted["deleted"] is True


def test_airtable_write_gate(monkeypatch):
    _install_fake_httpx(monkeypatch)
    adp = AirtableAdapter(api_key="k", base_id="app1", allow_write=False, allow_tables=["users"])
    try:
        adp.call("create", ["users", {"name": "x"}], {})
        assert False, "expected write gate"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allow_write" in str(e)


def test_airtable_allowlist(monkeypatch):
    _install_fake_httpx(monkeypatch)
    adp = AirtableAdapter(api_key="k", base_id="app1", allow_write=True, allow_tables=["users"])
    try:
        adp.call("list", ["other"], {})
        assert False, "expected allowlist block"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allowlist" in str(e)


def test_airtable_attachment_and_webhook_contract(monkeypatch):
    _install_fake_httpx(monkeypatch)
    adp = AirtableAdapter(
        api_key="k",
        base_id="app1",
        allow_write=True,
        allow_tables=["users"],
        allow_attachment_hosts=["files.example.com"],
    )
    up = adp.call("attachment.upload", ["users", "rec1", "Files", b"abc", "a.bin"], {})
    assert up["ok"] is True
    dl = adp.call("attachment.download", ["users", "https://files.example.com/a.bin"], {})
    assert isinstance(dl["bytes_b64"], str)
    wh = adp.call("webhook.create", ["users", "users", ["create", "update"], "https://hooks.example.com/airtable"], {})
    assert wh["webhook_id"] == "wh_1"
    listed = adp.call("webhook.list", ["users"], {})
    assert listed["webhooks"][0]["id"] == "wh_1"
    deleted = adp.call("webhook.delete", ["users", "wh_1"], {})
    assert deleted["deleted"] is True


def test_airtable_async_attachment_and_webhook_contract(monkeypatch):
    _install_fake_httpx(monkeypatch)
    adp = AirtableAdapter(api_key="k", base_id="app1", allow_write=True, allow_tables=["users"], allow_attachment_hosts=["files.example.com"])
    up = asyncio.run(adp.call_async("attachment.upload", ["users", "rec1", "Files", b"abc", "a.bin"], {}))
    assert up["ok"] is True
    wh = asyncio.run(adp.call_async("webhook.create", ["users", "users", ["create"], "https://hooks.example.com/airtable"], {}))
    assert wh["webhook_id"] == "wh_1"
