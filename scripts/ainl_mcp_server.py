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
import hashlib
import json
import os
import re
import threading
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

from compiler_diagnostics import CompilationDiagnosticError, CompilerContext
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
# max_depth raised from 20 to 500: tail-recursive loops over real data sets (e.g.
# 73 liens × 3 call frames each) require much more than 20. max_steps and
# max_adapter_calls raised proportionally. max_time_ms raised to 900s (15min)
# to support HTTP-enrichment workflows that make one outbound call per record
# (73 records × ~10s/call = ~730s worst-case with no cache warm-up).
_MCP_DEFAULT_LIMITS: Dict[str, Any] = {
    "max_steps": 500000,
    "max_depth": 500,
    "max_adapter_calls": 50000,
    "max_time_ms": 900000,
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
    "ainl://authoring-cheatsheet",
    "ainl://impact-checklist",
    "ainl://adapter-risk-matrix",
    "ainl://run-readiness",
    "ainl://policy-contract",
]

# Short MCP-facing authoring guide (mirrors AGENTS.md highlights for agent loops).
_AUTHORING_CHEATSHEET_MARKDOWN: str = """# AINL authoring — MCP cheatsheet

**Golden path:** `ainl_validate` (`strict=true`) after every edit → fix using `primary_diagnostic`, `source_context`, `agent_repair_steps` → `ainl_compile` for IR + `frame_hints` → `ainl_run` with `adapters` when the graph uses http/fs/cache/sqlite.

## Avoid
- Using repo-wide `file_search` / greps on random `.ainl` files as your primary syntax reference — trust validate output and `ainl_capabilities`.
- `params=` / `timeout=` as fake named arguments on `R http.GET` / `R http.POST` — use positional URL, optional headers dict, optional timeout (seconds), query string in the URL.
- Inline `{...}` dict literals on `R` lines where you need a real dict — they are tokenized as raw strings; pass dicts via `frame` or build with `core` ops and variables.

## Prefer
- `ainl_capabilities` before inventing `R adapter.VERB` lines for strict graphs.
- `ainl_run`: pass `adapters` to register http, fs, cache, sqlite when the IR references them (not registered by default in MCP).
- `core.GET`: first positional arg is the container (dict/list), second is the key/index string.

Ground truth in-repo: **AGENTS.md** (HTTP adapter, queue, strict-valid examples).
"""

_IMPACT_CHECKLIST_MARKDOWN: str = """# Impact-first checklist (GitNexus-style alignment)

1. `ainl_validate` (`strict=true`) after every edit.
2. `ainl_compile` for canonical IR.
3. `ainl_ir_diff` when comparing to a prior IR file (blast-radius on graph delta).
4. `ainl_run` only with explicit `adapters` for http/fs/cache/sqlite as needed.

If a **repo-intelligence MCP** (e.g. GitNexus) is available in your host, prefer its `impact` / `context` tools before broad filesystem edits.
"""

_ADAPTER_RISK_MATRIX_MARKDOWN: str = """# Adapter risk matrix (summary)

| Area | Notes |
|------|------|
| `http` / `web` | Network egress; use host allowlists (`ainl_capabilities` + grants). |
| `fs` | Sandboxed paths; never assume repo-wide read without policy. |
| `llm` | May require `AINL_CONFIG` / MCP LLM enablement. |

Full manifest: resource `ainl://adapter-manifest`, privileges: `ainl://security-profiles`.
"""

_RUN_READINESS_MARKDOWN: str = """# Run readiness

- **Context freshness** (contract): often `unknown` in MCP-only hosts — ArmaraOS may supply `fresh`/`stale` via integrations.
- **Recommended chain**: see `ainl://policy-contract` and `recommended_next_tools` on validate/compile responses.
- **Telemetry names** (stable): `capability_profile_state`, `freshness_state_at_decision`, `impact_checked_before_write` (see policy contract JSON).
"""


def _load_policy_contract_json() -> Dict[str, Any]:
    """Mirror of `tooling/ainl_policy_contract.json` for MCP clients."""
    p = _TOOLING_DIR / "ainl_policy_contract.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "error": "missing_or_invalid_ainl_policy_contract.json"}


