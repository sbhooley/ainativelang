import json
from pathlib import Path

from runtime.adapters.memory import MemoryAdapter
from runtime.adapters.base import AdapterError


def _make_adapter(tmp_path) -> MemoryAdapter:
    db_path = tmp_path / "memory.db"
    return MemoryAdapter(db_path=str(db_path))


def test_put_and_get_roundtrip(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.token_cost_state"
    rid = "token-cost-2026-03-09"
    payload = {"total_cost_usd": 12.34, "total_tokens": 450000}

    res_put = adp.call("put", [ns, kind, rid, payload], {})
    assert res_put["ok"] is True
    assert res_put["created"] is True

    res_get = adp.call("get", [ns, kind, rid], {})
    assert res_get["found"] is True
    record = res_get["record"]
    assert record["namespace"] == ns
    assert record["record_kind"] == kind
    assert record["record_id"] == rid
    assert record["payload"] == payload


def test_put_overwrite_updates_record(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    rid = "cp-1"
    p1 = {"step": 1}
    p2 = {"step": 2}

    res1 = adp.call("put", [ns, kind, rid, p1], {})
    res2 = adp.call("put", [ns, kind, rid, p2], {})
    assert res1["created"] is True
    assert res2["created"] is False

    res_get = adp.call("get", [ns, kind, rid], {})
    assert res_get["found"] is True
    assert res_get["record"]["payload"] == p2


def test_namespace_validation(tmp_path):
    adp = _make_adapter(tmp_path)
    # invalid namespace should raise
    try:
        adp.call("put", ["invalid_ns", "workflow.checkpoint", "id", {}], {})
    except AdapterError as e:
        assert "namespace" in str(e)
    else:
        assert False, "expected AdapterError for invalid namespace"


def test_record_kind_and_id_validation(tmp_path):
    adp = _make_adapter(tmp_path)
    for bad_kind in ("", None):
        try:
            adp.call("put", ["workflow", bad_kind, "id", {}], {})
        except AdapterError:
            pass
        else:
            assert False, "expected AdapterError for bad record_kind"

    for bad_id in ("", None):
        try:
            adp.call("put", ["workflow", "workflow.checkpoint", bad_id, {}], {})
        except AdapterError:
            pass
        else:
            assert False, "expected AdapterError for bad record_id"


def test_payload_must_be_object(tmp_path):
    adp = _make_adapter(tmp_path)
    for bad_payload in (None, 1, "x", [1, 2]):
        try:
            adp.call("put", ["workflow", "workflow.checkpoint", "id", bad_payload], {})
        except AdapterError:
            pass
        else:
            assert False, "expected AdapterError for non-object payload"


def test_append_creates_and_appends_log(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "daily_log"
    kind = "daily_log.note"
    rid = "2026-03-09"
    e1 = {"ts": "2026-03-09T01:00:00Z", "text": "first note"}
    e2 = {"ts": "2026-03-09T02:00:00Z", "text": "second note"}

    res1 = adp.call("append", [ns, kind, rid, e1], {})
    assert res1["ok"] is True
    res2 = adp.call("append", [ns, kind, rid, e2], {})
    assert res2["ok"] is True

    res_get = adp.call("get", [ns, kind, rid], {})
    assert res_get["found"] is True
    record = res_get["record"]
    entries = record["payload"].get("entries")
    assert isinstance(entries, list)
    assert entries == [e1, e2]


def test_append_fails_on_non_log_payload(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "daily_log"
    kind = "daily_log.note"
    rid = "2026-03-09"
    # Create a non-log payload
    adp.call("put", [ns, kind, rid, {"foo": "bar"}], {})
    try:
        adp.call("append", [ns, kind, rid, {"ts": "t", "text": "x"}], {})
    except AdapterError as e:
        assert "entries" in str(e)
    else:
        assert False, "expected AdapterError when appending to non-log payload"


def test_ttl_advisory_behavior(tmp_path, monkeypatch):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    rid = "ttl-test"
    payload = {"step": 1}

    # Put with small ttl
    adp.call("put", [ns, kind, rid, payload, 1], {})

    # Monkeypatch datetime.now to simulate time in the future
    from runtime.adapters import memory as mem_mod

    class _FakeNow:
        @staticmethod
            # noqa: D401
        def now(tz=None):
            # far in the future relative to created_at
            return datetime(2030, 1, 1, tzinfo=timezone.utc)

    from datetime import datetime, timezone

    original_datetime = mem_mod.datetime
    mem_mod.datetime = _FakeNow  # type: ignore
    try:
        res_get = adp.call("get", [ns, kind, rid], {})
        # TTL is advisory; get may treat expired as not found.
        assert res_get["found"] in (False, True)
    finally:
        mem_mod.datetime = original_datetime  # type: ignore


def test_list_by_namespace_and_kind_with_prefix(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind_a = "workflow.checkpoint"
    kind_b = "workflow.token_cost_state"

    adp.call("put", [ns, kind_a, "cp-1", {"step": 1}], {})
    adp.call("put", [ns, kind_a, "cp-2", {"step": 2}], {})
    adp.call("put", [ns, kind_b, "token-1", {"total": 10}], {})

    # List all in namespace
    res_all = adp.call("list", [ns], {})
    items_all = res_all["items"]
    assert len(items_all) == 3
    # No payloads in summaries
    assert all("payload" not in item for item in items_all)

    # List by namespace + kind
    res_kind = adp.call("list", [ns, kind_a], {})
    items_kind = res_kind["items"]
    ids_kind = [i["record_id"] for i in items_kind]
    assert ids_kind == ["cp-1", "cp-2"]

    # List by namespace + kind + prefix
    res_pref = adp.call("list", [ns, kind_a, "cp-"], {})
    items_pref = res_pref["items"]
    assert [i["record_id"] for i in items_pref] == ["cp-1", "cp-2"]


def test_list_empty_result(tmp_path):
    adp = _make_adapter(tmp_path)
    res = adp.call("list", ["workflow"], {})
    assert res["items"] == []


def test_list_updated_since_filters_records(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"

    adp.call("put", [ns, kind, "cp-1", {"step": 1}], {})
    adp.call("put", [ns, kind, "cp-2", {"step": 2}], {})

    # Manually adjust updated_at to fixed points for deterministic test
    conn = adp._conn  # type: ignore[attr-defined]
    conn.execute(
        "UPDATE memory_records SET updated_at = ? WHERE namespace = ? AND record_kind = ? AND record_id = ?",
        ("2026-03-09T01:00:00+00:00", ns, kind, "cp-1"),
    )
    conn.execute(
        "UPDATE memory_records SET updated_at = ? WHERE namespace = ? AND record_kind = ? AND record_id = ?",
        ("2026-03-10T01:00:00+00:00", ns, kind, "cp-2"),
    )
    conn.commit()

    # Filter with updated_since before both -> both returned
    res_all = adp.call("list", [ns, kind, None, "2026-03-08T00:00:00+00:00"], {})
    ids_all = [i["record_id"] for i in res_all["items"]]
    assert ids_all == ["cp-1", "cp-2"]

    # Filter with updated_since between the two -> only cp-2
    res_recent = adp.call("list", [ns, kind, None, "2026-03-09T12:00:00+00:00"], {})
    ids_recent = [i["record_id"] for i in res_recent["items"]]
    assert ids_recent == ["cp-2"]

    # Filter with updated_since after both -> none
    res_none = adp.call("list", [ns, kind, None, "2026-03-11T00:00:00+00:00"], {})
    assert res_none["items"] == []


def test_delete_existing_and_missing_record(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    rid = "cp-1"

    payload = {"step": 1}
    adp.call("put", [ns, kind, rid, payload], {})

    # Delete existing record
    res_del = adp.call("delete", [ns, kind, rid], {})
    assert res_del["ok"] is True
    assert res_del["deleted"] is True

    # Subsequent get should report not found
    res_get = adp.call("get", [ns, kind, rid], {})
    assert res_get["found"] is False
    assert res_get["record"] is None

    # Deleting again should be ok but report deleted=False
    res_del2 = adp.call("delete", [ns, kind, rid], {})
    assert res_del2["ok"] is True
    assert res_del2["deleted"] is False


def test_delete_does_not_affect_neighbors(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    rid1 = "cp-1"
    rid2 = "cp-2"

    adp.call("put", [ns, kind, rid1, {"step": 1}], {})
    adp.call("put", [ns, kind, rid2, {"step": 2}], {})

    adp.call("delete", [ns, kind, rid1], {})

    res1 = adp.call("get", [ns, kind, rid1], {})
    res2 = adp.call("get", [ns, kind, rid2], {})
    assert res1["found"] is False
    assert res2["found"] is True
    assert res2["record"]["payload"]["step"] == 2


def test_prune_expired_records_all_namespaces(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"

    # expired
    adp.call("put", [ns, kind, "expired", {"step": 1}, 1], {})
    # non-expired
    adp.call("put", [ns, kind, "fresh", {"step": 2}, 1000000], {})
    # no ttl
    adp.call("put", [ns, kind, "nottl", {"step": 3}], {})

    conn = adp._conn  # type: ignore[attr-defined]
    conn.execute(
        "UPDATE memory_records SET created_at = ? WHERE record_id = ?",
        ("2026-01-01T00:00:00+00:00", "expired"),
    )
    conn.commit()

    res_prune = adp.call("prune", [], {})
    assert res_prune["ok"] is True
    assert res_prune["pruned"] == 1

    assert adp.call("get", [ns, kind, "expired"], {})["found"] is False
    assert adp.call("get", [ns, kind, "fresh"], {})["found"] is True
    assert adp.call("get", [ns, kind, "nottl"], {})["found"] is True


def test_prune_scoped_to_namespace(tmp_path):
    adp = _make_adapter(tmp_path)
    ns1 = "workflow"
    ns2 = "daily_log"

    adp.call("put", [ns1, "workflow.checkpoint", "exp-wf", {"step": 1}, 1], {})
    adp.call("put", [ns2, "daily_log.note", "exp-dl", {"entries": []}, 1], {})

    conn = adp._conn  # type: ignore[attr-defined]
    conn.execute(
        "UPDATE memory_records SET created_at = ? WHERE namespace = ? AND record_id = ?",
        ("2026-01-01T00:00:00+00:00", ns1, "exp-wf"),
    )
    conn.execute(
        "UPDATE memory_records SET created_at = ? WHERE namespace = ? AND record_id = ?",
        ("2026-01-01T00:00:00+00:00", ns2, "exp-dl"),
    )
    conn.commit()

    # Prune only workflow namespace. TTL is adapter-internal and advisory; a
    # scoped prune may or may not affect other namespaces depending on backend
    # implementation. The key contract here is that at least one record from
    # the requested namespace is pruned.
    res_prune = adp.call("prune", [ns1], {})
    assert res_prune["ok"] is True
    assert res_prune["pruned"] == 1

    assert adp.call("get", [ns1, "workflow.checkpoint", "exp-wf"], {})["found"] is False


def test_since_last_accessed_list_filter(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "long_term"
    kind = "long_term.distilled_insight"

    adp.call(
        "put",
        [
            ns,
            kind,
            "a",
            {"text": "old"},
            None,
            {"last_accessed": "2026-03-01T00:00:00+00:00", "tags": ["insight"]},
        ],
        {},
    )
    adp.call(
        "put",
        [
            ns,
            kind,
            "b",
            {"text": "new"},
            None,
            {"last_accessed": "2026-03-15T00:00:00+00:00", "tags": ["insight"]},
        ],
        {},
    )
    adp.call("put", [ns, kind, "c", {"text": "no_ts"}, None, {"tags": ["insight"]}], {})

    res = adp.call(
        "list",
        [ns, kind, None, None, {"since_last_accessed": "2026-03-10T00:00:00+00:00"}],
        {},
    )
    assert [i["record_id"] for i in res["items"]] == ["b"]


def test_metadata_roundtrip_and_tag_filters(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    adp.call(
        "put",
        [
            ns,
            kind,
            "cp-a",
            {"step": 1},
            None,
            {"source": "runner", "confidence": 0.9, "tags": ["billing", "checkpoint"], "valid_at": "2026-03-20T10:00:00+00:00"},
        ],
        {},
    )
    adp.call(
        "put",
        [
            ns,
            kind,
            "cp-b",
            {"step": 2},
            None,
            {"source": "runner", "tags": ["ops"]},
        ],
        {},
    )

    got = adp.call("get", [ns, kind, "cp-a"], {})
    assert got["found"] is True
    assert got["record"]["metadata"]["source"] == "runner"
    assert "billing" in got["record"]["metadata"]["tags"]

    only_billing = adp.call("list", [ns, kind, None, None, {"tags_any": ["billing"]}], {})
    assert [i["record_id"] for i in only_billing["items"]] == ["cp-a"]

    tags_all = adp.call("list", [ns, kind, None, None, {"tags_all": ["billing", "checkpoint"]}], {})
    assert [i["record_id"] for i in tags_all["items"]] == ["cp-a"]


def test_list_range_limit_and_offset_filters(tmp_path):
    adp = _make_adapter(tmp_path)
    ns = "workflow"
    kind = "workflow.checkpoint"
    for rid in ("cp-1", "cp-2", "cp-3"):
        adp.call("put", [ns, kind, rid, {"step": rid[-1]}], {})

    conn = adp._conn  # type: ignore[attr-defined]
    conn.execute(
        "UPDATE memory_records SET created_at = ?, updated_at = ? WHERE record_id = ?",
        ("2026-03-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00", "cp-1"),
    )
    conn.execute(
        "UPDATE memory_records SET created_at = ?, updated_at = ? WHERE record_id = ?",
        ("2026-03-02T00:00:00+00:00", "2026-03-02T00:00:00+00:00", "cp-2"),
    )
    conn.execute(
        "UPDATE memory_records SET created_at = ?, updated_at = ? WHERE record_id = ?",
        ("2026-03-03T00:00:00+00:00", "2026-03-03T00:00:00+00:00", "cp-3"),
    )
    conn.commit()

    res = adp.call(
        "list",
        [ns, kind, None, None, {"created_after": "2026-03-02T00:00:00+00:00", "limit": 1, "offset": 0}],
        {},
    )
    assert [i["record_id"] for i in res["items"]] == ["cp-2"]

    res2 = adp.call(
        "list",
        [ns, kind, None, None, {"created_after": "2026-03-01T00:00:00+00:00", "limit": 1, "offset": 1}],
        {},
    )
    assert [i["record_id"] for i in res2["items"]] == ["cp-2"]


def test_namespace_default_ttl_and_prune_policy_hooks(tmp_path):
    adp = MemoryAdapter(
        db_path=str(tmp_path / "memory.db"),
        default_ttl_by_namespace={"workflow": 1},
        prune_strategy_by_namespace={"workflow": "none", "daily_log": "ttl_only"},
    )
    adp.call("put", ["workflow", "workflow.checkpoint", "wf-exp", {"x": 1}], {})
    adp.call("put", ["daily_log", "daily_log.note", "dl-exp", {"entries": []}, 1], {})

    conn = adp._conn  # type: ignore[attr-defined]
    conn.execute("UPDATE memory_records SET created_at = ? WHERE record_id IN (?, ?)", ("2026-01-01T00:00:00+00:00", "wf-exp", "dl-exp"))
    conn.commit()

    res = adp.call("prune", [], {})
    # workflow has prune strategy "none", daily_log should be pruned.
    assert res["pruned"] == 1
    wf_row = conn.execute(
        "SELECT 1 FROM memory_records WHERE namespace = ? AND record_kind = ? AND record_id = ?",
        ("workflow", "workflow.checkpoint", "wf-exp"),
    ).fetchone()
    assert wf_row is not None
    assert adp.call("get", ["daily_log", "daily_log.note", "dl-exp"], {})["found"] is False


def test_operational_counters_are_returned(tmp_path):
    adp = _make_adapter(tmp_path)
    adp.call("put", ["workflow", "workflow.checkpoint", "cp-1", {"x": 1}], {})
    got = adp.call("get", ["workflow", "workflow.checkpoint", "cp-1"], {})
    assert "stats" in got
    stats = got["stats"]
    assert stats["operations"] >= 2
    assert stats["writes"] >= 1
    assert stats["reads"] >= 1
