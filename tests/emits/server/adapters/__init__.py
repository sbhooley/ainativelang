"""
Adapters: pluggable backends for R (db, api), P (pay), Sc (scrape).
Replace mock adapters with real implementations (Prisma, Stripe, etc.).
"""
from .base import AdapterRegistry, DBAdapter, APIAdapter, PayAdapter, ScrapeAdapter
from .mock import mock_registry

__all__ = [
    "AdapterRegistry",
    "DBAdapter",
    "APIAdapter",
    "PayAdapter",
    "ScrapeAdapter",
    "mock_registry",
]
