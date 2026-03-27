import os
import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib import request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.dynamodb import DynamoDBAdapter
from runtime.adapters.base import AdapterError


pytestmark = pytest.mark.integration

_DEFAULT_DDB_URL = "http://127.0.0.1:8000"
_DEFAULT_REGION = "us-east-1"


def _integration_url(pytestconfig) -> str:
    cli = str(pytestconfig.getoption("--dynamodb-url") or "").strip()
    if cli:
        return cli
    return str(os.environ.get("AINL_DYNAMODB_URL") or "").strip()


def _require_integration_url(pytestconfig) -> str:
    try:
        import boto3  # noqa: F401
    except Exception:
        pytest.skip("boto3 is not installed; install with `pip install -e \".[dynamodb,dev]\"`")
    url = _integration_url(pytestconfig)
    if not url:
        pytest.skip("AINL_DYNAMODB_URL is not set; skipping dynamodb integration tests")
    return url


def _tbl(prefix: str = "ainl_ddb_it") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _mk_table(adapter: DynamoDBAdapter, table: str) -> None:
    c = adapter._require_client()
    c.create_table(
        TableName=table,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    for _ in range(30):
        try:
            s = c.describe_table(TableName=table).get("Table", {}).get("TableStatus")
            if s == "ACTIVE":
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("table did not become ACTIVE")


@pytest.fixture(scope="session", autouse=True)
def maybe_docker_dynamodb(pytestconfig):
    use_docker = str(os.environ.get("AINL_TEST_USE_DOCKER_DYNAMODB") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_docker:
        yield
        return
    compose_file = Path(__file__).resolve().parent / "fixtures" / "docker-compose.dynamodb.yml"
    if not compose_file.exists():
        pytest.skip(f"docker dynamodb fixture missing: {compose_file}")
    try:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d", "dynamodb"], check=True, capture_output=True, text=True)
    except Exception as e:
        pytest.skip(f"docker compose unavailable or failed: {e}")
    try:
        ready = False
        for _ in range(30):
            try:
                with request.urlopen("http://127.0.0.1:8000/shell/", timeout=1.0) as resp:
                    if int(getattr(resp, "status", 0)) in {200, 301, 302}:
                        ready = True
                        break
            except Exception:
                pass
            time.sleep(1.0)
        if not ready:
            pytest.skip("docker dynamodb fixture did not become healthy in time")
        os.environ.setdefault("AINL_DYNAMODB_URL", _DEFAULT_DDB_URL)
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "dummy")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
        os.environ.setdefault("AWS_DEFAULT_REGION", _DEFAULT_REGION)
        yield
    finally:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "down", "-v"], capture_output=True, text=True)


def test_dynamodb_integration_single_item_and_query(pytestconfig):
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    admin = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True)
    _mk_table(admin, table)
    adp = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True, allow_tables=[table])
    adp.call("put", [table, {"pk": "u#1", "sk": "profile", "name": "alice", "age": 30}], {})
    got = adp.call("get", [table, {"pk": "u#1", "sk": "profile"}], {})
    assert got["item"] and got["item"]["name"] == "alice"
    qry = adp.call("query", [table, "pk = :pk", {":pk": "u#1"}], {})
    assert qry["count"] >= 1


def test_dynamodb_integration_update_delete_and_write_block(pytestconfig):
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    admin = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True)
    _mk_table(admin, table)
    adp = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True, allow_tables=[table])
    adp.call("put", [table, {"pk": "u#2", "sk": "profile", "name": "bob"}], {})
    upd = adp.call("update", [table, {"pk": "u#2", "sk": "profile"}, "SET #n = :v", {":v": "bobby"}, {"#n": "name"}], {})
    assert upd["attributes"] and upd["attributes"]["name"] == "bobby"
    adp.call("delete", [table, {"pk": "u#2", "sk": "profile"}], {})
    ro = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=False, allow_tables=[table])
    with pytest.raises(AdapterError):
        ro.call("put", [table, {"pk": "x", "sk": "y"}], {})


def test_dynamodb_integration_batch_and_transact(pytestconfig):
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    admin = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True)
    _mk_table(admin, table)
    adp = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True, allow_tables=[table])
    adp.call(
        "batch_write",
        [{table: [{"put_request": {"item": {"pk": "u#10", "sk": "profile", "name": "x"}}}, {"put_request": {"item": {"pk": "u#11", "sk": "profile", "name": "y"}}}]}],
        {},
    )
    bg = adp.call("batch_get", [{table: {"keys": [{"pk": "u#10", "sk": "profile"}, {"pk": "u#11", "sk": "profile"}]}}], {})
    assert len(bg["responses"].get(table, [])) >= 2
    tw = adp.call("transact_write", [[{"action": "put", "table": table, "item": {"pk": "u#20", "sk": "profile", "name": "z"}}]], {})
    assert tw["ok"] is True
    tg = adp.call("transact_get", [[{"table": table, "key": {"pk": "u#20", "sk": "profile"}}]], {})
    assert tg["ok"] is True and tg["results"][0]["item"]["name"] == "z"


def test_dynamodb_integration_streams_async_smoke(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    url = _require_integration_url(pytestconfig)
    table = _tbl()
    admin = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True)
    _mk_table(admin, table)
    c = admin._require_client()
    try:
        c.update_table(
            TableName=table,
            StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"},
        )
    except Exception:
        pytest.skip("dynamodb local endpoint does not support streams update_table in this environment")
    adp = DynamoDBAdapter(url=url, region=_DEFAULT_REGION, allow_write=True, allow_tables=[table])
    asyncio.run(adp.call_async("streams.subscribe", [table, "LATEST", None, 0.2, 10], {}))
    adp.call("put", [table, {"pk": "u#s", "sk": "profile", "name": "streamed"}], {})
    out = asyncio.run(adp.call_async("streams.subscribe", [table, "LATEST", None, 1.0, 20], {}))
    if not isinstance(out.get("events"), list):
        pytest.skip("streams response shape unavailable on this endpoint")
    assert any(str(e.get("eventName")) in {"INSERT", "MODIFY", "REMOVE"} for e in out["events"])
    rem = asyncio.run(adp.call_async("streams.unsubscribe", [table], {}))
    assert rem["table"] == table