def _impact_first_mode() -> bool:
    """Impact-first recommended steps when profile or env requests it."""
    if env_truthy(os.environ.get("AINL_MCP_IMPACT_FIRST")):
        return True
    prof = (os.environ.get("AINL_MCP_EXPOSURE_PROFILE") or "").strip()
    return prof == "design_impact_first"


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

# --- Process-local MCP telemetry (stdio server lifetime; for operator / agent metrics) ---
_TELEM_LOCK = threading.Lock()
_MCP_TELEM: Dict[str, int] = {}
_pending_validate_ok_sha256: Optional[str] = None
_last_validate_was_fail = False


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _telemetry_snapshot() -> Dict[str, int]:
    with _TELEM_LOCK:
        return dict(_MCP_TELEM)


def _on_validate_finished(ok: bool, code: str) -> None:
    global _pending_validate_ok_sha256, _last_validate_was_fail
    h = _sha256_text(code)
    with _TELEM_LOCK:
        _MCP_TELEM["validate_calls"] = _MCP_TELEM.get("validate_calls", 0) + 1
        if ok:
            _MCP_TELEM["validate_ok"] = _MCP_TELEM.get("validate_ok", 0) + 1
            _pending_validate_ok_sha256 = h
            if _last_validate_was_fail:
                _MCP_TELEM["validate_recovery_after_fail"] = (
                    _MCP_TELEM.get("validate_recovery_after_fail", 0) + 1
                )
            _last_validate_was_fail = False
        else:
            _MCP_TELEM["validate_fail"] = _MCP_TELEM.get("validate_fail", 0) + 1
            _pending_validate_ok_sha256 = None
            _last_validate_was_fail = True


def _on_compile_finished(ok: bool, code: str) -> None:
    global _pending_validate_ok_sha256
    h = _sha256_text(code)
    with _TELEM_LOCK:
        _MCP_TELEM["compile_calls"] = _MCP_TELEM.get("compile_calls", 0) + 1
        if ok:
            _MCP_TELEM["compile_ok"] = _MCP_TELEM.get("compile_ok", 0) + 1
            if _pending_validate_ok_sha256 == h:
                _pending_validate_ok_sha256 = None
        else:
            _MCP_TELEM["compile_fail"] = _MCP_TELEM.get("compile_fail", 0) + 1


def _on_run_started(code: str) -> None:
    global _pending_validate_ok_sha256
    h = _sha256_text(code)
    with _TELEM_LOCK:
        _MCP_TELEM["run_calls"] = _MCP_TELEM.get("run_calls", 0) + 1
        if _pending_validate_ok_sha256 == h:
            _MCP_TELEM["run_after_validate_without_compile"] = (
                _MCP_TELEM.get("run_after_validate_without_compile", 0) + 1
            )
        _pending_validate_ok_sha256 = None


def _failure_tags_from_diagnostics(
    diagnostics: List[Dict[str, Any]],
    primary: Optional[Dict[str, Any]],
) -> Set[str]:
    """Coarse tags for branching ``recommended_next_tools`` / resources."""
    tags: Set[str] = set()
    pool: List[Dict[str, Any]] = []
    if primary and isinstance(primary, dict):
        pool.append(primary)
    for d in diagnostics or []:
        if isinstance(d, dict) and d is not primary:
            pool.append(d)
    for d in pool[:12]:
        kind = str(d.get("kind", "")).lower()
        msg = str(d.get("message", "")).lower()
        comb = f"{kind} {msg}"
        if kind in (
            "unknown_adapter_verb",
            "strict_validation_failure",
            "contract_violation",
        ):
            tags.add("adapter_or_verb")
        if any(
            x in comb
            for x in (
                "unknown adapter",
                "unknown verb",
                "does not exist on adapter",
                "strict adapter",
            )
        ):
            tags.add("adapter_or_verb")
        if "http" in msg and any(
            x in msg for x in ("params", "timeout =", "named argument", "inline", "dict literal")
        ):
            tags.add("http_or_rline")
        if "could not convert string to float" in msg and "http" in comb:
            tags.add("http_or_rline")
        if "tokenize" in comb and "http" in comb:
            tags.add("http_or_rline")
    return tags


