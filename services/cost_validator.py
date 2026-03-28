"""
Cost Estimator Validation Service

Periodically fetches live pricing from providers and compares against
adapter's estimate_cost(). Emits metrics and logs warnings on drift.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

import httpx

# Optional: try to import runtime observability if available
try:
    from runtime.observability import RuntimeObservability
except ImportError:
    RuntimeObservability = None

# Import adapters for isinstance checks
try:
    from adapters.llm.openrouter import OpenRouterAdapter
except ImportError:
    OpenRouterAdapter = None

OPENROUTER_MODELS_CACHE_TTL_S = 24 * 3600


class CostValidator:
    """
    Background service that validates adapter cost estimates against live provider prices.
    """

    def __init__(self, observability: Optional[Any] = None, interval_hours: float = 6.0):
        self.interval_s = interval_hours * 3600.0
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.observability = observability
        self._openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        # Process-local cache for OpenRouter /v1/models JSON (24h TTL); on fetch failure keep last good payload.
        self._or_models_payload: Optional[Dict[str, Any]] = None
        self._or_models_fetched_at: float = 0.0
        self._or_models_ttl_s: float = OPENROUTER_MODELS_CACHE_TTL_S

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        # Sleep briefly on start to avoid immediate burst
        time.sleep(min(60, self.interval_s))
        while not self._stop_event.is_set():
            try:
                self.validate_once()
            except Exception as e:
                # Never crash the thread
                print(f"[cost_validator] error: {e}")
            # Wait for next interval
            self._stop_event.wait(self.interval_s)

    def validate_once(self) -> None:
        """
        For each provider+model combination known, fetch live prices (if available)
        and compare with adapter's estimate_cost(). Emit metrics on drift >10%.
        """
        # For Phase 1, we only fetch OpenRouter live prices; others use static mappings.
        from adapters.registry import LLMAdapterRegistry
        from adapters.llm.openrouter import OpenRouterAdapter

        providers = LLMAdapterRegistry.list_providers()
        for provider in providers:
            try:
                # Get default config for provider (minimal)
                adapter = LLMAdapterRegistry.get_llm_adapter(provider, {})
            except Exception:
                continue

            # Only OpenRouter has a live price endpoint in this phase
            if OpenRouterAdapter is not None and isinstance(adapter, OpenRouterAdapter):
                self._validate_openrouter(adapter)
            else:
                self._validate_static(adapter)

    def _fetch_openrouter_models_payload(self) -> Optional[Dict[str, Any]]:
        """GET OpenRouter models JSON with 24h in-memory TTL; on error return last cached payload if any."""
        if not self._openrouter_api_key:
            return None
        now = time.time()
        with self._lock:
            if self._or_models_payload is not None and (now - self._or_models_fetched_at) < self._or_models_ttl_s:
                return self._or_models_payload

        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {self._openrouter_api_key}"}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            print(f"[cost_validator] OpenRouter price fetch failed: {e}")
            with self._lock:
                return self._or_models_payload

        with self._lock:
            self._or_models_payload = data
            self._or_models_fetched_at = time.time()
            return data

    def _validate_openrouter(self, adapter: OpenRouterAdapter) -> None:
        data = self._fetch_openrouter_models_payload()
        if not data:
            return

        # data is a dict with 'data' list of models
        models = data.get("data", [])
        for model_info in models:
            model_id = model_info.get("id")
            pricing = model_info.get("pricing", {})
            if not model_id or not pricing:
                continue
            prompt_price_per_1k = pricing.get("prompt")  # e.g. "0.00003"
            completion_price_per_1k = pricing.get("completion")
            if prompt_price_per_1k is None or completion_price_per_1k is None:
                continue
            try:
                prompt_price = float(prompt_price_per_1k) * 1000  # per token
                completion_price = float(completion_price_per_1k) * 1000
            except ValueError:
                continue

            # Estimate cost for a sample size? We'll pick a standard test: 1000 prompt, 500 completion.
            sample_prompt_toks = 1000
            sample_completion_toks = 500
            estimated = adapter.estimate_cost(sample_prompt_toks, sample_completion_toks)
            live = prompt_price * sample_prompt_toks + completion_price * sample_completion_toks
            if estimated == 0:
                continue
            drift_pct = abs(estimated - live) / estimated * 100.0
            if drift_pct > 10.0:
                # Log warning
                print(f"[cost_validator] Drift detected for {model_id}: estimate=${estimated:.6f} vs live=${live:.6f} ({drift_pct:.1f}%)")
                # Emit metrics
                self._emit_counter("cost_estimate_drift_total", 1, labels={"provider": "openrouter", "model": model_id})
                self._emit_gauge("cost_estimate_drift_pct", drift_pct, labels={"provider": "openrouter", "model": model_id})

    def _validate_static(self, adapter: Any) -> None:
        # For static adapters (Anthropic, Cohere), compare estimate against its own constants (should match).
        # We'll simulate a sample to ensure the math is consistent; if there is a discrepancy we report.
        sample_prompt = 1000
        sample_completion = 500
        estimated = adapter.estimate_cost(sample_prompt, sample_completion)
        # Since we trust static mappings, we can skip emitting drift unless we have a live source to compare.
        # In future, we could hardcode known correct values and check. For Phase 1, no action.

    def _emit_counter(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if self.observability:
            self.observability.emit(name, value, labels=labels)

    def _emit_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if self.observability:
            self.observability.emit(name, value, labels=labels)


# Global singleton (optional)
_validator_instance: Optional[CostValidator] = None


def get_validator(observability: Optional[Any] = None, interval_hours: float = 6.0) -> CostValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = CostValidator(observability=observability, interval_hours=interval_hours)
    return _validator_instance
