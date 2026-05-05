#!/usr/bin/env python3
"""
Handwritten async baseline mirroring a vanilla (non-compiled) 5-step document pipeline.

Every step that would be a free IR branch in the compiled AINL version instead makes an
LLM API call here.  The LLM is fully mocked — no network traffic — so this benchmark is
hermetic and reproducible.

Pipeline steps
--------------
1. classify_type   → calls LLM with full document  (zero tokens in compiled AINL)
2. route_action    → calls LLM with type + document (zero tokens in compiled AINL)
3. extract_fields  → calls LLM with full document  (also present in compiled, but prompt is longer)
4. summarize       → calls LLM with full document  (also present in compiled, but prompt is longer)
5. action_items    → calls LLM with full document  (also present in compiled, but prompt is longer)

Token accounting
----------------
``DocPipelineInput.token_ledger`` records (step, input_tokens, output_tokens) for every
mock LLM call so ``scripts/benchmark_token_savings.py`` can compute analytics.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# Vanilla prompts must be type-agnostic because the type is not yet known at
# steps 1–2, and in a typical "send full context each time" chain the same
# broad framing bleeds into steps 3–5.  This is what makes them longer.

CLASSIFY_SYSTEM = (
    "You are a document classifier for a business automation system. "
    "Analyse the provided document and classify it into exactly one of the "
    "following categories: invoice, contract, support_ticket, proposal, or other. "
    "Consider the document's structure, language, and content. "
    "Reply with only the document type, nothing else.\n\n"
    "Examples:\n"
    "Document: 'Invoice #42 — Amount Due: $1,200 — Due Date: 2026-03-01 — Vendor: TechCorp'\n"
    "Classification: invoice\n\n"
    "Document: 'This Service Agreement is entered into by Party A and Party B as of Jan 1 2026...'\n"
    "Classification: contract\n\n"
    "Document: 'RE: Login not working — I have been unable to log in since yesterday. Steps tried...'\n"
    "Classification: support_ticket"
)
CLASSIFY_INSTRUCTION = "Document type:"

ROUTE_SYSTEM = (
    "You are a document workflow router. Given a classified document, determine "
    "the appropriate processing action from: process_payment (invoices over 30 days "
    "past due), request_approval (current invoices), legal_review (contracts), "
    "escalate_to_support (critical or high-severity support tickets), "
    "standard_support (other tickets), review_for_approval (proposals), "
    "archive (other). Consider the document type, amounts, dates, and urgency "
    "indicators carefully.\n\n"
    "Examples:\n"
    "Type: invoice | Due date: 45 days past → process_payment\n"
    "Type: invoice | Due date: 10 days future → request_approval\n"
    "Type: contract → legal_review\n"
    "Type: support_ticket | Severity: critical → escalate_to_support"
)
ROUTE_INSTRUCTION = "Recommended action:"

EXTRACT_SYSTEM_VANILLA = (
    "You are a document data extractor. Extract all relevant structured information "
    "from the provided document. The document type has been classified as {doc_type}. "
    "For invoices: extract invoice_number, vendor_name, amount_due, due_date, and "
    "line_items. For contracts: extract parties, effective_date, term_length, and "
    "key_obligations. For support tickets: extract ticket_id, customer_name, "
    "issue_summary, severity, and steps_already_taken. For proposals: extract "
    "proposal_id, submitter, scope_summary, and estimated_value. "
    "Return all fields as a JSON object with null for missing fields.\n\n"
    "Example for invoice: "
    "{{\"invoice_number\":\"INV-001\",\"vendor_name\":\"Acme Corp\",\"amount_due\":5000.00,"
    "\"due_date\":\"2026-04-30\",\"line_items\":[{{\"description\":\"Servers\",\"amount\":5000.00}}]}}"
)
EXTRACT_INSTRUCTION_VANILLA = "Extracted fields (JSON):"

SUMMARIZE_SYSTEM_VANILLA = (
    "You are a document summariser. Summarise the provided {doc_type} in 2–3 "
    "sentences that capture the most important points for a business reviewer. "
    "Include key entities, amounts or dates if present, and any urgency indicators. "
    "Be concise and factual."
)
SUMMARIZE_INSTRUCTION_VANILLA = "Summary:"

ACTION_ITEMS_SYSTEM_VANILLA = (
    "You are a task extractor for a business workflow engine. Given a {doc_type}, "
    "list all action items that a human reviewer must complete. Each item should be "
    "a single actionable sentence starting with a verb. "
    "Return a JSON array of strings. Include at least 2 items.\n\n"
    'Example: [\"Approve invoice INV-42 for payment\", \"Verify vendor bank details\"]'
)
ACTION_ITEMS_INSTRUCTION_VANILLA = "Action items (JSON array):"

# Compiled prompts (type-specific, shorter because type is already known from IR dispatch)
EXTRACT_SYSTEM_COMPILED: Dict[str, str] = {
    "invoice": (
        "Extract structured data from this invoice. Return JSON with: "
        "invoice_number, vendor_name, amount_due, due_date, line_items "
        "(array of {description, amount})."
    ),
    "contract": (
        "Extract structured data from this contract. Return JSON with: "
        "parties (array), effective_date, term_length_months, key_obligations "
        "(array of strings)."
    ),
    "support": (
        "Extract structured data from this support ticket. Return JSON with: "
        "ticket_id, customer_name, issue_summary, severity, steps_taken (array)."
    ),
    "other": (
        "Extract the key structured fields from this document. Return JSON with "
        "whatever fields best represent the document's content."
    ),
}
EXTRACT_INSTRUCTION_COMPILED = "Extracted fields (JSON):"

SUMMARIZE_SYSTEM_COMPILED: Dict[str, str] = {
    "invoice": "Summarise this invoice in 2 sentences: what is owed, by whom, and when.",
    "contract": "Summarise this contract in 2 sentences: parties, scope, and key terms.",
    "support": "Summarise this support ticket in 2 sentences: issue and current status.",
    "other": "Summarise this document in 2–3 sentences for a business reviewer.",
}
SUMMARIZE_INSTRUCTION_COMPILED = "Summary:"

ACTION_ITEMS_SYSTEM_COMPILED: Dict[str, str] = {
    "invoice": "List action items for this invoice. Return a JSON array of strings.",
    "contract": "List action items for this contract. Return a JSON array of strings.",
    "support": "List action items for this support ticket. Return a JSON array of strings.",
    "other": "List action items for this document. Return a JSON array of strings.",
}
ACTION_ITEMS_INSTRUCTION_COMPILED = "Action items (JSON array):"


# ---------------------------------------------------------------------------
# Typical mock outputs (stable for reproducible output token counts)
# ---------------------------------------------------------------------------

MOCK_DOC_TYPE = "invoice"
MOCK_ROUTE = "process_payment"
MOCK_FIELDS_JSON = (
    '{"invoice_number": "INV-2026-0042", "vendor_name": "Acme Supplies Ltd", '
    '"amount_due": 4200.00, "due_date": "2026-05-15", '
    '"line_items": [{"description": "Server hardware", "amount": 3500.00}, '
    '{"description": "Installation fee", "amount": 700.00}]}'
)
MOCK_SUMMARY = (
    "Acme Supplies Ltd invoice #INV-2026-0042 for $4,200 due May 15 2026, "
    "covering server hardware and installation."
)
MOCK_ACTION_ITEMS_JSON = (
    '["Approve invoice INV-2026-0042 for payment", '
    '"Verify vendor bank details for Acme Supplies Ltd", '
    '"Schedule payment before 2026-05-15"]'
)


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

@dataclass
class MockLLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class MockLLM:
    """Returns deterministic canned outputs; counts actual tiktoken chars for inputs."""

    def __init__(self, use_tiktoken: bool = True) -> None:
        self._use_tiktoken = use_tiktoken

    def _count(self, text: str) -> int:
        if self._use_tiktoken:
            try:
                import tiktoken
                enc = tiktoken.get_encoding("cl100k_base")
                return len(enc.encode(text))
            except Exception:
                pass
        return max(1, len(text.split()))

    async def call(self, system: str, user: str, mock_output: str) -> MockLLMResponse:
        await asyncio.sleep(0)
        full_input = system + "\n\n" + user
        input_tokens = self._count(full_input)
        output_tokens = self._count(mock_output)
        return MockLLMResponse(text=mock_output, input_tokens=input_tokens, output_tokens=output_tokens)


# ---------------------------------------------------------------------------
# Pipeline I/O types
# ---------------------------------------------------------------------------

@dataclass
class DocPipelineInput:
    document: str
    doc_type_hint: str = "invoice"
    approach: str = "vanilla"   # "vanilla" | "compiled"
    token_ledger: List[Tuple[str, int, int]] = field(default_factory=list)

    def record(self, step: str, inp: int, out: int) -> None:
        self.token_ledger.append((step, inp, out))

    @property
    def total_tokens(self) -> int:
        return sum(i + o for _, i, o in self.token_ledger)

    @property
    def llm_calls(self) -> int:
        return len(self.token_ledger)


@dataclass
class DocPipelineOutput:
    doc_type: str
    action: str
    fields: str
    summary: str
    action_items: str
    token_ledger: List[Tuple[str, int, int]]
    elapsed_ms: float

    @property
    def total_tokens(self) -> int:
        return sum(i + o for _, i, o in self.token_ledger)

    @property
    def total_input_tokens(self) -> int:
        return sum(i for _, i, _ in self.token_ledger)

    @property
    def total_output_tokens(self) -> int:
        return sum(o for _, _, o in self.token_ledger)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "action": self.action,
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "llm_calls": len(self.token_ledger),
            "token_ledger": [
                {"step": s, "input_tokens": i, "output_tokens": o}
                for s, i, o in self.token_ledger
            ],
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# Vanilla pipeline (all 5 steps use LLM)
# ---------------------------------------------------------------------------

async def run_vanilla_pipeline(
    inp: DocPipelineInput,
    llm: Optional[MockLLM] = None,
) -> DocPipelineOutput:
    """All five steps call the (mock) LLM including routing and classification."""
    if llm is None:
        llm = MockLLM()
    t0 = time.perf_counter()

    # Step 1: classify_type — LLM call with full document
    r1 = await llm.call(
        system=CLASSIFY_SYSTEM,
        user=f"{inp.document}\n\n{CLASSIFY_INSTRUCTION}",
        mock_output=MOCK_DOC_TYPE,
    )
    inp.record("classify_type", r1.input_tokens, r1.output_tokens)
    doc_type = r1.text

    # Step 2: route_action — LLM call with type + full document
    r2 = await llm.call(
        system=ROUTE_SYSTEM,
        user=f"Document type: {doc_type}\n\n{inp.document}\n\n{ROUTE_INSTRUCTION}",
        mock_output=MOCK_ROUTE,
    )
    inp.record("route_action", r2.input_tokens, r2.output_tokens)
    action = r2.text

    # Step 3: extract_fields — LLM call with type-stamped but generic prompt
    r3 = await llm.call(
        system=EXTRACT_SYSTEM_VANILLA.format(doc_type=doc_type),
        user=f"{inp.document}\n\n{EXTRACT_INSTRUCTION_VANILLA}",
        mock_output=MOCK_FIELDS_JSON,
    )
    inp.record("extract_fields", r3.input_tokens, r3.output_tokens)
    fields = r3.text

    # Step 4: summarize
    r4 = await llm.call(
        system=SUMMARIZE_SYSTEM_VANILLA.format(doc_type=doc_type),
        user=f"{inp.document}\n\n{SUMMARIZE_INSTRUCTION_VANILLA}",
        mock_output=MOCK_SUMMARY,
    )
    inp.record("summarize", r4.input_tokens, r4.output_tokens)
    summary = r4.text

    # Step 5: action_items
    r5 = await llm.call(
        system=ACTION_ITEMS_SYSTEM_VANILLA.format(doc_type=doc_type),
        user=f"{inp.document}\n\n{ACTION_ITEMS_INSTRUCTION_VANILLA}",
        mock_output=MOCK_ACTION_ITEMS_JSON,
    )
    inp.record("action_items", r5.input_tokens, r5.output_tokens)
    action_items = r5.text

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return DocPipelineOutput(
        doc_type=doc_type,
        action=action,
        fields=fields,
        summary=summary,
        action_items=action_items,
        token_ledger=list(inp.token_ledger),
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Compiled pipeline (only 3 content steps use LLM; routing = IR = 0 tokens)
# ---------------------------------------------------------------------------

async def run_compiled_pipeline(
    inp: DocPipelineInput,
    llm: Optional[MockLLM] = None,
) -> DocPipelineOutput:
    """
    Mirrors what the compiled AINL runtime does.

    Steps 1+2 (classify_type, route_action) are free IR branches — the doc_type is
    supplied in the frame and the branch is a compiled conditional, zero LLM tokens.
    Steps 3–5 use type-specific, shorter prompts because the type is already known.
    """
    if llm is None:
        llm = MockLLM()
    t0 = time.perf_counter()

    # Steps 1+2 are IR dispatch — zero LLM tokens; doc_type comes from the frame.
    doc_type = inp.doc_type_hint
    action = {
        "invoice": "process_payment",
        "contract": "legal_review",
        "support": "escalate_to_support",
    }.get(doc_type, "archive")

    # Step 3: extract_fields — type-specific, shorter prompt
    r3 = await llm.call(
        system=EXTRACT_SYSTEM_COMPILED.get(doc_type, EXTRACT_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{EXTRACT_INSTRUCTION_COMPILED}",
        mock_output=MOCK_FIELDS_JSON,
    )
    inp.record("extract_fields", r3.input_tokens, r3.output_tokens)
    fields = r3.text

    # Step 4: summarize — type-specific, shorter prompt
    r4 = await llm.call(
        system=SUMMARIZE_SYSTEM_COMPILED.get(doc_type, SUMMARIZE_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{SUMMARIZE_INSTRUCTION_COMPILED}",
        mock_output=MOCK_SUMMARY,
    )
    inp.record("summarize", r4.input_tokens, r4.output_tokens)
    summary = r4.text

    # Step 5: action_items — type-specific, shorter prompt
    r5 = await llm.call(
        system=ACTION_ITEMS_SYSTEM_COMPILED.get(doc_type, ACTION_ITEMS_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{ACTION_ITEMS_INSTRUCTION_COMPILED}",
        mock_output=MOCK_ACTION_ITEMS_JSON,
    )
    inp.record("action_items", r5.input_tokens, r5.output_tokens)
    action_items = r5.text

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return DocPipelineOutput(
        doc_type=doc_type,
        action=action,
        fields=fields,
        summary=summary,
        action_items=action_items,
        token_ledger=list(inp.token_ledger),
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# "Vanilla optimised" pipeline — third baseline for honest 3-way comparison
#
# This represents what a SKILLED engineer builds WITHOUT AINL compilation:
#   • Step 1 (classify_type): LLM call with vanilla prompt (type not yet known)
#   • Step 2 (route_action):  rule-based switch — ZERO LLM tokens
#   • Steps 3-5:              type-specific compiled prompts (same as AINL compiled)
#
# Compared to compiled AINL, the only remaining cost is the single
# classification LLM call.  This lets auditors cleanly attribute savings:
#   compiled vs vanilla_optimised  → routing-elimination effect alone (~1.4×)
#   compiled vs vanilla_naive      → full effect incl. prompt focus (~2.1×)
# ---------------------------------------------------------------------------

async def run_vanilla_optimized_pipeline(
    inp: DocPipelineInput,
    llm: Optional[MockLLM] = None,
) -> DocPipelineOutput:
    """
    "Smart vanilla" baseline: one LLM call for classification, then rule-based
    routing, then type-specific prompts identical to the compiled pipeline.

    This is what a well-engineered hand-coded stack looks like *without* AINL.
    The ONLY advantage the compiled pipeline still has over this baseline is
    that IR dispatch eliminates even the classification LLM call.
    """
    if llm is None:
        llm = MockLLM()
    t0 = time.perf_counter()

    # Step 1: classify_type — still requires an LLM call (type unknown at start)
    r1 = await llm.call(
        system=CLASSIFY_SYSTEM,
        user=f"{inp.document}\n\n{CLASSIFY_INSTRUCTION}",
        mock_output=MOCK_DOC_TYPE,
    )
    inp.record("classify_type", r1.input_tokens, r1.output_tokens)
    doc_type = r1.text

    # Step 2: route_action — rule-based dispatch; ZERO LLM tokens
    action = {
        "invoice": "process_payment",
        "contract": "legal_review",
        "support": "escalate_to_support",
    }.get(doc_type, "archive")

    # Steps 3-5: type-specific prompts — IDENTICAL to compiled pipeline
    r3 = await llm.call(
        system=EXTRACT_SYSTEM_COMPILED.get(doc_type, EXTRACT_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{EXTRACT_INSTRUCTION_COMPILED}",
        mock_output=MOCK_FIELDS_JSON,
    )
    inp.record("extract_fields", r3.input_tokens, r3.output_tokens)
    fields = r3.text

    r4 = await llm.call(
        system=SUMMARIZE_SYSTEM_COMPILED.get(doc_type, SUMMARIZE_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{SUMMARIZE_INSTRUCTION_COMPILED}",
        mock_output=MOCK_SUMMARY,
    )
    inp.record("summarize", r4.input_tokens, r4.output_tokens)
    summary = r4.text

    r5 = await llm.call(
        system=ACTION_ITEMS_SYSTEM_COMPILED.get(doc_type, ACTION_ITEMS_SYSTEM_COMPILED["other"]),
        user=f"{inp.document}\n\n{ACTION_ITEMS_INSTRUCTION_COMPILED}",
        mock_output=MOCK_ACTION_ITEMS_JSON,
    )
    inp.record("action_items", r5.input_tokens, r5.output_tokens)
    action_items = r5.text

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return DocPipelineOutput(
        doc_type=doc_type,
        action=action,
        fields=fields,
        summary=summary,
        action_items=action_items,
        token_ledger=list(inp.token_ledger),
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Sample documents (used by the benchmark script)
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENT_INVOICE = """\
INVOICE

