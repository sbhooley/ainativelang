"""
Authoring-density baseline: B2B lead enrichment pipeline — idiomatic Python.

Semantically equivalent to examples/workflows/lead_enrichment.ainl.
Written in the style a proficient Python developer (or LLM) would produce
when asked to "build a lead enrichment pipeline with caching and tier-based
sales context generation."

Dependencies: httpx, openai  (pip install httpx openai)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI


# ---------------------------------------------------------------------------
# Simple file-backed cache (mirrors cache adapter behaviour)
# ---------------------------------------------------------------------------

class FileCache:
    """Persistent JSON key-value store backed by a local file."""

    def __init__(self, path: str = ".lead_cache.json") -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._path.write_text(json.dumps(self._data, indent=2))


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class LeadEnrichmentResult:
    tier: str
    domain: str
    name: str
    industry: str
    country: str
    employees: int
    sales_context: str
    from_cache: bool


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def enrich_lead(
    domain: str,
    enrich_url: str,
    cache: Optional[FileCache] = None,
    openai_client: Optional[OpenAI] = None,
    http_timeout: float = 15.0,
) -> LeadEnrichmentResult:
    """
    Fetch firmographic data, classify account tier, generate sales context.

    Returns a LeadEnrichmentResult with tier, company metadata, and a
    LLM-generated sales context string.  Caches the result on first call.
    """
    if cache is None:
        cache = FileCache()
    if openai_client is None:
        openai_client = OpenAI()

    # Cache-first: return immediately on hit
    cached = cache.get(domain)
    if cached:
        tier, _, sales_context = cached.partition("|")
        return LeadEnrichmentResult(
            tier=tier,
            domain=domain,
            name="",
            industry="",
            country="",
            employees=0,
            sales_context=sales_context,
            from_cache=True,
        )

    # Fetch firmographic data
    with httpx.Client(timeout=http_timeout) as client:
        response = client.get(f"{enrich_url}{domain}")
        response.raise_for_status()
        data: dict = response.json()

    company_name: str = data.get("name", "")
    industry: str = data.get("industry", "")
    country: str = data.get("country", "")
    emp_count: int = int(data.get("employees", 0))

    # Tier classification — deterministic, zero LLM tokens
    if emp_count > 500:
        tier = "enterprise"
        prompt = (
            f"Write a 2-sentence enterprise sales context for {company_name} "
            f"in the {industry} industry. "
            "Emphasise strategic value and multi-year ROI."
        )
        max_tokens = 150
    elif emp_count > 100:
        tier = "mid_market"
        prompt = (
            f"Write a 2-sentence mid-market sales context for {company_name} "
            f"in the {industry} industry. "
            "Focus on team adoption and productivity."
        )
        max_tokens = 120
    else:
        tier = "smb"
        prompt = (
            f"Write a 1-sentence SMB sales context for {company_name} "
            f"in the {industry} industry. "
            "Keep it punchy and value-focused."
        )
        max_tokens = 80

    # Single LLM call for sales context
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.4,
    )
    sales_context: str = completion.choices[0].message.content or ""

    # Cache result
    cache.set(domain, f"{tier}|{domain}|{sales_context}")

    return LeadEnrichmentResult(
        tier=tier,
        domain=domain,
        name=company_name,
        industry=industry,
        country=country,
        employees=emp_count,
        sales_context=sales_context,
        from_cache=False,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else "stripe.com"
    enrich_url = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "https://company.clearbit.com/v2/companies/find?domain="
    )
    result = enrich_lead(domain, enrich_url)
    print(json.dumps(vars(result), indent=2))
