"""Shared **tiktoken** counting and LLM **unit economics** for benchmark scripts.

All list prices are **USD per 1 million tokens** as commonly published **March 2026**
(OpenAI / Anthropic consumer API tiers). Update ``PRICING_USD_PER_MILLION_TOKENS`` when
vendors change pricing.

Estimates use a fixed input/output token **split** plus optional **overhead multiplier**
when real adapter token counts are unavailable (core-only benchmarks).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TIKTOKEN_ENCODING = "cl100k_base"

_encoder = None

# ---------------------------------------------------------------------------
# Tokenizer (single process-wide encoder instance)
# ---------------------------------------------------------------------------


def get_cl100k_encoder():
    """Lazily construct and cache the ``cl100k_base`` tiktoken encoding."""
    global _encoder
    if _encoder is None:
        import tiktoken  # type: ignore

        _encoder = tiktoken.get_encoding(TIKTOKEN_ENCODING)
    return _encoder


def tiktoken_count(text: str) -> int:
    """Count tokens using **tiktoken** ``cl100k_base`` (same as size/runtime benchmarks)."""
    if not text:
        return 0
    return len(get_cl100k_encoder().encode(text))


# ---------------------------------------------------------------------------
# Pricing (USD / 1M tokens) — March 2026 reference
# ---------------------------------------------------------------------------

PRICING_USD_PER_MILLION_TOKENS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-haiku": {"input": 1.00, "output": 5.00},
}

# When we only have a single “bundle” token count (e.g. source or emitted text).
DEFAULT_INPUT_TOKEN_FRACTION = 0.7
DEFAULT_PROMPT_OVERHEAD_MULTIPLIER = 1.5


def estimate_cost_usd(
    token_count: int,
    model_key: str,
    *,
    input_fraction: float = DEFAULT_INPUT_TOKEN_FRACTION,
    overhead_multiplier: float = DEFAULT_PROMPT_OVERHEAD_MULTIPLIER,
    measured_input_tokens: Optional[int] = None,
    measured_output_tokens: Optional[int] = None,
) -> Optional[float]:
    """
    Estimated **USD** for one logical LLM round-trip.

    If ``measured_input_tokens`` and ``measured_output_tokens`` are set (e.g. from an
    adapter), use those; otherwise scale ``token_count`` by ``overhead_multiplier`` and
    split into input/output using ``input_fraction``.
    """
    if model_key not in PRICING_USD_PER_MILLION_TOKENS:
        return None
    p = PRICING_USD_PER_MILLION_TOKENS[model_key]
    if measured_input_tokens is not None and measured_output_tokens is not None:
        return (measured_input_tokens * p["input"] + measured_output_tokens * p["output"]) / 1_000_000.0
    adj = max(0, int(token_count * overhead_multiplier))
    inp = max(0, int(adj * input_fraction))
    out = max(0, adj - inp)
    return (inp * p["input"] + out * p["output"]) / 1_000_000.0


def parse_cost_model_arg(value: str) -> List[str]:
    """Map CLI ``--cost-model`` to a list of pricing keys (empty = skip cost columns)."""
    v = (value or "").strip().lower()
    if v in ("", "none", "off"):
        return []
    if v == "both":
        return ["gpt-4o", "claude-3-5-sonnet"]
    if v in PRICING_USD_PER_MILLION_TOKENS:
        return [v]
    raise ValueError(f"unknown cost model: {value!r}")


def economics_block(*, cost_models: List[str]) -> Dict[str, Any]:
    """Metadata block stored at the top of benchmark JSON reports."""
    return {
        "tokenizer": {"library": "tiktoken", "encoding": TIKTOKEN_ENCODING},
        "pricing_usd_per_million_tokens": {k: dict(v) for k, v in PRICING_USD_PER_MILLION_TOKENS.items()},
        "cost_models_reported": list(cost_models),
        "estimation_assumptions": {
            "input_token_fraction": DEFAULT_INPUT_TOKEN_FRACTION,
            "prompt_overhead_multiplier": DEFAULT_PROMPT_OVERHEAD_MULTIPLIER,
            "note": (
                "Costs are illustrative unless adapter-reported input/output tokens exist. "
                "Runtime uses AINL **source** tiktoken count × overhead; size uses **aggregate emitted** "
                "tiktoken count × overhead when metric is tiktoken."
            ),
        },
    }


def cost_dict_for_tokens(token_count: int, cost_models: List[str]) -> Dict[str, Optional[float]]:
    """Per-model estimated USD for a single scalar token budget."""
    out: Dict[str, Optional[float]] = {}
    for m in cost_models:
        out[m] = estimate_cost_usd(token_count, m)
    return out
