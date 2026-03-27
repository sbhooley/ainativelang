import os
import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.mysql import MySQLAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine
from runtime.adapters.base import AdapterError


pytestmark = pytest.mark.integration

_DEFAULT_DOCKER_URL = "mysql://ainl:ainl_test_pw_change_me@127.0.0.1:3306/ainl_test"


def _integration_url(pytestconfig) -> str:
    cli = str(pytestconfig.getoption("--mysql-url") or "").strip()
    if cli:
        return cli
    return str(os.environ.get("AINL_MYSQL_URL") or "").strip()


def _require_integration_url(pytestconfig) -> str:
    try:
        import pymysql  # noqa: F401
    except Exception:
        pytest.skip("pymysql is not installed; install with `pip install -e \".[mysql,dev]\"`")
    url = _integration_url(pytestconfig)
    if not url:
        pytest.skip("AINL_MYSQL_URL is not set; skipping mysql integration tests")
    return url


def _tbl(prefix: str = "ainl_my_it") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="session", autouse=True)
def maybe_docker_mysql(pytestconfig):
    """
    Optional turnkey docker fixture.
    Enable with AINL_TEST_USE_DOCKER_MYSQL=1.
    """
    use_docker = str(os.environ.get("AINL_TEST_USE_DOCKER_MYSQL") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_docker:
        return
    compose_file = Path(__file__).resolve().parent / "fixtures" / "docker-compose.mysql.yml"
    if not compose_file.exists():
        pytest.skip(f"docker mysql fixture missing: {compose_file}")
    try:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d", "mysql"], check=True, capture_output=True, text=True)
    except Exception as e:
        pytest.skip(f"docker compose unavailable or failed: {e}")
    try:
        ready = False
        for _ in range(40):
            probe = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "exec", "-T", "mysql", "mysqladmin", "ping", "-h", "localhost", "-uainl", "-painl_test_pw_change_me", "--silent"],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(1.0)
        if not ready:
            pytest.skip("docker mysql fixture did not become healthy in time")
        init = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "run", "--rm", "mysql_init"],
            capture_output=True,
            text=True,
        )
        if init.returncode != 0:
            pytest.skip(f"docker mysql init failed: {init.stderr.strip() or init.stdout.strip()}")
        os.environ.setdefault("AINL_MYSQL_URL", _DEFAULT_DOCKER_URL)
        yield
    finally:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "down", "-v"], capture_output=True, text=True)


def test_mysql_integration_query_execute_and_write_controls(pytestconfig):
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    adp_rw = MySQLAdapter(dsn=url, allow_write=True, allow_tables=[table])
    adp_ro = MySQLAdapter(dsn=url, allow_write=False, allow_tables=[table])
    adp_rw.call("execute", [f"CREATE TABLE {table} (id BIGINT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(64) NOT NULL)"], {})
    try:
        created = adp_rw.call("execute", [f"INSERT INTO {table}(name) VALUES (%s)", ["alice"]], {})
        assert int(created["rows_affected"]) == 1
        rows = adp_rw.call("query", [f"SELECT id, name FROM {table} ORDER BY id"], {})
        assert rows and rows[0]["name"] == "alice"
        with pytest.raises(AdapterError):
            adp_ro.call("execute", [f"UPDATE {table} SET name = %s WHERE id = %s", ["bob", rows[0]["id"]]], {})
    finally:
        adp_rw.call("execute", [f"DROP TABLE IF EXISTS {table}"], {})


def test_mysql_integration_transaction_commit_and_rollback(pytestconfig):
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    adp = MySQLAdapter(dsn=url, allow_write=True, allow_tables=[table])
    adp.call("execute", [f"CREATE TABLE {table} (id BIGINT PRIMARY KEY, name VARCHAR(64) NOT NULL)"], {})
    try:
        txn_ok = [
            {"verb": "execute", "sql": f"INSERT INTO {table}(id, name) VALUES (%s, %s)", "params": [1, "ok"]},
            {"verb": "query", "sql": f"SELECT id, name FROM {table} WHERE id = %s", "params": [1]},
        ]
        out = adp.call("transaction", [txn_ok], {})
        assert out["ok"] is True
        assert out["results"][1][0]["name"] == "ok"

        txn_fail = [
            {"verb": "execute", "sql": f"INSERT INTO {table}(id, name) VALUES (%s, %s)", "params": [2, "x"]},
            {"verb": "execute", "sql": f"INSERT INTO {table}(id, name) VALUES (%s, %s)", "params": [1, "dup"]},
        ]
        with pytest.raises(AdapterError):
            adp.call("transaction", [txn_fail], {})

        rows = adp.call("query", [f"SELECT id FROM {table} WHERE id = %s", [2]], {})
        assert rows == []
    finally:
        adp.call("execute", [f"DROP TABLE IF EXISTS {table}"], {})


def test_mysql_integration_table_allowlist_is_enforced(pytestconfig):
    url = _require_integration_url(pytestconfig)
    allowed = _tbl("ainl_my_allowed")
    blocked = _tbl("ainl_my_blocked")
    adp_admin = MySQLAdapter(dsn=url, allow_write=True)
    adp = MySQLAdapter(dsn=url, allow_write=True, allow_tables=[allowed])
    adp_admin.call("execute", [f"CREATE TABLE {allowed} (id BIGINT)"], {})
    adp_admin.call("execute", [f"CREATE TABLE {blocked} (id BIGINT)"], {})
    try:
        adp.call("query", [f"SELECT id FROM {allowed}"], {})
        with pytest.raises(AdapterError):
            adp.call("query", [f"SELECT id FROM {blocked}"], {})
    finally:
        adp_admin.call("execute", [f"DROP TABLE IF EXISTS {allowed}"], {})
        adp_admin.call("execute", [f"DROP TABLE IF EXISTS {blocked}"], {})


def test_mysql_integration_fixture_seed_table_roundtrip(pytestconfig):
    url = _require_integration_url(pytestconfig)
    adp = MySQLAdapter(dsn=url, allow_write=True, allow_tables=["events"])
    ext_id = f"evt_{uuid.uuid4().hex[:10]}"
    inserted = adp.call(
        "execute",
        ["INSERT INTO events(external_id, status, amount_cents) VALUES (%s, %s, %s)", [ext_id, "new", 1234]],
        {},
    )
    assert int(inserted["rows_affected"]) == 1
    rows = adp.call("query", ["SELECT external_id, status, amount_cents FROM events WHERE external_id = %s", [ext_id]], {})
    assert rows and rows[0]["external_id"] == ext_id and int(rows[0]["amount_cents"]) == 1234


def test_mysql_integration_async_call_path(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    url = _require_integration_url(pytestconfig)
    adp = MySQLAdapter(dsn=url, allow_write=False)
    rows = asyncio.run(adp.call_async("query", ["SELECT 1 AS n"], {}))
    assert rows and int(rows[0]["n"]) == 1


def test_mysql_integration_native_async_engine(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    url = _require_integration_url(pytestconfig)
    reg = AdapterRegistry(allowed=["core", "mysql"])
    reg.register("mysql", MySQLAdapter(dsn=url, allow_write=False))
    code = 'L1: R mysql.query "SELECT 1 AS n" ->rows J rows\n'
    eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=True)
    rows = asyncio.run(eng.run_label_async("1", frame={}))
    assert rows and int(rows[0]["n"]) == 1
