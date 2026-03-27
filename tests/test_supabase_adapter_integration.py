import os
import asyncio
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.supabase import SupabaseAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine
from runtime.adapters.base import AdapterError


pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return str(os.environ.get("AINL_TEST_USE_DOCKER_SUPABASE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _require_env(pytestconfig):
    if not _enabled():
        pytest.skip("AINL_TEST_USE_DOCKER_SUPABASE is not enabled")
    db_url = str(os.environ.get("AINL_SUPABASE_DB_URL") or os.environ.get("AINL_POSTGRES_URL") or "").strip()
    if not db_url:
        pytest.skip("Supabase integration requires AINL_SUPABASE_DB_URL or AINL_POSTGRES_URL")
    supabase_url = str(pytestconfig.getoption("--supabase-url") or os.environ.get("AINL_SUPABASE_URL") or "").strip()
    service_role = str(pytestconfig.getoption("--supabase-service-role-key") or os.environ.get("AINL_SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return db_url, supabase_url, service_role


def test_supabase_integration_db_passthrough(pytestconfig):
    db_url, supabase_url, service_role = _require_env(pytestconfig)
    table = f"ainl_sb_it_{uuid.uuid4().hex[:8]}"
    adp = SupabaseAdapter(db_url=db_url, supabase_url=supabase_url, service_role_key=service_role, allow_write=True, allow_tables=[table])
    admin = SupabaseAdapter(db_url=db_url, allow_write=True)
    admin._require_postgres().call("execute", [f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"], {})
    try:
        ins = adp.call("insert", [table, {"id": 1, "name": "alice"}], {})
        assert ins["data"]["rows_affected"] == 1
        rows = adp.call("select", [table, {"id": 1}], {})
        assert rows["data"] and rows["data"][0]["name"] == "alice"
    finally:
        admin._require_postgres().call("execute", [f"DROP TABLE IF EXISTS {table}"], {})


def test_supabase_integration_allowlists_and_write_gate(pytestconfig):
    db_url, supabase_url, service_role = _require_env(pytestconfig)
    adp = SupabaseAdapter(
        db_url=db_url,
        supabase_url=supabase_url,
        service_role_key=service_role,
        allow_write=False,
        allow_tables=["allowed_table"],
        allow_buckets=["bkt"],
        allow_channels=["chan"],
    )
    with pytest.raises(AdapterError):
        adp.call("insert", ["allowed_table", {"id": 1}], {})
    with pytest.raises(AdapterError):
        adp.call("select", ["blocked_table"], {})
    with pytest.raises(AdapterError):
        adp.call("storage.list", ["blocked_bucket"], {})
    with pytest.raises(AdapterError):
        adp.call("realtime.subscribe", ["blocked_channel"], {})


def test_supabase_integration_async_call_path(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    db_url, supabase_url, service_role = _require_env(pytestconfig)
    table = f"ainl_sb_it_{uuid.uuid4().hex[:8]}"
    adp = SupabaseAdapter(db_url=db_url, supabase_url=supabase_url, service_role_key=service_role, allow_write=True, allow_tables=[table])
    admin = SupabaseAdapter(db_url=db_url, allow_write=True)
    admin._require_postgres().call("execute", [f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"], {})
    try:
        ins = asyncio.run(adp.call_async("insert", [table, {"id": 2, "name": "async-alice"}], {}))
        assert ins["data"]["rows_affected"] == 1
        rows = asyncio.run(adp.call_async("select", [table, {"id": 2}], {}))
        assert rows["data"] and rows["data"][0]["name"] == "async-alice"
    finally:
        admin._require_postgres().call("execute", [f"DROP TABLE IF EXISTS {table}"], {})


def test_supabase_integration_native_async_engine(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    db_url, supabase_url, service_role = _require_env(pytestconfig)
    table = f"ainl_sb_it_{uuid.uuid4().hex[:8]}"
    adp = SupabaseAdapter(db_url=db_url, supabase_url=supabase_url, service_role_key=service_role, allow_write=True, allow_tables=[table])
    admin = SupabaseAdapter(db_url=db_url, allow_write=True)
    admin._require_postgres().call("execute", [f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"], {})
    try:
        reg = AdapterRegistry(allowed=["core", "supabase"])
        reg.register("supabase", adp)
        code = f'L1: R supabase.insert "{table}" {{"id":3,"name":"native"}} ->ins\nL2: R supabase.select "{table}" {{"id":3}} ->rows\nL3: J rows\n'
        eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=True)
        rows = asyncio.run(eng.run_label_async("1", frame={}))
        assert rows["data"] and rows["data"][0]["name"] == "native"
    finally:
        admin._require_postgres().call("execute", [f"DROP TABLE IF EXISTS {table}"], {})


def test_supabase_integration_realtime_smoke(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    use_rt = str(os.environ.get("AINL_TEST_USE_SUPABASE_REALTIME") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async or not use_rt:
        pytest.skip("Supabase realtime integration requires AINL_RUNTIME_ASYNC=1 and AINL_TEST_USE_SUPABASE_REALTIME=1")
    db_url, supabase_url, service_role = _require_env(pytestconfig)
    channel = str(os.environ.get("AINL_SUPABASE_REALTIME_CHANNEL") or "ainl-it").strip()
    adp = SupabaseAdapter(
        db_url=db_url,
        supabase_url=supabase_url,
        service_role_key=service_role,
        allow_write=True,
        allow_channels=[channel],
    )
    try:
        sub = asyncio.run(adp.call_async("realtime.subscribe", [channel, None, ["*"], None, 0.2, 2], {}))
        assert sub["ok"] is True
        rep = asyncio.run(adp.call_async("realtime.replay", [channel, "latest", 5, 0.01], {}))
        assert rep["ok"] is True
        ack = asyncio.run(adp.call_async("realtime.ack", [channel, "cursor-it", "group-it", "consumer-it"], {}))
        assert ack["ok"] is True
        cur = asyncio.run(adp.call_async("realtime.get_cursor", [channel, "group-it", "consumer-it"], {}))
        assert cur["ok"] is True
        b = asyncio.run(adp.call_async("realtime.broadcast", [channel, "ping", {"test": True}], {}))
        assert b["ok"] is True
    finally:
        asyncio.run(adp.call_async("realtime.unsubscribe", [channel], {}))