Invoice Number: INV-2026-0042
Date: April 10, 2026
Due Date: May 15, 2026

Bill To:
Meridian Tech Solutions
123 Commerce Blvd, Austin TX 78701

From:
Acme Supplies Ltd
456 Industrial Park, Dallas TX 75201

Description                         Qty   Unit Price    Total
-----------------------------------------------------------------
Dell PowerEdge R750 Server           1    $3,200.00   $3,200.00
Installation & Configuration         4h     $75.00     $300.00
Annual Support Contract (1 yr)       1      $700.00     $700.00
-----------------------------------------------------------------
Subtotal                                              $4,200.00
Tax (8.25%)                                             $346.50
Total Due                                             $4,546.50

Payment Terms: Net 30
Bank: First National Bank
Account: 9012-3456-7890
Routing: 021000021

Please include invoice number on remittance.
""".strip()

SAMPLE_DOCUMENT_CONTRACT = """\
SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of March 1, 2026
("Effective Date") by and between:

Client: Meridian Tech Solutions, Inc., a Delaware corporation ("Client")
Provider: CloudOps Partners LLC, a Texas LLC ("Provider")

1. SERVICES. Provider agrees to deliver managed cloud infrastructure services
   including 24/7 monitoring, incident response, and monthly reporting.

2. TERM. This Agreement commences on the Effective Date and continues for
   twelve (12) months, renewing automatically unless either party provides
   thirty (30) days written notice of termination.

