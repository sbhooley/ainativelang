#!/usr/bin/env python3
"""
Handwritten async baseline for ``examples/scraper/basic_scraper.ainl``.

AINL flow (hourly cron omitted here):

- ``R http.GET <products_url> -> resp`` — fetch HTML
- ``R db.C Product * -> stored`` — persist parsed rows (modeled as an in-memory store)

The ``Sc`` line in the example selects ``.product-title`` and ``.product-price``; we parse those
with regex so the baseline stays on stdlib + aiohttp only.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import aiohttp

DEFAULT_URL = "https://example.com/products"

PRODUCT_TITLE_RE = re.compile(
    r'class\s*=\s*["\']product-title["\'][^>]*>([^<]+)',
    re.IGNORECASE | re.DOTALL,
)
PRODUCT_PRICE_RE = re.compile(
    r'class\s*=\s*["\']product-price["\'][^>]*>([^<]+)',
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ScraperResult:
    """Same information as the AINL frame after the scrape label (products + DB projection)."""

    products: List[Dict[str, str]]
    stored: List[Dict[str, str]]


@dataclass
class ProductStore:
    """In-memory ``db.C`` stand-in (append parsed products, return full table)."""

    rows: List[Dict[str, str]] = field(default_factory=list)

    async def commit_products(self, products: List[Dict[str, str]]) -> List[Dict[str, str]]:
        await asyncio.sleep(0)
        self.rows.extend(products)
        return list(self.rows)


async def fetch_html(
    url: str,
    *,
    session: Optional[aiohttp.ClientSession] = None,
    mock_html: Optional[str] = None,
) -> str:
    """
    Fetch page body. Pass ``mock_html`` for offline/deterministic runs (no network).
    """
    if mock_html is not None:
        await asyncio.sleep(0)
        return mock_html

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()
    finally:
        if close_session:
            await session.close()


def parse_products(html: str) -> List[Dict[str, str]]:
    """Extract title/price pairs matching the AINL scraper selectors."""
    titles = [t.strip() for t in PRODUCT_TITLE_RE.findall(html)]
    prices = [p.strip() for p in PRODUCT_PRICE_RE.findall(html)]
    n = min(len(titles), len(prices))
    return [{"title": titles[i], "price": prices[i]} for i in range(n)]


async def run_basic_scrape(
    url: str = DEFAULT_URL,
    *,
    store: Optional[ProductStore] = None,
    mock_html: Optional[str] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> ScraperResult:
    """
    One pass through ``L_scrape``: GET, parse, commit — returns final ``stored`` snapshot.
    """
    store = store or ProductStore()
    html = await fetch_html(url, session=session, mock_html=mock_html)
    products = parse_products(html)
    stored = await store.commit_products(products)
    return ScraperResult(products=products, stored=stored)


async def _demo() -> None:
    sample = """
    <html><body>
      <div class="product-title">Widget A</div><span class="product-price">$10</span>
      <div class="product-title">Widget B</div><span class="product-price">$12</span>
    </body></html>
    """
    r = await run_basic_scrape(mock_html=sample)
    print("stored:", r.stored)


if __name__ == "__main__":
    asyncio.run(_demo())
