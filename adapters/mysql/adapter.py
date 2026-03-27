from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter

from adapters.mysql.sql_guard import (
    assert_allowed_tables,
    assert_execute_sql,
    assert_query_sql,
    normalize_params,
    normalize_tables,
)


class MySQLAdapter(RuntimeAdapter):
    """
    MySQL runtime adapter.

    Verbs:
    - query(sql, params?)
    - execute(sql, params?)
    - transaction(ops)
    """

    def __init__(
        self,
        *,
        dsn: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        ssl_mode: Optional[str] = None,
        ssl_ca: Optional[str] = None,
        timeout_s: float = 5.0,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        pool_min_size: int = 1,
        pool_max_size: int = 5,
    ):
        self.dsn = (dsn or os.environ.get("AINL_MYSQL_URL") or "").strip() or None
        self.host = (host or os.environ.get("AINL_MYSQL_HOST") or "").strip() or None
        self.port = int(port or os.environ.get("AINL_MYSQL_PORT") or 3306)
        self.database = (database or os.environ.get("AINL_MYSQL_DB") or "").strip() or None
        self.user = (user or os.environ.get("AINL_MYSQL_USER") or "").strip() or None
        self.password = password if password is not None else os.environ.get("AINL_MYSQL_PASSWORD")
        self.ssl_mode = (ssl_mode or os.environ.get("AINL_MYSQL_SSL_MODE") or "REQUIRED").strip().upper()
        self.ssl_ca = (ssl_ca or os.environ.get("AINL_MYSQL_SSL_CA") or "").strip() or None
        self.timeout_s = float(timeout_s)
        self.allow_write = bool(allow_write)
        self.allow_tables = normalize_tables(allow_tables)
        self.pool_min_size = max(1, int(pool_min_size or os.environ.get("AINL_MYSQL_POOL_MIN") or 1))
        self.pool_max_size = max(self.pool_min_size, int(pool_max_size or os.environ.get("AINL_MYSQL_POOL_MAX") or 5))
        self._pool: Any = None
        self._async_pool: Any = None
        self._validate_connection_config()
        self._init_pool()

    def _validate_connection_config(self) -> None:
        if self.dsn:
            return
        required = {"host": self.host, "database": self.database, "user": self.user}
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise AdapterError(
                f"mysql configuration missing required values: {', '.join(missing)} "
                "(set AINL_MYSQL_URL or explicit host/db/user settings)"
            )

    def _load_pymysql(self) -> Any:
        try:
            import pymysql
        except Exception as e:  # pragma: no cover - import failure path
            raise AdapterError("mysql adapter requires pymysql. Install with: pip install 'pymysql>=1.1.0'") from e
        return pymysql

    def _connect_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "connect_timeout": self.timeout_s,
            "read_timeout": self.timeout_s,
            "write_timeout": self.timeout_s,
            "autocommit": False,
            "charset": "utf8mb4",
            "cursorclass": self._load_pymysql().cursors.DictCursor,
        }
        if self.dsn:
            try:
                from urllib.parse import parse_qs, unquote, urlparse
            except Exception as e:  # pragma: no cover
                raise AdapterError(f"mysql URL parsing error: {e}") from e
            p = urlparse(self.dsn)
            if p.scheme not in {"mysql", "mysql+pymysql"}:
                raise AdapterError("mysql URL must use mysql:// or mysql+pymysql://")
            kwargs.update(
                {
                    "host": p.hostname or self.host,
                    "port": int(p.port or self.port),
                    "user": unquote(p.username or self.user or ""),
                    "password": unquote(p.password or self.password or ""),
                    "database": (p.path or "").lstrip("/") or self.database,
                }
            )
            if p.query:
                q = parse_qs(p.query, keep_blank_values=True)
                if "ssl_ca" in q and q["ssl_ca"]:
                    self.ssl_ca = q["ssl_ca"][0]
                if "ssl_mode" in q and q["ssl_mode"]:
                    self.ssl_mode = q["ssl_mode"][0].upper()
        else:
            kwargs.update(
                {
                    "host": self.host,
                    "port": self.port,
                    "user": self.user,
                    "password": self.password,
                    "database": self.database,
                }
            )
        if self.ssl_ca:
            kwargs["ssl"] = {"ca": self.ssl_ca}
        return kwargs

    def _connect_kwargs_async(self) -> Dict[str, Any]:
        kwargs = self._connect_kwargs()
        kwargs.pop("cursorclass", None)
        kwargs["autocommit"] = False
        return kwargs

    def _init_pool(self) -> None:
        # Keep pooling optional; fallback to direct connections when queue pool isn't available.
        try:
            from queue import Empty, Queue
        except Exception:
            self._pool = None
            return
        self._pool = Queue(maxsize=self.pool_max_size)
        # Seed minimal warm pool.
        for _ in range(self.pool_min_size):
            try:
                self._pool.put_nowait(self._connect_direct())
            except Exception:
                break

    def _connect_direct(self) -> Any:
        pymysql = self._load_pymysql()
        try:
            return pymysql.connect(**self._connect_kwargs())
        except Exception as e:
            raise AdapterError(f"mysql connection error: {e}") from e

    @contextmanager
    def _connect(self):
        conn = None
        from_pool = False
        try:
            if self._pool is not None:
                try:
                    conn = self._pool.get_nowait()
                    from_pool = True
                except Exception:
                    conn = self._connect_direct()
            else:
                conn = self._connect_direct()
            yield conn
        finally:
            if conn is not None:
                if from_pool and self._pool is not None:
                    try:
                        # Connection may be dead; ping with reconnect and keep if healthy.
                        conn.ping(reconnect=True)
                        self._pool.put_nowait(conn)
                        conn = None
                    except Exception:
                        pass
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def _query(self, sql: str, params: object) -> List[Dict[str, Any]]:
        assert_query_sql(sql)
        assert_allowed_tables(sql, self.allow_tables)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, normalize_params(params))
                rows = cur.fetchall()
                return [dict(r) for r in rows]

    def _execute(self, sql: str, params: object) -> Dict[str, Any]:
        assert_execute_sql(sql, allow_write=self.allow_write)
        assert_allowed_tables(sql, self.allow_tables)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, normalize_params(params))
                rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                lastrowid = getattr(cur, "lastrowid", None)
            conn.commit()
            return {"rows_affected": rows_affected, "lastrowid": lastrowid}

    def _transaction(self, ops: object) -> Dict[str, Any]:
        if not isinstance(ops, list) or not ops:
            raise AdapterError("mysql transaction target requires non-empty list of ops")
        with self._connect() as conn:
            results: List[Any] = []
            try:
                with conn.cursor() as cur:
                    for op in ops:
                        if not isinstance(op, dict):
                            raise AdapterError("mysql transaction op must be dict")
                        verb = str(op.get("verb") or "").strip().lower()
                        sql = str(op.get("sql") or "")
                        params = normalize_params(op.get("params"))
                        if verb == "query":
                            assert_query_sql(sql)
                            assert_allowed_tables(sql, self.allow_tables)
                            cur.execute(sql, params)
                            results.append([dict(r) for r in cur.fetchall()])
                        elif verb == "execute":
                            assert_execute_sql(sql, allow_write=self.allow_write)
                            assert_allowed_tables(sql, self.allow_tables)
                            cur.execute(sql, params)
                            rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                            lastrowid = getattr(cur, "lastrowid", None)
                            results.append({"rows_affected": rows_affected, "lastrowid": lastrowid})
                        else:
                            raise AdapterError(f"unsupported mysql transaction op verb: {verb}")
                conn.commit()
                return {"ok": True, "results": results}
            except Exception as e:
                conn.rollback()
                if isinstance(e, AdapterError):
                    raise
                raise AdapterError(f"mysql transaction error: {e}") from e

    def _load_aiomysql(self) -> Any:
        try:
            import aiomysql
        except Exception:
            return None
        return aiomysql

    async def _init_async_pool(self) -> Any:
        if self._async_pool is not None:
            return self._async_pool
        aiomysql = self._load_aiomysql()
        if aiomysql is None:
            return None
        try:
            self._async_pool = await aiomysql.create_pool(
                minsize=self.pool_min_size,
                maxsize=self.pool_max_size,
                **self._connect_kwargs_async(),
            )
            return self._async_pool
        except Exception as e:
            raise AdapterError(f"mysql async pool init error: {e}") from e

    @asynccontextmanager
    async def _connect_async(self):
        pool = await self._init_async_pool()
        if pool is not None:
            async with pool.acquire() as conn:
                yield conn
            return
        # Graceful fallback when aiomysql is unavailable.
        conn = await asyncio.to_thread(self._connect_direct)
        try:
            yield conn
        finally:
            await asyncio.to_thread(conn.close)

    async def _query_async(self, sql: str, params: object) -> List[Dict[str, Any]]:
        assert_query_sql(sql)
        assert_allowed_tables(sql, self.allow_tables)
        aiomysql = self._load_aiomysql()
        if aiomysql is None:
            return await asyncio.to_thread(self._query, sql, params)
        async with self._connect_async() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, normalize_params(params))
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def _execute_async(self, sql: str, params: object) -> Dict[str, Any]:
        assert_execute_sql(sql, allow_write=self.allow_write)
        assert_allowed_tables(sql, self.allow_tables)
        aiomysql = self._load_aiomysql()
        if aiomysql is None:
            return await asyncio.to_thread(self._execute, sql, params)
        async with self._connect_async() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, normalize_params(params))
                rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                lastrowid = getattr(cur, "lastrowid", None)
            await conn.commit()
            return {"rows_affected": rows_affected, "lastrowid": lastrowid}

    async def _transaction_async(self, ops: object) -> Dict[str, Any]:
        if not isinstance(ops, list) or not ops:
            raise AdapterError("mysql transaction target requires non-empty list of ops")
        aiomysql = self._load_aiomysql()
        if aiomysql is None:
            return await asyncio.to_thread(self._transaction, ops)
        async with self._connect_async() as conn:
            results: List[Any] = []
            try:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    for op in ops:
                        if not isinstance(op, dict):
                            raise AdapterError("mysql transaction op must be dict")
                        verb = str(op.get("verb") or "").strip().lower()
                        sql = str(op.get("sql") or "")
                        p = normalize_params(op.get("params"))
                        if verb == "query":
                            assert_query_sql(sql)
                            assert_allowed_tables(sql, self.allow_tables)
                            await cur.execute(sql, p)
                            results.append([dict(r) for r in (await cur.fetchall())])
                        elif verb == "execute":
                            assert_execute_sql(sql, allow_write=self.allow_write)
                            assert_allowed_tables(sql, self.allow_tables)
                            await cur.execute(sql, p)
                            rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                            lastrowid = getattr(cur, "lastrowid", None)
                            results.append({"rows_affected": rows_affected, "lastrowid": lastrowid})
                        else:
                            raise AdapterError(f"unsupported mysql transaction op verb: {verb}")
                await conn.commit()
                return {"ok": True, "results": results}
            except Exception as e:
                await conn.rollback()
                if isinstance(e, AdapterError):
                    raise
                raise AdapterError(f"mysql transaction error: {e}") from e

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in {"query", "execute", "transaction"}:
            raise AdapterError(f"unsupported mysql target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("mysql transaction missing ops argument")
            return self._transaction(args[0])
        if not args:
            raise AdapterError("mysql adapter missing sql argument")
        sql = str(args[0] or "")
        params = args[1] if len(args) > 1 else None
        if verb == "query":
            return self._query(sql, params)
        return self._execute(sql, params)

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in {"query", "execute", "transaction"}:
            raise AdapterError(f"unsupported mysql target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("mysql transaction missing ops argument")
            return await self._transaction_async(args[0])
        if not args:
            raise AdapterError("mysql adapter missing sql argument")
        sql = str(args[0] or "")
        params = args[1] if len(args) > 1 else None
        if verb == "query":
            return await self._query_async(sql, params)
        return await self._execute_async(sql, params)

    # Async-ready note: when RuntimeEngine gets async adapter dispatch, this class
    # can add an aiomysql-backed variant with identical verb contracts.
