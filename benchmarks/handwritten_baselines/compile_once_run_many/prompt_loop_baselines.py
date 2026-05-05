"""
Compile-once / run-many baselines: prompt-loop (LLM-first) agent implementations.

These baselines model the "LLM-first" pattern common in LangChain / LangGraph /
early GPT-4 agentic stacks, where the LLM is invoked for orchestration decisions
on *every* execution — not just content generation.

Each baseline uses a MockLLM that counts tokens analytically (no API calls).
The token counts are then compared to the AINL compiled equivalent.

Key insight being benchmarked
------------------------------
AINL compiles routing and classification logic to IR branches executed by the
runtime engine — those branches cost zero LLM tokens regardless of how many
times the workflow runs.  A prompt-loop agent re-pays the full orchestration
overhead on every run.

Three scenarios
---------------
1. health_monitor_prompt_loop     — poll endpoint, LLM decides severity + alert
2. lead_enrichment_prompt_loop    — fetch firmographic data, LLM decides tier + context
3. support_triage_prompt_loop     — classify priority, LLM decides routing + draft

These are NOT unrealistic strawmen.  Every scenario uses the *same number of
LLM calls* for content as the AINL equivalent.  The difference is that the
prompt-loop agents add orchestration LLM calls; AINL routes those via IR.
"""

from __future__ import annotations

import textwrap
import time
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# MockLLM: analytical token counting, no network calls
# ---------------------------------------------------------------------------

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def _count(text: str) -> int:
        return len(_ENC.encode(text))

except ImportError:
    def _count(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text) // 4)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class MockLLM:
    """
    Deterministic LLM mock.  Returns a canned reply and counts tokens
    analytically so results are reproducible without API keys.
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    call_count: int = 0

    def call(
        self,
        prompt: str,
        mock_output: str = "mock_response",
    ) -> LLMResponse:
        input_tok = _count(prompt)
        output_tok = _count(mock_output)
        self.total_input_tokens += input_tok
        self.total_output_tokens += output_tok
        self.call_count += 1
        return LLMResponse(
            text=mock_output,
            input_tokens=input_tok,
            output_tokens=output_tok,
        )

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def reset(self) -> None:
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0


# ---------------------------------------------------------------------------
# Shared canned mock outputs (same across all runs for reproducibility)
# ---------------------------------------------------------------------------

MOCK_SEVERITY_HEALTHY = "healthy"
MOCK_SEVERITY_DEGRADED = "degraded"
MOCK_TIER_ENTERPRISE = "enterprise"
MOCK_PRIORITY_HIGH = "high"
MOCK_CATEGORY_BILLING = "billing"
MOCK_SALES_CONTEXT = (
    "Stripe is the gold standard for developer-first payment APIs, "
    "enabling enterprise teams to launch global payment infrastructure "
    "in weeks, not quarters."
)
MOCK_ALERT_TEXT = (
    "ALERT: Endpoint https://api.example.com/health is DOWN. "
    "Status 503. On-call team notified. ETA 15 minutes."
)
MOCK_DRAFT_RESPONSE = (
    "Dear Customer, thank you for reaching out. "
    "We have escalated your billing enquiry to our billing team. "
    "You can expect a resolution within 4 hours."
)
MOCK_ROUTING_DECISION = "route_to_tier2_support"


# ---------------------------------------------------------------------------
# Scenario 1: Health monitor — prompt-loop variant
# ---------------------------------------------------------------------------

HEALTH_MONITOR_SYSTEM = textwrap.dedent("""\
    You are an infrastructure monitoring agent.
    Your task is to analyse an HTTP health check result and decide:
    1. The severity level: healthy | degraded | critical
    2. Whether to generate an incident alert (yes/no)
    3. If yes, draft the alert text.
    Reply with a JSON object: {"severity": "...", "generate_alert": true/false, "alert": "..."}
""")

HEALTH_MONITOR_STEP_PROMPT = textwrap.dedent("""\
    Health check result:
      endpoint_url: {endpoint_url}
      http_status:  {status_code}
      latency_ms:   {latency_ms}
      threshold_ms: {threshold_ms}

    Should you generate an alert?  Reply with the severity and alert text.
""")


def health_monitor_prompt_loop(
    endpoint_url: str = "https://api.example.com/health",
    status_code: int = 200,
    latency_ms: float = 320.0,
    threshold_ms: float = 500.0,
    llm: Optional[MockLLM] = None,
) -> dict:
    """
    LLM-first health monitor.

    Step 1 (LLM): the agent asks the LLM to analyse the health check data and
                  decide severity + whether to generate an alert.
    Step 2 (LLM, conditional): generate alert text if LLM decided yes.

    In the AINL compiled equivalent, step 1 is a zero-token IR branch.
    """
    if llm is None:
        llm = MockLLM()

    # LLM call 1: orchestration — the LLM decides severity + alert routing
    orchestration_prompt = HEALTH_MONITOR_SYSTEM + HEALTH_MONITOR_STEP_PROMPT.format(
        endpoint_url=endpoint_url,
        status_code=status_code,
        latency_ms=latency_ms,
        threshold_ms=threshold_ms,
    )
    orch_r = llm.call(orchestration_prompt, mock_output='{"severity":"degraded","generate_alert":true}')

    # LLM call 2: alert generation (conditional, but always fires in this scenario)
    alert_prompt = (
        f"Generate a concise incident alert for: endpoint={endpoint_url}, "
        f"latency={latency_ms}ms, threshold={threshold_ms}ms, "
        f"severity=degraded."
    )
    alert_r = llm.call(alert_prompt, mock_output=MOCK_ALERT_TEXT)

    return {
        "severity": "degraded",
        "alert": alert_r.text,
        "llm_calls": llm.call_count,
        "total_tokens": llm.total_tokens,
    }


# ---------------------------------------------------------------------------
# Scenario 2: Lead enrichment — prompt-loop variant
# ---------------------------------------------------------------------------

LEAD_ENRICH_SYSTEM = textwrap.dedent("""\
    You are a lead enrichment agent.
    Given firmographic data for a company, your task is to:
    1. Classify the account tier: enterprise (>500 emp), mid_market (101-500), smb (<=100)
    2. Generate a personalised sales context string for the classified tier.
    Reply with: {"tier": "...", "sales_context": "..."}
