import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterError, AdapterRegistry
from adapters.ptc_runner import PtcRunnerAdapter


def test_ptc_runner_mock_success_envelope():
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"
        reg = AdapterRegistry(allowed=["ptc_runner"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))
        out = reg.call("ptc_runner", "run", ["(+ 1 2)", "{total :float}", 5], {"session": "x"})
        assert out["ok"] is True
        assert out["runtime"] == "ptc_runner"
        assert isinstance(out.get("traces"), list)
        assert isinstance(out.get("result"), dict)
        assert isinstance(out.get("beam_metrics"), dict)
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock


def test_ptc_runner_requires_lisp_argument():
    reg = AdapterRegistry(allowed=["ptc_runner"])
    reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))
    try:
        reg.call("ptc_runner", "run", [], {})
    except AdapterError as e:
        assert "requires at least lisp" in str(e).lower()
    else:
        raise AssertionError("expected AdapterError")


def test_ptc_runner_blocks_when_disabled():
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"
        reg = AdapterRegistry(allowed=["ptc_runner"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=False))
        try:
            reg.call("ptc_runner", "run", ["(+ 1 2)"], {})
        except AdapterError as e:
            assert "disabled" in str(e).lower()
        else:
            raise AssertionError("expected AdapterError")
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock


def test_ptc_runner_invalid_budget_raises():
    reg = AdapterRegistry(allowed=["ptc_runner"])
    reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))
    try:
        reg.call("ptc_runner", "RUN", ["(+ 1 2)", "{total :float}", "abc"], {})
    except AdapterError as e:
        assert "invalid subagent_budget" in str(e).lower()
    else:
        raise AssertionError("expected AdapterError")


def test_ptc_runner_private_context_firewall():
    adp = PtcRunnerAdapter(enabled=True, runner_url="http://localhost:4000/run")

    def _fake_post(payload):
        assert "_secret" not in payload.get("context", {})
        assert "visible" in payload.get("context", {})
        return {"ok": True, "status_code": 200, "body": {"result": {"ok": True}, "traces": []}}

    adp._post_http = _fake_post  # type: ignore[attr-defined]
    out = adp.run("(+ 1 2)", context={"visible": 1, "_secret": 2})
    assert out["ok"] is True


def test_ptc_runner_health_mock_success():
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"
        reg = AdapterRegistry(allowed=["ptc_runner"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))
        out = reg.call("ptc_runner", "health", [], {})
        assert out["ok"] is True
        assert out["result"]["beam_status"] == "running"
        assert isinstance(out.get("beam_metrics"), dict)
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock


def test_ptc_runner_status_alias_calls_health():
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"
        reg = AdapterRegistry(allowed=["ptc_runner"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))
        out = reg.call("ptc_runner", "status", [], {})
        assert out["ok"] is True
        assert out["result"]["beam_status"] == "running"
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock


def test_ptc_runner_beam_metrics_passthrough_from_body():
    adp = PtcRunnerAdapter(enabled=True, runner_url="http://localhost:4000/run")

    def _fake_post(payload):
        return {
            "ok": True,
            "status_code": 200,
            "body": {
                "result": {"ok": True},
                "beam_metrics": {"heap": 123, "reductions": 5, "execution_time_ms": 7, "process_id": "<0.1.0>"},
                "traces": [],
            },
        }

    adp._post_http = _fake_post  # type: ignore[attr-defined]
    out = adp.run("(+ 1 2)", context={})
    assert out["ok"] is True
    assert out["beam_metrics"]["heap_bytes"] == 123
    assert out["beam_metrics"]["reductions"] == 5
    assert out["beam_metrics"]["exec_time_ms"] == 7
    assert out["beam_metrics"]["pid"] == "<0.1.0>"
