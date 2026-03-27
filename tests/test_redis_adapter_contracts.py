import os
import sys
import asyncio
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.redis import RedisAdapter
from runtime.adapters.base import AdapterError


class _FakePubSub:
    def __init__(self):
        self._messages = [{"type": "message", "data": "hello"}]

    def subscribe(self, channel):
        return None

    def get_message(self, ignore_subscribe_messages=True, timeout=0.1):
        return self._messages.pop(0) if self._messages else None

    def close(self):
        return None


class _FakeAsyncPubSub:
    def __init__(self):
        self._messages = [{"type": "message", "data": "hello-async"}]

    async def subscribe(self, channel):
        return None

    async def get_message(self, ignore_subscribe_messages=True, timeout=0.1):
        await asyncio.sleep(0)
        return self._messages.pop(0) if self._messages else None

    async def unsubscribe(self, channel):
        return None

    async def close(self):
        return None


class _FakePipeline:
    def __init__(self):
        self.ops = []

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value, ex))
        return True

    def get(self, key):
        self.ops.append(("get", key))
        return "v"

    def execute(self):
        return [True, "v"]

    def reset(self):
        return None


class _FakeAsyncPipeline:
    def __init__(self):
        self.ops = []

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value, ex))
        return self

    def get(self, key):
        self.ops.append(("get", key))
        return self

    def hset(self, key, field, value):
        self.ops.append(("hset", key, field, value))
        return self

    def lpush(self, key, value):
        self.ops.append(("lpush", key, value))
        return self

    def publish(self, channel, message):
        self.ops.append(("publish", channel, message))
        return self

    def ping(self):
        self.ops.append(("ping",))
        return self

    async def execute(self):
        return [True for _ in self.ops]

    async def reset(self):
        return None


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.lists = {}

    def ping(self):
        return True

    def info(self, section=None):
        return {"section": section or "all"}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    def delete(self, key):
        existed = key in self.store
        self.store.pop(key, None)
        return 1 if existed else 0

    def incr(self, key, amount=1):
        self.store[key] = int(self.store.get(key, 0)) + int(amount)
        return self.store[key]

    def decr(self, key, amount=1):
        self.store[key] = int(self.store.get(key, 0)) - int(amount)
        return self.store[key]

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hdel(self, key, field):
        h = self.hashes.get(key, {})
        existed = field in h
        h.pop(field, None)
        return 1 if existed else 0

    def hmget(self, key, fields):
        h = self.hashes.get(key, {})
        return [h.get(f) for f in fields]

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    def lpop(self, key):
        lst = self.lists.get(key, [])
        return lst.pop(0) if lst else None

    def rpop(self, key):
        lst = self.lists.get(key, [])
        return lst.pop() if lst else None

    def llen(self, key):
        return len(self.lists.get(key, []))

    def publish(self, channel, message):
        return 1

    def pubsub(self):
        return _FakePubSub()

    def pipeline(self, transaction=True):
        return _FakePipeline()


class _FakeAsyncRedis:
    def __init__(self, backing):
        self.backing = backing

    async def ping(self):
        return self.backing.ping()

    async def info(self, section=None):
        return self.backing.info(section=section)

    async def get(self, key):
        return self.backing.get(key)

    async def set(self, key, value, ex=None):
        return self.backing.set(key, value, ex=ex)

    async def delete(self, key):
        return self.backing.delete(key)

    async def incr(self, key, amount=1):
        return self.backing.incr(key, amount=amount)

    async def decr(self, key, amount=1):
        return self.backing.decr(key, amount=amount)

    async def hget(self, key, field):
        return self.backing.hget(key, field)

    async def hset(self, key, field, value):
        return self.backing.hset(key, field, value)

    async def hdel(self, key, field):
        return self.backing.hdel(key, field)

    async def hmget(self, key, fields):
        return self.backing.hmget(key, fields)

    async def lpush(self, key, value):
        return self.backing.lpush(key, value)

    async def rpush(self, key, value):
        return self.backing.rpush(key, value)

    async def lpop(self, key):
        return self.backing.lpop(key)

    async def rpop(self, key):
        return self.backing.rpop(key)

    async def llen(self, key):
        return self.backing.llen(key)

    async def publish(self, channel, message):
        return self.backing.publish(channel, message)

    def pubsub(self):
        return _FakeAsyncPubSub()

    def pipeline(self, transaction=True):
        return _FakeAsyncPipeline()


