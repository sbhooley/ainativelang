from __future__ import annotations

from contextlib import asynccontextmanager
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter

from adapters.postgres.sql_guard import (
    assert_allowed_tables,
    assert_execute_sql,
    assert_query_sql,
    normalize_params,
    normalize_tables,
)


class PostgresAdapter(RuntimeAdapter):
    """
    PostgreSQL runtime adapter.

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
        sslmode: Optional[str] = None,
        sslrootcert: Optional[str] = None,
        timeout_s: float = 5.0,
        statement_timeout_ms: int = 5000,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        pool_min_size: int = 1,
        pool_max_size: int = 5,
    ):
        self.dsn = (dsn or os.environ.get("AINL_POSTGRES_URL") or "").strip() or None
        self.host = (host or os.environ.get("AINL_POSTGRES_HOST") or "").strip() or None
        self.port = int(port or os.environ.get("AINL_POSTGRES_PORT") or 5432)
        self.database = (database or os.environ.get("AINL_POSTGRES_DB") or "").strip() or None
        self.user = (user or os.environ.get("AINL_POSTGRES_USER") or "").strip() or None
        self.password = password if password is not None else os.environ.get("AINL_POSTGRES_PASSWORD")
        self.sslmode = (sslmode or os.environ.get("AINL_POSTGRES_SSLMODE") or "require").strip()
        self.sslrootcert = (sslrootcert or os.environ.get("AINL_POSTGRES_SSLROOTCERT") or "").strip() or None
        self.timeout_s = float(timeout_s)
        self.statement_timeout_ms = int(statement_timeout_ms)
        self.allow_write = bool(allow_write)
        self.allow_tables = normalize_tables(allow_tables)
        self.pool_min_size = max(1, int(pool_min_size or os.environ.get("AINL_POSTGRES_POOL_MIN") or 1))
        self.pool_max_size = max(self.pool_min_size, int(pool_max_size or os.environ.get("AINL_POSTGRES_POOL_MAX") or 5))
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
                f"postgres configuration missing required values: {', '.join(missing)} "
                "(set AINL_POSTGRES_URL or explicit host/db/user settings)"
            )

    def _connect_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "connect_timeout": self.timeout_s,
        }
        if self.dsn:
            kwargs["conninfo"] = self.dsn
        else:
            kwargs.update(
                {
                    "host": self.host,
                    "port": self.port,
                    "dbname": self.database,
                    "user": self.user,
                    "password": self.password,
                }
            )
        if self.sslmode:
            kwargs["sslmode"] = self.sslmode
        if self.sslrootcert:
            kwargs["sslrootcert"] = self.sslrootcert
        return kwargs

    def _load_psycopg(self) -> Any:
        try:
            import psycopg
        except Exception as e:  # pragma: no cover - import failure path
            raise AdapterError(
                "postgres adapter requires psycopg. Install with: pip install 'psycopg[binary]>=3.2.0'"
            ) from e
        return psycopg

    def _init_pool(self) -> None:
        # Keep pool optional so environments can run without psycopg-pool.
        try:
            from psycopg_pool import ConnectionPool  # type: ignore
        except Exception:
            self._pool = None
            return
        try:
            self._pool = ConnectionPool(
                conninfo=self._pool_conninfo(),
                kwargs=self._pool_connect_kwargs(),
                min_size=self.pool_min_size,
                max_size=self.pool_max_size,
                open=True,
            )
        except Exception as e:
            raise AdapterError(f"postgres pool init error: {e}") from e

    def _pool_conninfo(self) -> str:
        if self.dsn:
            return self.dsn
        return (
            f"host={self.host} port={self.port} dbname={self.database} user={self.user}"
            + (f" password={self.password}" if self.password else "")
        )

    def _pool_connect_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "connect_timeout": self.timeout_s,
        }
        if self.sslmode:
            kwargs["sslmode"] = self.sslmode
        if self.sslrootcert:
            kwargs["sslrootcert"] = self.sslrootcert
        return kwargs

    def _connect_direct(self) -> Any:
        psycopg = self._load_psycopg()
        try:
            conn = psycopg.connect(**self._connect_kwargs())
            return conn
        except Exception as e:
            raise AdapterError(f"postgres connection error: {e}") from e

    async def _connect_direct_async(self) -> Any:
        psycopg = self._load_psycopg()
        try:
            return await psycopg.AsyncConnection.connect(**self._connect_kwargs())
        except Exception as e:
            raise AdapterError(f"postgres async connection error: {e}") from e

    @contextmanager
    def _connect(self):
        conn = None
        try:
            if self._pool is not None:
                with self._pool.connection() as pooled_conn:
                    self._apply_session_settings(pooled_conn)
                    yield pooled_conn
                    return
            conn = self._connect_direct()
            self._apply_session_settings(conn)
            yield conn
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _apply_session_settings(self, conn: Any) -> None:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (self.statement_timeout_ms,))

    async def _apply_session_settings_async(self, conn: Any) -> None:
        async with conn.cursor() as cur:
            await cur.execute("SET statement_timeout = %s", (self.statement_timeout_ms,))

    def _fetch_rows(self, cur: Any) -> List[Dict[str, Any]]:
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
            elif hasattr(row, "_mapping"):
                out.append(dict(row._mapping))
            else:
                cols = [d[0] for d in (cur.description or [])]
                out.append({cols[i]: row[i] for i in range(len(cols))})
        return out

    async def _fetch_rows_async(self, cur: Any) -> List[Dict[str, Any]]:
        rows = await cur.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
            elif hasattr(row, "_mapping"):
                out.append(dict(row._mapping))
            else:
                cols = [d[0] for d in (cur.description or [])]
                out.append({cols[i]: row[i] for i in range(len(cols))})
        return out

    def _init_async_pool(self) -> None:
        if self._async_pool is not None:
            return
        try:
            from psycopg_pool import AsyncConnectionPool  # type: ignore
        except Exception:
            self._async_pool = None
            return
        try:
            self._async_pool = AsyncConnectionPool(
                conninfo=self._pool_conninfo(),
                kwargs=self._pool_connect_kwargs(),
                min_size=self.pool_min_size,
                max_size=self.pool_max_size,
                open=False,
            )
        except Exception as e:
            raise AdapterError(f"postgres async pool init error: {e}") from e

    @asynccontextmanager
    async def _connect_async(self):
        conn = None
        self._init_async_pool()
        try:
            if self._async_pool is not None:
                await self._async_pool.open()
                async with self._async_pool.connection() as pooled_conn:
                    await self._apply_session_settings_async(pooled_conn)
                    yield pooled_conn
                    return
            conn = await self._connect_direct_async()
            await self._apply_session_settings_async(conn)
            yield conn
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass

    def _query(self, sql: str, params: object) -> List[Dict[str, Any]]:
        assert_query_sql(sql)
        assert_allowed_tables(sql, self.allow_tables)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, normalize_params(params))
                return self._fetch_rows(cur)

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
            raise AdapterError("postgres transaction target requires non-empty list of ops")
        with self._connect() as conn:
            results: List[Any] = []
            try:
                with conn.cursor() as cur:
                    for op in ops:
                        if not isinstance(op, dict):
                            raise AdapterError("postgres transaction op must be dict")
                        verb = str(op.get("verb") or "").strip().lower()
                        sql = str(op.get("sql") or "")
                        params = normalize_params(op.get("params"))
                        if verb == "query":
                            assert_query_sql(sql)
                            assert_allowed_tables(sql, self.allow_tables)
                            cur.execute(sql, params)
                            results.append(self._fetch_rows(cur))
                        elif verb == "execute":
                            assert_execute_sql(sql, allow_write=self.allow_write)
                            assert_allowed_tables(sql, self.allow_tables)
                            cur.execute(sql, params)
                            rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                            lastrowid = getattr(cur, "lastrowid", None)
                            results.append({"rows_affected": rows_affected, "lastrowid": lastrowid})
                        else:
                            raise AdapterError(f"unsupported postgres transaction op verb: {verb}")
                conn.commit()
                return {"ok": True, "results": results}
            except Exception as e:
                conn.rollback()
                if isinstance(e, AdapterError):
                    raise
                raise AdapterError(f"postgres transaction error: {e}") from e

    async def _query_async(self, sql: str, params: object) -> List[Dict[str, Any]]:
        assert_query_sql(sql)
        assert_allowed_tables(sql, self.allow_tables)
        async with self._connect_async() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, normalize_params(params))
                return await self._fetch_rows_async(cur)

    async def _execute_async(self, sql: str, params: object) -> Dict[str, Any]:
        assert_execute_sql(sql, allow_write=self.allow_write)
        assert_allowed_tables(sql, self.allow_tables)
        async with self._connect_async() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, normalize_params(params))
                rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                lastrowid = getattr(cur, "lastrowid", None)
            await conn.commit()
            return {"rows_affected": rows_affected, "lastrowid": lastrowid}

    async def _transaction_async(self, ops: object) -> Dict[str, Any]:
        if not isinstance(ops, list) or not ops:
            raise AdapterError("postgres transaction target requires non-empty list of ops")
        async with self._connect_async() as conn:
            results: List[Any] = []
            try:
                async with conn.cursor() as cur:
                    for op in ops:
                        if not isinstance(op, dict):
                            raise AdapterError("postgres transaction op must be dict")
                        verb = str(op.get("verb") or "").strip().lower()
                        sql = str(op.get("sql") or "")
                        params = normalize_params(op.get("params"))
                        if verb == "query":
                            assert_query_sql(sql)
                            assert_allowed_tables(sql, self.allow_tables)
                            await cur.execute(sql, params)
                            results.append(await self._fetch_rows_async(cur))
                        elif verb == "execute":
                            assert_execute_sql(sql, allow_write=self.allow_write)
                            assert_allowed_tables(sql, self.allow_tables)
                            await cur.execute(sql, params)
                            rows_affected = int(cur.rowcount if cur.rowcount is not None else 0)
                            lastrowid = getattr(cur, "lastrowid", None)
                            results.append({"rows_affected": rows_affected, "lastrowid": lastrowid})
                        else:
                            raise AdapterError(f"unsupported postgres transaction op verb: {verb}")
                await conn.commit()
                return {"ok": True, "results": results}
            except Exception as e:
                await conn.rollback()
                if isinstance(e, AdapterError):
                    raise
                raise AdapterError(f"postgres transaction error: {e}") from e

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in {"query", "execute", "transaction"}:
            raise AdapterError(f"unsupported postgres target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("postgres transaction missing ops argument")
            return self._transaction(args[0])
        if not args:
            raise AdapterError("postgres adapter missing sql argument")
        sql = str(args[0] or "")
        params = args[1] if len(args) > 1 else None
        if verb == "query":
            return self._query(sql, params)
        return self._execute(sql, params)

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        if verb not in {"query", "execute", "transaction"}:
            raise AdapterError(f"unsupported postgres target: {target}")
        if verb == "transaction":
            if not args:
                raise AdapterError("postgres transaction missing ops argument")
            return await self._transaction_async(args[0])
        if not args:
            raise AdapterError("postgres adapter missing sql argument")
        sql = str(args[0] or "")
        params = args[1] if len(args) > 1 else None
        if verb == "query":
            return await self._query_async(sql, params)
        return await self._execute_async(sql, params)

    # Async-ready note: when RuntimeEngine gets async adapter dispatch, this class
    # can add an AsyncConnection/AsyncConnectionPool variant with identical verb contracts.
