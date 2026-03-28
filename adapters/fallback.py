"""
Fallback adapter and circuit breaker for LLM providers.
"""
from __future__ import annotations

from runtime.observability import RuntimeObservability

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from adapters.llm.base import AbstractLLMAdapter, LLMResponse


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and calls are short-circuited."""
    pass


@dataclass
class CircuitBreaker:
    """
    Classic circuit breaker with CLOSED, OPEN, HALF_OPEN states.
    Metrics emitter hook integrates with runtime observability.
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout_s: float = 300.0
    _state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    _failure_count: int = 0
    _opened_until: float = 0.0
    _last_failure_time: Optional[float] = None

    # metrics hook (optional)
    emit_metric: Optional[callable] = None

    def before_call(self) -> None:
        """Check state before allowing a call."""
        if self._state == "OPEN":
            if time.time() >= self._opened_until:
                # Transition to HALF_OPEN and allow one trial
                self._state = "HALF_OPEN"
                if self.emit_metric:
                    self.emit_metric("circuit_breaker_state", 1, labels={"provider": self.name, "state": "half_open"})
                return
            raise CircuitOpenError(f"Circuit breaker for '{self.name}' is OPEN")
        # HALF_OPEN or CLOSED: allow

    def after_success(self) -> None:
        """On success, reset failure count and close circuit."""
        if self._state != "CLOSED":
            self._state = "CLOSED"
        self._failure_count = 0
        if self.emit_metric:
            self.emit_metric("circuit_breaker_state", 0, labels={"provider": self.name, "state": "closed"})

    def after_failure(self) -> None:
        """On failure, increment count and possibly open circuit."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == "CLOSED" and self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            self._opened_until = time.time() + self.recovery_timeout_s
            if self.emit_metric:
                self.emit_metric("circuit_breaker_state", 1, labels={"provider": self.name, "state": "open"})
        elif self._state == "HALF_OPEN":
            # Any failure in HALF_OPEN immediately reopens the circuit
            self._state = "OPEN"
            self._opened_until = time.time() + self.recovery_timeout_s
            if self.emit_metric:
                self.emit_metric("circuit_breaker_state", 1, labels={"provider": self.name, "state": "open"})

    def is_closed(self) -> bool:
        return self._state == "CLOSED"

    def get_state(self) -> str:
        return self._state


class FallbackLLMAdapter(AbstractLLMAdapter):
    """
    Adapter that tries a chain of LLM adapters in order until one succeeds.
    Each adapter in the chain is wrapped with its own CircuitBreaker.
    """

    def __init__(self, adapters_with_breakers: List[Tuple[AbstractLLMAdapter, CircuitBreaker]]):
        self._adapters_with_breakers = adapters_with_breakers

    def complete(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> LLMResponse:
        last_exception = None
        for adapter, breaker in self._adapters_with_breakers:
            try:
                # Check circuit state before attempting
                breaker.before_call()
                resp = adapter.complete(prompt=prompt, max_tokens=max_tokens, **kwargs)
                breaker.after_success()
                return resp
            except Exception as e:
                breaker.after_failure()
                last_exception = e
                # If circuit is now open, continue to next adapter
                continue
        # All adapters failed
        raise RuntimeError(f"All LLM adapters in fallback chain failed") from last_exception

    def validate(self) -> bool:
        # Validate all adapters; consider valid if at least one is available
        for adapter, _ in self._adapters_with_breakers:
            try:
                if adapter.validate():
                    return True
            except Exception:
                continue
        return False

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Use the first adapter's estimate as heuristic
        if self._adapters_with_breakers:
            adapter, _ = self._adapters_with_breakers[0]
            return adapter.estimate_cost(prompt_tokens, completion_tokens)
        return 0.0


def create_fallback_from_config(config: dict, llm_adapter_registry: LLMAdapterRegistry) -> FallbackLLMAdapter:
    """
    Construct a fallback chain from configuration.

    Expected config structure:
      config["llm"]["fallback_chain"] = ["openrouter", "anthropic", "ollama"]
      config["llm"]["circuit_breaker"] = {"failure_threshold": 5, "recovery_timeout_s": 300}
      config["llm"]["providers"] = { "openrouter": { ... }, "anthropic": { ... }, ... }

    Returns a FallbackLLMAdapter.
    """
    chain_names = config.get("llm", {}).get("fallback_chain", [])
    cb_cfg = config.get("llm", {}).get("circuit_breaker", {})
    providers_cfg = config.get("llm", {}).get("providers", {})

    adapters_with_breakers: List[Tuple[AbstractLLMAdapter, CircuitBreaker]] = []

    for provider_name in chain_names:
        prov_cfg = providers_cfg.get(provider_name, {})
        try:
            adapter = llm_adapter_registry.get_llm_adapter(provider_name, prov_cfg)
        except Exception as e:
            # Skip missing providers but log
            print(f"[warning] Skipping LLM provider '{provider_name}': {e}")
            continue

        breaker = CircuitBreaker(
            name=provider_name,
            failure_threshold=cb_cfg.get("failure_threshold", 5),
            recovery_timeout_s=cb_cfg.get("recovery_timeout_s", 300.0),
        )
        # Wire circuit breaker metrics to observability
        # Wire circuit breaker metrics to observability
        emit = RuntimeObservability.from_env_or_flag().emit
        breaker.emit_metric = lambda metric_name, value, labels=None: emit(
            metric_name, value, labels=labels or {}
        )
        adapters_with_breakers.append((adapter, breaker))

    if not adapters_with_breakers:
        raise ValueError("No valid LLM adapters in fallback chain")

    return FallbackLLMAdapter(adapters_with_breakers)
