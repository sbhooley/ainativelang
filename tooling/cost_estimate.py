"""Static per-node cost estimation for AINL IR graphs.

Pure static analysis — no LLM calls, no runtime state mutations. Walks compiled
IR, estimates token usage (tiktoken when available; len//4 fallback), and computes
USD cost from a model pricing table. Optionally warns against BudgetPolicy limits.

Usage::

    from tooling.cost_estimate import estimate_ir_cost, estimate_file_cost, format_estimate_report

    report = estimate_ir_cost(ir, pricing_model="gpt-4o")
    print(format_estimate_report(report, style="table"))

    report = estimate_file_cost("my_graph.ainl", model="claude-haiku-4-5")
    print(format_estimate_report(report, style="summary"))
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Model pricing (USD per 1M tokens). Public catalog for CLI/docs.
# ---------------------------------------------------------------------------
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 5.00, "output": 15.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

DEFAULT_MODEL = "gpt-4o"
_DEFAULT_OUTPUT_TOKENS = 400

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


def _count_tokens(text: str) -> int:
    if _HAS_TIKTOKEN and _ENCODER is not None:
        try:
            return len(_ENCODER.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)


def resolve_model_pricing(model: str) -> Tuple[str, float, float, List[str]]:
    """Return ``(resolved_name, input_per_1m, output_per_1m, warnings)``."""
    ml = (model or "").strip().lower()
    warnings: List[str] = []
    if ml in MODEL_PRICING:
        p = MODEL_PRICING[ml]
        return ml, p["input"], p["output"], warnings
    for key, p in MODEL_PRICING.items():
        if key in ml or ml in key:
            return key, p["input"], p["output"], warnings
    p = MODEL_PRICING[DEFAULT_MODEL]
    warnings.append(f"Unknown model '{model}' — using {DEFAULT_MODEL} pricing")
    return DEFAULT_MODEL, p["input"], p["output"], warnings


def _cost_usd(input_tokens: int, output_tokens: int, input_per_1m: float, output_per_1m: float) -> float:
    return (input_tokens * input_per_1m + output_tokens * output_per_1m) / 1_000_000


def _is_llm_node(node: Dict[str, Any]) -> bool:
    if node.get("op") != "R":
        return False
    data = node.get("data") or {}
    adapter = str(data.get("adapter") or "").lower().split("/")[-1]
    if adapter in _LLM_ADAPTER_NAMES:
        return True
    target = str(data.get("target") or "").lower()
    return any(target.startswith(name + ".") or target == name for name in _LLM_ADAPTER_NAMES)


def _node_type(node: Dict[str, Any]) -> str:
    data = node.get("data") or {}
    target = str(data.get("target") or "").strip()
    if target:
        return target
    adapter = str(data.get("adapter") or "").strip()
    if adapter:
        return adapter
    return str(node.get("op") or "unknown")


def _extract_prompt_text(node: Dict[str, Any]) -> str:
    data = node.get("data") or {}
    parts: List[str] = []
    args = data.get("args") or []
    if isinstance(args, list):
        for a in args[:5]:
            if isinstance(a, str):
                parts.append(a)
    target = str(data.get("target") or "")
    if target:
        parts.append(target)
    return " ".join(parts) if parts else "LLM call"


def _iter_label_nodes(ir: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
    labels = (ir or {}).get("labels") or {}
    for label_id, body in labels.items():
        if not isinstance(body, dict):
            continue
        nodes = body.get("nodes") or []
        if isinstance(nodes, dict):
            for node_id, node in nodes.items():
                if isinstance(node, dict):
                    merged = dict(node)
                    merged.setdefault("id", node_id)
                    out.append((str(label_id), merged))
            continue
        if isinstance(nodes, list):
            for i, node in enumerate(nodes):
                if isinstance(node, dict):
                    merged = dict(node)
                    merged.setdefault("id", merged.get("id") or f"step_{i}")
                    out.append((str(label_id), merged))
            continue
        steps = body.get("steps") or []
        if isinstance(steps, list):
            for i, step in enumerate(steps):
                if isinstance(step, dict):
                    merged = dict(step)
                    merged.setdefault("id", merged.get("id") or f"step_{i}")
                    out.append((str(label_id), merged))
    return out


def estimate_ir_cost(
    ir: Dict[str, Any],
    default_model: Optional[str] = None,
    pricing_model: Optional[str] = None,
    runs_per_day: int = 10,
    include_zero_cost_nodes: bool = True,
) -> Dict[str, Any]:
    """Statically estimate token usage and USD cost for nodes in *ir*."""
    if default_model is None:
        default_model = os.environ.get("AINL_DEFAULT_MODEL", "gpt-4o-mini")
    pricing_name = pricing_model or default_model or DEFAULT_MODEL
    resolved_name, input_per_1m, output_per_1m, pricing_warnings = resolve_model_pricing(pricing_name)

    per_node: List[Dict[str, Any]] = []
    per_label_map: Dict[str, Dict[str, Any]] = {}
    total_input = 0
    total_output = 0
    total_cost = 0.0
    llm_node_count = 0
    total_node_count = 0

    for label_id, node in _iter_label_nodes(ir):
        total_node_count += 1
        is_llm = _is_llm_node(node)
        node_type = _node_type(node)
        data = node.get("data") or {}

        if is_llm:
            llm_node_count += 1
            node_model = str(data.get("model") or default_model or "gpt-4o-mini")
            _, node_in_per_1m, node_out_per_1m, _ = resolve_model_pricing(
                pricing_model or node_model
            )
            prompt_text = _extract_prompt_text(node)
            input_tokens = _count_tokens(prompt_text)
            output_tokens = int(data.get("max_tokens") or _DEFAULT_OUTPUT_TOKENS)
            cost = _cost_usd(input_tokens, output_tokens, node_in_per_1m, node_out_per_1m)
        elif include_zero_cost_nodes:
            input_tokens = 0
            output_tokens = 0
            cost = 0.0
        else:
            continue

        row = {
            "label_id": label_id,
            "node_id": str(node.get("id") or ""),
            "node_type": node_type,
            "adapter": str(data.get("adapter") or ""),
            "target": str(data.get("target") or ""),
            "model": str(data.get("model") or resolved_name),
            "is_llm_node": is_llm,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": round(cost, 6),
            "token_method": "tiktoken" if _HAS_TIKTOKEN and is_llm else ("n/a" if not is_llm else "heuristic_len_div_4"),
        }
        per_node.append(row)

        label_tot = per_label_map.setdefault(
            label_id,
            {
                "label_id": label_id,
                "node_count": 0,
                "llm_node_count": 0,
                "sum_input_tokens": 0,
                "sum_output_tokens": 0,
                "sum_cost_usd": 0.0,
            },
        )
        label_tot["node_count"] += 1
        if is_llm:
            label_tot["llm_node_count"] += 1
        label_tot["sum_input_tokens"] += input_tokens
        label_tot["sum_output_tokens"] += output_tokens
        label_tot["sum_cost_usd"] = round(label_tot["sum_cost_usd"] + cost, 6)
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
        pass

    runs = max(1, int(runs_per_day or 10))
    per_label = []
    for label_id in sorted(per_label_map.keys()):
        entry = dict(per_label_map[label_id])
        entry["sum_cost_usd"] = round(float(entry["sum_cost_usd"]), 6)
        per_label.append(entry)

    warnings = list(pricing_warnings)
    if not per_node and not _iter_label_nodes(ir):
        warnings.append("No labels/nodes found in IR — graph may be empty.")

    return {
        "model": resolved_name,
        "per_node": per_node,
        "per_label": per_label,
        "totals": {
            "node_count": total_node_count,
            "llm_node_count": llm_node_count,
            "sum_input_tokens": total_input,
            "sum_output_tokens": total_output,
            "sum_total_tokens": total_input + total_output,
            "sum_cost_usd": round(total_cost, 6),
        },
        "projections": {
            "runs_per_day": runs,
            "daily_cost_usd": round(total_cost * runs, 6),
            "monthly_cost_usd": round(total_cost * runs * 30, 4),
        },
        "warnings": warnings,
        "budget_warnings": budget_warnings,
    }


def estimate_file_cost(
    path: str,
    *,
    model: Optional[str] = None,
    strict: bool = False,
    runs_per_day: int = 10,
) -> Dict[str, Any]:
    """Compile an ``.ainl`` / ``.lang`` file and return a cost estimate dict."""
    from compiler_v2 import AICodeCompiler

    src_path = str(Path(path).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    compiler = AICodeCompiler(strict_mode=strict)
    ir = compiler.compile(code, emit_graph=True, source_path=src_path)
    errors = ir.get("errors") or []
    if errors:
        raise ValueError(f"compile failed: {errors}")
    return estimate_ir_cost(
        ir,
        pricing_model=model or DEFAULT_MODEL,
        runs_per_day=runs_per_day,
    )


def format_estimate_summary(estimate: Dict[str, Any]) -> str:
    totals = estimate.get("totals") or {}
    projections = estimate.get("projections") or {}
    warnings = (estimate.get("warnings") or []) + (estimate.get("budget_warnings") or [])
    model = estimate.get("model") or DEFAULT_MODEL
    lines = [
        f"AINL Graph Cost Estimate — model: {model}",
        "─" * 48,
        f"  Total nodes       : {totals.get('node_count', 0)}",
        f"  LLM nodes         : {totals.get('llm_node_count', 0)}",
        f"  Input tokens      : {totals.get('sum_input_tokens', 0):,}",
        f"  Output tokens     : {totals.get('sum_output_tokens', 0):,}",
        f"  Total tokens      : {totals.get('sum_total_tokens', 0):,}",
        f"  Estimated cost    : ${totals.get('sum_cost_usd', 0.0):.6f} per execution",
        f"  Daily ({projections.get('runs_per_day', 10)}x/day)   : ${projections.get('daily_cost_usd', 0.0):.4f}",
        f"  Monthly ({projections.get('runs_per_day', 10)}x/day) : ${projections.get('monthly_cost_usd', 0.0):.4f}",
    ]
    if warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in warnings:
            lines.append(f"    - {w}")
    return "\n".join(lines) + "\n"


def format_estimate_table(estimate: Dict[str, Any]) -> str:
    """Return a human-readable table string for a cost estimate dict."""
    rows = estimate.get("per_node") or []
    totals = estimate.get("totals") or {}
    projections = estimate.get("projections") or {}
    warnings = (estimate.get("warnings") or []) + (estimate.get("budget_warnings") or [])
    model = estimate.get("model") or DEFAULT_MODEL

    if not rows:
        return format_estimate_summary(estimate)

    lines = [
        f"AINL Graph Cost Estimate — model: {model}",
        "─" * 72,
        f"{'Label':<16} {'Node':<20} {'Type':<22} {'Tokens':>8} {'Cost':>12}",
        "─" * 72,
    ]

    current_label = None
    for r in rows:
        label = str(r.get("label_id") or "")
        if label != current_label:
            current_label = label
        node = str(r.get("node_id") or "")[:20]
        node_type = str(r.get("node_type") or r.get("target") or "")[:20]
        marker = "🤖 " if r.get("is_llm_node") else "   "
        tokens = int(r.get("estimated_total_tokens") or 0)
        cost_usd = float(r.get("estimated_cost_usd") or 0.0)
        lines.append(
            f"{label:<16} {node:<20} {marker}{node_type:<20} {tokens:>8,} ${cost_usd:>10.6f}"
        )

    lines.append("─" * 72)
    lines.append(
        f"{'GRAPH TOTAL':<40} {totals.get('sum_total_tokens', 0):>8,} "
        f"${totals.get('sum_cost_usd', 0.0):>10.6f}"
    )
    lines.append("")
    lines.append(
        f"  Daily  ({projections.get('runs_per_day', 10)} runs/day) : "
        f"${projections.get('daily_cost_usd', 0.0):.4f}"
    )
    lines.append(
        f"  Monthly({projections.get('runs_per_day', 10)} runs/day) : "
        f"${projections.get('monthly_cost_usd', 0.0):.4f}"
    )
    if warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in warnings:
            lines.append(f"    - {w}")
    return "\n".join(lines) + "\n"


def format_estimate_report(estimate: Dict[str, Any], style: str = "table") -> str:
    """Format *estimate* as ``table``, ``summary``, or ``json``."""
    normalized = (style or "table").strip().lower()
    if normalized == "json":
        return json.dumps(estimate, indent=2)
    if normalized == "summary":
        return format_estimate_summary(estimate)
    return format_estimate_table(estimate)
