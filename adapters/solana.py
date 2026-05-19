"""Stable alias for the Solana adapter (Extended tier).

This module is a transparent re-export of `adapters.extended.solana`. Both
import paths are permanent and supported — there is no deprecation, no
removal, no migration window. The Extended namespace clarifies that Solana
is part of the broader supported adapter catalog rather than the universal
Core orchestration primitives.

    # Both of these work identically and produce no warnings:
    from adapters.solana import SolanaAdapter
    from adapters.extended.solana import SolanaAdapter

    # Private / underscore-prefixed module symbols are also exposed through
    # the alias for downstream tests and tooling that depend on them.

The implementation uses PEP 562 module-level `__getattr__` to forward any
attribute access (public or private) to the canonical module, so every
symbol declared in `adapters.extended.solana` is reachable through both
paths without needing an explicit re-export list.

See `docs/adapters/ADAPTER_TIERS.md` for the tier model.
"""

from adapters.extended import solana as _impl
from adapters.extended.solana import *  # noqa: F401,F403  (public surface)


def __getattr__(name: str):  # PEP 562 — covers private symbols too
    return getattr(_impl, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))
