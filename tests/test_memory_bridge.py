import json
from pathlib import Path

from runtime.adapters.memory import MemoryAdapter
from tooling.memory_bridge import ExportOptions, export_records, import_records


def _make_db(tmp_path) -> str:
    return str(tmp_path / "memory.db")


def test_export_and_import_roundtrip(tmp_path):
    db_path = _make_db(tmp_path)
    # Seed with MemoryAdapter
    adp = MemoryAdapter(db_path=db_path)
    ns = "long_term"
    kind = "long_term.project_fact"
    rid = "fact-1"
    payload = {"text": "Backups must complete daily."}
    adp.call("put", [ns, kind, rid, payload], {})

    # Export
    opts = ExportOptions(db_path=db_path, namespaces=[ns], record_kinds=[kind])
    records = export_records(opts)
    assert len(records) == 1
    env = records[0]
    assert env["namespace"] == ns
    assert env["record_kind"] == kind
    assert env["record_id"] == rid
    assert env["payload"] == payload
    assert env["provenance"]["source_system"] == "ainl.memory"

    # Import into a fresh DB
    db_path2 = _make_db(tmp_path / "other")
    Path(db_path2).parent.mkdir(parents=True, exist_ok=True)
    result = import_records(db_path2, records)
    assert result.ok
    assert result.inserted == 1

    adp2 = MemoryAdapter(db_path=db_path2)
    res_get = adp2.call("get", [ns, kind, rid], {})
    assert res_get["found"] is True
    rec2 = res_get["record"]
    assert rec2["payload"]["text"] == payload["text"]
    # Bridge-layer provenance/flags are preserved under reserved keys in payload.
    assert "_provenance" in rec2["payload"]
    assert "_flags" in rec2["payload"]


def test_imported_provenance_roundtrips_via_payload(tmp_path):
    db_path = _make_db(tmp_path)
    records = [
        {
            "namespace": "long_term",
            "record_kind": "long_term.user_preference",
            "record_id": "pref-1",
            "created_at": "2026-03-09T01:00:00Z",
            "updated_at": "2026-03-09T01:00:00Z",
            "ttl_seconds": None,
            "payload": {"key": "theme", "value": "dark"},
            "provenance": {
                "source_system": "obsidian",
                "origin_uri": "file://vault/prefs/theme.md",
                "authored_by": "human",
                "confidence": None,
            },
            "flags": {
                "authoritative": True,
                "ephemeral": False,
                "curated": True,
            },
        }
    ]

    # Import
    result = import_records(db_path, records)
    assert result.ok
    assert result.inserted == 1

    # Read via MemoryAdapter and confirm payload contains preserved provenance/flags.
    adp = MemoryAdapter(db_path=db_path)
    res_get = adp.call(
        "get",
        ["long_term", "long_term.user_preference", "pref-1"],
        {},
    )
    assert res_get["found"] is True
    rec = res_get["record"]
    payload = rec["payload"]
    assert payload.get("key") == "theme"
    assert payload.get("_provenance", {}).get("source_system") == "obsidian"
    assert payload.get("_flags", {}).get("authoritative") is True


def test_import_rejects_invalid_records(tmp_path):
    db_path = _make_db(tmp_path)
    bad_records = [
        {
            "namespace": "invalid_ns",
            "record_kind": "long_term.project_fact",
            "record_id": "fact-1",
            "payload": {},
        }
    ]
    result = import_records(db_path, bad_records)
    assert not result.ok
    assert result.inserted == 0
    assert result.updated == 0
    assert result.errors