def _attach_policy_contract_hints(out: Dict[str, Any]) -> None:
    """Attach cross-runtime policy hints (JSON-serializable; aligns with ainl-contracts)."""
    pc = _load_policy_contract_json()
    out["policy_contract"] = {
        "schema_version": pc.get("schema_version", 1),
        "context_freshness": "unknown",
        "telemetry_field_names": pc.get("telemetry_field_names", {}),
        "golden_recommended_next_tools_chain": pc.get("golden_recommended_next_tools_chain", []),
    }


def _add_recommended_next_steps(
    out: Dict[str, Any],
    kind: str,
    *,
    failure_tags: Optional[Set[str]] = None,
) -> None:
    """Attach ``recommended_next_tools`` and optional ``recommended_resources`` (MCP URIs).

    Names are filtered to the current exposure (``_ALLOWED_*``) so agents are not
    pointed at tools/resources they cannot call.

    kind: validate_ok | validate_fail | compile_ok | compile_fail
    """
    tools: List[str] = []
    resources: List[str] = []
    if_ = _impact_first_mode()
    if kind == "validate_ok":
        if if_:
            tools = [
                "ainl_compile",
                "ainl_ir_diff",
                "ainl_capabilities",
                "ainl_security_report",
                "ainl_run",
            ]
        else:
            tools = ["ainl_compile", "ainl_capabilities", "ainl_security_report", "ainl_run"]
    elif kind in ("validate_fail", "compile_fail"):
        tags = failure_tags or set()
        adapter = "adapter_or_verb" in tags
        http = "http_or_rline" in tags
        if adapter and not http:
            tools = ["ainl_capabilities", "ainl_validate", "ainl_compile"]
            resources = []
        elif http and not adapter:
            tools = ["ainl_validate"]
            resources = ["ainl://authoring-cheatsheet"]
        elif adapter and http:
            tools = ["ainl_capabilities", "ainl_validate"]
            resources = ["ainl://authoring-cheatsheet"]
        else:
            tools = ["ainl_validate", "ainl_capabilities"]
            resources = ["ainl://authoring-cheatsheet"]
    elif kind == "compile_ok":
        if if_:
            tools = ["ainl_ir_diff", "ainl_run", "ainl_validate", "ainl_security_report"]
        else:
            tools = ["ainl_run", "ainl_security_report", "ainl_validate"]
    else:
        return
    tools_f = [t for t in tools if t in _ALLOWED_TOOLS]
    res_f = [r for r in resources if r in _ALLOWED_RESOURCES]
    out["recommended_next_tools"] = tools_f
    if res_f:
        out["recommended_resources"] = res_f
    _attach_policy_contract_hints(out)


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
            "On compile errors, responses include primary_diagnostic, "
            "per-diagnostic source_context (snippet+caret), llm_repair_hint, "
            "and agent_repair_steps — fix those before searching the repo for examples. "
            "Use ainl_list_ecosystem for curated Clawflows/Agency-Agents presets; "
            "ainl_import_clawflow, ainl_import_agency_agent, and ainl_import_markdown "
            "fetch Markdown and return deterministic .ainl source (network). "
            "MCP resource ainl://authoring-cheatsheet summarizes HTTP R-lines and adapters; "
            "validate/compile responses include recommended_next_tools. "
            "ainl_capabilities returns mcp_telemetry (call counters for this server process)."
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


def _ir_from_compilation_diagnostic_error(exc: CompilationDiagnosticError) -> Dict[str, Any]:
    """Minimal IR-shaped dict when strict compile raises with structured diagnostics."""
    text = exc.source
    lines = text.split("\n")
    structs = [d.to_dict() for d in exc.diagnostics]
    errors: List[str] = []
    for d in exc.diagnostics:
        ln = d.lineno if getattr(d, "lineno", 0) and d.lineno > 0 else 1
        errors.append(f"Line {ln}: {d.message}")
    return {
        "source": {"text": text, "lines": lines},
        "errors": errors,
        "warnings": [],
        "structured_diagnostics": structs,
        "diagnostics": list(structs),
    }


