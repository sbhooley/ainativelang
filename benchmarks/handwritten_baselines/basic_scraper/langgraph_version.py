#!/usr/bin/env python3
"""
LangGraph mapping of ``basic_scraper.ainl``: linear GET → parse → commit as three nodes.

Requires: ``langgraph``, ``aiohttp`` (same as ``pure_async_python.py``).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, TypedDict

_SUB = Path(__file__).resolve().parent
if str(_SUB) not in sys.path:
    sys.path.insert(0, str(_SUB))

import aiohttp  # noqa: E402

from pure_async_python import (  # noqa: E402
    DEFAULT_URL,
    ProductStore,
    ScraperResult,
    fetch_html,
    parse_products,
    run_basic_scrape,
)

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError("langgraph is required. Install with: pip install langgraph") from e


class ScrapeState(TypedDict, total=False):
    url: str
    mock_html: Optional[str]
    store: ProductStore
    session: Optional[aiohttp.ClientSession]
    html: str
    products: List[dict]
    stored: List[dict]


async def node_fetch(state: ScrapeState) -> dict:
    html = await fetch_html(
        state["url"],
        session=state.get("session"),
        mock_html=state.get("mock_html"),
    )
    return {"html": html}


async def node_parse(state: ScrapeState) -> dict:
    products = parse_products(state["html"])
    return {"products": products}


async def node_store(state: ScrapeState) -> dict:
    stored = await state["store"].commit_products(state["products"])
    return {"stored": stored}


def build_scrape_graph():
    g = StateGraph(ScrapeState)
    g.add_node("fetch", node_fetch)
    g.add_node("parse", node_parse)
    g.add_node("store", node_store)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "parse")
    g.add_edge("parse", "store")
    g.add_edge("store", END)
    return g.compile()


async def run_via_langgraph(
    url: str = DEFAULT_URL,
    *,
    store: Optional[ProductStore] = None,
    mock_html: Optional[str] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> ScraperResult:
    store = store or ProductStore()
    app = build_scrape_graph()
    final = await app.ainvoke(
        {
            "url": url,
            "mock_html": mock_html,
            "store": store,
            "session": session,
        }
    )
    return ScraperResult(
        products=list(final.get("products") or []),
        stored=list(final.get("stored") or []),
    )


async def _verify_equivalence() -> None:
    sample = '<div class="product-title">X</div><span class="product-price">1</span>'
    s1 = ProductStore()
    s2 = ProductStore()
    a = await run_basic_scrape(mock_html=sample, store=s1)
    b = await run_via_langgraph(mock_html=sample, store=s2)
    assert a.products == b.products and a.stored == b.stored
    print("equivalence check: ok")


if __name__ == "__main__":
    asyncio.run(_verify_equivalence())