3. FEES. Client shall pay Provider $8,500 per month, due within 15 days of
   invoice receipt. Late payments accrue interest at 1.5% per month.

4. CONFIDENTIALITY. Each party agrees to maintain the confidentiality of
   the other party's proprietary information disclosed during the term.

5. GOVERNING LAW. This Agreement is governed by the laws of Texas.

Signed:
/s/ Jane Doe, CEO, Meridian Tech Solutions
/s/ Bob Smith, Managing Director, CloudOps Partners LLC
""".strip()

SAMPLE_DOCUMENT_SUPPORT = """\
SUPPORT TICKET #SUP-8821

Submitted: 2026-04-28 09:14 UTC
Priority: HIGH
Customer: GlobalRetail Inc. — jane.kim@globalretail.com

Subject: Order processing API returning 500 errors intermittently

Description:
Our order management system began throwing HTTP 500 errors from your
/v2/orders/create endpoint at approximately 08:45 UTC today. Roughly
30% of requests are failing. The errors started without any changes
on our side.

Steps taken so far:
- Verified our API key is valid (tested separately — works for /v2/orders/list)
- Retried with exponential backoff — failures are not consistent
- Checked our payload structure — matches your documentation exactly
- Opened a ticket with our ISP to rule out network issues (they see no anomalies)

