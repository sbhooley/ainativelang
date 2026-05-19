"""Extended adapter catalog (Tier 2).

Extended adapters are fully supported alongside the Core tier. They live here
because they cover narrower domains (web3, social, browser automation, niche
interop bridges) rather than the universal orchestration primitives in the
Core tier.

See `docs/adapters/ADAPTER_TIERS.md` for the model description and the full
Core / Extended lists.

Both `from adapters.<name>` and `from adapters.extended.<name>` are stable
import paths and produce no deprecation warnings. They will both keep working
indefinitely.
"""
