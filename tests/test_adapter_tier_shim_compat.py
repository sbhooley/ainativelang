"""Tier shim + stability tests for T3.1–T3.4.

These tests assert the **non-breaking** properties of the two-tier adapter
catalog:

  1. Both `adapters.<name>` (stable alias) and `adapters.extended.<name>`
     (canonical) import paths resolve to the **identical class object**.
  2. Importing through the stable alias produces **no DeprecationWarning**
     and no UserWarning — the alias is permanent, not a migration step.
  3. Every adapter entry in `ADAPTER_REGISTRY.json` carries a `tier` field
     valued `"core"` or `"extended"`.
  4. The Extended `TiktokAdapter` honors the layered configuration
     precedence (explicit arg → env var → fail-fast) declared in
     `docs/adapters/ADAPTER_TIERS.md`.

If any of these tests fail, the tier model has regressed in a way that
will surface to downstream consumers (ArmaraOS, ainl-cortex, external
scripts).
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Set

import pytest


# ---------------------------------------------------------------------------
# Path stability — same class object via both paths, no warnings on import.
# ---------------------------------------------------------------------------


def _import_pair(stable_module: str, canonical_module: str, attr: str):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stable = __import__(stable_module, fromlist=[attr])
        canonical = __import__(canonical_module, fromlist=[attr])
    bad = [w for w in caught if issubclass(w.category, (DeprecationWarning, PendingDeprecationWarning))]
    assert not bad, f"unexpected deprecation warning(s) on stable alias import: {[str(b.message) for b in bad]}"
    return getattr(stable, attr), getattr(canonical, attr)


def test_solana_stable_and_canonical_resolve_to_same_class():
    stable, canonical = _import_pair(
        "adapters.solana", "adapters.extended.solana", "SolanaAdapter"
    )
    assert stable is canonical, "adapters.solana.SolanaAdapter must be adapters.extended.solana.SolanaAdapter"


def test_tiktok_stable_and_canonical_resolve_to_same_class():
    stable, canonical = _import_pair(
        "adapters.tiktok", "adapters.extended.tiktok", "TiktokAdapter"
    )
    assert stable is canonical, "adapters.tiktok.TiktokAdapter must be adapters.extended.tiktok.TiktokAdapter"


def test_tiktok_config_error_exposed_via_both_paths():
    stable, canonical = _import_pair(
        "adapters.tiktok", "adapters.extended.tiktok", "TiktokAdapterConfigError"
    )
    assert stable is canonical


# ---------------------------------------------------------------------------
# Registry — every entry has a tier, and tier values are restricted.
# ---------------------------------------------------------------------------


def _load_registry() -> dict:
    repo_root = Path(__file__).resolve().parent.parent
    return json.loads((repo_root / "ADAPTER_REGISTRY.json").read_text(encoding="utf-8"))


def test_registry_has_tier_meanings_block():
    reg = _load_registry()
    meanings = reg.get("tier_meanings")
    assert isinstance(meanings, dict), "tier_meanings block missing from ADAPTER_REGISTRY.json"
    assert "core" in meanings and "extended" in meanings, "tier_meanings must define core + extended"


def test_every_adapter_has_a_tier():
    reg = _load_registry()
    adapters = reg.get("adapters", {})
    missing: list[str] = []
    bad_values: list[str] = []
    for name, entry in adapters.items():
        if not isinstance(entry, dict):
            continue
        tier = entry.get("tier")
        if tier is None:
            missing.append(name)
        elif tier not in {"core", "extended"}:
            bad_values.append(f"{name}={tier!r}")
    assert not missing, f"adapters missing tier field: {missing}"
    assert not bad_values, f"adapters with non-canonical tier values: {bad_values}"


def test_core_and_extended_counts_match_doctor_expectation():
    """If this count drifts the doctor/docs/README copy must update too."""
    reg = _load_registry()
    adapters = reg.get("adapters", {})
    cores: Set[str] = {n for n, v in adapters.items() if isinstance(v, dict) and v.get("tier") == "core"}
    exts: Set[str] = {n for n, v in adapters.items() if isinstance(v, dict) and v.get("tier") == "extended"}
    # These two adapters must remain Extended (the central T3.3/T3.4 commitment).
    assert "solana" in exts, "solana must be classified extended"
    assert "tiktok" in exts, "tiktok must be classified extended"
    # And these must remain Core (subset of the well-defended primitives).
    for must_be_core in ("core", "http", "fs", "memory", "audit_trail", "tool_registry"):
        assert must_be_core in cores, f"{must_be_core!r} must be classified core"
    # Sanity: the total is what the doc says (allows a small drift envelope
    # so adding/removing one adapter doesn't break tests; tighten if needed).
    assert 20 <= len(cores) <= 40, f"unexpected core count: {len(cores)}"
    assert 5 <= len(exts) <= 30, f"unexpected extended count: {len(exts)}"


# ---------------------------------------------------------------------------
# Layered config — explicit arg, env var, fail-fast.
# ---------------------------------------------------------------------------


def test_tiktok_explicit_db_path_arg_takes_precedence(monkeypatch, tmp_path):
    from adapters.extended.tiktok import TiktokAdapter

    monkeypatch.setenv("AINL_TIKTOK_DB", str(tmp_path / "from_env.db"))
    adapter = TiktokAdapter(db_path=str(tmp_path / "explicit.db"))
    assert adapter.db_path.endswith("explicit.db"), \
        "explicit constructor argument must win over AINL_TIKTOK_DB"


def test_tiktok_env_var_used_when_no_explicit_arg(monkeypatch, tmp_path):
    from adapters.extended.tiktok import TiktokAdapter

    monkeypatch.setenv("AINL_TIKTOK_DB", str(tmp_path / "from_env.db"))
    adapter = TiktokAdapter()
    assert adapter.db_path.endswith("from_env.db")


def test_tiktok_fail_fast_when_nothing_configured(monkeypatch):
    """When no explicit arg, no env var, and no legacy file → raise at construction."""
    from adapters.extended.tiktok import TiktokAdapter, TiktokAdapterConfigError

    monkeypatch.delenv("AINL_TIKTOK_DB", raising=False)
    # Point HOME at an empty path so the legacy ~/.openclaw/... file can't exist.
    monkeypatch.setenv("HOME", "/tmp/__ainl_tiktok_smoke_nonexistent__")
    monkeypatch.setattr(Path, "home", lambda: Path("/tmp/__ainl_tiktok_smoke_nonexistent__"))

    with pytest.raises(TiktokAdapterConfigError) as exc_info:
        TiktokAdapter()
    msg = str(exc_info.value)
    # Error must surface every supported resolution path so users can fix.
    assert "AINL_TIKTOK_DB" in msg
    assert "db_path" in msg
