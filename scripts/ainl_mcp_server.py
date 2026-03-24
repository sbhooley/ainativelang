#!/usr/bin/env python3
"""AINL MCP Server — workflow-level MCP integration for AI coding agents.

Exposes AINL compilation, validation, execution, capability discovery, and
security introspection as MCP tools.  Designed for stdio transport so any
MCP-compatible host (Gemini CLI, Claude Code, Codex Agents SDK, etc.) can
discover and call AINL without custom integration code.

Security posture:
  - Safe-by-default: ``ainl-run`` is restricted to the ``core`` adapter with
    conservative limits.  Callers can add *further* restrictions via a
    ``policy`` parameter but can never widen beyond the server defaults.
  - Read-only tools (validate, compile, capabilities, security-report) have
    no side effects.
  - Ecosystem import tools (``ainl_import_*``, ``ainl_list_ecosystem``) perform
    **HTTPS fetches** to GitHub/raw URLs when resolving presets or URLs; they
    return generated ``.ainl`` text and metadata but do not write the filesystem.

MCP exposure scoping:
  - ``AINL_MCP_TOOLS``: comma-separated list of tools to expose (inclusion).
  - ``AINL_MCP_TOOLS_EXCLUDE``: comma-separated list of tools to hide.
  - ``AINL_MCP_RESOURCES``: comma-separated list of resource URIs to expose.
  - ``AINL_MCP_RESOURCES_EXCLUDE``: comma-separated list of resource URIs to hide.
  - ``AINL_MCP_EXPOSURE_PROFILE``: named exposure profile from
    ``tooling/mcp_exposure_profiles.json``.
  - Inclusion lists take precedence over exclusion lists; profile is applied
    first, then env-var overrides narrow further.

Requires Python >=3.10 and the ``mcp`` extra:
    pip install -e ".[mcp]"

Run:
    ainl-mcp                     # stdio (default)
    python -m scripts.ainl_mcp_server
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from mcp.server.fastmcp import FastMCP

    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False

from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.engine import AinlRuntimeError, RuntimeEngine, RUNTIME_VERSION
from tooling.policy_validator import validate_ir_against_policy
from tooling.security_report import analyze_ir
from tooling.capability_grant import (
    empty_grant,
    merge_grants,
    grant_to_policy,
    grant_to_limits,
    grant_to_allowed_adapters,
    load_profile_as_grant,
)
from tooling.mcp_ecosystem_import import (
    import_agency_agent_mcp,
    import_clawflow_mcp,
    import_markdown_mcp,
    list_ecosystem_templates,
)

_TOOLING_DIR = Path(__file__).resolve().parent.parent / "tooling"

_DEFAULT_ALLOWED_ADAPTERS: List[str] = ["core"]
_DEFAULT_POLICY: Dict[str, Any] = {
    "forbidden_privilege_tiers": ["local_state", "network", "operator_sensitive"],
}
_DEFAULT_LIMITS: Dict[str, Any] = {
    "max_steps": 500,
    "max_depth": 10,
    "max_adapter_calls": 50,
    "max_time_ms": 5000,
}

ALL_TOOL_NAMES: List[str] = [
    "ainl_validate",
    "ainl_compile",
    "ainl_capabilities",
    "ainl_security_report",
    "ainl_run",
    "ainl_import_clawflow",
    "ainl_import_agency_agent",
    "ainl_import_markdown",
    "ainl_list_ecosystem",
]

ALL_RESOURCE_URIS: List[str] = [
    "ainl://adapter-manifest",
    "ainl://security-profiles",
]


# ---------------------------------------------------------------------------
# Exposure scoping
# ---------------------------------------------------------------------------

def _load_exposure_profiles() -> Dict[str, Any]:
    path = _TOOLING_DIR / "mcp_exposure_profiles.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _csv_set(env_key: str) -> Optional[Set[str]]:
    """Parse a comma-separated env var into a set, or None if unset/empty."""
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return None
    return {s.strip() for s in raw.split(",") if s.strip()}


def _resolve_exposure() -> tuple[Set[str], Set[str]]:
    """Return (allowed_tools, allowed_resources) after applying profile + env.

    Resolution order:
    1. Start with everything allowed.
    2. If AINL_MCP_EXPOSURE_PROFILE is set, restrict to profile's sets.
    3. If AINL_MCP_TOOLS / AINL_MCP_RESOURCES inclusion env vars are set,
       intersect with them (narrowing further).
    4. If AINL_MCP_TOOLS_EXCLUDE / AINL_MCP_RESOURCES_EXCLUDE are set,
       subtract from the remaining set.
    Inclusion always takes precedence: if both include and exclude are set,
    the result is include minus exclude.
    """
    tools: Set[str] = set(ALL_TOOL_NAMES)
    resources: Set[str] = set(ALL_RESOURCE_URIS)

    profile_name = os.environ.get("AINL_MCP_EXPOSURE_PROFILE", "").strip()
    if profile_name:
        profiles = _load_exposure_profiles()
        profile = (profiles.get("profiles") or {}).get(profile_name)
        if isinstance(profile, dict):
            p_tools = profile.get("tools")
            if isinstance(p_tools, list):
                tools &= set(p_tools)
            p_resources = profile.get("resources")
            if isinstance(p_resources, list):
                resources &= set(p_resources)

    inc_tools = _csv_set("AINL_MCP_TOOLS")
    if inc_tools is not None:
        tools &= inc_tools
    exc_tools = _csv_set("AINL_MCP_TOOLS_EXCLUDE")
    if exc_tools is not None:
        tools -= exc_tools

    inc_res = _csv_set("AINL_MCP_RESOURCES")
    if inc_res is not None:
        resources &= inc_res
    exc_res = _csv_set("AINL_MCP_RESOURCES_EXCLUDE")
    if exc_res is not None:
        resources -= exc_res

    return tools, resources


_ALLOWED_TOOLS: Set[str] = set()
_ALLOWED_RESOURCES: Set[str] = set()

def _init_exposure() -> None:
    global _ALLOWED_TOOLS, _ALLOWED_RESOURCES
    _ALLOWED_TOOLS, _ALLOWED_RESOURCES = _resolve_exposure()

_init_exposure()


def _load_mcp_server_grant() -> Dict[str, Any]:
    """Build the MCP server-level capability grant."""
    profile_name = os.environ.get("AINL_MCP_PROFILE")
    if profile_name:
        try:
            return load_profile_as_grant(profile_name)
        except ValueError:
            pass
    return {
        "allowed_adapters": list(_DEFAULT_ALLOWED_ADAPTERS),
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": list(_DEFAULT_POLICY.get("forbidden_privilege_tiers") or []),
        "limits": dict(_DEFAULT_LIMITS),
        "adapter_constraints": {},
    }

_MCP_SERVER_GRANT: Dict[str, Any] = _load_mcp_server_grant()

_mcp_server: Any = None

if _HAS_MCP:
    _mcp_server = FastMCP(
        "AINL",
        instructions=(
            "AINL is a graph-canonical workflow execution layer. "
            "Use ainl_validate to check syntax, ainl_compile to produce IR, "
            "ainl_capabilities to discover adapters, ainl_security_report to "
            "audit privilege tiers, and ainl_run to execute workflows. "
            "Use ainl_list_ecosystem for curated Clawflows/Agency-Agents presets; "
            "ainl_import_clawflow, ainl_import_agency_agent, and ainl_import_markdown "
            "fetch Markdown and return deterministic .ainl source (network)."
        ),
    )


def _compile(code: str, strict: bool = True) -> Dict[str, Any]:
    compiler = AICodeCompiler(strict_mode=strict)
    return compiler.compile(code)


def _load_json(name: str) -> Dict[str, Any]:
    path = _TOOLING_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_capabilities() -> Dict[str, Any]:
    manifest = _load_json("adapter_manifest.json")
    adapters: Dict[str, Any] = {}
    for name, info in (manifest.get("adapters") or {}).items():
        adapters[name] = {
            "support_tier": info.get("support_tier"),
            "verbs": info.get("verbs", []),
            "effect_default": info.get("effect_default"),
            "recommended_lane": info.get("recommended_lane"),
            "privilege_tier": info.get("privilege_tier"),
            "destructive": info.get("destructive"),
            "network_facing": info.get("network_facing"),
            "sandbox_safe": info.get("sandbox_safe"),
        }
    return {
        "schema_version": "1.1",
        "runtime_version": RUNTIME_VERSION,
        "policy_support": True,
        "adapters": adapters,
    }


def _merge_policy(caller_policy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Restrictively merge caller policy on top of server defaults via grants."""
    caller_grant = empty_grant()
    if isinstance(caller_policy, dict):
        for key in ("forbidden_adapters", "forbidden_effects",
                     "forbidden_effect_tiers", "forbidden_privilege_tiers"):
            vals = caller_policy.get(key)
            if vals:
                caller_grant[key] = list(vals)
    effective = merge_grants(_MCP_SERVER_GRANT, caller_grant)
    return grant_to_policy(effective)


