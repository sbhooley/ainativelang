from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from runtime.adapters.base import AdapterError, RuntimeAdapter


class RedisAdapter(RuntimeAdapter):
    """
    Redis runtime adapter.

    Verbs:
    - get, set, delete, incr, decr
    - hget, hset, hdel, hmget
    - lpush, rpush, lpop, rpop, llen
    - publish, subscribe
    - ping, info
    - transaction(ops)
    """

    _READ_VERBS = {"get", "hget", "hmget", "llen", "ping", "info", "subscribe"}
    _WRITE_VERBS = {
        "set",
        "delete",
        "incr",
        "decr",
        "hset",
        "hdel",
        "lpush",
        "rpush",
        "lpop",
        "rpop",
        "publish",
    }
    _ALL_VERBS = _READ_VERBS | _WRITE_VERBS | {"transaction"}

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        timeout_s: float = 5.0,
        allow_write: bool = True,
        allow_prefixes: Optional[Iterable[str]] = None,
    ):
        self.url = (url or os.environ.get("AINL_REDIS_URL") or "").strip() or None
        self.host = (host or os.environ.get("AINL_REDIS_HOST") or "").strip() or "127.0.0.1"
        self.port = int(port or os.environ.get("AINL_REDIS_PORT") or 6379)
        self.db = int(db if db is not None else (os.environ.get("AINL_REDIS_DB") or 0))
        self.username = (username or os.environ.get("AINL_REDIS_USER") or "").strip() or None
        self.password = password if password is not None else os.environ.get("AINL_REDIS_PASSWORD")
        self.ssl = bool(ssl) if ssl is not None else str(os.environ.get("AINL_REDIS_SSL") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.timeout_s = float(timeout_s)
        self.allow_write = bool(allow_write)
        self.allow_prefixes = {str(p).strip() for p in (allow_prefixes or []) if str(p).strip()}
        self._client: Any = None
        self._async_client: Any = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_subscriptions: Dict[str, Dict[str, Any]] = {}
        self._validate_config()
        self._init_client()

    def _validate_config(self) -> None:
        if self.url:
            return
        if not self.host:
            raise AdapterError("redis configuration missing host (set AINL_REDIS_URL or host settings)")

    def _load_redis(self) -> Any:
        try:
            import redis
        except Exception as e:  # pragma: no cover - import failure path
            raise AdapterError("redis adapter requires redis-py. Install with: pip install 'redis>=5.0.0'") from e
        return redis

    def _load_redis_async(self) -> Any:
        redis = self._load_redis()
        try:
            return redis.asyncio
        except Exception:
            return None

    def _init_client(self) -> None:
        redis = self._load_redis()
        try:
            if self.url:
                self._client = redis.Redis.from_url(
                    self.url,
                    socket_connect_timeout=self.timeout_s,
                    socket_timeout=self.timeout_s,
                    decode_responses=True,
                )
            else:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    username=self.username,
                    password=self.password,
                    ssl=self.ssl,
                    socket_connect_timeout=self.timeout_s,
                    socket_timeout=self.timeout_s,
                    decode_responses=True,
                )
            self._client.ping()
        except Exception as e:
            raise AdapterError(f"redis connection error: {e}") from e

    def _require_client(self) -> Any:
        if self._client is None:
            self._init_client()
        return self._client

    def _check_write(self, verb: str) -> None:
        if verb in self._WRITE_VERBS and not self.allow_write:
            raise AdapterError("redis write blocked: allow_write is false")

    def _check_allowed_key(self, key: str) -> None:
        if not self.allow_prefixes:
            return
        if not any(str(key).startswith(prefix) for prefix in self.allow_prefixes):
            raise AdapterError("redis key blocked by allow_prefixes policy")

    def _check_allowed_channel(self, channel: str) -> None:
        if not self.allow_prefixes:
            return
        if not any(str(channel).startswith(prefix) for prefix in self.allow_prefixes):
            raise AdapterError("redis channel blocked by allow_prefixes policy")

    def _as_int(self, value: Any) -> int:
        try:
            return int(value)
        except Exception as e:
            raise AdapterError(f"redis value is not int-coercible: {value!r}") from e

    def _do(self, verb: str, args: Sequence[Any], *, client: Any = None) -> Any:
        c = client or self._require_client()
        self._check_write(verb)

        if verb == "ping":
            return c.ping()
        if verb == "info":
            section = str(args[0]).strip() if args else None
            return c.info(section=section) if section else c.info()

        if verb in {"get", "set", "delete", "incr", "decr"}:
            if not args:
                raise AdapterError(f"redis {verb} requires key argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "get":
                return c.get(key)
            if verb == "set":
                if len(args) < 2:
                    raise AdapterError("redis set requires value argument")
                ttl = int(args[2]) if len(args) > 2 and args[2] is not None else None
                ok = c.set(key, args[1], ex=ttl)
                return {"ok": bool(ok)}
            if verb == "delete":
                return {"deleted": self._as_int(c.delete(key))}
            if verb == "incr":
                amount = self._as_int(args[1]) if len(args) > 1 else 1
                return self._as_int(c.incr(key, amount))
            if verb == "decr":
                amount = self._as_int(args[1]) if len(args) > 1 else 1
                return self._as_int(c.decr(key, amount))

        if verb in {"hget", "hset", "hdel", "hmget"}:
            if len(args) < 2:
                raise AdapterError(f"redis {verb} requires key and field argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "hget":
                return c.hget(key, str(args[1]))
            if verb == "hset":
                if len(args) < 3:
                    raise AdapterError("redis hset requires value argument")
                return {"updated": self._as_int(c.hset(key, str(args[1]), args[2]))}
            if verb == "hdel":
                return {"deleted": self._as_int(c.hdel(key, str(args[1])))}
            # hmget
            fields = args[1]
            if not isinstance(fields, (list, tuple)) or not fields:
                raise AdapterError("redis hmget requires non-empty list of fields")
            return c.hmget(key, [str(f) for f in fields])

        if verb in {"lpush", "rpush", "lpop", "rpop", "llen"}:
            if not args:
                raise AdapterError(f"redis {verb} requires key argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "lpush":
                if len(args) < 2:
                    raise AdapterError("redis lpush requires value argument")
                return self._as_int(c.lpush(key, args[1]))
            if verb == "rpush":
                if len(args) < 2:
                    raise AdapterError("redis rpush requires value argument")
                return self._as_int(c.rpush(key, args[1]))
            if verb == "lpop":
                return c.lpop(key)
            if verb == "rpop":
                return c.rpop(key)
            return self._as_int(c.llen(key))

        if verb == "publish":
            if len(args) < 2:
                raise AdapterError("redis publish requires channel and message arguments")
            channel = str(args[0])
            self._check_allowed_channel(channel)
            return {"subscribers": self._as_int(c.publish(channel, args[1]))}

        if verb == "subscribe":
            if not args:
                raise AdapterError("redis subscribe requires channel argument")
            channel = str(args[0])
            self._check_allowed_channel(channel)
            timeout_s = float(args[1]) if len(args) > 1 and args[1] is not None else 1.0
            max_messages = self._as_int(args[2]) if len(args) > 2 and args[2] is not None else 10
            pubsub = c.pubsub()
            try:
                pubsub.subscribe(channel)
                messages: List[Any] = []
                start = time.time()
                while time.time() - start <= timeout_s and len(messages) < max_messages:
                    msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                    if msg and msg.get("type") == "message":
                        messages.append(msg.get("data"))
                return {"channel": channel, "messages": messages}
            finally:
                try:
                    pubsub.close()
                except Exception:
                    pass

        raise AdapterError(f"unsupported redis target: {verb}")

    def _transaction(self, ops: object) -> Dict[str, Any]:
        if not isinstance(ops, list) or not ops:
            raise AdapterError("redis transaction target requires non-empty list of ops")
        c = self._require_client()
        pipe = c.pipeline(transaction=True)
        try:
            for op in ops:
                if not isinstance(op, dict):
                    raise AdapterError("redis transaction op must be dict")
                verb = str(op.get("verb") or "").strip().lower()
                if verb not in self._ALL_VERBS or verb in {"subscribe", "transaction"}:
                    raise AdapterError(f"unsupported redis transaction op verb: {verb}")
                args = op.get("args")
                if args is None:
                    args = []
                if not isinstance(args, list):
                    raise AdapterError("redis transaction op args must be list when provided")
                self._do(verb, args, client=pipe)
            raw = pipe.execute()
            return {"ok": True, "results": [self._normalize_result(v) for v in raw]}
        except Exception as e:
            try:
                pipe.reset()
            except Exception:
                pass
            if isinstance(e, AdapterError):
                raise
            raise AdapterError(f"redis transaction error: {e}") from e

    def _normalize_result(self, value: Any) -> Any:
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value
        if isinstance(value, list):
            return [self._normalize_result(v) for v in value]
        if isinstance(value, dict):
            return {k: self._normalize_result(v) for k, v in value.items()}
        return value

    async def _ensure_async_client(self) -> Any:
        current_loop = asyncio.get_running_loop()
        if self._async_loop is not None and self._async_loop is not current_loop:
            # Support callers that invoke call_async via separate asyncio.run() loops.
            for sub in list(self._async_subscriptions.values()):
                task = sub.get("task")
                if task is not None:
                    task.cancel()
            self._async_subscriptions.clear()
            if self._async_client is not None:
                with contextlib.suppress(Exception):
                    await self._async_client.close()
            self._async_client = None
            self._async_loop = None
        if self._async_client is not None:
            return self._async_client
        r_async = self._load_redis_async()
        if r_async is None:
            return None
        if self.url:
            self._async_client = r_async.Redis.from_url(
                self.url,
                socket_connect_timeout=self.timeout_s,
                socket_timeout=self.timeout_s,
                decode_responses=True,
            )
        else:
            self._async_client = r_async.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ssl=self.ssl,
                socket_connect_timeout=self.timeout_s,
                socket_timeout=self.timeout_s,
                decode_responses=True,
            )
        await self._async_client.ping()
        self._async_loop = current_loop
        return self._async_client

    async def _do_async(self, verb: str, args: Sequence[Any], *, client: Any = None) -> Any:
        c = client or await self._ensure_async_client()
        if c is None:
            return await asyncio.to_thread(self._do, verb, args)
        self._check_write(verb)

        if verb == "ping":
            return await c.ping()
        if verb == "info":
            section = str(args[0]).strip() if args else None
            return await c.info(section=section) if section else await c.info()

        if verb in {"get", "set", "delete", "incr", "decr"}:
            if not args:
                raise AdapterError(f"redis {verb} requires key argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "get":
                return await c.get(key)
            if verb == "set":
                if len(args) < 2:
                    raise AdapterError("redis set requires value argument")
                ttl = int(args[2]) if len(args) > 2 and args[2] is not None else None
                ok = await c.set(key, args[1], ex=ttl)
                return {"ok": bool(ok)}
            if verb == "delete":
                return {"deleted": self._as_int(await c.delete(key))}
            if verb == "incr":
                amount = self._as_int(args[1]) if len(args) > 1 else 1
                return self._as_int(await c.incr(key, amount))
            amount = self._as_int(args[1]) if len(args) > 1 else 1
            return self._as_int(await c.decr(key, amount))

        if verb in {"hget", "hset", "hdel", "hmget"}:
            if len(args) < 2:
                raise AdapterError(f"redis {verb} requires key and field argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "hget":
                return await c.hget(key, str(args[1]))
            if verb == "hset":
                if len(args) < 3:
                    raise AdapterError("redis hset requires value argument")
                return {"updated": self._as_int(await c.hset(key, str(args[1]), args[2]))}
            if verb == "hdel":
                return {"deleted": self._as_int(await c.hdel(key, str(args[1])))}
            fields = args[1]
            if not isinstance(fields, (list, tuple)) or not fields:
                raise AdapterError("redis hmget requires non-empty list of fields")
            return await c.hmget(key, [str(f) for f in fields])

        if verb in {"lpush", "rpush", "lpop", "rpop", "llen"}:
            if not args:
                raise AdapterError(f"redis {verb} requires key argument")
            key = str(args[0])
            self._check_allowed_key(key)
            if verb == "lpush":
                if len(args) < 2:
                    raise AdapterError("redis lpush requires value argument")
                return self._as_int(await c.lpush(key, args[1]))
            if verb == "rpush":
                if len(args) < 2:
                    raise AdapterError("redis rpush requires value argument")
                return self._as_int(await c.rpush(key, args[1]))
            if verb == "lpop":
                return await c.lpop(key)
            if verb == "rpop":
                return await c.rpop(key)
            return self._as_int(await c.llen(key))

        if verb == "publish":
            if len(args) < 2:
                raise AdapterError("redis publish requires channel and message arguments")
            channel = str(args[0])
            self._check_allowed_channel(channel)
            return {"subscribers": self._as_int(await c.publish(channel, args[1]))}

        raise AdapterError(f"unsupported redis target: {verb}")

    async def _subscribe_loop_async(self, channel: str, pubsub: Any, queue: asyncio.Queue) -> None:
        try:
            await pubsub.subscribe(channel)
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if msg and msg.get("type") == "message":
                    await queue.put(self._normalize_result(msg.get("data")))
        except asyncio.CancelledError:
            raise
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(channel)
            with contextlib.suppress(Exception):
                await pubsub.close()

    async def _subscribe_async(self, channel: str, timeout_s: float, max_messages: int) -> Dict[str, Any]:
        self._check_allowed_channel(channel)
        c = await self._ensure_async_client()
        if c is None:
            return await asyncio.to_thread(self._do, "subscribe", [channel, timeout_s, max_messages])
        sub = self._async_subscriptions.get(channel)
        if sub is None:
            queue: asyncio.Queue = asyncio.Queue()
            pubsub = c.pubsub()
            task = asyncio.create_task(self._subscribe_loop_async(channel, pubsub, queue))
            sub = {"queue": queue, "task": task, "pubsub": pubsub}
            self._async_subscriptions[channel] = sub
        queue = sub["queue"]
        messages: List[Any] = []
        end = time.time() + max(0.0, timeout_s)
        while len(messages) < max_messages and time.time() <= end:
            remaining = max(0.0, end - time.time())
            if remaining <= 0:
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=remaining)
                messages.append(msg)
            except asyncio.TimeoutError:
                break
        return {"channel": channel, "messages": messages, "active": True}

    async def _unsubscribe_async(self, channel: str) -> Dict[str, Any]:
        self._check_allowed_channel(channel)
        sub = self._async_subscriptions.pop(channel, None)
        if not sub:
            return {"channel": channel, "removed": False}
        task = sub.get("task")
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        return {"channel": channel, "removed": True}

    async def _transaction_async(self, ops: object) -> Dict[str, Any]:
        if not isinstance(ops, list) or not ops:
            raise AdapterError("redis transaction target requires non-empty list of ops")
        c = await self._ensure_async_client()
        if c is None:
            return await asyncio.to_thread(self._transaction, ops)
        pipe = c.pipeline(transaction=True)
        try:
            for op in ops:
                if not isinstance(op, dict):
                    raise AdapterError("redis transaction op must be dict")
                verb = str(op.get("verb") or "").strip().lower()
                if verb not in self._ALL_VERBS or verb in {"subscribe", "transaction"}:
                    raise AdapterError(f"unsupported redis transaction op verb: {verb}")
                a = op.get("args")
                if a is None:
                    a = []
                if not isinstance(a, list):
                    raise AdapterError("redis transaction op args must be list when provided")
                # Queue pipeline ops without awaiting command methods.
                if verb in {"get", "set", "delete", "incr", "decr"}:
                    key = str(a[0]) if a else ""
                    if not key:
                        raise AdapterError(f"redis {verb} requires key argument")
                    self._check_allowed_key(key)
                    if verb == "get":
                        pipe.get(key)
                    elif verb == "set":
                        if len(a) < 2:
                            raise AdapterError("redis set requires value argument")
                        ttl = int(a[2]) if len(a) > 2 and a[2] is not None else None
                        pipe.set(key, a[1], ex=ttl)
                    elif verb == "delete":
                        pipe.delete(key)
                    elif verb == "incr":
                        amount = self._as_int(a[1]) if len(a) > 1 else 1
                        pipe.incr(key, amount)
                    else:
                        amount = self._as_int(a[1]) if len(a) > 1 else 1
                        pipe.decr(key, amount)
                elif verb in {"hget", "hset", "hdel", "hmget"}:
                    if len(a) < 2:
                        raise AdapterError(f"redis {verb} requires key and field argument")
                    key = str(a[0])
                    self._check_allowed_key(key)
                    if verb == "hget":
                        pipe.hget(key, str(a[1]))
                    elif verb == "hset":
                        if len(a) < 3:
                            raise AdapterError("redis hset requires value argument")
                        pipe.hset(key, str(a[1]), a[2])
                    elif verb == "hdel":
                        pipe.hdel(key, str(a[1]))
                    else:
                        fields = a[1]
                        if not isinstance(fields, (list, tuple)) or not fields:
                            raise AdapterError("redis hmget requires non-empty list of fields")
                        pipe.hmget(key, [str(f) for f in fields])
                elif verb in {"lpush", "rpush", "lpop", "rpop", "llen"}:
                    if not a:
                        raise AdapterError(f"redis {verb} requires key argument")
                    key = str(a[0])
                    self._check_allowed_key(key)
                    if verb == "lpush":
                        if len(a) < 2:
                            raise AdapterError("redis lpush requires value argument")
                        pipe.lpush(key, a[1])
                    elif verb == "rpush":
                        if len(a) < 2:
                            raise AdapterError("redis rpush requires value argument")
                        pipe.rpush(key, a[1])
                    elif verb == "lpop":
                        pipe.lpop(key)
                    elif verb == "rpop":
                        pipe.rpop(key)
                    else:
                        pipe.llen(key)
                elif verb == "publish":
                    if len(a) < 2:
                        raise AdapterError("redis publish requires channel and message arguments")
                    channel = str(a[0])
                    self._check_allowed_channel(channel)
                    pipe.publish(channel, a[1])
                elif verb == "ping":
                    pipe.ping()
                elif verb == "info":
                    section = str(a[0]).strip() if a else None
                    pipe.info(section=section) if section else pipe.info()
                else:
                    raise AdapterError(f"unsupported redis transaction op verb: {verb}")
            raw = await pipe.execute()
            return {"ok": True, "results": [self._normalize_result(v) for v in raw]}
        except Exception as e:
            with contextlib.suppress(Exception):
                await pipe.reset()
            if isinstance(e, AdapterError):
                raise
            raise AdapterError(f"redis transaction error: {e}") from e

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported redis target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("redis transaction missing ops argument")
            return await self._transaction_async(args[0])
        if verb == "subscribe":
            if not args:
                raise AdapterError("redis subscribe requires channel argument")
            channel = str(args[0])
            timeout_s = float(args[1]) if len(args) > 1 and args[1] is not None else 1.0
            max_messages = self._as_int(args[2]) if len(args) > 2 and args[2] is not None else 10
            return await self._subscribe_async(channel, timeout_s, max_messages)
        return self._normalize_result(await self._do_async(verb, args))

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported redis target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("redis transaction missing ops argument")
            return self._transaction(args[0])
        return self._normalize_result(self._do(verb, args))

    # Async path supports full verb parity via redis.asyncio when available.