def _compile(code: str, strict: bool = True) -> Dict[str, Any]:
    """Compile with :class:`CompilerContext` so IR includes rich structured diagnostics."""
    compiler = AICodeCompiler(strict_mode=strict)
    ctx = CompilerContext()
    try:
        return compiler.compile(code, context=ctx)
    except CompilationDiagnosticError as e:
        return _ir_from_compilation_diagnostic_error(e)


def _extract_frame_hints(code: str, ir: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract variables that callers should supply via the ``frame`` parameter.

    Two sources:
    1. Explicit ``# frame: name: type`` comment lines in source (authoritative).
    2. Variables referenced in IR ``X`` / ``R`` nodes that are not assigned
       anywhere in the graph (heuristic — catches undeclared inputs).

    Returns a list of ``{"name": ..., "type": ..., "source": "comment"|"inferred"}``
    dicts, deduplicated by name (comment entries take precedence).
    """
    hints: Dict[str, Dict[str, str]] = {}

    # Pass 1 — explicit comment declarations: "# frame: name: type" or "# frame: name"
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        body = stripped[1:].strip()
        if not body.lower().startswith("frame:"):
            continue
        rest = body[6:].strip()
        if not rest:
            continue
        parts = rest.split(":", 1)
        name = parts[0].strip()
        typ = parts[1].strip() if len(parts) > 1 else "any"
        if name:
            hints[name] = {"name": name, "type": typ, "source": "comment"}

    # Pass 2 — heuristic: collect all variable names assigned in the IR graph,
    # then find args in R/X nodes that reference names never assigned (inputs).
    try:
        nodes = ir.get("nodes") or []
        assigned: set = set()
        referenced: set = set()

        for node in nodes:
            if not isinstance(node, dict):
                continue
            op = node.get("op", "")
            # Track assignment targets
            out_var = node.get("out") or node.get("var")
            if out_var and isinstance(out_var, str) and not out_var.startswith("_"):
                assigned.add(out_var)
            # Track args used in R calls
            if op in ("R", "X", "Set"):
                for arg in node.get("args") or []:
                    if isinstance(arg, str) and re.match(r'^[a-z_][a-z0-9_]*$', arg):
                        referenced.add(arg)

        # Variables referenced but never assigned = probable frame inputs
        _BUILTIN_NAMES = {"null", "true", "false", "none"}
        for name in sorted(referenced - assigned - _BUILTIN_NAMES):
            if name not in hints:
                hints[name] = {"name": name, "type": "any", "source": "inferred"}
    except Exception:
        pass  # Heuristic is best-effort; never fail compile

    return list(hints.values())


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


def _ir_source_lines(ir: Dict[str, Any]) -> List[str]:
    """Line list from IR ``source`` (same text the compiler used)."""
    src = ir.get("source") if isinstance(ir.get("source"), dict) else {}
    lines = src.get("lines")
    if isinstance(lines, list) and lines:
        return [str(x) for x in lines]
    text = src.get("text")
    if isinstance(text, str) and text:
        return text.splitlines()
    return []


def _diag_lineno_col(d: Dict[str, Any]) -> tuple[int, int]:
    """Best-effort 1-based line and 0-based column from heterogeneous diagnostic dicts."""
    ln = d.get("lineno")
    line_no = int(ln) if isinstance(ln, int) else 0
    if line_no <= 0:
        sp = d.get("span")
        if isinstance(sp, dict):
            sl = sp.get("line")
            if isinstance(sl, int) and sl > 0:
                line_no = sl
    col = 0
    co = d.get("col_offset")
    if isinstance(co, int):
        col = co
    else:
        sp = d.get("span")
        if isinstance(sp, dict):
            cs = sp.get("col_start")
            if isinstance(cs, int):
                col = cs
    return line_no, col


def _diag_dup_key(d: Dict[str, Any]) -> tuple[Any, ...]:
    ln, _ = _diag_lineno_col(d)
    msg = str(d.get("message", ""))[:160]
    sev = str(d.get("severity", d.get("kind", "")))
    return (ln, msg, sev)


def _merge_ir_diagnostics(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Merge ``structured_diagnostics`` (rich) with legacy ``diagnostics`` without duplicates."""
    merged: List[Dict[str, Any]] = []
    seen: Set[tuple[Any, ...]] = set()
    for key in ("structured_diagnostics", "diagnostics"):
        block = ir.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            k = _diag_dup_key(item)
            if k in seen:
                continue
            seen.add(k)
            merged.append(item)
    return merged


def _source_context_for_diagnostic(
    lines: List[str],
    lineno: int,
    col: int,
    *,
    radius: int = 2,
) -> Optional[Dict[str, Any]]:
    if lineno < 1 or not lines:
        return None
    if lineno > len(lines):
        return None
    idx = lineno - 1
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    width = max(4, len(str(end)))
    numbered: List[str] = []
    for i in range(start, end):
        numbered.append(f"{i + 1:{width}d} | {lines[i]}")
    caret_pad = width + 3 + max(0, col)
    caret = " " * caret_pad + "^"
    return {
        "line_start": start + 1,
        "line_end": end,
        "focus_line": lineno,
        "numbered_lines": numbered,
        "caret": caret,
    }


def _attach_source_contexts(lines: List[str], diags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in diags:
        row = dict(d)
        ln, col = _diag_lineno_col(row)
        ctx = _source_context_for_diagnostic(lines, ln, col) if ln > 0 else None
        if ctx is not None:
            row["source_context"] = ctx
        out.append(row)
    return out


def _pick_primary_diagnostic(diags: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not diags:
        return None
    errors = []
    for d in diags:
        sev = str(d.get("severity", "")).lower()
        kind = str(d.get("kind", "")).lower()
        code = str(d.get("code", "")).upper()
        if sev == "error" or "error" in kind or code.endswith("_ERROR"):
            errors.append(d)
    pool = errors if errors else list(diags)

    def sort_key(d: Dict[str, Any]) -> tuple[int, int, str]:
        ln, col = _diag_lineno_col(d)
        return (ln if ln > 0 else 9999, col, str(d.get("message", "")))

    pool_sorted = sorted(pool, key=sort_key)
    return dict(pool_sorted[0]) if pool_sorted else None


# Short, stable guidance so small models rely on tool output instead of repo-wide search.
_AGENT_REPAIR_STEPS: List[str] = [
    "Fix primary_diagnostic first, then re-call ainl_validate (one change at a time).",
    "Follow llm_repair_hint on each diagnostic — it is grounded in this compile, not in other files.",
    "For adapter and verb names, call ainl_capabilities; avoid copying random .ainl files as templates.",
]


def _enriched_compile_feedback(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Shared shape for validate / compile / run when compilation produced errors or warnings."""
    lines = _ir_source_lines(ir)
    merged = _merge_ir_diagnostics(ir)
    hinted = _with_llm_repair_hint(merged)
    diagnostics = _attach_source_contexts(lines, hinted)
    primary = _pick_primary_diagnostic(diagnostics)
    if primary is not None and lines:
        ln, col = _diag_lineno_col(primary)
        ctx = _source_context_for_diagnostic(lines, ln, col)
        if ctx is not None:
            primary = dict(primary)
            primary["source_context"] = ctx
    errors_list = list(ir.get("errors") or [])
    out: Dict[str, Any] = {
        "errors": errors_list,
        "warnings": list(ir.get("warnings") or []),
        "diagnostics": diagnostics,
        "primary_diagnostic": primary,
    }
    if errors_list:
        out["agent_repair_steps"] = list(_AGENT_REPAIR_STEPS)
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
        "mcp_telemetry": _telemetry_snapshot(),
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


def _resolve_code_arg(code: Optional[str], ainl: Optional[str] = None) -> str:
    """Accept `code` (canonical) and legacy alias `ainl`."""
    if isinstance(code, str) and code.strip():
        return code
    if isinstance(ainl, str) and ainl.strip():
        return ainl
    return ""


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@_register_tool
def ainl_validate(code: Optional[str] = None, strict: bool = True, ainl: Optional[str] = None) -> dict:
    """Validate AINL source code without executing it.

    Returns whether the code compiles successfully, along with any errors
    or warnings.  No side effects.

    On failure, ``primary_diagnostic`` and per-row ``source_context`` (snippet +
    caret) point at the first error to fix; ``agent_repair_steps`` suggests a
    tight validate loop instead of copying unrelated files as templates.

    Always includes ``recommended_next_tools`` (and on failure,
    ``recommended_resources`` may list ``ainl://authoring-cheatsheet``) filtered
    by MCP exposure.
    """
    source = _resolve_code_arg(code, ainl)
    if not source:
        return {"ok": False, "errors": ["missing required argument: code"]}
    ir = _compile(source, strict=strict)
    fb = _enriched_compile_feedback(ir)
    ok = len(fb["errors"]) == 0
    _on_validate_finished(ok, source)
    out: Dict[str, Any] = {
        "ok": ok,
        "errors": fb["errors"],
        "warnings": fb["warnings"],
        "diagnostics": fb["diagnostics"],
        "primary_diagnostic": fb["primary_diagnostic"],
    }
    if "agent_repair_steps" in fb:
        out["agent_repair_steps"] = fb["agent_repair_steps"]
    if ok:
        _add_recommended_next_steps(out, "validate_ok")
    else:
        tags = _failure_tags_from_diagnostics(
            fb["diagnostics"],
            fb.get("primary_diagnostic"),
        )
        _add_recommended_next_steps(out, "validate_fail", failure_tags=tags)
    return out


@_register_tool
def ainl_compile(code: Optional[str] = None, strict: bool = True, ainl: Optional[str] = None) -> dict:
    """Compile AINL source code to canonical graph IR.

    Returns the full IR JSON on success, plus a ``frame_hints`` list that
    describes variables the caller should supply via the ``frame`` parameter
    when calling ``ainl_run``.  Frame hints are derived from two sources:

    1. Explicit ``# frame: name: type`` comment lines in source (authoritative).
    2. Variables referenced in the IR that are never assigned (heuristic).

    No execution, no side effects.

    On compile failure, returns the same diagnostic bundle as ``ainl_validate``
    (merged structured diagnostics, snippets, ``primary_diagnostic``).

    Success and failure responses include ``recommended_next_tools`` (and
    failure may add ``recommended_resources``) like ``ainl_validate``.
    """
    source = _resolve_code_arg(code, ainl)
    if not source:
        return {"ok": False, "errors": ["missing required argument: code"]}
    ir = _compile(source, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        fb = _enriched_compile_feedback(ir)
        _on_compile_finished(False, source)
        out: Dict[str, Any] = {"ok": False, "errors": fb["errors"], "warnings": fb["warnings"]}
        out["diagnostics"] = fb["diagnostics"]
        out["primary_diagnostic"] = fb["primary_diagnostic"]
        if "agent_repair_steps" in fb:
            out["agent_repair_steps"] = fb["agent_repair_steps"]
        tags = _failure_tags_from_diagnostics(
            fb["diagnostics"],
            fb.get("primary_diagnostic"),
        )
        _add_recommended_next_steps(out, "compile_fail", failure_tags=tags)
        return out
    _on_compile_finished(True, source)
    frame_hints = _extract_frame_hints(source, ir)
    out_ok: Dict[str, Any] = {"ok": True, "ir": ir, "frame_hints": frame_hints}
    _add_recommended_next_steps(out_ok, "compile_ok")
    return out_ok


@_register_tool
def ainl_capabilities() -> dict:
    """Discover runtime adapter capabilities, privilege tiers, and metadata.

    Returns available adapters with their verbs, support tiers, effect
    defaults, recommended lanes, and privilege tiers.  Also includes
    ``mcp_telemetry`` (per-process counters for validate/compile/run).  No side
    effects beyond bump-free read of those counters.
    """
    return _load_capabilities()


@_register_tool
def ainl_security_report(code: Optional[str] = None, ainl: Optional[str] = None) -> dict:
    """Generate a security/privilege map for an AINL workflow.

    Shows which adapters, verbs, and privilege tiers the workflow uses,
    broken down per label and in aggregate.  No execution, no side effects.
    """
    source = _resolve_code_arg(code, ainl)
    if not source:
        return {"ok": False, "errors": ["missing required argument: code"]}
    ir = _compile(source, strict=False)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    report = analyze_ir(ir)
    return {"ok": True, "report": report}


@_register_tool
def ainl_run(
    code: Optional[str] = None,
    strict: bool = True,
    policy: Optional[dict] = None,
    limits: Optional[dict] = None,
    frame: Optional[dict] = None,
    label: Optional[str] = None,
    adapters: Optional[dict] = None,
    ainl: Optional[str] = None,
) -> dict:
    """Compile, validate policy, and execute an AINL workflow.

    By default only the ``core`` adapter is registered. Any workflow that uses
    ``http``, ``fs``, ``cache``, or ``sqlite`` adapters MUST pass them via the
    ``adapters`` parameter or the run will fail with "adapter not registered".

    IMPORTANT — adapter registration is opt-in per-run:
      - ``http``  → requires ``allow_hosts`` (list of hostnames, e.g. ["example.com"])
      - ``fs``    → requires ``root`` (absolute path to sandbox directory)
      - ``cache`` → requires ``path`` (absolute path to cache JSON file)
      - ``sqlite``→ requires ``db_path``

    IMPORTANT — dict literals in AINL source ``{"key": "val"}`` on ``R`` lines
    are tokenized as raw strings, NOT evaluated as dicts at runtime. If your
    workflow calls ``R http.POST url my_body ->resp``, the ``my_body`` variable
    must be a pre-built dict — pass it via the ``frame`` parameter::

        frame={"my_body": {"FirstName": "", "DocumentType": "LIEN", ...}}

    IMPORTANT — variable shadowing in ``R`` arguments: string literals in ``R``
    arg positions (e.g. ``"records"``) have their quotes stripped during compilation
    and are resolved against the live frame before being used as literals.  If a
    frame variable named ``records`` already exists, ``R core.GET data "records"``
    will pass that variable's value rather than the string ``"records"``.

    Prevention: use unique variable name prefixes in every label that iterates
    or recurses over similar data.  Example: first loop uses ``lien_*`` names,
    second loop uses ``out_*`` names — that way ``"records"`` never collides with
    a live ``records`` variable.  The ``ainl_compile`` tool returns a
    ``frame_hints`` list that documents variables expected via ``frame``.

    Example — workflow that does HTTP + file I/O + caching::

        adapters={
          "enable": ["http", "fs", "cache"],
          "http": {
            "allow_hosts": ["ohwarren.fidlar.com", "auditor.warrencountyohio.gov"],
            "timeout_s": 15.0
          },
          "fs": {
            "root": "/Users/me/.armaraos/workspaces/MyProject",
            "allow_extensions": [".json", ".csv"]
          },
          "cache": {
            "path": "/Users/me/.armaraos/workspaces/MyProject/cache.json"
          }
        }

    Resource limits enforce a safety floor. The caller may supply additional
    policy restrictions and tighter limits but cannot widen beyond the merged
    server defaults.

    Returns structured execution output on success or a policy/runtime
    error on failure.
    """
    trace_id = str(uuid.uuid4())
    source = _resolve_code_arg(code, ainl)
    if not source:
        return {"ok": False, "error": "missing required argument: code"}
    _on_run_started(source)
    run_warnings: List[str] = []

    ir = _compile(source, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        fb = _enriched_compile_feedback(ir)
        out: Dict[str, Any] = {
            "ok": False,
            "trace_id": trace_id,
            "errors": fb["errors"],
            "warnings": fb["warnings"],
            "diagnostics": fb["diagnostics"],
            "primary_diagnostic": fb["primary_diagnostic"],
        }
        if "agent_repair_steps" in fb:
            out["agent_repair_steps"] = fb["agent_repair_steps"]
        return out

    merged_policy = _merge_policy(policy)
    policy_result = validate_ir_against_policy(ir, merged_policy)
    if not policy_result["ok"]:
        return {
            "ok": False,
            "trace_id": trace_id,
            "error": "policy_violation",
            "policy_errors": policy_result["errors"],
        }

    # Item 9: Per-workspace limits override.
    # If the fs adapter root contains an ``ainl_mcp_limits.json`` file, merge it
    # into the caller-supplied limits BEFORE applying server defaults.  This lets
    # a workspace raise (or tighten) limits for known long-running scripts without
    # editing the global server file.  Server defaults still cap the result via
    # ``_merge_limits`` — workspace overrides only widen up to the server ceiling.
    workspace_limits: Dict[str, Any] = {}
    _fs_root_for_limits: Optional[str] = None
    if isinstance(adapters, dict) and isinstance(adapters.get("fs"), dict):
        _fs_root_for_limits = (adapters["fs"].get("root") or "").strip() or None
    if _fs_root_for_limits:
        _ws_limits_path = Path(_fs_root_for_limits) / "ainl_mcp_limits.json"
        if _ws_limits_path.is_file():
            try:
                workspace_limits = json.loads(_ws_limits_path.read_text(encoding="utf-8"))
            except Exception:
                workspace_limits = {}
                run_warnings.append(
                    f"ainl_mcp_limits.json at {_ws_limits_path} is not valid JSON; "
                    "using default limits."
                )
    # Caller limits override workspace defaults; workspace defaults override nothing
    # (server ceiling enforced in _merge_limits either way).
    effective_caller_limits: Dict[str, Any] = {**workspace_limits, **(limits or {})}
    merged_limits = _merge_limits(effective_caller_limits)

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
    # Item 10: Auto-register cache adapter when a cache.json exists in the workspace.
    # If the fs adapter is enabled with a root directory, and the caller did NOT
    # explicitly enable the cache adapter, check for a cache file at the
    # conventional locations (output/cache.json, then cache.json at root).
    # This makes caching zero-config for workspace scripts that already have a
    # cache file on disk — callers still need to use ``R cache.GET/SET`` in code.
    if isinstance(adapters, dict) and "cache" not in set(adapters.get("enable") or []):
        _auto_cache_root = (adapters.get("fs") or {}).get("root")
        if _auto_cache_root:
            _candidates = [
                Path(_auto_cache_root) / "output" / "cache.json",
                Path(_auto_cache_root) / "cache.json",
            ]
            for _cp in _candidates:
                if _cp.is_file():
                    try:
                        raw = _cp.read_text(encoding="utf-8")
                        if raw.strip():
                            json.loads(raw)
                    except json.JSONDecodeError as e:
                        return {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": f"cache.json at {_cp} is not valid JSON: {e}",
                        }
                    reg.register("cache", LocalFileCacheAdapter(path=str(_cp)))
                    break

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

    out_run: Dict[str, Any] = {
        "ok": True,
        "trace_id": trace_id,
        "label": entry,
        "out": out,
        "runtime_version": RUNTIME_VERSION,
        "ir_version": ir.get("ir_version"),
    }
    if run_warnings:
        out_run["warnings"] = run_warnings
    return out_run


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


@_register_resource("ainl://authoring-cheatsheet")
def authoring_cheatsheet_resource() -> str:
    """Concise AINL authoring rules: validate-first, HTTP R-lines, adapters, frame dicts."""
    return _AUTHORING_CHEATSHEET_MARKDOWN


@_register_resource("ainl://impact-checklist")
def impact_checklist_resource() -> str:
    """Impact-first editing checklist aligned with ainl-impact-policy golden chain."""
    return _IMPACT_CHECKLIST_MARKDOWN


@_register_resource("ainl://adapter-risk-matrix")
def adapter_risk_matrix_resource() -> str:
    """Short adapter risk summary; full data in adapter-manifest + security-profiles."""
    return _ADAPTER_RISK_MATRIX_MARKDOWN


@_register_resource("ainl://run-readiness")
def run_readiness_resource() -> str:
    """Context freshness and telemetry field names for operator dashboards."""
    return _RUN_READINESS_MARKDOWN


@_register_resource("ainl://policy-contract")
def policy_contract_resource() -> str:
    """Serialized `tooling/ainl_policy_contract.json` (cross-runtime contract with Rust ainl-contracts)."""
    return json.dumps(_load_policy_contract_json(), indent=2)


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
