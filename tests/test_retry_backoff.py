"""
Tests for retry backoff strategies (fixed and exponential).

Covers:
- _compute_retry_delay_ms helper with fixed and exponential strategies
- backward compatibility: default strategy is fixed
- exponential cap via max_backoff_ms
- compiler parsing of optional backoff_strategy token
- runtime integration: retry step with backoff_strategy field
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import RuntimeEngine


class TestComputeRetryDelay:
    def test_fixed_default(self):
        cfg = {"backoff_ms": 100}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 100.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 2) == 100.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 5) == 100.0

    def test_fixed_explicit(self):
        cfg = {"backoff_ms": 200, "backoff_strategy": "fixed"}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 200.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 3) == 200.0

    def test_exponential(self):
        cfg = {"backoff_ms": 100, "backoff_strategy": "exponential"}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 100.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 2) == 200.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 3) == 400.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 4) == 800.0

    def test_exponential_cap(self):
        cfg = {"backoff_ms": 100, "backoff_strategy": "exponential", "max_backoff_ms": 500}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 100.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 2) == 200.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 3) == 400.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 4) == 500.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 10) == 500.0

    def test_exponential_default_cap(self):
        cfg = {"backoff_ms": 10000, "backoff_strategy": "exponential"}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 10000.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 2) == 20000.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 3) == 30000.0  # capped at default 30000

    def test_zero_backoff(self):
        cfg = {"backoff_ms": 0, "backoff_strategy": "exponential"}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 0.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 5) == 0.0

    def test_unknown_strategy_falls_back_to_fixed(self):
        cfg = {"backoff_ms": 100, "backoff_strategy": "unknown"}
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 1) == 100.0
        assert RuntimeEngine._compute_retry_delay_ms(cfg, 3) == 100.0


class TestCompilerParsesBackoffStrategy:
    def test_standalone_retry_with_strategy(self):
        from compiler_v2 import AICodeCompiler

        code = "S app api /api\nL1:\nR ext.OP \"task\" ->res\nRetry 3 500 exponential\nJ res"
        c = AICodeCompiler()
        ir = c.compile(code)
        steps = ir["labels"]["1"]["legacy"]["steps"]
        retry_steps = [s for s in steps if s["op"] == "Retry"]
        assert len(retry_steps) == 1
        assert retry_steps[0]["backoff_strategy"] == "exponential"
        assert retry_steps[0]["count"] == "3"
        assert retry_steps[0]["backoff_ms"] == "500"

    def test_standalone_retry_without_strategy(self):
        from compiler_v2 import AICodeCompiler

        code = "S app api /api\nL1:\nR ext.OP \"task\" ->res\nRetry 3 500\nJ res"
        c = AICodeCompiler()
        ir = c.compile(code)
        steps = ir["labels"]["1"]["legacy"]["steps"]
        retry_steps = [s for s in steps if s["op"] == "Retry"]
        assert len(retry_steps) == 1
        assert "backoff_strategy" not in retry_steps[0]

    def test_retry_with_node_target_and_strategy(self):
        from compiler_v2 import AICodeCompiler

        code = "S app api /api\nL1:\nR ext.OP \"task\" ->res\nRetry @n1 2 1000 exponential\nJ res"
        c = AICodeCompiler()
        ir = c.compile(code)
        steps = ir["labels"]["1"]["legacy"]["steps"]
        retry_steps = [s for s in steps if s["op"] == "Retry"]
        assert len(retry_steps) == 1
        assert retry_steps[0]["backoff_strategy"] == "exponential"
        assert retry_steps[0]["at_node_id"] == "n1"


class TestRetryIntegration:
    def test_retry_fixed_backward_compat(self):
        from runtime.adapters.base import AdapterRegistry, RuntimeAdapter, AdapterError

        call_count = 0

        class FailThenSucceed(RuntimeAdapter):
            def call(self, target, args, context):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise AdapterError("transient failure")
                return "ok"

        reg = AdapterRegistry(allowed=["ext"])
        reg.register("ext", FailThenSucceed())
        code = "S app api /api\nL1:\nR ext.OP \"task\" ->res\nRetry 3 0\nJ res"
        eng = RuntimeEngine.from_code(code, strict=False)
        eng.adapters = reg
        result = eng.run_label("1", frame={})
        assert result is not None
        assert call_count == 3

    def test_retry_exponential_delays(self):
        """Verify exponential backoff computes correct delays via step-mode."""
        from runtime.adapters.base import AdapterRegistry, RuntimeAdapter, AdapterError

        delays_observed = []
        original_sleep = __import__("time").sleep

        def mock_sleep(seconds):
            delays_observed.append(round(seconds * 1000))

        call_count = 0

        class AlwaysFail(RuntimeAdapter):
            def call(self, target, args, context):
                nonlocal call_count
                call_count += 1
                raise AdapterError("always fails")

        reg = AdapterRegistry(allowed=["ext"])
        reg.register("ext", AlwaysFail())
        code = "S app api /api\nL1:\nR ext.OP \"task\" ->res\nRetry @n1 3 100 exponential\nErr @n1 L2\nJ res\nL2:\nSet out \"failed\"\nJ out"
        eng = RuntimeEngine.from_code(code, strict=False)
        eng.adapters = reg
        eng.execution_mode = "steps-only"

        import time
        time.sleep = mock_sleep
        try:
            result = eng.run_label("1", frame={})
        finally:
            time.sleep = original_sleep

        assert result is not None
        assert len(delays_observed) == 3
        assert delays_observed[0] == 100
        assert delays_observed[1] == 200
        assert delays_observed[2] == 400
