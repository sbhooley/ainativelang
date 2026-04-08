"""AINL_HOST_ADAPTER_ALLOWLIST and CLI --host-adapter-allowlist intersect IR with a host grant."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.engine import RuntimeEngine  # noqa: E402

_EXT_PROG = """S app ext echo

L1:
 R ext.echo 1 ->x
 J x
"""


def test_env_ainl_host_adapter_allowlist_blocks_ext():
    old = os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST")
    os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = "core"
    try:
        eng = RuntimeEngine.from_code(_EXT_PROG, strict=True)
        with pytest.raises(Exception) as exc:
            eng.run_label("1")
        msg = str(exc.value).lower()
        assert "blocked" in msg or "not registered" in msg
    finally:
        if old is None:
            os.environ.pop("AINL_HOST_ADAPTER_ALLOWLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = old


def test_kwarg_host_adapter_allowlist_blocks_ext():
    eng = RuntimeEngine.from_code(_EXT_PROG, strict=True, host_adapter_allowlist=["core"])
    with pytest.raises(Exception) as exc:
        eng.run_label("1")
    msg = str(exc.value).lower()
    assert "blocked" in msg or "not registered" in msg


def test_env_ainl_host_adapter_denylist_blocks_ext():
    old = os.environ.get("AINL_HOST_ADAPTER_DENYLIST")
    os.environ["AINL_HOST_ADAPTER_DENYLIST"] = "ext"
    try:
        eng = RuntimeEngine.from_code(_EXT_PROG, strict=True)
        with pytest.raises(Exception) as exc:
            eng.run_label("1")
        msg = str(exc.value).lower()
        assert "blocked" in msg or "not registered" in msg
    finally:
        if old is None:
            os.environ.pop("AINL_HOST_ADAPTER_DENYLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_DENYLIST"] = old


def test_kwarg_host_adapter_denylist_blocks_ext():
    eng = RuntimeEngine.from_code(_EXT_PROG, strict=True, host_adapter_denylist=["ext"])
    with pytest.raises(Exception) as exc:
        eng.run_label("1")
    msg = str(exc.value).lower()
    assert "blocked" in msg or "not registered" in msg


def test_intelligence_path_overrides_preset_allow_ir_zero():
    """Even with AINL_ALLOW_IR_DECLARED_ADAPTERS=0, intelligence/ sources use IR adapters (web, …)."""
    old_allow = os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST")
    old_relax = os.environ.get("AINL_ALLOW_IR_DECLARED_ADAPTERS")
    old_strict = os.environ.get("AINL_INTELLIGENCE_FORCE_HOST_POLICY")
    os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = "core"
    os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = "0"
    for k in ("AINL_INTELLIGENCE_FORCE_HOST_POLICY",):
        os.environ.pop(k, None)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "intelligence", "intelligence_digest.lang")
    if not os.path.isfile(src):
        pytest.skip("intelligence_digest.lang not present")
    code = open(src, encoding="utf-8").read()
    try:
        eng = RuntimeEngine.from_code(code, strict=False, source_path=src)
        assert "web" in eng.adapters._allowed
    finally:
        if old_allow is None:
            os.environ.pop("AINL_HOST_ADAPTER_ALLOWLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = old_allow
        if old_relax is None:
            os.environ.pop("AINL_ALLOW_IR_DECLARED_ADAPTERS", None)
        else:
            os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = old_relax
        if old_strict is None:
            os.environ.pop("AINL_INTELLIGENCE_FORCE_HOST_POLICY", None)
        else:
            os.environ["AINL_INTELLIGENCE_FORCE_HOST_POLICY"] = old_strict


def test_intelligence_force_host_policy_respects_allow_ir_zero():
    """AINL_INTELLIGENCE_FORCE_HOST_POLICY=1 keeps host narrowing for intelligence paths."""
    old_allow = os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST")
    old_relax = os.environ.get("AINL_ALLOW_IR_DECLARED_ADAPTERS")
    old_strict = os.environ.get("AINL_INTELLIGENCE_FORCE_HOST_POLICY")
    os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = "core"
    os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = "0"
    os.environ["AINL_INTELLIGENCE_FORCE_HOST_POLICY"] = "1"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "intelligence", "intelligence_digest.lang")
    if not os.path.isfile(src):
        pytest.skip("intelligence_digest.lang not present")
    code = open(src, encoding="utf-8").read()
    try:
        eng = RuntimeEngine.from_code(code, strict=False, source_path=src)
        assert "web" not in eng.adapters._allowed
    finally:
        if old_allow is None:
            os.environ.pop("AINL_HOST_ADAPTER_ALLOWLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = old_allow
        if old_relax is None:
            os.environ.pop("AINL_ALLOW_IR_DECLARED_ADAPTERS", None)
        else:
            os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = old_relax
        if old_strict is None:
            os.environ.pop("AINL_INTELLIGENCE_FORCE_HOST_POLICY", None)
        else:
            os.environ["AINL_INTELLIGENCE_FORCE_HOST_POLICY"] = old_strict


def test_from_code_intelligence_source_path_sets_relax_env():
    """Files under .../intelligence/ opt into IR-declared adapters when env not preset."""
    old_allow = os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST")
    old_relax = os.environ.get("AINL_ALLOW_IR_DECLARED_ADAPTERS")
    os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = "core"
    os.environ.pop("AINL_ALLOW_IR_DECLARED_ADAPTERS", None)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "intelligence", "intelligence_digest.lang")
    if not os.path.isfile(src):
        pytest.skip("intelligence_digest.lang not present")
    code = open(src, encoding="utf-8").read()
    try:
        eng = RuntimeEngine.from_code(code, strict=False, source_path=src)
        assert "web" in eng.adapters._allowed
    finally:
        if old_allow is None:
            os.environ.pop("AINL_HOST_ADAPTER_ALLOWLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = old_allow
        if old_relax is None:
            os.environ.pop("AINL_ALLOW_IR_DECLARED_ADAPTERS", None)
        else:
            os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = old_relax


def test_env_allow_ir_declared_ignores_host_allowlist():
    """AINL_ALLOW_IR_DECLARED_ADAPTERS=1 skips env AINL_HOST_ADAPTER_ALLOWLIST; IR adapters stay allowed."""
    code = """S app core noop

L1:
 R http.Get "https://example.com" ->r
 J r
"""
    old_allow = os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST")
    old_relax = os.environ.get("AINL_ALLOW_IR_DECLARED_ADAPTERS")
    os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = "core"
    os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = "1"
    try:
        eng = RuntimeEngine.from_code(code, strict=True)
        assert "http" in eng.adapters._allowed
    finally:
        if old_allow is None:
            os.environ.pop("AINL_HOST_ADAPTER_ALLOWLIST", None)
        else:
            os.environ["AINL_HOST_ADAPTER_ALLOWLIST"] = old_allow
        if old_relax is None:
            os.environ.pop("AINL_ALLOW_IR_DECLARED_ADAPTERS", None)
        else:
            os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = old_relax
