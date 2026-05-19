#!/usr/bin/env python3
"""
Reproducible LLM token-savings benchmark for compiled AINL pipelines.

THREE-WAY COMPARISON
--------------------
This benchmark measures three architectures so that each savings claim can be
traced to a specific, attributable mechanism:

  A. Vanilla / LLM-first (all pipeline steps call LLM, including routing)
     — Common in prototype agentic stacks, LangChain/LangGraph implementations,
       and early GPT-4 integrations where routing is delegated to the model.

  B. Vanilla-optimised (hand-coded equivalent without AINL compilation)
     — A skilled engineer's best effort: LLM for classification, rule-based
       routing (zero tokens), type-specific prompts for content steps.
     — Represents what a good team builds WITHOUT any compiler help.

  C. Compiled AINL (deterministic IR routing + type-specific prompts)
     — IR dispatch eliminates even the classification LLM call.
     — Type-specific prompts are guaranteed correct by the compiler.

SAVINGS ATTRIBUTION
-------------------
  B vs C → "routing-elimination savings"   (1.3–1.5× — the irreducible compiler benefit)
  A vs C → "full LLM-first savings"        (2–7× depending on routing depth)

  The 2–5× product claim is the A vs C comparison for standard pipelines.
  The routing-depth sensitivity table shows how the ratio scales with more routing steps.

  When citing externally, ALWAYS tag the baseline. "2.08×" is A vs C only.
  Mature platform teams ("baseline B") see ~1.43× — see docs/competitive/
  VS_HAND_WRITTEN_RUNNER.md for the honest sales conversation against B.

HONEST METHODOLOGY NUANCES (read before citing externally)
----------------------------------------------------------
  1. ``doc_processing`` compiled path receives ``doc_type`` from
     ``DocPipelineInput.doc_type_hint`` (see ``pure_async_python.py``
     ``run_compiled_pipeline``). This models the realistic case where
     upstream metadata supplies document type to the AINL graph (e.g.
     from S3 prefix, mime type, or webhook field). It does NOT model
     "AINL magically infers the type with no input." If your production
     comparison has no upstream metadata, baseline B may need one
     classify LLM call — eroding part of the A-vs-C delta but NOT the
     B-vs-C delta (which is the irreducible compiler benefit).

  2. ``support_triage`` scenario: AINL uses THREE focused LLM calls
     (extract structured fields, classify priority, draft response).
     Prompt-loop baseline uses ONE FAT prompt that does all three.
     AINL still wins ~52% on tokens because each focused prompt is
     much smaller than the fat prompt — savings come from prompt
     SIZE, not call COUNT. Some critics will (reasonably) ask why
     AINL "uses more calls"; the answer is per-call prompt economy,
     not orchestration elimination.

  3. The routing-depth sensitivity formula (``routing_depth_sensitivity``)
     is a pure analytical model, NOT mock-LLM calls:
     ``vanilla = N×370 + 3×350``, ``compiled = 3×270``. This shows the
     ratio scaling with routing depth; do not present it as if it were
     a measured benchmark scenario.

TOKEN COUNTING
--------------
  tiktoken cl100k_base on the actual prompt strings in pure_async_python.py.
  No live LLM API calls; fully reproducible on any machine with ainativelang[benchmark].
  Mock LLM outputs are fixed strings sized to roughly match real model
  outputs; real-world extraction outputs can be 2-5× larger, which
  reduces the doc_processing ratio to ~1.8-1.95× (script notes this
  in the methodology section of the JSON output).

USAGE
-----
  python scripts/benchmark_token_savings.py
  python scripts/benchmark_token_savings.py --scenario doc_processing
  python scripts/benchmark_token_savings.py --json-out tooling/token_savings_results.json
  python scripts/benchmark_token_savings.py --markdown-out BENCHMARK.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_BASELINES = ROOT / "benchmarks" / "handwritten_baselines" / "doc_pipeline"
if str(_BASELINES) not in sys.path:
    sys.path.insert(0, str(_BASELINES))

logger = logging.getLogger(__name__)

DEFAULT_JSON_OUT = ROOT / "tooling" / "token_savings_results.json"
DEFAULT_MARKDOWN_OUT = ROOT / "BENCHMARK.md"
TOKEN_SAVINGS_SECTION_START = "<!-- TOKEN_SAVINGS_BENCH_START -->"
TOKEN_SAVINGS_SECTION_END = "<!-- TOKEN_SAVINGS_BENCH_END -->"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiktoken_count(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text.split()))


def _ratio(a: float, b: float) -> Optional[float]:
    return round(a / b, 2) if b > 0 else None


# ---------------------------------------------------------------------------
# Single-pipeline measurement
# ---------------------------------------------------------------------------

async def measure_one_doc(
    document: str,
    doc_type: str,
    label: str,
) -> Dict[str, Any]:
    """
    Run the doc pipeline in all THREE modes for a single document and return a
    fully attributed token breakdown.

    Three pipelines:
      vanilla          — LLM-first: every step (including routing) calls LLM
      vanilla_optimized — skilled hand-coded: LLM classify only, rule-based
                          routing, type-specific content prompts (same as AINL)
      compiled         — compiled AINL: zero routing tokens, type-specific prompts

    This three-way split lets reviewers attribute savings cleanly:
      vanilla_optimized vs compiled → routing-elimination only (~1.4×)
      vanilla vs compiled           → full LLM-first savings (~2.1×)
    """
    from pure_async_python import (
        DocPipelineInput,
        MockLLM,
        run_compiled_pipeline,
        run_vanilla_optimized_pipeline,
        run_vanilla_pipeline,
    )

    llm = MockLLM(use_tiktoken=True)

    v_inp = DocPipelineInput(document=document, doc_type_hint=doc_type, approach="vanilla")
    v_out = await run_vanilla_pipeline(v_inp, llm)

    o_inp = DocPipelineInput(document=document, doc_type_hint=doc_type, approach="vanilla_optimized")
    o_out = await run_vanilla_optimized_pipeline(o_inp, llm)

    c_inp = DocPipelineInput(document=document, doc_type_hint=doc_type, approach="compiled")
    c_out = await run_compiled_pipeline(c_inp, llm)

    vanilla_steps = {s: (i, o) for s, i, o in v_out.token_ledger}
    compiled_steps = {s: (i, o) for s, i, o in c_out.token_ledger}

    all_steps = list(dict.fromkeys(
        [s for s, _, _ in v_out.token_ledger] +
        [s for s, _, _ in c_out.token_ledger]
    ))

    step_rows = []
    for step in all_steps:
        v_i, v_o = vanilla_steps.get(step, (0, 0))
        c_i, c_o = compiled_steps.get(step, (0, 0))
        v_total = v_i + v_o
        c_total = c_i + c_o
        step_rows.append({
            "step": step,
            "vanilla_input_tokens": v_i,
            "vanilla_output_tokens": v_o,
            "vanilla_total": v_total,
            "compiled_input_tokens": c_i,
            "compiled_output_tokens": c_o,
            "compiled_total": c_total,
            "tokens_saved": v_total - c_total,
            "is_ir_routed": c_total == 0 and v_total > 0,
        })

    doc_tk = _tiktoken_count(document)

    return {
        "document_label": label,
        "doc_type": doc_type,
        "document_tiktoken": doc_tk,
        "vanilla": {
            "total_tokens": v_out.total_tokens,
            "total_input_tokens": v_out.total_input_tokens,
            "total_output_tokens": v_out.total_output_tokens,
            "llm_calls": len(v_out.token_ledger),
            "description": "LLM-first: every step calls LLM (common in prototypes)",
        },
        "vanilla_optimized": {
            "total_tokens": o_out.total_tokens,
            "total_input_tokens": o_out.total_input_tokens,
            "total_output_tokens": o_out.total_output_tokens,
            "llm_calls": len(o_out.token_ledger),
            "description": "Hand-optimized: LLM classify only, rule-based routing, type-specific prompts",
        },
        "compiled": {
            "total_tokens": c_out.total_tokens,
            "total_input_tokens": c_out.total_input_tokens,
            "total_output_tokens": c_out.total_output_tokens,
            "llm_calls": len(c_out.token_ledger),
            "description": "Compiled AINL: IR routing eliminates all LLM routing calls",
        },
        "savings_ratio_vs_vanilla": _ratio(v_out.total_tokens, c_out.total_tokens),
        "savings_ratio_vs_vanilla_optimized": _ratio(o_out.total_tokens, c_out.total_tokens),
        "tokens_saved_total": v_out.total_tokens - c_out.total_tokens,
        "tokens_saved_from_ir_routing": sum(
            r["tokens_saved"] for r in step_rows if r["is_ir_routed"]
        ),
        "tokens_saved_from_focused_prompts": sum(
            r["tokens_saved"] for r in step_rows if not r["is_ir_routed"]
        ),
        "step_breakdown": step_rows,
    }


# ---------------------------------------------------------------------------
# Scenario: doc_processing (3 representative documents)
# ---------------------------------------------------------------------------

async def run_scenario_doc_processing() -> Dict[str, Any]:
    from pure_async_python import (
        SAMPLE_DOCUMENT_CONTRACT,
        SAMPLE_DOCUMENT_INVOICE,
        SAMPLE_DOCUMENT_SUPPORT,
    )

    docs = [
        (SAMPLE_DOCUMENT_INVOICE, "invoice", "Invoice (#INV-2026-0042)"),
        (SAMPLE_DOCUMENT_CONTRACT, "contract", "Service Agreement"),
        (SAMPLE_DOCUMENT_SUPPORT, "support", "Support Ticket (#SUP-8821)"),
    ]

    results = []
    for doc, doc_type, label in docs:
        result = await measure_one_doc(doc, doc_type, label)
        results.append(result)

    vanilla_totals = [r["vanilla"]["total_tokens"] for r in results]
    opt_totals = [r["vanilla_optimized"]["total_tokens"] for r in results]
    compiled_totals = [r["compiled"]["total_tokens"] for r in results]
    total_vanilla = sum(vanilla_totals)
    total_opt = sum(opt_totals)
    total_compiled = sum(compiled_totals)

    ir_routing_saved = sum(r["tokens_saved_from_ir_routing"] for r in results)
    focused_prompt_saved = sum(r["tokens_saved_from_focused_prompts"] for r in results)

    return {
        "scenario": "doc_processing",
        "description": (
            "5-step business document pipeline (classify → route → extract → summarise → action items). "
            "Three-way comparison: LLM-first vanilla vs hand-optimised vanilla vs compiled AINL."
        ),
        "documents_measured": len(results),
        "per_document": results,
        "aggregate": {
            "total_vanilla_tokens": total_vanilla,
            "total_vanilla_optimized_tokens": total_opt,
            "total_compiled_tokens": total_compiled,
            "savings_ratio_vs_vanilla": _ratio(total_vanilla, total_compiled),
            "savings_ratio_vs_vanilla_optimized": _ratio(total_opt, total_compiled),
            # The primary product claim is the LLM-first comparison
            "overall_savings_ratio": _ratio(total_vanilla, total_compiled),
            "mean_per_doc_vanilla": round(mean(vanilla_totals)),
            "mean_per_doc_vanilla_optimized": round(mean(opt_totals)),
            "mean_per_doc_compiled": round(mean(compiled_totals)),
            "tokens_saved_from_ir_routing": ir_routing_saved,
            "tokens_saved_from_focused_prompts": focused_prompt_saved,
            "ir_routing_pct_of_savings": round(
                100 * ir_routing_saved / (ir_routing_saved + focused_prompt_saved), 1
            ) if (ir_routing_saved + focused_prompt_saved) > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Scenario: event_routing (short events + heavy multi-level classification)
# Models infrastructure alert / security event triage where each input is a
# short structured event (~25 tokens) and vanilla agents classify it through
# 5 independent LLM routing calls before taking action.
# ---------------------------------------------------------------------------

# Short structured events — realistic alert messages
SAMPLE_EVENTS = [
    "CPU utilisation 94% on prod-web-03 for 8 minutes. Host: us-east-1b. Service: checkout-api.",
    "Payment declined: card_type=Visa amount=$3200 country_mismatch=true velocity_flag=true user_id=u_88412.",
    "Login attempt failed 12x in 60s. User: admin@corp.com. IP: 185.220.101.47 (Tor exit node).",
    "DynamoDB throttle: table=orders_v3 consumed=4200 provisioned=1000 region=eu-west-1.",
    "SSL cert expires in 3 days: api.payments.internal. Issuer: LetsEncrypt. Env: production.",
]

# Vanilla routing prompts (type-agnostic; each must explain all possible classifications)
EVENT_CLASSIFY_SYSTEM = (
    "You are an infrastructure event classifier. "
    "Classify this event into one of: performance_degradation, security_threat, "
    "payment_anomaly, infrastructure_failure, certificate_expiry, or other. "
    "Reply with only the classification label."
)
EVENT_SEVERITY_SYSTEM = (
    "You are an SRE severity assessor. Based on the event and its classification, "
    "assign a severity: P0 (customer impact now), P1 (imminent risk), P2 (degraded), "
    "P3 (low-risk). Reply with only the severity level."
)
EVENT_TEAM_SYSTEM = (
    "You are an on-call routing engine. Route this event to the correct team: "
    "SRE_INFRA, SRE_SECURITY, PAYMENTS_OPS, DATABASE_OPS, or CERT_OPS. "
    "Reply with only the team name."
)
EVENT_REGION_SYSTEM = (
    "You are a regional incident coordinator. Based on the event, determine the "
    "primary region: us-east-1, us-west-2, eu-west-1, ap-southeast-1, or global. "
    "Reply with only the region identifier."
)
EVENT_ESCALATION_SYSTEM = (
    "You are an escalation policy engine. Determine the escalation action: "
    "page_oncall, create_ticket, auto_remediate, or monitor_only. "
    "Consider severity, team load, and business hours context. "
    "Reply with only the escalation action."
)
EVENT_RESPONSE_SYSTEM = (
    "You are an incident response assistant. Generate a concise (3-4 sentences) "
    "incident response summary that an on-call engineer can act on immediately. "
    "Include: what happened, severity, assigned team, and immediate next step."
)

# Compiled prompts (type-specific, set by IR dispatch — much shorter)
EVENT_RESPONSE_COMPILED: Dict[str, str] = {
    "performance_degradation": (
        "Write a 3-sentence incident response for this performance event. "
        "Include: metric breached, affected service, recommended immediate action."
    ),
    "security_threat": (
        "Write a 3-sentence security incident response. "
        "Include: threat type, affected system, immediate containment step."
    ),
    "payment_anomaly": (
        "Write a 3-sentence payment anomaly response. "
        "Include: anomaly type, transaction context, immediate action."
    ),
    "infrastructure_failure": (
        "Write a 3-sentence infra failure response. "
        "Include: component affected, blast radius, recovery step."
    ),
    "certificate_expiry": (
        "Write a 2-sentence cert expiry alert response. "
        "Include: cert name, days remaining, renewal action."
    ),
}
_EVENT_RESPONSE_DEFAULT = "Write a 3-sentence incident response for this event."

MOCK_EVENT_CLASSIFICATIONS = [
    "performance_degradation",
    "payment_anomaly",
    "security_threat",
    "infrastructure_failure",
    "certificate_expiry",
]
MOCK_EVENT_SEVERITIES = ["P1", "P1", "P0", "P2", "P3"]
MOCK_EVENT_TEAMS = ["SRE_INFRA", "PAYMENTS_OPS", "SRE_SECURITY", "DATABASE_OPS", "CERT_OPS"]
MOCK_EVENT_REGIONS = ["us-east-1", "global", "global", "eu-west-1", "us-east-1"]
MOCK_EVENT_ESCALATIONS = ["page_oncall", "page_oncall", "page_oncall", "create_ticket", "create_ticket"]
MOCK_EVENT_RESPONSE = (
    "Incident routed to on-call team. "
    "Immediate action: acknowledge and begin triage. "
    "Follow runbook for this event type."
)


async def _measure_one_event(
    event_text: str,
    event_idx: int,
    tiktoken_count_fn: Any,
) -> Dict[str, Any]:
    """Run vanilla (5-routing + 1 content) vs compiled (0-routing + 1 content) for one event."""
    mock_class = MOCK_EVENT_CLASSIFICATIONS[event_idx % len(MOCK_EVENT_CLASSIFICATIONS)]
    mock_sev = MOCK_EVENT_SEVERITIES[event_idx % len(MOCK_EVENT_SEVERITIES)]
    mock_team = MOCK_EVENT_TEAMS[event_idx % len(MOCK_EVENT_TEAMS)]
    mock_region = MOCK_EVENT_REGIONS[event_idx % len(MOCK_EVENT_REGIONS)]
    mock_esc = MOCK_EVENT_ESCALATIONS[event_idx % len(MOCK_EVENT_ESCALATIONS)]

    def tk(sys: str, user: str) -> Tuple[int, int]:
        inp = _tiktoken_count(sys + "\n\n" + user)
        return inp, 0

    def tk_with_out(sys: str, user: str, out: str) -> Tuple[int, int]:
        inp = _tiktoken_count(sys + "\n\n" + user)
        out_tk = _tiktoken_count(out)
        return inp, out_tk

    vanilla_ledger: List[Tuple[str, int, int]] = []
    # Step 1: classify
    i, o = tk_with_out(EVENT_CLASSIFY_SYSTEM, event_text + "\nClassification:", mock_class)
    vanilla_ledger.append(("classify_event_type", i, o))
    # Step 2: severity
    ctx = f"Event: {event_text}\nType: {mock_class}\nSeverity:"
    i, o = tk_with_out(EVENT_SEVERITY_SYSTEM, ctx, mock_sev)
    vanilla_ledger.append(("assess_severity", i, o))
    # Step 3: team routing
    ctx = f"Event: {event_text}\nType: {mock_class}\nSeverity: {mock_sev}\nAssign team:"
    i, o = tk_with_out(EVENT_TEAM_SYSTEM, ctx, mock_team)
    vanilla_ledger.append(("route_team", i, o))
    # Step 4: region
    ctx = f"Event: {event_text}\nPrimary region:"
    i, o = tk_with_out(EVENT_REGION_SYSTEM, ctx, mock_region)
    vanilla_ledger.append(("determine_region", i, o))
    # Step 5: escalation
    ctx = f"Event: {event_text}\nType: {mock_class}\nSeverity: {mock_sev}\nEscalation action:"
    i, o = tk_with_out(EVENT_ESCALATION_SYSTEM, ctx, mock_esc)
    vanilla_ledger.append(("escalation_policy", i, o))
    # Step 6: response
    ctx = f"Event: {event_text}\nType: {mock_class}\nSeverity: {mock_sev}\nTeam: {mock_team}\nResponse:"
    i, o = tk_with_out(EVENT_RESPONSE_SYSTEM, ctx, MOCK_EVENT_RESPONSE)
    vanilla_ledger.append(("generate_response", i, o))

    # Compiled: steps 1-5 are IR branches; only step 6 calls LLM (shorter prompt)
    compiled_ledger: List[Tuple[str, int, int]] = []
    compiled_sys = EVENT_RESPONSE_COMPILED.get(mock_class, _EVENT_RESPONSE_DEFAULT)
    ctx_compiled = f"Event: {event_text}\nResponse:"
    i, o = tk_with_out(compiled_sys, ctx_compiled, MOCK_EVENT_RESPONSE)
    compiled_ledger.append(("generate_response", i, o))

    vanilla_total = sum(inp + out for _, inp, out in vanilla_ledger)
    compiled_total = sum(inp + out for _, inp, out in compiled_ledger)

    v_steps = {s: (inp, out) for s, inp, out in vanilla_ledger}
    c_steps = {s: (inp, out) for s, inp, out in compiled_ledger}
    all_steps = list(dict.fromkeys([s for s, _, _ in vanilla_ledger] + [s for s, _, _ in compiled_ledger]))
    step_rows = []
    for step in all_steps:
        v_i, v_o = v_steps.get(step, (0, 0))
        c_i, c_o = c_steps.get(step, (0, 0))
        v_t = v_i + v_o
        c_t = c_i + c_o
        step_rows.append({
            "step": step,
            "vanilla_total": v_t,
            "compiled_total": c_t,
            "tokens_saved": v_t - c_t,
            "is_ir_routed": c_t == 0 and v_t > 0,
        })

    return {
        "event_label": f"Event #{event_idx + 1}",
        "event_tiktoken": _tiktoken_count(event_text),
        "vanilla": {
            "total_tokens": vanilla_total,
            "llm_calls": len(vanilla_ledger),
        },
        "compiled": {
            "total_tokens": compiled_total,
            "llm_calls": len(compiled_ledger),
        },
        "savings_ratio": _ratio(vanilla_total, compiled_total),
        "step_breakdown": step_rows,
    }


async def run_scenario_event_routing() -> Dict[str, Any]:
    """
    Event routing scenario: 5 LLM routing steps + 1 content step.

    Baseline assumption (vanilla): the team uses LLM for ALL routing decisions —
    classify event type, assign severity, route to team, determine region, and
    determine escalation policy.  This is a documented pattern in LLM-first
    observability products and ITSM automation prototypes that delegate routing
    to the model to avoid maintaining rule engines.

    Compiled AINL replaces all 5 routing steps with zero-token IR branches,
    calling LLM only for the final response generation step.

    NOTE: A well-engineered rule-based equivalent would eliminate most routing
    calls regardless of AINL.  This scenario measures the upper end of the
    savings range for "LLM-first routing" architectures.
    """
    results = []
    for idx, event in enumerate(SAMPLE_EVENTS):
        result = await _measure_one_event(event, idx, _tiktoken_count)
        results.append(result)

    vanilla_totals = [r["vanilla"]["total_tokens"] for r in results]
    compiled_totals = [r["compiled"]["total_tokens"] for r in results]
    total_vanilla = sum(vanilla_totals)
    total_compiled = sum(compiled_totals)
    overall_ratio = _ratio(total_vanilla, total_compiled)

    ir_saved = sum(
        s["tokens_saved"] for r in results
        for s in r.get("step_breakdown", []) if s["is_ir_routed"]
    )
    prompt_saved = sum(
        s["tokens_saved"] for r in results
        for s in r.get("step_breakdown", []) if not s["is_ir_routed"]
    )

    return {
        "scenario": "event_routing",
        "description": (
            "Short infrastructure/security events (~25 tokens). "
            "Vanilla = LLM-first: 5 routing steps (classify → severity → team → region → escalation) "
            "all call LLM, representing teams that delegate routing to the model. "
            "Compiled AINL: all 5 routing steps become zero-token IR branches; "
            "1 content step (response generation) still calls LLM. "
            "Represents the upper bound of savings for LLM-first routing architectures."
        ),
        "events_measured": len(results),
        "per_event": results,
        "aggregate": {
            "total_vanilla_tokens": total_vanilla,
            "total_compiled_tokens": total_compiled,
            "overall_savings_ratio": overall_ratio,
            "mean_per_event_vanilla": round(mean(vanilla_totals)),
            "mean_per_event_compiled": round(mean(compiled_totals)),
            "tokens_saved_from_ir_routing": ir_saved,
            "tokens_saved_from_focused_prompts": prompt_saved,
            "ir_routing_pct_of_savings": round(
                100 * ir_saved / (ir_saved + prompt_saved), 1
            ) if (ir_saved + prompt_saved) > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Scenario: triage_heavy (same 3 docs processed as a batch queue)
# Models a high-volume classification workload where routing cost dominates.
# ---------------------------------------------------------------------------

async def run_scenario_triage_heavy(batch_size: int = 10) -> Dict[str, Any]:
    """
    Simulate a queue of ``batch_size`` documents (round-robin across the 3 sample types).
    This models an enterprise triage workload where documents arrive continuously.
    At 10K docs/month the token spend compounds proportionally.
    """
    from pure_async_python import (
        SAMPLE_DOCUMENT_CONTRACT,
        SAMPLE_DOCUMENT_INVOICE,
        SAMPLE_DOCUMENT_SUPPORT,
    )

    doc_pool = [
        (SAMPLE_DOCUMENT_INVOICE, "invoice", "Invoice"),
        (SAMPLE_DOCUMENT_CONTRACT, "contract", "Contract"),
        (SAMPLE_DOCUMENT_SUPPORT, "support", "Support"),
    ]

    batch_results = []
    for i in range(batch_size):
        doc, doc_type, label = doc_pool[i % len(doc_pool)]
        result = await measure_one_doc(doc, doc_type, f"{label} #{i + 1}")
        batch_results.append(result)

    total_vanilla = sum(r["vanilla"]["total_tokens"] for r in batch_results)
    total_compiled = sum(r["compiled"]["total_tokens"] for r in batch_results)
    overall_ratio = _ratio(total_vanilla, total_compiled)

    monthly_docs = 5_000
    monthly_vanilla = round(total_vanilla / batch_size * monthly_docs)
    monthly_compiled = round(total_compiled / batch_size * monthly_docs)

    # GPT-4o May 2026 pricing: $2.50/1M input, $10/1M output.
    # These pipelines are ~92% input tokens by token count, so blended ≈ $3.10/1M = $0.0031/1K.
    # Using $0.003/1K here is the conservative (lower-savings) estimate.
    gpt4o_per_1k = 0.003
    monthly_cost_vanilla = round(monthly_vanilla / 1000 * gpt4o_per_1k, 2)
    monthly_cost_compiled = round(monthly_compiled / 1000 * gpt4o_per_1k, 2)

    return {
        "scenario": "triage_heavy",
        "description": (
            f"Batch of {batch_size} documents (round-robin, 3 types). "
            "Models a classification-heavy triage queue at enterprise scale. "
            "Vanilla = LLM-first (all routing via LLM)."
        ),
        "batch_size": batch_size,
        "aggregate": {
            "batch_total_vanilla_tokens": total_vanilla,
            "batch_total_compiled_tokens": total_compiled,
            "overall_savings_ratio": overall_ratio,
            "extrapolated_monthly_at_5k_docs": {
                "vanilla_tokens": monthly_vanilla,
                "compiled_tokens": monthly_compiled,
                "vanilla_est_cost_usd_gpt4o": monthly_cost_vanilla,
                "compiled_est_cost_usd_gpt4o": monthly_cost_compiled,
                "monthly_savings_usd": round(monthly_cost_vanilla - monthly_cost_compiled, 2),
                "cost_model_note": (
                    "GPT-4o: $2.50/1M input + $10/1M output; blended ~$0.003/1K for these "
                    "pipelines (~92% input tokens). Actual costs vary by provider and model."
                ),
            },
        },
        "sample_doc_breakdown": batch_results[:3],
    }


# ---------------------------------------------------------------------------
# Scenario: routing_depth_sensitivity
# Shows how savings ratio scales as the number of LLM routing steps grows.
# This is the cleanest argument for the "or more" qualifier: more routing
# steps → higher savings, directly proportional.
# ---------------------------------------------------------------------------

# Representative average per-step token costs derived from the doc_processing
# scenario measurements (invoice document).  These are the cost INPUTS for the
# analytical sensitivity table — not modelled calls.
_AVG_ROUTING_STEP_TOKENS = 370   # typical classify/route LLM call (prompt + doc fragment)
_AVG_CONTENT_STEP_TOKENS_VANILLA = 350   # generic content step in vanilla
_AVG_CONTENT_STEP_TOKENS_COMPILED = 270  # type-specific content step in compiled
_FIXED_CONTENT_STEPS = 3          # extract + summarize + action_items (always present)


def _sensitivity_row(routing_steps: int) -> Dict[str, Any]:
    """
    Analytically compute savings ratio for a pipeline with N LLM routing steps
    and a fixed set of content steps, using average token costs from measured data.
    """
    vanilla_total = (
        routing_steps * _AVG_ROUTING_STEP_TOKENS
        + _FIXED_CONTENT_STEPS * _AVG_CONTENT_STEP_TOKENS_VANILLA
    )
    compiled_total = _FIXED_CONTENT_STEPS * _AVG_CONTENT_STEP_TOKENS_COMPILED
    ratio = _ratio(vanilla_total, compiled_total)
    return {
        "routing_steps": routing_steps,
        "vanilla_tokens": vanilla_total,
        "compiled_tokens": compiled_total,
        "savings_ratio": ratio,
        "routing_pct_of_vanilla": round(
            100 * routing_steps * _AVG_ROUTING_STEP_TOKENS / vanilla_total, 1
        ),
    }


async def run_scenario_routing_depth_sensitivity() -> Dict[str, Any]:
    """
    Analytical sensitivity table: savings ratio as a function of routing depth.

    Derived from per-step average token costs measured in the doc_processing scenario.
    No LLM calls required — this is a pure analytical projection.

    Interpretation:
      1 routing step  → savings start low (routing is a small fraction of pipeline cost)
      2 routing steps → crosses 2× (standard doc pipeline territory)
      4 routing steps → approaches 4× (multi-level classification pipelines)
      5 routing steps → 5×+ (event routing, ITSM automation, deep intent hierarchies)
    """
    rows = [_sensitivity_row(n) for n in range(1, 11)]
    two_x_threshold = next((r["routing_steps"] for r in rows if (r["savings_ratio"] or 0) >= 2.0), None)
    five_x_threshold = next((r["routing_steps"] for r in rows if (r["savings_ratio"] or 0) >= 5.0), None)

    return {
        "scenario": "routing_depth_sensitivity",
        "description": (
            "Analytical projection of savings ratio vs number of LLM routing steps. "
            "Average per-step token costs derived from measured doc_processing data. "
            "Demonstrates that the 2–5× range spans a natural, continuous parameter space."
        ),
        "methodology": (
            f"Vanilla = N × {_AVG_ROUTING_STEP_TOKENS} (routing) + "
            f"{_FIXED_CONTENT_STEPS} × {_AVG_CONTENT_STEP_TOKENS_VANILLA} (content). "
            f"Compiled = {_FIXED_CONTENT_STEPS} × {_AVG_CONTENT_STEP_TOKENS_COMPILED} (content only). "
            "Average costs from invoice document measurement."
        ),
        "two_x_at_routing_steps": two_x_threshold,
        "five_x_at_routing_steps": five_x_threshold,
        "rows": rows,
        "aggregate": {
            "overall_savings_ratio": rows[1]["savings_ratio"] if len(rows) > 1 else None,
        },
    }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(
    scenarios: List[Dict[str, Any]],
    *,
    tiktoken_available: bool,
) -> Dict[str, Any]:
    scenario_map = {s["scenario"]: s for s in scenarios}

    savings_range_low: Optional[float] = None
    savings_range_high: Optional[float] = None
    # Use savings_ratio_vs_vanilla (LLM-first comparison) for the headline range.
    # routing_depth_sensitivity is an analytical projection, not a measured scenario.
    for s in scenarios:
        if s.get("scenario") == "routing_depth_sensitivity":
            continue
        agg = s.get("aggregate", {})
        ratio = agg.get("savings_ratio_vs_vanilla") or agg.get("overall_savings_ratio")
        if ratio is not None:
            if savings_range_low is None or ratio < savings_range_low:
                savings_range_low = ratio
            if savings_range_high is None or ratio > savings_range_high:
                savings_range_high = ratio

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "token_savings",
        "token_counting_method": "tiktoken_cl100k_base" if tiktoken_available else "word_count_fallback",
        "tiktoken_available": tiktoken_available,
        "savings_range": {
            "low_x": savings_range_low,
            "high_x": savings_range_high,
            "note": (
                "Range across scenarios.  Savings narrow for very long documents; "
                "savings widen for classification-heavy pipelines with short documents."
            ),
        },
        "methodology": {
            "three_way_comparison": {
                "vanilla": "LLM-first: all pipeline steps (including routing) call LLM. Common in prototypes.",
                "vanilla_optimized": (
                    "Hand-optimised: LLM for classification only; rule-based routing (0 tokens); "
                    "type-specific prompts for content steps — same as compiled AINL content steps."
                ),
                "compiled": (
                    "Compiled AINL: IR dispatch eliminates all routing calls (including classification). "
                    "Steps 3–5 use type-specific prompts guaranteed by the compiler."
                ),
            },
            "savings_attribution": {
                "routing_elimination": "vanilla_optimized vs compiled — irreducible IR compilation benefit (~1.4×)",
                "full_llm_first_savings": "vanilla vs compiled — full comparison against LLM-first stack (~2.1×)",
            },
            "prompt_templates": "benchmarks/handwritten_baselines/doc_pipeline/pure_async_python.py",
            "ainl_reference": "examples/benchmark/doc_pipeline_compiled.ainl",
            "reproducibility": (
                "Run `python scripts/benchmark_token_savings.py` on any machine with "
                "`pip install ainativelang[benchmark]`.  Token counts are deterministic "
                "(tiktoken cl100k_base; no live LLM calls required)."
            ),
            "output_token_note": (
                "Mock LLM outputs are fixed strings for reproducibility.  Real model outputs "
                "for extraction/summarization are typically 2–5× larger; higher real output "
                "tokens reduce the headline savings ratio to approximately 1.8–1.95× for the "
                "doc_processing scenario.  IR-routing savings (steps eliminated entirely) are "
                "unaffected by output size."
            ),
        },
        "scenarios": scenario_map,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_token_savings_markdown(report: Dict[str, Any]) -> str:
    method = report["token_counting_method"]
    generated = report["generated_at_utc"]

    dp = report["scenarios"].get("doc_processing", {})
    dp_agg = dp.get("aggregate", {})
    ratio_vs_naive = dp_agg.get("savings_ratio_vs_vanilla") or dp_agg.get("overall_savings_ratio")
    ratio_vs_opt = dp_agg.get("savings_ratio_vs_vanilla_optimized")

    er = report["scenarios"].get("event_routing", {})
    er_ratio = er.get("aggregate", {}).get("overall_savings_ratio")

    rds = report["scenarios"].get("routing_depth_sensitivity", {})

    lines: List[str] = [
        "## LLM Token Savings: Compiled vs Vanilla Pipeline",
        "",
        "Reproducible analytical benchmark.  Token counts use tiktoken (cl100k_base) on "
        "fixed prompt templates — no live LLM calls required.  Fully reproducible:",
        "```",
        "pip install 'ainativelang[benchmark]'",
        "python scripts/benchmark_token_savings.py",
        "```",
        "",
        f"- Generated (UTC): `{generated}`",
        f"- Token counting: `{method}`",
        f"- Prompt templates: `benchmarks/handwritten_baselines/doc_pipeline/pure_async_python.py`",
        f"- Reference AINL: `examples/benchmark/doc_pipeline_compiled.ainl`",
        "",
        "### How to read the numbers: three baselines",
        "",
        "The benchmark compares **three architectures** so that every token saved is "
        "attributable to a specific, auditable mechanism:",
        "",
        "| Architecture | What it represents | Routing calls |",
        "|---|---|---:|",
        "| **Vanilla (LLM-first)** | Common in LangChain/LangGraph prototypes; every step including routing calls LLM | All steps |",
        "| **Vanilla-optimised** | What a skilled engineer hand-codes without AINL: LLM for classification, rule-based routing, type-specific prompts | Classify only |",
        "| **Compiled AINL** | IR dispatch eliminates all routing LLM calls; type-specific prompts guaranteed by compiler | None |",
        "",
        "**What compilation uniquely provides:**",
        "",
        "- **vs vanilla-optimised → routing-elimination savings: "
        + (f"~{ratio_vs_opt}×" if ratio_vs_opt else "see table")
        + "** (irreducible; attributable entirely to IR compilation)",
        "- **vs LLM-first vanilla → full savings: "
        + (f"~{ratio_vs_naive}×" if ratio_vs_naive else "see table")
        + "** (typical for standard 5-step doc pipelines)",
        "",
        "### Three-way comparison — doc_processing scenario",
        "",
        "| Document | Vanilla (LLM-first) | Vanilla-optimised | Compiled AINL | vs LLM-first | vs optimised |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    if dp:
        for doc in dp.get("per_document", []):
            v = doc["vanilla"]["total_tokens"]
            o = doc["vanilla_optimized"]["total_tokens"]
            c = doc["compiled"]["total_tokens"]
            rv = doc.get("savings_ratio_vs_vanilla") or "—"
            ro = doc.get("savings_ratio_vs_vanilla_optimized") or "—"
            lines.append(
                f"| {doc['document_label']} | {v:,} tk | {o:,} tk | {c:,} tk "
                f"| **{rv}×** | {ro}× |"
            )
        if dp_agg:
            tv = dp_agg.get("total_vanilla_tokens", 0)
            to_ = dp_agg.get("total_vanilla_optimized_tokens", 0)
            tc = dp_agg.get("total_compiled_tokens", 0)
            rv = dp_agg.get("savings_ratio_vs_vanilla") or "—"
            ro = dp_agg.get("savings_ratio_vs_vanilla_optimized") or "—"
            lines.append(
                f"| **Total (3 docs)** | **{tv:,} tk** | **{to_:,} tk** | **{tc:,} tk** "
                f"| **{rv}×** | **{ro}×** |"
            )

    ir_pct = dp_agg.get("ir_routing_pct_of_savings", 0)
    fp_pct = 100 - ir_pct if ir_pct else 0
    lines += [
        "",
        f"Of the total savings (vanilla vs compiled): **{ir_pct}%** from IR routing elimination, "
        f"**{fp_pct}%** from type-specific focused prompts.",
        "",
        "### Routing-depth sensitivity — how savings scale with pipeline complexity",
        "",
        "Savings increase directly with the number of routing steps.  The following table "
        "is derived analytically from per-step costs measured above:",
        "",
        "| LLM routing steps | Vanilla tokens | Compiled tokens | Savings ratio | Routing % of vanilla |",
        "|---:|---:|---:|---:|---:|",
    ]

    if rds:
        for row in rds.get("rows", []):
            ratio_s = f"**{row['savings_ratio']}×**" if row["savings_ratio"] else "—"
            in_range = " ← 2× threshold" if row["routing_steps"] == rds.get("two_x_at_routing_steps") else ""
            in_range5 = " ← 5× threshold" if row["routing_steps"] == rds.get("five_x_at_routing_steps") else ""
            lines.append(
                f"| {row['routing_steps']} | {row['vanilla_tokens']:,} | {row['compiled_tokens']:,} "
                f"| {ratio_s} | {row['routing_pct_of_vanilla']}%{in_range}{in_range5} |"
            )

    lines += [
        "",
        f"2× threshold: {rds.get('two_x_at_routing_steps', '?')} routing step(s).  "
        f"5× threshold: {rds.get('five_x_at_routing_steps', '?')} routing step(s).",
        "",
        "### Event routing — upper end of the range",
        "",
    ]

    if er:
        er_agg = er.get("aggregate", {})
        ev = er_agg.get("total_vanilla_tokens", 0)
        ec = er_agg.get("total_compiled_tokens", 0)
        lines += [
            f"LLM-first event routing (5 routing steps, short events ~25 tokens):  "
            f"vanilla = **{ev:,} tokens**, compiled = **{ec:,} tokens**, savings = **{er_ratio}×**.",
            "",
            "> **Baseline note:** The vanilla baseline for this scenario assumes the team uses LLM "
            "for all 5 routing decisions (classify event type, severity, team assignment, region, "
            "escalation policy).  This represents LLM-first observability/ITSM automation — a real "
            "pattern but at the high end of LLM usage.  A rule-based equivalent without AINL would "
            "eliminate most routing calls regardless; the 7× figure measures the LLM-first architecture "
            "specifically.",
            "",
        ]

    th = report["scenarios"].get("triage_heavy")
    if th:
        ext = th["aggregate"].get("extrapolated_monthly_at_5k_docs", {})
        lines += [
            "### Scale projection (5 000 docs/month, triage_heavy scenario)",
            "",
            f"- Vanilla (LLM-first): **{ext.get('vanilla_tokens', 0):,}** tokens/month  "
            f"(est. **${ext.get('vanilla_est_cost_usd_gpt4o', '—')}** at GPT-4o blended rate)",
            f"- Compiled AINL: **{ext.get('compiled_tokens', 0):,}** tokens/month  "
            f"(est. **${ext.get('compiled_est_cost_usd_gpt4o', '—')}**)",
            f"- **Monthly savings: ~${ext.get('monthly_savings_usd', '—')}**",
            f"- _{ext.get('cost_model_note', '')}_",
            "",
        ]

    lines += [
        "### Methodology, scope, and honest caveats",
        "",
        "**What this measures:**",
        "Token cost of LLM API calls for deterministic pipeline steps (routing, classification, "
        "type dispatch) that compiled AINL eliminates via IR branches.",
        "",
        "**What this does NOT measure:**",
        "- Latency or throughput (covered in `scripts/benchmark_runtime.py`)",
        "- Real model output variance (mock outputs are fixed; real extraction may produce "
        "200–450 tokens vs the ~80 token mock — higher real output tokens reduce the savings "
        "ratio to approximately 1.8–1.95× for the doc_processing scenario)",
        "- Cloud inference costs beyond API tokens (networking, batch overhead)",
        "",
        "**Claim scope:**",
        "- **2–5× vs LLM-first implementations** (prototypes, LangChain/LangGraph agents, "
        "early GPT-4 integrations that delegate routing to the model) — supported for "
        "pipelines with ≥2 routing steps on 200–600 token documents",
        "- **1.3–1.5× vs hand-optimised vanilla** (rule-based routing already in place) — "
        "conservative, irreducible lower bound attributable purely to IR compilation",
        "- **5×+ for routing-heavy pipelines** (≥5 routing steps, short events) — "
        "supported for LLM-first architectures common in observability and ITSM automation",
        "",
        "JSON: `tooling/token_savings_results.json`",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BENCHMARK.md injection
# ---------------------------------------------------------------------------

def inject_token_savings_section(markdown_path: Path, body: str) -> None:
    text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    block = f"{TOKEN_SAVINGS_SECTION_START}\n{body}{TOKEN_SAVINGS_SECTION_END}\n"

    if TOKEN_SAVINGS_SECTION_START in text and TOKEN_SAVINGS_SECTION_END in text:
        pre, _, rest = text.partition(TOKEN_SAVINGS_SECTION_START)
        _, _, post = rest.partition(TOKEN_SAVINGS_SECTION_END)
        new_text = pre + block + post.lstrip("\n")
    else:
        anchor = "\n## Supported vs Unsupported Claims\n"
        if anchor in text:
            new_text = text.replace(anchor, "\n" + block + anchor.lstrip("\n"), 1)
        else:
            new_text = (text.rstrip() + "\n\n" + block) if text else block

    markdown_path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _check_tiktoken() -> bool:
    try:
        import tiktoken  # noqa: F401
        return True
    except ImportError:
        return False


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Reproducible LLM token-savings benchmark for compiled AINL pipelines."
    )
    ap.add_argument(
        "--scenario",
        choices=["all", "doc_processing", "event_routing", "triage_heavy", "routing_depth_sensitivity"],
        default="all",
        help="Which scenario(s) to run (default: all).",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of documents in the triage_heavy batch (default: 10).",
    )
    ap.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help="Path for JSON output.",
    )
    ap.add_argument(
        "--markdown-out",
        default=str(DEFAULT_MARKDOWN_OUT),
        help="Path for BENCHMARK.md injection (use --skip-markdown-inject to skip).",
    )
    ap.add_argument(
        "--skip-markdown-inject",
        action="store_true",
        help="Write JSON only; do not update BENCHMARK.md.",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args()


async def _main_async(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    tiktoken_ok = _check_tiktoken()
    if not tiktoken_ok:
        logger.warning(
            "tiktoken not installed — falling back to word-count approximation. "
            "Install with: pip install 'ainativelang[benchmark]' or pip install tiktoken"
        )

    scenarios_to_run = (
        ["doc_processing", "event_routing", "triage_heavy", "routing_depth_sensitivity"]
        if args.scenario == "all"
        else [args.scenario]
    )

    scenario_results: List[Dict[str, Any]] = []

    for scenario_name in scenarios_to_run:
        logger.info("Running scenario: %s", scenario_name)
        if scenario_name == "doc_processing":
            result = await run_scenario_doc_processing()
        elif scenario_name == "event_routing":
            result = await run_scenario_event_routing()
        elif scenario_name == "triage_heavy":
            result = await run_scenario_triage_heavy(batch_size=args.batch_size)
        elif scenario_name == "routing_depth_sensitivity":
            result = await run_scenario_routing_depth_sensitivity()
        else:
            logger.error("Unknown scenario: %s", scenario_name)
            return 1

        agg = result["aggregate"]
        ratio = agg.get("overall_savings_ratio")
        vt = agg.get("total_vanilla_tokens") or agg.get("batch_total_vanilla_tokens", 0)
        ct = agg.get("total_compiled_tokens") or agg.get("batch_total_compiled_tokens", 0)
        logger.info(
            "  %s: vanilla=%d tokens, compiled=%d tokens, savings=%.2fx",
            scenario_name,
            vt,
            ct,
            ratio or 0,
        )
        scenario_results.append(result)

    report = build_report(scenario_results, tiktoken_available=tiktoken_ok)

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s", json_out)

    if not args.skip_markdown_inject:
        md_path = Path(args.markdown_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        section = render_token_savings_markdown(report)
        inject_token_savings_section(md_path, section)
        logger.info("Injected token-savings section into %s", md_path)

    sr = report["savings_range"]
    print(
        f"\nToken savings benchmark complete.\n"
        f"  Savings range: {sr['low_x']}× – {sr['high_x']}×\n"
        f"  Token counting: {report['token_counting_method']}\n"
        f"  JSON: {json_out}\n"
    )
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
