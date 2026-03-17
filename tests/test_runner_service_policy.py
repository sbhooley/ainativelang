"""
Tests for optional policy-gated execution on the runner service /run endpoint.

Covers:
- /run without policy works as before
- /run with policy and compliant IR executes normally
- /run with policy and violating IR returns 403 with structured policy errors
- both code-input and IR-input paths
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.runtime_runner_service import app

client = TestClient(app)

SIMPLE_CORE_CODE = "L1: R core.ADD 2 3 ->x J x\n"
HTTP_CODE = 'S core web /api\nE /ping G ->L1 ->out\nL1: R http.Get "https://example.com" ->out J out\n'

_RUN_OPTS = {"execution_mode": "graph-preferred", "limits": {"max_steps": 50}}


def test_run_without_policy_unchanged():
    resp = client.post("/run", json={"code": SIMPLE_CORE_CODE, **_RUN_OPTS})
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert "out" in body


def test_run_with_empty_policy_passes():
    resp = client.post("/run", json={"code": SIMPLE_CORE_CODE, "policy": {}, **_RUN_OPTS})
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert "out" in body


def test_run_with_compliant_policy_executes():
    resp = client.post(
        "/run",
        json={
            "code": SIMPLE_CORE_CODE,
            "policy": {"forbidden_adapters": ["http", "fs"]},
            **_RUN_OPTS,
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert "out" in body


def test_run_with_violating_policy_returns_403():
    resp = client.post(
        "/run",
        json={
            "code": HTTP_CODE,
            "strict": False,
            "policy": {"forbidden_adapters": ["http"]},
        },
    )
    assert resp.status_code == 403
    body = resp.json()
    detail = body.get("detail", body)
    assert detail["ok"] is False
    assert detail["error"] == "policy_violation"
    errors = detail["policy_errors"]
    assert isinstance(errors, list) and len(errors) >= 1
    assert errors[0]["code"] == "POLICY_ADAPTER_FORBIDDEN"
    assert errors[0]["data"]["adapter"] == "http"
    assert "trace_id" in detail


def test_run_policy_violation_does_not_execute():
    resp = client.post(
        "/run",
        json={
            "code": HTTP_CODE,
            "strict": False,
            "policy": {"forbidden_adapters": ["http"]},
        },
    )
    assert resp.status_code == 403
    assert "out" not in resp.json().get("detail", resp.json())


def test_run_with_ir_input_and_policy_compliant():
    from compiler_v2 import AICodeCompiler

    compiler = AICodeCompiler()
    ir = compiler.compile(SIMPLE_CORE_CODE)
    resp = client.post(
        "/run",
        json={
            "ir": ir,
            "policy": {"forbidden_adapters": ["http"]},
            **_RUN_OPTS,
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert "out" in body


def test_run_with_ir_input_and_policy_violating():
    from compiler_v2 import AICodeCompiler

    compiler = AICodeCompiler()
    ir = compiler.compile(HTTP_CODE)
    resp = client.post(
        "/run",
        json={
            "ir": ir,
            "policy": {"forbidden_adapters": ["http"]},
        },
    )
    assert resp.status_code == 403
    detail = resp.json().get("detail", resp.json())
    assert detail["ok"] is False
    assert detail["error"] == "policy_violation"


def test_run_policy_multiple_violations():
    code = 'L1: R http.Get "https://example.com" ->a R fs.Read "file.txt" ->b J b\n'
    resp = client.post(
        "/run",
        json={
            "code": code,
            "strict": False,
            "execution_mode": "steps-only",
            "policy": {"forbidden_adapters": ["http", "fs"]},
        },
    )
    assert resp.status_code == 403
    detail = resp.json().get("detail", resp.json())
    errors = detail["policy_errors"]
    adapters_found = {e["data"]["adapter"] for e in errors}
    assert "http" in adapters_found
    assert "fs" in adapters_found
