#!/usr/bin/env python3
"""
LangGraph-shaped baseline for support_ticket_router.ainl.

Semantically aligned with:
  - examples/workflows/support_ticket_router.ainl
  - benchmarks/handwritten_baselines/authoring_density/support_ticket_router.py

Install: pip install langgraph openai
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, TypedDict

from openai import OpenAI

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError(
        "langgraph is required for this baseline. Install with: pip install langgraph"
    ) from e

Priority = Literal["critical", "high", "normal", "low"]
Category = Literal["bug", "billing", "feature", "general"]

TEAM_TABLE: dict[tuple[Priority, Category], tuple[str, int]] = {
    ("critical", "billing"): ("billing-escalations", 2),
    ("critical", "bug"): ("engineering-oncall", 1),
    ("critical", "feature"): ("engineering-oncall", 1),
    ("critical", "general"): ("engineering-oncall", 1),
    ("high", "billing"): ("billing", 4),
    ("high", "bug"): ("support-tier2", 8),
    ("high", "feature"): ("support-tier2", 8),
    ("high", "general"): ("support-tier2", 8),
}

DRAFT_INSTRUCTIONS: dict[tuple[Priority, Category], str] = {
    ("critical", "billing"): (
        "Write an empathetic urgent response for this critical billing issue. "
        "State a 2-hour SLA and offer a direct callback."
    ),
    ("critical", "bug"): (
        "Write an empathetic urgent acknowledgment for this critical engineering issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "feature"): (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "general"): (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("high", "billing"): (
        "Write a professional response for this high-priority billing enquiry. "
        "Confirm 4-hour SLA and name the billing team as the owner."
    ),
    ("high", "bug"): (
        "Write a professional response for this high-priority support ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "feature"): (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "general"): (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
}

NORMAL_DRAFT = (
    "Write a friendly, helpful first response for this support ticket. "
    "Confirm 24-hour SLA."
)


@dataclass
class TicketRouteResult:
    ticket_id: str
    priority: Priority
    category: Category
    team: str
    sla_hours: int
    draft_response: str


class TicketState(TypedDict, total=False):
    ticket_id: str
    ticket_text: str
    priority: Priority
    category: Category
    team: str
    sla_hours: int
    draft_instruction: str
    draft_response: str
    openai_client: OpenAI


def _classify(client: OpenAI, ticket_text: str, instruction: str, max_tokens: int = 10) -> str:
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"{instruction} Ticket: {ticket_text}"}],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    return (completion.choices[0].message.content or "").strip().lower()


def node_classify_priority(state: TicketState) -> dict:
    client = state.get("openai_client") or OpenAI()
    raw = _classify(
        client,
        state["ticket_text"],
        "Classify this support ticket priority as exactly one word — "
        "critical, high, normal, or low.",
    )
    priority: Priority = raw if raw in ("critical", "high", "normal", "low") else "normal"  # type: ignore[assignment]
    return {"priority": priority}


def node_classify_category(state: TicketState) -> dict:
    client = state.get("openai_client") or OpenAI()
    raw = _classify(
        client,
        state["ticket_text"],
        "Classify this support ticket category as exactly one word — "
        "bug, billing, feature, or general.",
    )
    category: Category = raw if raw in ("bug", "billing", "feature", "general") else "general"  # type: ignore[assignment]
    return {"category": category}


def node_route_team(state: TicketState) -> dict:
    route_key = (state["priority"], state["category"])
    if route_key in TEAM_TABLE:
        team, sla_hours = TEAM_TABLE[route_key]
        draft_instruction = DRAFT_INSTRUCTIONS[route_key]
    else:
        team = "support-tier1"
        sla_hours = 24
        draft_instruction = NORMAL_DRAFT
    return {
        "team": team,
        "sla_hours": sla_hours,
        "draft_instruction": draft_instruction,
    }


def node_draft_response(state: TicketState) -> dict:
    client = state.get("openai_client") or OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"{state['draft_instruction']} Ticket: {state['ticket_text']}",
            }
        ],
        max_tokens=200,
        temperature=0.5,
    )
    draft = completion.choices[0].message.content or ""
    return {"draft_response": draft}


def build_support_ticket_router_graph():
    g = StateGraph(TicketState)
    g.add_node("classify_priority", node_classify_priority)
    g.add_node("classify_category", node_classify_category)
    g.add_node("route_team", node_route_team)
    g.add_node("draft_response", node_draft_response)
    g.add_edge(START, "classify_priority")
    g.add_edge("classify_priority", "classify_category")
    g.add_edge("classify_category", "route_team")
    g.add_edge("route_team", "draft_response")
    g.add_edge("draft_response", END)
    return g.compile()


def run_support_ticket_router_langgraph(
    ticket_id: str,
    ticket_text: str,
    *,
    openai_client: Optional[OpenAI] = None,
) -> TicketRouteResult:
    app = build_support_ticket_router_graph()
    final = app.invoke(
        {
            "ticket_id": ticket_id,
            "ticket_text": ticket_text,
            "openai_client": openai_client or OpenAI(),
        }
    )
    return TicketRouteResult(
        ticket_id=ticket_id,
        priority=final["priority"],
        category=final["category"],
        team=final["team"],
        sla_hours=int(final["sla_hours"]),
        draft_response=str(final.get("draft_response") or ""),
    )


def source_text_for_token_count() -> str:
    return Path(__file__).read_text(encoding="utf-8")


if __name__ == "__main__":
    ticket_id = sys.argv[1] if len(sys.argv) > 1 else "TKT-0001"
    ticket_text = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "I was charged twice for my subscription this month and need an immediate refund."
    )
    result = run_support_ticket_router_langgraph(ticket_id, ticket_text)
    print(json.dumps(vars(result), indent=2))
