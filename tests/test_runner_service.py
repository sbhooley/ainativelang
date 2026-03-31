import os
import sys
import tempfile
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.runtime_runner_service as _runner_mod
from scripts.runtime_runner_service import app

# Widen the server grant for integration tests so ext/fs/http adapters
# are allowed by the capability gate.  Production callers still cannot
# widen beyond whatever the real server grant allows.
_runner_mod._SERVER_GRANT = {
    "allowed_adapters": ["core", "ext", "http", "sqlite", "fs", "tools",
                          "cache", "queue", "txn", "auth", "wasm"],
    "forbidden_adapters": [],
    "forbidden_effects": [],
    "forbidden_effect_tiers": [],
    "forbidden_privilege_tiers": [],
    "limits": {},
    "adapter_constraints": {},
}

client = TestClient(app)


def test_runner_service_health_ready():
    h = client.get("/health")
    r = client.get("/ready")
    assert h.status_code == 200 and h.json()["status"] == "ok"
    assert r.status_code == 200 and "ready" in r.json()


def test_runner_service_does_not_expose_storefront_business_api():
    # Runtime runner is execution API only; storefront business routes are out of scope.
    resp = client.get("/api/products")
    assert resp.status_code == 404


def test_runner_sync_run_success_and_trace():
    resp = client.post(
        "/run",
        json={
            "code": "L1: R core.ADD 2 3 ->x J x\n",
            "trace": True,
            "execution_mode": "graph-preferred",
            "limits": {"max_steps": 50},
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["out"] == 5
    assert body["trace_id"]
    assert "replay_artifact_id" in body
    assert isinstance(body.get("trace", []), list)


def test_runner_enqueue_and_result():
    enq = client.post("/enqueue", json={"code": "L1: R core.ADD 20 22 ->x J x\n"})
    assert enq.status_code == 200
    job_id = enq.json()["job_id"]
    for _ in range(30):
        res = client.get(f"/result/{job_id}")
        body = res.json()
        if body.get("status") == "done":
            assert body["result"]["ok"] is True
            assert body["result"]["out"] == 42
            return
        time.sleep(0.05)
    assert False, "job did not complete in time"


def test_runner_limit_failure():
    resp = client.post("/run", json={"code": "L1: Set a 1 Set b 2 Set c 3 J c\n", "limits": {"max_steps": 2}})
    body = resp.json()
    assert body["ok"] is False
    assert "max_steps exceeded" in body["error"]
    assert isinstance(body.get("error_structured"), dict)
    assert body["error_structured"].get("code") == "RUNTIME_MAX_STEPS"


def test_runner_record_and_replay_with_ext():
    code = "L1: R ext.echo 7 ->x J x\n"
    live = client.post(
        "/run",
        json={
            "code": code,
            "record_calls": True,
            "adapters": {"enable": ["ext"]},
        },
    ).json()
    assert live["ok"] is True
    calls = live.get("adapter_calls")
    assert isinstance(calls, list) and calls
    replay = client.post(
        "/run",
        json={
            "code": code,
            "replay_log": calls,
        },
    ).json()
    assert replay["ok"] is True
    assert replay["out"] == live["out"]


def test_runner_replay_artifact_and_redaction():
    code = "L1: R ext.echo Authorization BearerToken ->x J x\n"
    resp = client.post(
        "/run",
        json={
            "code": code,
            "record_calls": True,
            "adapters": {"enable": ["ext"]},
            "replay_artifact_id": "artifact-123",
            "trace": True,
        },
    ).json()
    assert resp["ok"] is True
    assert resp["replay_artifact_id"] == "artifact-123"
    calls = resp.get("adapter_calls", [])
    assert calls and calls[0]["args"][0] == "[REDACTED]"


def test_runner_fs_adapter_integration():
    with tempfile.TemporaryDirectory() as td:
        resp = client.post(
            "/run",
            json={
                "code": "L1: R fs.write note.txt hi ->a\nR fs.read note.txt ->b\nJ b\n",
                "execution_mode": "steps-only",
                "adapters": {"enable": ["fs"], "fs": {"root": td}},
            },
        ).json()
        assert resp["ok"] is True
        assert resp["out"] == "hi"


def test_runner_metrics_include_adapter_breakdown():
    # drive at least one adapter call
    client.post("/run", json={"code": "L1: R ext.echo 1 ->x J x\n", "adapters": {"enable": ["ext"]}})
    m = client.get("/metrics").json()
    assert "adapter_counts" in m
    assert "adapter_p95_duration_ms" in m
    assert "ext" in m["adapter_counts"]
