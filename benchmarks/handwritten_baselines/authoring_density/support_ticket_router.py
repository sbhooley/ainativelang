"""
Authoring-density baseline: customer support ticket router — idiomatic Python.

Semantically equivalent to examples/workflows/support_ticket_router.ainl.
Written in the style a proficient Python developer (or LLM) would produce
when asked to "build a support ticket triage pipeline that classifies priority
and category, routes to the correct team, and generates a draft first response."

Dependencies: openai  (pip install openai)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from openai import OpenAI

Priority = Literal["critical", "high", "normal", "low"]
Category = Literal["bug", "billing", "feature", "general"]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TicketRouteResult:
    ticket_id: str
    priority: Priority
    category: Category
    team: str
    sla_hours: int
    draft_response: str


# ---------------------------------------------------------------------------
# Routing table (deterministic — zero LLM tokens)
# ---------------------------------------------------------------------------

TEAM_TABLE: dict[tuple[Priority, Category], tuple[str, int]] = {
    ("critical", "billing"):  ("billing-escalations", 2),
    ("critical", "bug"):      ("engineering-oncall",  1),
    ("critical", "feature"):  ("engineering-oncall",  1),
    ("critical", "general"):  ("engineering-oncall",  1),
    ("high",     "billing"):  ("billing",             4),
    ("high",     "bug"):      ("support-tier2",       8),
    ("high",     "feature"):  ("support-tier2",       8),
    ("high",     "general"):  ("support-tier2",       8),
}

DRAFT_INSTRUCTIONS: dict[tuple[Priority, Category], str] = {
    ("critical", "billing"):  (
        "Write an empathetic urgent response for this critical billing issue. "
        "State a 2-hour SLA and offer a direct callback."
    ),
    ("critical", "bug"):  (
        "Write an empathetic urgent acknowledgment for this critical engineering issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "feature"):  (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("critical", "general"):  (
        "Write an empathetic urgent acknowledgment for this critical issue. "
        "State the on-call team is engaged and commit to a 1-hour response."
    ),
    ("high", "billing"):  (
        "Write a professional response for this high-priority billing enquiry. "
        "Confirm 4-hour SLA and name the billing team as the owner."
    ),
    ("high", "bug"):  (
        "Write a professional response for this high-priority support ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "feature"):  (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
    ("high", "general"):  (
        "Write a professional response for this high-priority ticket. "
        "Confirm tier-2 assignment and 8-hour SLA."
    ),
}

NORMAL_DRAFT = (
    "Write a friendly, helpful first response for this support ticket. "
    "Confirm 24-hour SLA."
)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def route_ticket(
    ticket_id: str,
    ticket_text: str,
    openai_client: OpenAI | None = None,
) -> TicketRouteResult:
    """
    Classify ticket priority + category via LLM, assign team via routing table,
    generate a draft first response via LLM.
    """
    if openai_client is None:
        openai_client = OpenAI()

    def _classify(instruction: str, max_tokens: int = 10) -> str:
        completion = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"{instruction} Ticket: {ticket_text}"}],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return (completion.choices[0].message.content or "").strip().lower()

    # LLM call 1: classify priority
    priority_raw = _classify(
        "Classify this support ticket priority as exactly one word — "
        "critical, high, normal, or low."
    )
    priority: Priority = priority_raw if priority_raw in ("critical", "high", "normal", "low") else "normal"  # type: ignore[assignment]

    # LLM call 2: classify category
    category_raw = _classify(
        "Classify this support ticket category as exactly one word — "
        "bug, billing, feature, or general."
    )
    category: Category = category_raw if category_raw in ("bug", "billing", "feature", "general") else "general"  # type: ignore[assignment]

    # Deterministic routing — zero LLM tokens
    route_key = (priority, category)
    if route_key in TEAM_TABLE:
        team, sla_hours = TEAM_TABLE[route_key]
        draft_instruction = DRAFT_INSTRUCTIONS[route_key]
    else:
        team = "support-tier1"
        sla_hours = 24
        draft_instruction = NORMAL_DRAFT

    # LLM call 3: generate draft response
    draft_completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"{draft_instruction} Ticket: {ticket_text}",
            }
        ],
        max_tokens=200,
        temperature=0.5,
    )
    draft: str = draft_completion.choices[0].message.content or ""

    return TicketRouteResult(
        ticket_id=ticket_id,
        priority=priority,
        category=category,
        team=team,
        sla_hours=sla_hours,
        draft_response=draft,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    ticket_id = sys.argv[1] if len(sys.argv) > 1 else "TKT-0001"
    ticket_text = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "I was charged twice for my subscription this month and need an immediate refund."
    )
    result = route_ticket(ticket_id, ticket_text)
    print(json.dumps(vars(result), indent=2))