Error response body:
{"error": "internal_server_error", "request_id": "req_9xk2mNpQ", "code": 500}

Impact: ~$12,000/hour in lost order processing revenue.
""".strip()


# ---------------------------------------------------------------------------
# Entry point for quick manual verification
# ---------------------------------------------------------------------------

async def _smoke() -> None:
    llm = MockLLM()
    print(f"{'Document':15s}  {'Vanilla (naive)':>18s}  {'Vanilla (optimised)':>20s}  {'Compiled AINL':>15s}  {'naive/compiled':>14s}  {'opt/compiled':>12s}")
    print("-" * 110)
    for doc, doc_type, label in (
        (SAMPLE_DOCUMENT_INVOICE, "invoice", "Invoice"),
        (SAMPLE_DOCUMENT_CONTRACT, "contract", "Contract"),
        (SAMPLE_DOCUMENT_SUPPORT, "support", "Support ticket"),
    ):
        v_inp = DocPipelineInput(document=doc, doc_type_hint=doc_type, approach="vanilla")
        v_out = await run_vanilla_pipeline(v_inp, llm)

        o_inp = DocPipelineInput(document=doc, doc_type_hint=doc_type, approach="vanilla_optimized")
        o_out = await run_vanilla_optimized_pipeline(o_inp, llm)

        c_inp = DocPipelineInput(document=doc, doc_type_hint=doc_type, approach="compiled")
        c_out = await run_compiled_pipeline(c_inp, llm)

        naive_ratio = v_out.total_tokens / c_out.total_tokens if c_out.total_tokens else 0
        opt_ratio = o_out.total_tokens / c_out.total_tokens if c_out.total_tokens else 0
        print(
            f"{label:15s}  "
            f"{v_out.total_tokens:5d} tk ({len(v_out.token_ledger)} calls)  "
            f"{o_out.total_tokens:5d} tk ({len(o_out.token_ledger)} calls)      "
            f"{c_out.total_tokens:5d} tk ({len(c_out.token_ledger)} calls)  "
            f"{naive_ratio:.2f}×              "
            f"{opt_ratio:.2f}×"
        )


if __name__ == "__main__":
    asyncio.run(_smoke())
