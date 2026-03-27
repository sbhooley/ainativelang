import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.postgres import PostgresAdapter
from runtime.adapters.base import AdapterError


class _FakeCursor:
    def __init__(self):
        self.rowcount = 0
        self.lastrowid = None
        self.description = [("id",), ("name",)]
        self._rows = []

    def execute(self, sql, params=()):
        stmt = str(sql).strip().lower()
        if stmt.startswith("set statement_timeout"):
            return
        if stmt.startswith("select"):
            self._rows = [{"id": 1, "name": "a"}]
            self.rowcount = 1
            return
        if "bad_sql" in stmt:
            raise RuntimeError("boom")
        self.rowcount = 1
        self.lastrowid = 7

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self):
        self._cursor = _FakeCursor()
        self.did_commit = False
        self.did_rollback = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.did_commit = True

    def rollback(self):
        self.did_rollback = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _install_fake_psycopg(monkeypatch):
    fake_module = SimpleNamespace(connect=lambda **kwargs: _FakeConn())
    monkeypatch.setitem(sys.modules, "psycopg", fake_module)


def test_postgres_query_and_execute_contract(monkeypatch):
    _install_fake_psycopg(monkeypatch)
    adp = PostgresAdapter(dsn="postgresql://x", allow_write=True, allow_tables=["users"])
    rows = adp.call("query", ["SELECT id, name FROM users WHERE id = %s", [1]], {})
    assert isinstance(rows, list)
    assert rows[0]["name"] == "a"
    out = adp.call("execute", ["UPDATE users SET name = %s WHERE id = %s", ["b", 1]], {})
    assert out["rows_affected"] == 1


def test_postgres_blocks_write_when_not_allowed(monkeypatch):
    _install_fake_psycopg(monkeypatch)
    adp = PostgresAdapter(dsn="postgresql://x", allow_write=False)
    try:
        adp.call("execute", ["UPDATE users SET name = 'x'"], {})
        assert False, "expected write block"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allow_write" in str(e)


def test_postgres_transaction_rolls_back_on_error(monkeypatch):
    _install_fake_psycopg(monkeypatch)
    adp = PostgresAdapter(dsn="postgresql://x", allow_write=True)
    try:
        adp.call(
            "transaction",
            [[{"verb": "execute", "sql": "UPDATE users SET x = 1"}, {"verb": "execute", "sql": "UPDATE bad_sql SET x = 2"}]],
            {},
        )
        assert False, "expected transaction failure"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "transaction error" in str(e) or "boom" in str(e)
