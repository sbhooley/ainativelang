import json
from pathlib import Path

from tooling.audit_jsonl_verify import verify_jsonl_file, verify_jsonl_lines


def _hash_line(rec: dict) -> str:
    import hashlib

    base = {k: v for k, v in rec.items() if k != "event_hash"}
    blob = json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def test_verify_audit_trail_round_trip(tmp_path: Path) -> None:
    rec = {
        "trace_id": "t1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "label_id": "L1",
        "node_id": "n1",
        "event": "test",
        "args": [],
        "output": None,
    }
    rec["event_hash"] = _hash_line(rec)
    lines = [json.dumps(rec, ensure_ascii=False)]
    v, s, _ln, err = verify_jsonl_lines(lines)
    assert err == []
    assert v == 1
    assert s == 0


def test_verify_rejects_tamper(tmp_path: Path) -> None:
    rec = {
        "trace_id": "t1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "label_id": "L1",
        "node_id": "n1",
        "event": "test",
        "args": [],
        "output": None,
    }
    rec["event_hash"] = _hash_line(rec)
    rec["event"] = "tampered"
    lines = [json.dumps(rec, ensure_ascii=False)]
    v, s, ln, err = verify_jsonl_lines(lines)
    assert err
    assert v == 0


def test_verify_skips_trajectory_like_lines() -> None:
    traj = {"step_id": 0, "label": "L1", "operation": "core.ADD", "outcome": "ok"}
    lines = [json.dumps(traj, ensure_ascii=False)]
    v, s, _ln, err = verify_jsonl_lines(lines)
    assert err == []
    assert v == 0
    assert s == 1


def test_verify_jsonl_file_cli_path(tmp_path: Path) -> None:
    rec = {
        "trace_id": None,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "label_id": None,
        "node_id": None,
        "event": "e",
        "args": [],
        "output": None,
    }
    rec["event_hash"] = _hash_line(rec)
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    assert verify_jsonl_file(p) == 0
