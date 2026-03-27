import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.postgres.sql_guard import assert_execute_sql, assert_query_sql
from runtime.adapters.base import AdapterError


def test_query_sql_allows_leading_comments_and_explain_select():
    assert_query_sql("-- note\nSELECT 1")
    assert_query_sql("/* block */ EXPLAIN SELECT 1")
    assert_query_sql("WITH x AS (SELECT 1) SELECT * FROM x")


def test_execute_sql_enforces_write_in_cte():
    assert_execute_sql("WITH t AS (UPDATE users SET n = 1 RETURNING id) SELECT id FROM t", allow_write=True)
    with pytest.raises(AdapterError):
        assert_execute_sql("WITH t AS (SELECT 1) SELECT * FROM t", allow_write=True)
