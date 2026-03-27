import os
import sys
import uuid
import asyncio

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.airtable import AirtableAdapter
from runtime.adapters.base import AdapterError


pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return str(os.environ.get("AINL_TEST_USE_AIRTABLE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _require_env(pytestconfig):
    if not _enabled():
        pytest.skip("AINL_TEST_USE_AIRTABLE is not enabled")
    try:
        import httpx  # noqa: F401
    except Exception:
        pytest.skip("httpx is not installed; install with `pip install -e \".[airtable,dev]\"`")
    api_key = str(pytestconfig.getoption("--airtable-api-key") or os.environ.get("AINL_AIRTABLE_API_KEY") or "").strip()
    base_id = str(pytestconfig.getoption("--airtable-base-id") or os.environ.get("AINL_AIRTABLE_BASE_ID") or "").strip()
    table = str(os.environ.get("AINL_AIRTABLE_TEST_TABLE") or "").strip()
    if not api_key or not base_id or not table:
        pytest.skip("Airtable integration requires API key, base id, and AINL_AIRTABLE_TEST_TABLE")
    return api_key, base_id, table


def test_airtable_integration_list_find_create_update_delete(pytestconfig):
    api_key, base_id, table = _require_env(pytestconfig)
    adp = AirtableAdapter(api_key=api_key, base_id=base_id, allow_write=True, allow_tables=[table])

    token = f"ainl_it_{uuid.uuid4().hex[:10]}"
    created = adp.call("create", [table, {"Name": token}], {})
    assert created.get("id")
    rid = created["id"]
    try:
        listed = adp.call("list", [table, {"maxRecords": 5, "pageSize": 5}], {})
        assert isinstance(listed.get("records"), list)

        found = adp.call("find", [table, {"field": "Name", "value": token}], {})
        assert any((r.get("id") == rid) for r in (found.get("records") or []))

        updated = adp.call("update", [table, {"id": rid, "fields": {"Name": token, "Status": "updated"}}], {})
        assert updated.get("id") == rid
    finally:
        adp.call("delete", [table, rid], {})


def test_airtable_integration_write_gate_and_allowlist(pytestconfig):
    api_key, base_id, table = _require_env(pytestconfig)
    ro = AirtableAdapter(api_key=api_key, base_id=base_id, allow_write=False, allow_tables=[table])
    with pytest.raises(AdapterError):
        ro.call("create", [table, {"Name": "blocked"}], {})
    scoped = AirtableAdapter(api_key=api_key, base_id=base_id, allow_write=True, allow_tables=[table])
    with pytest.raises(AdapterError):
        scoped.call("list", ["other_table"], {})


def test_airtable_integration_attachment_and_webhook_smoke(pytestconfig):
    api_key, base_id, table = _require_env(pytestconfig)
    hook_url = str(os.environ.get("AINL_AIRTABLE_WEBHOOK_URL") or "").strip()
    if not hook_url:
        pytest.skip("AINL_AIRTABLE_WEBHOOK_URL is not set")
    adp = AirtableAdapter(api_key=api_key, base_id=base_id, allow_write=True, allow_tables=[table])
    created = adp.call("create", [table, {"Name": f"ainl_att_{uuid.uuid4().hex[:8]}"}], {})
    rid = created.get("id")
    if not rid:
        pytest.skip("unable to create Airtable record for attachment smoke")
    try:
        up = adp.call("attachment.upload", [table, rid, "Attachments", b"hello", "hello.txt"], {})
        assert isinstance(up, dict)
        wh = adp.call("webhook.create", [table, table, ["create", "update"], hook_url], {})
        wid = str(wh.get("webhook_id") or "")
        assert wid
        adp.call("webhook.delete", [table, wid], {})
    finally:
        adp.call("delete", [table, rid], {})


def test_airtable_integration_async_webhook_smoke(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    api_key, base_id, table = _require_env(pytestconfig)
    hook_url = str(os.environ.get("AINL_AIRTABLE_WEBHOOK_URL") or "").strip()
    if not hook_url:
        pytest.skip("AINL_AIRTABLE_WEBHOOK_URL is not set")
    adp = AirtableAdapter(api_key=api_key, base_id=base_id, allow_write=True, allow_tables=[table])
    wh = asyncio.run(adp.call_async("webhook.create", [table, table, ["create"], hook_url], {}))
    wid = str(wh.get("webhook_id") or "")
    if not wid:
        pytest.skip("webhook create did not return an id")
    out = asyncio.run(adp.call_async("webhook.delete", [table, wid], {}))
    assert out["deleted"] is True
