"""Tests for structured audit logging in the runner service."""
import json
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.runtime_runner_service as _runner_mod
from scripts.runtime_runner_service import _run_guarded, PolicyViolationError


def _trace_id():
    return str(uuid.uuid4())


def setup_module():
    _runner_mod._SERVER_GRANT = {
        "allowed_adapters": ["core", "ext"],
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": {"max_steps": 500},
        "adapter_constraints": {},
    }


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list = []

    def emit(self, record):
        try:
            self.records.append(json.loads(record.getMessage()))
        except (json.JSONDecodeError, TypeError):
            pass


def _capture_logs():
    cap = _LogCapture()
    logger = logging.getLogger("ainl.runner")
    logger.addHandler(cap)
    return cap, logger


def test_run_start_event_emitted():
    cap, logger = _capture_logs()
    try:
        _run_guarded({"code": "L1: Set a 1 J a\n"}, _trace_id())
        starts = [r for r in cap.records if r.get("event") == "run_start"]
        assert len(starts) >= 1
        ev = starts[0]
        assert "ts" in ev
        assert "trace_id" in ev
        assert "limits_summary" in ev
        assert isinstance(ev["limits_summary"], dict)
        assert "policy_present" in ev
    finally:
        logger.removeHandler(cap)


def test_adapter_call_has_ts_and_status():
    cap, logger = _capture_logs()
    try:
        _run_guarded(
            {"code": "L1: R core.ADD 1 2 ->x J x\n"},
            _trace_id(),
        )
        calls = [r for r in cap.records if r.get("event") == "adapter_call"]
        assert len(calls) >= 1
        ev = calls[0]
        assert "ts" in ev
        assert ev["status"] == "ok"
        assert "result_hash" in ev
        assert ev["result_hash"] is not None
        assert len(ev["result_hash"]) == 64  # SHA-256 hex
    finally:
        logger.removeHandler(cap)


def test_adapter_call_args_redacted():
    cap, logger = _capture_logs()
    try:
        _run_guarded(
            {
                "code": "L1: R ext.echo secret_token ->x J x\n",
                "adapters": {"enable": ["ext"]},
            },
            _trace_id(),
        )
        calls = [r for r in cap.records if r.get("event") == "adapter_call"]
        assert len(calls) >= 1
        for call in calls:
            assert "args" in call
    finally:
        logger.removeHandler(cap)


def test_run_complete_event_has_trace_id():
    cap, logger = _capture_logs()
    try:
        tid = _trace_id()
        _run_guarded({"code": "L1: Set a 1 J a\n"}, tid)
        completes = [r for r in cap.records if r.get("event") == "run_complete"]
        assert len(completes) >= 1
        assert completes[0]["trace_id"] == tid
    finally:
        logger.removeHandler(cap)


def test_policy_rejected_includes_replay_artifact_id():
    _runner_mod._SERVER_GRANT = {
        "allowed_adapters": ["core"],
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": ["network"],
        "limits": {"max_steps": 500},
        "adapter_constraints": {},
    }
    from fastapi.testclient import TestClient
    from scripts.runtime_runner_service import app

    client = TestClient(app)
    cap, logger = _capture_logs()
    try:
        resp = client.post("/run", json={
            "code": "L1: R http.Get example.com ->x J x\n",
            "replay_artifact_id": "art-999",
        })
        assert resp.status_code == 403
        rejected = [r for r in cap.records if r.get("event") == "policy_rejected"]
        assert len(rejected) >= 1
        assert rejected[0].get("replay_artifact_id") == "art-999"
    finally:
        logger.removeHandler(cap)
        setup_module()
