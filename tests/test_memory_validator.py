import json

from tooling import memory_validator as mv


def test_valid_memory_record_passes():
    record = {
        "namespace": "workflow",
        "record_kind": "workflow.checkpoint",
        "record_id": "cp-1",
        "created_at": "2026-03-09T01:00:00Z",
        "updated_at": "2026-03-09T01:00:00Z",
        "ttl_seconds": 3600,
        "payload": {"step": 1},
    }
    issues = mv.validate_memory_record(record)
    assert not any(i.kind == "error" for i in issues)


def test_missing_core_fields_fail():
    bad = {"namespace": "workflow", "payload": {}}
    issues = mv.validate_memory_record(bad)
    paths = {i.path for i in issues}
    assert "record_kind" in paths
    assert "record_id" in paths
    assert any(i.kind == "error" for i in issues)


def test_non_object_payload_fails():
    bad = {
        "namespace": "workflow",
        "record_kind": "workflow.checkpoint",
        "record_id": "cp-1",
        "payload": ["not", "object"],
    }
    issues = mv.validate_memory_record(bad)
    assert any(i.kind == "error" and i.path == "payload" for i in issues)


def test_namespace_whitelist_enforced():
    bad = {
        "namespace": "invalid_ns",
        "record_kind": "workflow.checkpoint",
        "record_id": "cp-1",
        "payload": {},
    }
    issues = mv.validate_memory_record(bad)
    assert any(i.kind == "error" and i.path == "namespace" for i in issues)


def test_ttl_must_be_int_or_null():
    bad = {
        "namespace": "workflow",
        "record_kind": "workflow.checkpoint",
        "record_id": "cp-1",
        "payload": {},
        "ttl_seconds": "not_int",
    }
    issues = mv.validate_memory_record(bad)
    assert any(i.kind == "error" and i.path == "ttl_seconds" for i in issues)


def test_namespace_kind_consistency_errors():
    bad = {
        "namespace": "daily_log",
        "record_kind": "workflow.checkpoint",
        "record_id": "cp-1",
        "payload": {"step": 1},
    }
    issues = mv.validate_memory_record(bad)
    assert any(i.kind == "error" and i.path == "namespace" for i in issues)


def test_array_of_records_reports_indexed_paths(tmp_path):
    records = [
        {
            "namespace": "workflow",
            "record_kind": "workflow.checkpoint",
            "record_id": "cp-1",
            "payload": {"step": 1},
        },
        {
            "namespace": "invalid_ns",
            "record_kind": "workflow.checkpoint",
            "record_id": "cp-2",
            "payload": {},
        },
    ]
    json_path = tmp_path / "records.json"
    json_path.write_text(json.dumps(records), encoding="utf-8")

    with json_path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    issues = mv.validate_records_obj(obj)
    # Second record should have an error with path prefix [1].
    assert any(i.kind == "error" and i.path.startswith("[1].") for i in issues)

