import os
import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.redis import RedisAdapter
from runtime.adapters.base import AdapterRegistry
from runtime.engine import RuntimeEngine
from runtime.adapters.base import AdapterError


pytestmark = pytest.mark.integration

_DEFAULT_DOCKER_URL = "redis://127.0.0.1:6379/0"


def _integration_url(pytestconfig) -> str:
    cli = str(pytestconfig.getoption("--redis-url") or "").strip()
    if cli:
        return cli
    return str(os.environ.get("AINL_REDIS_URL") or "").strip()


def _require_integration_url(pytestconfig) -> str:
    try:
        import redis  # noqa: F401
    except Exception:
        pytest.skip("redis-py is not installed; install with `pip install -e \".[redis,dev]\"`")
    url = _integration_url(pytestconfig)
    if not url:
        pytest.skip("AINL_REDIS_URL is not set; skipping redis integration tests")
    return url


def _k(prefix: str = "ainl_redis_it") -> str:
    return f"{prefix}:{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="session", autouse=True)
def maybe_docker_redis(pytestconfig):
    use_docker = str(os.environ.get("AINL_TEST_USE_DOCKER_REDIS") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_docker:
        yield
        return
    compose_file = Path(__file__).resolve().parent / "fixtures" / "docker-compose.redis.yml"
    if not compose_file.exists():
        pytest.skip(f"docker redis fixture missing: {compose_file}")
    try:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d", "redis"], check=True, capture_output=True, text=True)
    except Exception as e:
        pytest.skip(f"docker compose unavailable or failed: {e}")
    try:
        ready = False
        for _ in range(30):
            probe = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "exec", "-T", "redis", "redis-cli", "ping"],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0 and "PONG" in (probe.stdout or ""):
                ready = True
                break
            time.sleep(1.0)
        if not ready:
            pytest.skip("docker redis fixture did not become healthy in time")
        os.environ.setdefault("AINL_REDIS_URL", _DEFAULT_DOCKER_URL)
        yield
    finally:
        subprocess.run(["docker", "compose", "-f", str(compose_file), "down", "-v"], capture_output=True, text=True)


def test_redis_integration_kv_hash_list(pytestconfig):
    url = _require_integration_url(pytestconfig)
    base = _k()
    adp = RedisAdapter(url=url, allow_write=True, allow_prefixes=[base])
    assert adp.call("set", [f"{base}:k", "v"], {})["ok"] is True
    assert adp.call("get", [f"{base}:k"], {}) == "v"
    assert adp.call("hset", [f"{base}:h", "f1", "x"], {})["updated"] >= 0
    assert adp.call("hget", [f"{base}:h", "f1"], {}) == "x"
    assert adp.call("rpush", [f"{base}:q", "a"], {}) >= 1
    assert adp.call("llen", [f"{base}:q"], {}) >= 1
    assert adp.call("lpop", [f"{base}:q"], {}) == "a"


def test_redis_integration_write_block_and_prefix_guard(pytestconfig):
    url = _require_integration_url(pytestconfig)
    base = _k()
    adp_ro = RedisAdapter(url=url, allow_write=False, allow_prefixes=[base])
    with pytest.raises(AdapterError):
        adp_ro.call("set", [f"{base}:k", "v"], {})
    adp_rw = RedisAdapter(url=url, allow_write=True, allow_prefixes=[base])
    with pytest.raises(AdapterError):
        adp_rw.call("set", ["other:key", "v"], {})


def test_redis_integration_transaction_and_health(pytestconfig):
    url = _require_integration_url(pytestconfig)
    base = _k()
    adp = RedisAdapter(url=url, allow_write=True, allow_prefixes=[base])
    out = adp.call(
        "transaction",
        [[{"verb": "set", "args": [f"{base}:k", "v"]}, {"verb": "get", "args": [f"{base}:k"]}]],
        {},
    )
    assert out["ok"] is True
    assert adp.call("ping", [], {}) in (True, "PONG")
    info = adp.call("info", [], {})
    assert isinstance(info, dict)


def test_redis_integration_async_call_path(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    url = _require_integration_url(pytestconfig)
    base = _k()
    adp = RedisAdapter(url=url, allow_write=True, allow_prefixes=[base])
    set_out = asyncio.run(adp.call_async("set", [f"{base}:k", "v"], {}))
    assert set_out["ok"] is True
    val = asyncio.run(adp.call_async("get", [f"{base}:k"], {}))
    assert val == "v"
    assert asyncio.run(adp.call_async("hset", [f"{base}:h", "f1", "x"], {}))["updated"] >= 0
    assert asyncio.run(adp.call_async("hget", [f"{base}:h", "f1"], {})) == "x"
    assert asyncio.run(adp.call_async("rpush", [f"{base}:q", "a"], {})) >= 1
    assert asyncio.run(adp.call_async("lpop", [f"{base}:q"], {})) == "a"
    sub = asyncio.run(adp.call_async("subscribe", [f"{base}:c", 0.3, 5], {}))
    asyncio.run(adp.call_async("publish", [f"{base}:c", "m1"], {}))
    sub2 = asyncio.run(adp.call_async("subscribe", [f"{base}:c", 0.5, 10], {}))
    assert isinstance(sub["messages"], list)
    assert "m1" in sub2["messages"]
    tx = asyncio.run(
        adp.call_async(
            "transaction",
            [[{"verb": "set", "args": [f"{base}:t", "1"]}, {"verb": "get", "args": [f"{base}:t"]}]],
            {},
        )
    )
    assert tx["ok"] is True


def test_redis_integration_native_async_engine(pytestconfig):
    use_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_async:
        pytest.skip("AINL_RUNTIME_ASYNC is not enabled")
    url = _require_integration_url(pytestconfig)
    base = _k()
    reg = AdapterRegistry(allowed=["core", "redis"])
    reg.register("redis", RedisAdapter(url=url, allow_write=True, allow_prefixes=[base]))
    code = f'L1: R redis.set "{base}:k" "v" ->ok\nL2: R redis.get "{base}:k" ->val\nL3: J val\n'
    eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=True)
    val = asyncio.run(eng.run_label_async("1", frame={}))
    assert val == "v"
