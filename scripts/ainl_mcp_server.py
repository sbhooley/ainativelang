#!/usr/bin/env python3
"""AINL MCP Server — workflow-level MCP integration for AI coding agents.

Exposes AINL compilation, validation, execution, capability discovery, and
security introspection as MCP tools.  Designed for stdio transport so any
MCP-compatible host (Gemini CLI, Claude Code, Codex Agents SDK, etc.) can
discover and call AINL without custom integration code.

Security posture:
  - Default execution matches the runtime runner: adapter allowlist is unset at
    the grant layer so IR-declared adapters (``http``, ``web``, ``llm``, …) work
    out of the box; resource limits provide the safety floor.  Callers may add
    further restrictions via ``policy`` / ``limits`` but cannot widen beyond
    the merged server defaults.
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
import time
import uuid
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from mcp.server.fastmcp import FastMCP

    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False

from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.sandbox_shim import SandboxClient
from runtime.engine import AinlRuntimeError, RuntimeEngine, RUNTIME_VERSION
from tooling.policy_validator import validate_ir_against_policy
from tooling.security_report import analyze_ir
from tooling.capability_grant import (
    empty_grant,
    env_truthy,
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
from tooling.graph_diff import graph_diff
from intelligence.signature_enforcer import collect_signature_annotations, run_with_signature_retry
from intelligence.trace_export_ptc_jsonl import export_file as export_ptc_trace_file
from adapters.local_cache import LocalFileCacheAdapter
_TOOLING_DIR = Path(__file__).resolve().parent.parent / "tooling"

# Resource floor aligned with ``scripts/runtime_runner_service._SERVER_DEFAULT_LIMITS``.
_MCP_DEFAULT_LIMITS: Dict[str, Any] = {
    "max_steps": 2000,
    "max_depth": 20,
    "max_adapter_calls": 200,
    "max_time_ms": 30000,
}
# Back-compat for tests and introspection; same values as _MCP_DEFAULT_LIMITS.
_DEFAULT_LIMITS: Dict[str, Any] = dict(_MCP_DEFAULT_LIMITS)


# NOTE: These lists are part of the testing contract for exposure scoping.
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
    "ainl_fitness_report",
    "ainl_ir_diff",
    "ainl_ptc_signature_check",
    "ainl_trace_export",
    "ainl_ptc_run",
    "ainl_ptc_health_check",
]
ALL_RESOURCE_URIS: List[str] = [
    "ainl://adapter-manifest",
    "ainl://security-profiles",
]


def _csv_set(val: Optional[str]) -> Set[str]:
    if not val:
        return set()
    parts = [p.strip() for p in str(val).split(",")]
    return {p for p in parts if p}


def _resolve_exposure() -> tuple[Set[str], Set[str]]:
    """
    Resolve allowed MCP tools/resources.

    Precedence:
    - Start from profile (if AINL_MCP_EXPOSURE_PROFILE is valid), else "full".
    - Apply env inclusion lists (AINL_MCP_TOOLS / AINL_MCP_RESOURCES) if set (non-empty).
    - Apply env exclusion lists (AINL_MCP_TOOLS_EXCLUDE / AINL_MCP_RESOURCES_EXCLUDE).
    Unknown names/URIs are ignored.
    """
    base_tools = set(ALL_TOOL_NAMES)
    base_resources = set(ALL_RESOURCE_URIS)

    profile = (os.environ.get("AINL_MCP_EXPOSURE_PROFILE") or "").strip()
    if profile:
        try:
            prof_path = _TOOLING_DIR / "mcp_exposure_profiles.json"
            data = json.loads(prof_path.read_text(encoding="utf-8")) if prof_path.is_file() else {}
            prof = ((data.get("profiles") or {}) if isinstance(data, dict) else {}).get(profile)
            if isinstance(prof, dict):
                prof_tools = prof.get("tools")
                prof_res = prof.get("resources")
                if isinstance(prof_tools, list):
                    base_tools = set(x for x in prof_tools if isinstance(x, str) and x in base_tools)
                if isinstance(prof_res, list):
                    base_resources = set(x for x in prof_res if isinstance(x, str) and x in base_resources)
        except Exception:
            # Ignore profile errors; default to full exposure.
            base_tools = set(ALL_TOOL_NAMES)
            base_resources = set(ALL_RESOURCE_URIS)

    tools_include_raw = os.environ.get("AINL_MCP_TOOLS")
    if tools_include_raw is not None and str(tools_include_raw).strip():
        include = {n for n in _csv_set(tools_include_raw) if n in set(ALL_TOOL_NAMES)}
        base_tools = base_tools.intersection(include)

    res_include_raw = os.environ.get("AINL_MCP_RESOURCES")
    if res_include_raw is not None and str(res_include_raw).strip():
        include = {u for u in _csv_set(res_include_raw) if u in set(ALL_RESOURCE_URIS)}
        base_resources = base_resources.intersection(include)

    tools_ex = {n for n in _csv_set(os.environ.get("AINL_MCP_TOOLS_EXCLUDE")) if n in set(ALL_TOOL_NAMES)}
    res_ex = {u for u in _csv_set(os.environ.get("AINL_MCP_RESOURCES_EXCLUDE")) if u in set(ALL_RESOURCE_URIS)}
    base_tools = {t for t in base_tools if t not in tools_ex}
    base_resources = {r for r in base_resources if r not in res_ex}
    return base_tools, base_resources


_ALLOWED_TOOLS, _ALLOWED_RESOURCES = _resolve_exposure()


def _mcp_bare_floor() -> Dict[str, Any]:
    """Resource floor + permissive adapter cap (None), matching the default runner grant."""
    return {
        "allowed_adapters": None,
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": dict(_MCP_DEFAULT_LIMITS),
        "adapter_constraints": {},
    }


def _load_mcp_server_grant() -> Dict[str, Any]:
    """Build the MCP server-level capability grant."""
    profile_name = (os.environ.get("AINL_MCP_PROFILE") or "").strip()
    if profile_name:
        try:
            return merge_grants(_mcp_bare_floor(), load_profile_as_grant(profile_name))
        except ValueError:
            pass
    if env_truthy(os.environ.get("AINL_STRICT_MODE")):
        sp = (os.environ.get("AINL_STRICT_PROFILE") or "consumer_secure_default").strip()
        try:
            return merge_grants(_mcp_bare_floor(), load_profile_as_grant(sp))
        except ValueError:
            pass
    return _mcp_bare_floor()
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




def _load_config_from_path(config_path: str) -> dict:
    """Load YAML config from path and expand environment variables."""
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    def _expand(v):
        if isinstance(v, str):
            return os.path.expandvars(v)
        if isinstance(v, dict):
            return {k: _expand(v) for k, v in v.items()}
        if isinstance(v, list):
            return [_expand(x) for x in v]
        return v

    return _expand(raw)
def _compile(code: str, strict: bool = True) -> Dict[str, Any]:
    compiler = AICodeCompiler(strict_mode=strict)
    return compiler.compile(code)


def _with_llm_repair_hint(diags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in diags or []:
        if not isinstance(d, dict):
            continue
        row = dict(d)
        hint = row.get("llm_repair_hint") or row.get("suggested_fix") or row.get("message")
        row["llm_repair_hint"] = hint
        out.append(row)
    return out


def _file_to_ir(path: str, strict: bool = True) -> Dict[str, Any]:
    p = Path(path).expanduser()
    code = p.read_text(encoding="utf-8")
    return _compile(code, strict=strict)


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
    diagnostics = _with_llm_repair_hint(list(ir.get("diagnostics") or []))
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "diagnostics": diagnostics}


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
    adapters: Optional[dict] = None,
) -> dict:
    """Compile, validate policy, and execute an AINL workflow.

    By default, adapters referenced in the IR are allowed (same as the hosted
    runner); resource limits enforce a safety floor.  The caller may supply
    additional policy restrictions and tighter limits but cannot widen beyond
    the merged server defaults.

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
    mcp_allowed = grant_to_allowed_adapters(_MCP_SERVER_GRANT)
    reg = AdapterRegistry(allowed=None)
    reg.register("core", CoreBuiltinAdapter())
    # Optional runtime adapters can be enabled per-run. This avoids requiring
    # end users to edit global config while still allowing strict, scoped IO.
    #
    # Schema mirrors the runner service:
    # adapters: { enable: ["http","fs","cache","sqlite"], http: {...}, fs: {...}, cache: {...}, sqlite: {...} }
    if isinstance(adapters, dict):
        enabled = set(adapters.get("enable") or [])
        if "http" in enabled:
            h = adapters.get("http") or {}
            allow_hosts = h.get("allow_hosts") or []
            if not isinstance(allow_hosts, list) or not allow_hosts:
                return {
                    "ok": False,
                    "trace_id": trace_id,
                    "error": "adapter_config_error",
                    "details": "http adapter enabled but adapters.http.allow_hosts must be a non-empty list",
                }
            reg.register(
                "http",
                SimpleHttpAdapter(
                    default_timeout_s=float(h.get("timeout_s", 5.0)),
                    max_response_bytes=int(h.get("max_response_bytes", 1_000_000)),
                    allow_hosts=[str(x) for x in allow_hosts],
                ),
            )
        if "fs" in enabled:
            f = adapters.get("fs") or {}
            root = f.get("root")
            if not root:
                return {
                    "ok": False,
                    "trace_id": trace_id,
                    "error": "adapter_config_error",
                    "details": "fs adapter enabled but adapters.fs.root is missing",
                }
            reg.register(
                "fs",
                SandboxedFileSystemAdapter(
                    sandbox_root=str(root),
                    max_read_bytes=int(f.get("max_read_bytes", 1_000_000)),
                    max_write_bytes=int(f.get("max_write_bytes", 1_000_000)),
                    allow_extensions=f.get("allow_extensions") or [],
                    allow_delete=bool(f.get("allow_delete")),
                ),
            )
        if "cache" in enabled:
            c = adapters.get("cache") or {}
            cache_path = c.get("path")
            if not cache_path:
                return {
                    "ok": False,
                    "trace_id": trace_id,
                    "error": "adapter_config_error",
                    "details": "cache adapter enabled but adapters.cache.path is missing",
                }
            reg.register("cache", LocalFileCacheAdapter(path=str(cache_path)))
        if "sqlite" in enabled:
            s = adapters.get("sqlite") or {}
            db_path = s.get("db_path")
            if not db_path:
                return {
                    "ok": False,
                    "trace_id": trace_id,
                    "error": "adapter_config_error",
                    "details": "sqlite adapter enabled but adapters.sqlite.db_path is missing",
                }
            reg.register(
                "sqlite",
                SimpleSqliteAdapter(
                    db_path=str(db_path),
                    allow_write=bool(s.get("allow_write")),
                    allow_tables=s.get("allow_tables") or [],
                    timeout_s=float(s.get("timeout_s", 5.0)),
                ),
            )
    # Optional LLM adapter registration if AINL_CONFIG present
    config_path = os.environ.get("AINL_CONFIG")
    if config_path:
        try:
            config = _load_config_from_path(config_path)
            # Only attempt if llm providers are defined
            if config.get("llm", {}).get("providers"):
                from adapters import register_llm_adapters
                register_llm_adapters(reg, config)
        except Exception as e:
            # Log warning but continue; server remains functional without LLM
            print(f"[ainl_mcp_server] Warning: failed to register LLM adapters: {e}")


    try:
        eng = RuntimeEngine(
            ir=ir,
            adapters=reg,
            trace=False,
            step_fallback=True,
            execution_mode="graph-preferred",
            limits=merged_limits,
            host_adapter_allowlist=mcp_allowed,
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


@_register_tool
def ainl_fitness_report(file: str, runs: int = 5, strict: bool = True) -> dict:
    """Run a workflow repeatedly with safe adapters and report fitness metrics."""
    trace_id = str(uuid.uuid4())
    ir = _file_to_ir(file, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "trace_id": trace_id, "errors": errors}

    runs = max(1, int(runs))
    latencies_ms: List[float] = []
    step_counts: List[int] = []
    adapter_call_counts: List[int] = []
    final_frame_key_counts: List[int] = []
    op_histogram: Dict[str, int] = {}
    successes = 0
    last_error: Optional[str] = None
    sample_runs: List[Dict[str, Any]] = []
    fitness_allowed = grant_to_allowed_adapters(_MCP_SERVER_GRANT)
    merged_fitness_limits = _merge_limits(None)
    for _ in range(runs):
        reg = AdapterRegistry(allowed=None)
        reg.register("core", CoreBuiltinAdapter())
        start = time.perf_counter()
        run_summary: Dict[str, Any] = {"ok": False}
        try:
            eng = RuntimeEngine(
                ir=ir,
                adapters=reg,
                trace=True,
                step_fallback=True,
                execution_mode="graph-preferred",
                limits=dict(merged_fitness_limits),
                host_adapter_allowlist=fitness_allowed,
            )
            entry = eng.default_entry_label()
            eng.run_label(entry, frame={})
            successes += 1
            trace_events = list(eng.trace_events)
            run_steps = len(trace_events)
            run_adapter_calls = int(getattr(eng, "_adapter_calls", 0))
            end_frame_keys = trace_events[-1].get("frame_keys", []) if trace_events else []
            run_summary = {
                "ok": True,
                "steps": run_steps,
                "adapter_calls": run_adapter_calls,
                "final_frame_key_count": len(end_frame_keys),
            }
            step_counts.append(run_steps)
            adapter_call_counts.append(run_adapter_calls)
            final_frame_key_counts.append(len(end_frame_keys))
            for ev in trace_events:
                op = str(ev.get("op") or "")
                if op:
                    op_histogram[op] = op_histogram.get(op, 0) + 1
        except Exception as e:
            last_error = str(e)
            step_counts.append(0)
            adapter_call_counts.append(0)
            final_frame_key_counts.append(0)
            run_summary["error"] = str(e)
        latencies_ms.append(round((time.perf_counter() - start) * 1000.0, 3))
        if len(sample_runs) < 5:
            run_summary["latency_ms"] = latencies_ms[-1]
            sample_runs.append(run_summary)

    reliability = round(float(successes) / float(runs), 4)
    latency_avg = sum(latencies_ms) / len(latencies_ms)
    steps_avg = sum(step_counts) / len(step_counts)
    adapter_calls_avg = sum(adapter_call_counts) / len(adapter_call_counts)
    # Bounded 0..1 components with reliability emphasized for selection.
    latency_component = 1.0 / (1.0 + (latency_avg / 100.0))
    step_component = 1.0 / (1.0 + (steps_avg / 20.0))
    adapter_component = 1.0 / (1.0 + (adapter_calls_avg / 20.0))
    raw_fitness_score = (
        0.6 * reliability + 0.2 * latency_component + 0.1 * step_component + 0.1 * adapter_component
    )
    # Reliability gate: fully failing workflows should not rank above viable candidates.
    fitness_score = 0.0 if reliability <= 0.0 else round(raw_fitness_score, 6)
    return {
        "ok": successes > 0,
        "trace_id": trace_id,
        "file": str(file),
        "runs": runs,
        "metrics": {
            "latency_ms": {
                "avg": round(sum(latencies_ms) / len(latencies_ms), 3),
                "min": min(latencies_ms),
                "max": max(latencies_ms),
            },
            "step_count": {
                "avg": round(sum(step_counts) / len(step_counts), 3),
                "min": min(step_counts),
                "max": max(step_counts),
            },
            "adapter_calls": {
                "avg": round(sum(adapter_call_counts) / len(adapter_call_counts), 3),
                "min": min(adapter_call_counts),
                "max": max(adapter_call_counts),
            },
            "memory_deltas": {
                "tracked": True,
                "proxy": "trace.frame_keys",
                "final_frame_key_count": {
                    "avg": round(sum(final_frame_key_counts) / len(final_frame_key_counts), 3),
                    "min": min(final_frame_key_counts),
                    "max": max(final_frame_key_counts),
                },
            },
            "operation_histogram": dict(sorted(op_histogram.items())),
            "token_use_estimate": {
                "source_chars": len("\n".join((ir.get("source") or {}).get("lines", [])).encode("utf-8"))
            },
            "reliability_score": reliability,
            "fitness_score": fitness_score,
            "fitness_components": {
                "reliability_component": round(reliability, 6),
                "latency_component": round(latency_component, 6),
                "step_component": round(step_component, 6),
                "adapter_component": round(adapter_component, 6),
                "weights": {
                    "reliability": 0.6,
                    "latency": 0.2,
                    "steps": 0.1,
                    "adapter_calls": 0.1,
                },
            },
        },
        "sample_runs": sample_runs,
        "last_error": last_error,
    }


@_register_tool
def ainl_ir_diff(file1: str, file2: str, strict: bool = True) -> dict:
    """Return a minimal JSON diff between two canonical graph IRs."""
    left = _file_to_ir(file1, strict=strict)
    right = _file_to_ir(file2, strict=strict)
    lerr = left.get("errors") or []
    rerr = right.get("errors") or []
    if lerr or rerr:
        return {"ok": False, "file1_errors": lerr, "file2_errors": rerr}
    diff = graph_diff(left, right)
    changed_nodes_raw = diff.get("changed_nodes", {}) or {}
    changed_nodes_serialized: List[Dict[str, Any]] = []
    for (label_id, node_id), changes in changed_nodes_raw.items():
        changed_nodes_serialized.append(
            {"label_id": str(label_id), "node_id": str(node_id), "changes": dict(changes or {})}
        )
    return {
        "ok": True,
        "diff": {
            "added_nodes": diff.get("added_nodes", []),
            "removed_nodes": diff.get("removed_nodes", []),
            "changed_nodes": changed_nodes_serialized,
            "added_edges": diff.get("added_edges", []),
            "removed_edges": diff.get("removed_edges", []),
            "rewired_edges": diff.get("rewired_edges", []),
            "human_summary": diff.get("human_summary", ""),
        },
    }


@_register_tool
def ainl_ptc_signature_check(code: str, strict: bool = True) -> dict:
    """Inspect optional '# signature: ...' metadata annotations in source."""
    ir = _compile(code, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    annotations = collect_signature_annotations(code)
    return {"ok": True, "count": len(annotations), "annotations": annotations}


@_register_tool
def ainl_trace_export(trace_jsonl: str, output_jsonl: str) -> dict:
    """Export AINL trajectory JSONL to PTC-compatible JSONL."""
    return export_ptc_trace_file(trace_jsonl, output_jsonl)


@_register_tool
def ainl_ptc_run(
    lisp: str,
    signature: Optional[str] = None,
    subagent_budget: Optional[int] = None,
    max_attempts: int = 1,
) -> dict:
    """Run PTC-Lisp through the optional ptc_runner adapter."""
    from adapters.ptc_runner import PtcRunnerAdapter

    adapter = PtcRunnerAdapter(
        enabled=True,
        allow_hosts=[],
        timeout_s=30.0,
        max_response_bytes=1_000_000,
    )
    if signature:
        out = run_with_signature_retry(
            adapter=adapter,
            lisp=lisp,
            signature=signature,
            subagent_budget=subagent_budget,
            context={},
            max_attempts=max_attempts,
        )
        return {"ok": bool(out.get("ok")), "result": out}
    out = adapter.run(lisp, signature=signature, subagent_budget=subagent_budget, context={})
    return {"ok": bool(out.get("ok")), "result": out}


@_register_tool
def ainl_ptc_health_check(
    allow_hosts: Optional[List[str]] = None,
    timeout_s: float = 5.0,
) -> dict:
    """Lightweight health/status check for the optional ptc_runner service."""
    from adapters.ptc_runner import PtcRunnerAdapter

    try:
        adapter = PtcRunnerAdapter(
            enabled=True,
            allow_hosts=allow_hosts or [],
            timeout_s=timeout_s,
            max_response_bytes=200_000,
        )
        out = adapter.health(context={})
        return {"ok": bool(out.get("ok")), "result": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
