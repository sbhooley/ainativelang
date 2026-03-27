"""
Tests for CircuitBreaker.
"""

import time
import pytest
from adapters.fallback import CircuitBreaker, CircuitOpenError


class DummyAdapter:
    def __init__(self, fail=False):
        self.fail = fail
    def complete(self, prompt, max_tokens=None, **kwargs):
        if self.fail:
            raise RuntimeError("simulated failure")
        return "ok"
    def validate(self):
        return True
    def estimate_cost(self, pt, ct):
        return 0.0


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout_s=1)
    adapter = DummyAdapter(fail=True)
    # Should allow up to threshold
    for _ in range(3):
        try:
            cb.before_call()
            adapter.complete("test")
            cb.after_success()
        except CircuitOpenError:
            assert False, "Should not be open yet"
        except RuntimeError:
            cb.after_failure()
    # After 3 failures, circuit should be OPEN and next call raises
    assert cb.get_state() == "OPEN"
    with pytest.raises(CircuitOpenError):
        cb.before_call()


def test_circuit_breaker_half_open_after_timeout():
    cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_s=0.5)
    adapter = DummyAdapter(fail=True)
    # Open circuit
    for _ in range(2):
        try:
            cb.before_call()
            adapter.complete("test")
            cb.after_success()
        except RuntimeError:
            cb.after_failure()
    assert cb.get_state() == "OPEN"
    # Wait for recovery timeout
    time.sleep(0.6)
    # Now before_call should transition to HALF_OPEN and allow one trial
    cb.before_call()  # should not raise
    assert cb.get_state() == "HALF_OPEN"
    # If that trial fails, circuit goes back to OPEN
    try:
        adapter.complete("test")  # fails
    except RuntimeError:
        cb.after_failure()
    assert cb.get_state() == "OPEN"


def test_circuit_breaker_recovers():
    cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_s=0.5)
    adapter = DummyAdapter(fail=True)
    # Open circuit
    for _ in range(2):
        try:
            cb.before_call()
            adapter.complete("test")
            cb.after_success()
        except RuntimeError:
            cb.after_failure()
    assert cb.get_state() == "OPEN"
    time.sleep(0.6)
    # HALF_OPEN trial succeeds
    cb.before_call()
    assert cb.get_state() == "HALF_OPEN"
    adapter_fixed = DummyAdapter(fail=False)
    result = adapter_fixed.complete("test")
    cb.after_success()
    assert cb.get_state() == "CLOSED"