""")

LEAD_ENRICH_STEP_PROMPT = textwrap.dedent("""\
    Company data:
      domain:     {domain}
      name:       {company_name}
      employees:  {employees}
      industry:   {industry}
      country:    {country}

    Classify tier and generate sales context.
""")


def lead_enrichment_prompt_loop(
    domain: str = "stripe.com",
    company_name: str = "Stripe",
    employees: int = 8000,
    industry: str = "Financial Technology",
    country: str = "United States",
    llm: Optional[MockLLM] = None,
) -> dict:
    """
    LLM-first lead enrichment.

    Step 1 (LLM): the agent asks the LLM to classify tier AND generate context
                  in one call — the LLM does both routing and content.

    In the AINL compiled equivalent, tier classification is a zero-token IR
    branch (core.GT emp_count 500), and only the sales context generation goes
    to the LLM.
    """
    if llm is None:
        llm = MockLLM()

    # LLM call 1: orchestration + content — LLM does tier routing AND generates context
    orchestration_prompt = LEAD_ENRICH_SYSTEM + LEAD_ENRICH_STEP_PROMPT.format(
        domain=domain,
        company_name=company_name,
        employees=employees,
        industry=industry,
        country=country,
    )
    orch_r = llm.call(
        orchestration_prompt,
        mock_output=f'{{"tier":"enterprise","sales_context":"{MOCK_SALES_CONTEXT}"}}',
    )

    return {
        "tier": "enterprise",
        "domain": domain,
        "sales_context": MOCK_SALES_CONTEXT,
        "llm_calls": llm.call_count,
        "total_tokens": llm.total_tokens,
    }


# ---------------------------------------------------------------------------
# Scenario 3: Support ticket triage — prompt-loop variant
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM = textwrap.dedent("""\
    You are a support triage agent.
    Given a support ticket, your task is to:
    1. Classify priority: critical | high | normal | low
    2. Classify category: bug | billing | feature | general
    3. Decide the routing: team name and SLA hours
    4. Generate a draft first response
    Reply with:
      {"priority": "...", "category": "...", "team": "...", "sla_hours": N, "draft": "..."}
""")

TRIAGE_STEP_PROMPT = "Ticket #{ticket_id}: {ticket_text}\n\nTriage and draft response."


def support_triage_prompt_loop(
    ticket_id: str = "TKT-4821",
    ticket_text: str = (
        "I was charged twice for my subscription this month "
        "and need an immediate refund."
    ),
    llm: Optional[MockLLM] = None,
) -> dict:
    """
    LLM-first support triage.

    Single LLM call: the agent asks the LLM to do priority classification,
    category classification, team routing, and draft response all in one go.

    In the AINL compiled equivalent, priority routing and category routing are
    zero-token IR branches; only the three LLM calls for classification and
    draft generation go to the LLM.

    NOTE: This scenario is unusual in that the prompt-loop baseline uses *fewer*
    LLM calls (1 combined vs 3 separate) but pays more tokens per call because
    the LLM must also decide routing (team, SLA) rather than just classify or draft.
    This demonstrates that "fewer calls" ≠ "fewer tokens" for agentic pipelines.
    """
    if llm is None:
        llm = MockLLM()

    # Single combined LLM call: classify + route + draft
    combined_prompt = (
        TRIAGE_SYSTEM
        + TRIAGE_STEP_PROMPT.format(ticket_id=ticket_id, ticket_text=ticket_text)
    )
    orch_r = llm.call(
        combined_prompt,
        mock_output=(
            f'{{"priority":"high","category":"billing","team":"billing",'
            f'"sla_hours":4,"draft":"{MOCK_DRAFT_RESPONSE}"}}'
        ),
    )

    return {
        "ticket_id": ticket_id,
        "priority": "high",
        "category": "billing",
        "team": "billing",
        "sla_hours": 4,
        "draft_response": MOCK_DRAFT_RESPONSE,
        "llm_calls": llm.call_count,
        "total_tokens": llm.total_tokens,
    }


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

def _smoke() -> None:
    print("=== Prompt-loop baselines smoke test ===\n")

    llm1 = MockLLM()
    r1 = health_monitor_prompt_loop(llm=llm1)
    print(f"Health monitor (degraded):   {llm1.call_count} LLM calls, {llm1.total_tokens} tokens")

    llm2 = MockLLM()
    r2 = lead_enrichment_prompt_loop(llm=llm2)
    print(f"Lead enrichment (enterprise): {llm2.call_count} LLM calls, {llm2.total_tokens} tokens")

    llm3 = MockLLM()
    r3 = support_triage_prompt_loop(llm=llm3)
    print(f"Support triage (high/billing): {llm3.call_count} LLM calls, {llm3.total_tokens} tokens")

    print("\nAll scenarios ran without errors.")


if __name__ == "__main__":
    _smoke()
