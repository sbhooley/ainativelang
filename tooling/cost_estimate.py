"""Static per-node cost estimation for AINL IR graphs.

Additive v1.3.4 module. Pure static analysis — no LLM calls, no runtime
state mutations. Walks the compiled IR, identifies LLM-related nodes, estimates
token counts (tiktoken when available; len//4 heuristic as fallback), and
computes a rough USD cost. Optionally warns against the current BudgetPolicy
limit (read-only).

Usage::

    from tooling.cost_estimate import estimate_ir_cost
    result = estimate_ir_cost(ir)
    # result = {"per_node": [...], "totals": {...}, "budget_warnings": [...]}
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional tiktoken (cl100k_base encoder)
# ---------------------------------------------------------------------------
try:
    import tiktoken as _tiktoken

    _ENCODER = _tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except Exception:
    _ENCODER = None  # type: ignore[assignment]
    _HAS_TIKTOKEN = False


def _count_tokens(text: str) -> int:
    if _HAS_TIKTOKEN and _ENCODER is not None:
        try:
            return len(_ENCODER.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# LLM adapter name set (from registry + common usage patterns)
# ---------------------------------------------------------------------------
_LLM_ADAPTER_NAMES = frozenset(
    {
        "llm",
        "llm_query",
        "llm_runtime",
        "openrouter",
        "anthropic",
        "ollama",
        "cohere",
        "openai",
    }
)

# Rough per-1k-token pricing (input, output) in USD. Used when no adapter
# metadata provides an estimate. Keys are lowercase model name substrings.
_MODEL_PRICING: List[tuple[str, float, float]] = [
    ("gpt-4o-mini", 0.00015, 0.0006),
    ("gpt-4o", 0.005, 0.015),
    ("gpt-4", 0.03, 0.06),
    ("gpt-3.5", 0.0005, 0.0015),
    ("claude-3-5", 0.003, 0.015),
    ("claude-3", 0.003, 0.015),
    ("claude", 0.003, 0.015),
    ("gemini-1.5", 0.00035, 0.00105),
    ("gemini", 0.00035, 0.00105),
    ("llama", 0.0002, 0.0002),
]
_DEFAULT_INPUT_COST_PER_1K = 0.0005
_DEFAULT_OUTPUT_COST_PER_1K = 0.0015
_DEFAULT_OUTPUT_TOKENS = 400


def _price_for_model(model: str) -> tuple[float, float]:
    """Return (input_cost_per_1k, output_cost_per_1k) for ``model``."""
    ml = (model or "").lower()
    for substr, inp, out in _MODEL_PRICING:
        if substr in ml:
            return inp, out
    return _DEFAULT_INPUT_COST_PER_1K, _DEFAULT_OUTPUT_COST_PER_1K


def _is_llm_node(node: Dict[str, Any]) -> bool:
    """Return True if this IR node calls an LLM adapter."""
    if node.get("op") != "R":
        return False
    data = node.get("data") or {}
    adapter = str(data.get("adapter") or "").lower().split("/")[-1]
    if adapter in _LLM_ADAPTER_NAMES:
        return True
    # Also detect dotted-form like "llm_query.QUERY"
    target = str(data.get("target") or "").lower()
    if any(target.startswith(name + ".") or target == name for name in _LLM_ADAPTER_NAMES):
        return True
    return False


def _extract_prompt_text(node: Dict[str, Any]) -> str:
    """Best-effort prompt text extraction from an LLM IR node for token estimation."""
    data = node.get("data") or {}
    parts: List[str] = []
    # Some adapters store the prompt in args list
    args = data.get("args") or []
    if isinstance(args, list):
        for a in args[:5]:
            if isinstance(a, str):
                parts.append(a)
    # Also include the target (e.g. "llm_query.QUERY")
    target = str(data.get("target") or "")
    if target:
        parts.append(target)
    return " ".join(parts) if parts else "LLM call"


def estimate_ir_cost(
    ir: Dict[str, Any],
    default_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Statically estimate token usage and USD cost for LLM nodes in *ir*.

    Parameters
    ----------
    ir:
        Compiled AINL IR dict (as returned by ``AICodeCompiler.compile``).
    default_model:
        Fallback model name for pricing when not specified in the IR node.
        Defaults to the ``AINL_DEFAULT_MODEL`` env var or ``"gpt-4o-mini"``.

    Returns
    -------
    dict with keys:
        ``per_node`` — list of per-node estimate dicts
        ``totals`` — ``{sum_input_tokens, sum_output_tokens, sum_cost_usd}``
        ``budget_warnings`` — list of warning strings from BudgetPolicy (read-only)
    """
    if default_model is None:
        default_model = os.environ.get("AINL_DEFAULT_MODEL", "gpt-4o-mini")

    per_node: List[Dict[str, Any]] = []
    total_input = 0
    total_output = 0
    total_cost = 0.0

    labels = (ir or {}).get("labels") or {}
    for label_id, body in labels.items():
        if not isinstance(body, dict):
            continue
        nodes = body.get("nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if not _is_llm_node(node):
                continue

            data = node.get("data") or {}
            model = str(data.get("model") or default_model or "gpt-4o-mini")
            prompt_text = _extract_prompt_text(node)
            input_tokens = _count_tokens(prompt_text)
            output_tokens = int(data.get("max_tokens") or _DEFAULT_OUTPUT_TOKENS)
            inp_rate, out_rate = _price_for_model(model)
            cost = (input_tokens / 1000 * inp_rate) + (output_tokens / 1000 * out_rate)

            per_node.append(
                {
                    "label_id": str(label_id),
                    "node_id": str(node.get("id") or ""),
                    "adapter": str((data.get("adapter") or "")),
                    "target": str(data.get("target") or ""),
                    "model": model,
                    "estimated_input_tokens": input_tokens,
                    "estimated_output_tokens": output_tokens,
                    "estimated_cost_usd": round(cost, 6),
                    "token_method": "tiktoken" if _HAS_TIKTOKEN else "heuristic_len_div_4",
                }
            )
            total_input += input_tokens
            total_output += output_tokens
            total_cost += cost

    budget_warnings: List[str] = []
    try:
        from intelligence.monitor.cost_tracker import CostTracker
        from intelligence.monitor.budget_policy import BudgetPolicy  # noqa: F401

        tracker = CostTracker(":memory:")
        budget = tracker.get_budget()
        monthly_limit = float(budget.get("monthly_limit_usd") or 20.0)
        alert_pct = float(budget.get("alert_threshold_pct") or 0.8)
        throttle_pct = float(budget.get("throttle_threshold_pct") or 0.95)
        if monthly_limit > 0:
            frac = total_cost / monthly_limit
            if frac >= throttle_pct:
                budget_warnings.append(
                    f"THROTTLE: estimated cost ${total_cost:.4f} exceeds "
                    f"{throttle_pct:.0%} of monthly limit ${monthly_limit:.2f}"
                )
            elif frac >= alert_pct:
                budget_warnings.append(
                    f"ALERT: estimated cost ${total_cost:.4f} approaches "
                    f"{alert_pct:.0%} of monthly limit ${monthly_limit:.2f}"
                )
    except Exception:
        pass  # Budget policy unavailable — silently skip

    return {
        "per_node": per_node,
        "totals": {
            "sum_input_tokens": total_input,
            "sum_output_tokens": total_output,
            "sum_cost_usd": round(total_cost, 6),
        },
        "budget_warnings": budget_warnings,
    }


def format_estimate_table(estimate: Dict[str, Any]) -> str:
    """Return a human-readable table string for a cost estimate dict."""
    rows = estimate.get("per_node") or []
    totals = estimate.get("totals") or {}
    warnings = estimate.get("budget_warnings") or []

    if not rows:
        return "  (no LLM nodes found — cost estimate: $0.000000)\n"

    lines = ["  Cost estimate (static, no LLM calls):"]
    lines.append(
        f"  {'Node':<12} {'Label':<12} {'Adapter':<14} {'In tok':>8} {'Out tok':>8} {'Est USD':>10}"
    )
    lines.append("  " + "-" * 68)
    for r in rows:
        node = str(r.get("node_id") or "")[:12]
        label = str(r.get("label_id") or "")[:12]
        adapter = str(r.get("adapter") or r.get("target") or "")[:14]
        in_tok = r.get("estimated_input_tokens", 0)
        out_tok = r.get("estimated_output_tokens", 0)
        cost_usd = r.get("estimated_cost_usd", 0.0)
        lines.append(
            f"  {node:<12} {label:<12} {adapter:<14} {in_tok:>8} {out_tok:>8} ${cost_usd:>9.6f}"
        )
    lines.append("  " + "-" * 68)
    lines.append(
        f"  {'TOTAL':<12} {'':<12} {'':<14} "
        f"{totals.get('sum_input_tokens', 0):>8} "
        f"{totals.get('sum_output_tokens', 0):>8} "
        f"${totals.get('sum_cost_usd', 0.0):>9.6f}"
    )
    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"  ⚠  {w}")
    return "\n".join(lines) + "\n"