def _install_fake_redis(monkeypatch):
    fake_client = _FakeRedis()
    async_client = _FakeAsyncRedis(fake_client)
    fake_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda *a, **k: fake_client),
        asyncio=SimpleNamespace(Redis=SimpleNamespace(from_url=lambda *a, **k: async_client)),
    )
    monkeypatch.setitem(sys.modules, "redis", fake_module)
    return fake_client, async_client


def test_redis_kv_hash_list_contract(monkeypatch):
    _install_fake_redis(monkeypatch)
    adp = RedisAdapter(url="redis://x", allow_write=True, allow_prefixes=["app:"])
    assert adp.call("set", ["app:key", "v"], {})["ok"] is True
    assert adp.call("get", ["app:key"], {}) == "v"
    assert adp.call("incr", ["app:count"], {}) == 1
    assert adp.call("hset", ["app:h", "f1", "x"], {})["updated"] == 1
    assert adp.call("hmget", ["app:h", ["f1", "f2"]], {}) == ["x", None]
    assert adp.call("lpush", ["app:q", "a"], {}) == 1
    assert adp.call("llen", ["app:q"], {}) == 1
    assert adp.call("lpop", ["app:q"], {}) == "a"


def test_redis_blocks_write_when_not_allowed(monkeypatch):
    _install_fake_redis(monkeypatch)
    adp = RedisAdapter(url="redis://x", allow_write=False)
    with_raise = False
    try:
        adp.call("set", ["k", "v"], {})
    except Exception as e:
        with_raise = True
        assert isinstance(e, AdapterError)
        assert "allow_write" in str(e)
    assert with_raise


def test_redis_transaction_contract(monkeypatch):
    _install_fake_redis(monkeypatch)
    adp = RedisAdapter(url="redis://x", allow_write=True)
    out = adp.call("transaction", [[{"verb": "set", "args": ["k", "v"]}, {"verb": "get", "args": ["k"]}]], {})
    assert out["ok"] is True
    assert isinstance(out["results"], list)


def test_redis_full_async_verb_parity_contract(monkeypatch):
    _install_fake_redis(monkeypatch)
    adp = RedisAdapter(url="redis://x", allow_write=True, allow_prefixes=["app:"])
    assert asyncio.run(adp.call_async("set", ["app:k", "v"], {}))["ok"] is True
    assert asyncio.run(adp.call_async("get", ["app:k"], {})) == "v"
    assert asyncio.run(adp.call_async("hset", ["app:h", "f1", "x"], {}))["updated"] == 1
    assert asyncio.run(adp.call_async("hget", ["app:h", "f1"], {})) == "x"
    assert asyncio.run(adp.call_async("lpush", ["app:q", "a"], {})) == 1
    assert asyncio.run(adp.call_async("llen", ["app:q"], {})) == 1
    assert asyncio.run(adp.call_async("publish", ["app:c", "m"], {}))["subscribers"] == 1
    sub = asyncio.run(adp.call_async("subscribe", ["app:c", 0.05, 5], {}))
    assert sub["active"] is True
    assert sub["messages"] == ["hello-async"]
    tx = asyncio.run(
        adp.call_async(
            "transaction",
            [[{"verb": "set", "args": ["app:t", "1"]}, {"verb": "get", "args": ["app:t"]}, {"verb": "publish", "args": ["app:c", "x"]}]],
            {},
        )
    )
    assert tx["ok"] is True