def _merge_limits(caller_limits: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge caller limits with server defaults via grants — more restrictive wins."""
    caller_grant = empty_grant()
    if isinstance(caller_limits, dict):
        caller_grant["limits"] = {k: int(v) for k, v in caller_limits.items()
                                   if isinstance(v, (int, float))}
    effective = merge_grants(_MCP_SERVER_GRANT, caller_grant)
    return grant_to_limits(effective)


class _EchoAdapter(RuntimeAdapter):
    def call(self, target: str, args: list, context: dict) -> Any:
        return args[0] if args else target


def _register_tool(fn: Any) -> Any:
    """Register a function as an MCP tool if it is in the allowed set."""
    if _mcp_server is not None and fn.__name__ in _ALLOWED_TOOLS:
        _mcp_server.tool()(fn)
    return fn


def _register_resource(uri: str):
    """Register a function as an MCP resource if it is in the allowed set."""
    def decorator(fn: Any) -> Any:
        if _mcp_server is not None and uri in _ALLOWED_RESOURCES:
            _mcp_server.resource(uri)(fn)
        return fn
    return decorator


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@_register_tool
def ainl_validate(code: str, strict: bool = True) -> dict:
    """Validate AINL source code without executing it.

    Returns whether the code compiles successfully, along with any errors
    or warnings.  No side effects.
    """
    ir = _compile(code, strict=strict)
    errors = ir.get("errors") or []
    warnings = ir.get("warnings") or []
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


@_register_tool
def ainl_compile(code: str, strict: bool = True) -> dict:
    """Compile AINL source code to canonical graph IR.

    Returns the full IR JSON on success.  No execution, no side effects.
    """
    ir = _compile(code, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "ir": ir}


@_register_tool
def ainl_capabilities() -> dict:
    """Discover runtime adapter capabilities, privilege tiers, and metadata.

    Returns available adapters with their verbs, support tiers, effect
    defaults, recommended lanes, and privilege tiers.  No side effects.
    """
    return _load_capabilities()


@_register_tool
def ainl_security_report(code: str) -> dict:
    """Generate a security/privilege map for an AINL workflow.

    Shows which adapters, verbs, and privilege tiers the workflow uses,
    broken down per label and in aggregate.  No execution, no side effects.
    """
    ir = _compile(code, strict=False)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    report = analyze_ir(ir)
    return {"ok": True, "report": report}


@_register_tool
def ainl_run(
    code: str,
    strict: bool = True,
    policy: Optional[dict] = None,
    limits: Optional[dict] = None,
    frame: Optional[dict] = None,
    label: Optional[str] = None,
) -> dict:
    """Compile, validate policy, and execute an AINL workflow.

    By default, only the ``core`` adapter is available and conservative
    resource limits are applied.  The caller may supply additional policy
    restrictions and tighter limits but cannot widen beyond the server
    defaults.

    Returns structured execution output on success or a policy/runtime
    error on failure.
    """
    trace_id = str(uuid.uuid4())

    ir = _compile(code, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "trace_id": trace_id, "errors": errors}

    merged_policy = _merge_policy(policy)
    policy_result = validate_ir_against_policy(ir, merged_policy)
    if not policy_result["ok"]:
        return {
            "ok": False,
            "trace_id": trace_id,
            "error": "policy_violation",
            "policy_errors": policy_result["errors"],
        }

    merged_limits = _merge_limits(limits)
    reg = AdapterRegistry(allowed=list(_DEFAULT_ALLOWED_ADAPTERS))
    reg.register("core", _EchoAdapter())

    try:
        eng = RuntimeEngine(
            ir=ir,
            adapters=reg,
            trace=False,
            step_fallback=True,
            execution_mode="graph-preferred",
            limits=merged_limits,
        )
        entry = label or eng.default_entry_label()
        out = eng.run_label(entry, frame=frame or {})
    except AinlRuntimeError as e:
        return {
            "ok": False,
            "trace_id": trace_id,
            "error": str(e),
            "error_structured": e.to_dict(),
        }
    except Exception as e:
        return {"ok": False, "trace_id": trace_id, "error": str(e)}

    return {
        "ok": True,
        "trace_id": trace_id,
        "label": entry,
        "out": out,
        "runtime_version": RUNTIME_VERSION,
        "ir_version": ir.get("ir_version"),
    }


@_register_tool
def ainl_import_clawflow(
    url_or_name: str,
    openclaw_bridge: bool = True,
    import_all_preset_samples: bool = False,
) -> dict:
    """Import a Clawflows-style WORKFLOW.md into a deterministic AINL graph.

    Pass a raw HTTPS URL to a Markdown file, or a curated preset slug (e.g.
    ``check-calendar``, ``morning-journal``). Set ``import_all_preset_samples``
    to true to fetch every bundled Clawflows sample (same set as ``ainl import clawflows``).

    Performs outbound HTTPS. Returns ``ainl`` source and ``meta``; does not write files.
    """
    return import_clawflow_mcp(
        url_or_name,
        openclaw_bridge=openclaw_bridge,
        import_all_preset_samples=import_all_preset_samples,
    )


@_register_tool
def ainl_import_agency_agent(
    personality_name: str,
    tone: Optional[str] = None,
    openclaw_bridge: bool = True,
    import_all_preset_samples: bool = False,
) -> dict:
    """Import an Agency-Agents-style Markdown agent into a deterministic AINL graph.

    ``personality_name`` is a preset slug (e.g. ``mcp-builder``) or an HTTPS URL
    to agent Markdown. Optional ``tone`` is merged like CLI ``--personality``.
    Set ``import_all_preset_samples`` to true to fetch every bundled agent sample.

    Performs outbound HTTPS. Returns ``ainl`` source and ``meta``; does not write files.
    """
    return import_agency_agent_mcp(
        personality_name,
        tone=tone,
        openclaw_bridge=openclaw_bridge,
        import_all_preset_samples=import_all_preset_samples,
    )


@_register_tool
def ainl_import_markdown(
    url: str,
    type: str,
    personality: Optional[str] = None,
    openclaw_bridge: bool = True,
) -> dict:
    """Fetch Markdown from a URL or path-like URL and convert to AINL.

    ``type`` must be ``workflow`` or ``agent``. Optional ``personality`` applies
    to agent imports. Performs outbound HTTPS when ``url`` is remote.

    Returns ``ainl`` source and ``meta``; does not write files.
    """
    return import_markdown_mcp(
        url,
        type,
        personality=personality,
        openclaw_bridge=openclaw_bridge,
    )


@_register_tool
def ainl_list_ecosystem() -> dict:
    """List curated Clawflows and Agency-Agents preset URLs and local template paths.

    No network I/O. Use before ``ainl_import_clawflow`` / ``ainl_import_agency_agent``
    to discover slugs and ``examples/ecosystem`` folders shipped with the repo.
    """
    return list_ecosystem_templates()


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@_register_resource("ainl://adapter-manifest")
def adapter_manifest_resource() -> str:
    """Full adapter metadata including verbs, tiers, effects, and privilege levels."""
    return json.dumps(_load_json("adapter_manifest.json"), indent=2)


@_register_resource("ainl://security-profiles")
def security_profiles_resource() -> str:
    """Named security profiles for common deployment scenarios."""
    return json.dumps(_load_json("security_profiles.json"), indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ainl-mcp",
        description="AINL MCP stdio server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport mode (stdio only)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print AINL runtime version and exit",
    )
    args = parser.parse_args()
    if args.version:
        from runtime.engine import RUNTIME_VERSION

        print(RUNTIME_VERSION)
        return
    if _mcp_server is None:
        raise SystemExit(
            "MCP SDK not installed. Install with: pip install -e '.[mcp]'"
        )
    _mcp_server.run(transport=args.transport)


if __name__ == "__main__":
    main()
