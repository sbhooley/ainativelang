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
import copy
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
import yaml
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

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
from runtime.adapters.a2a import A2aAdapter
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
from tooling.ainl_get_started import (
    adapter_contract as ainl_adapter_contract_payload,
    get_started as ainl_get_started_wizard,
    load_artifact_profiles,
    reverse_engineer_corpus as reverse_engineer_ainl_corpus,
    reverse_engineer_source as reverse_engineer_ainl_source,
    step_examples as ainl_get_started_step_examples,
    WizardState,
    wizard_state_from_tool_result,
)
from tooling.mission_mcp import (
    MISSION_AUTHORING_CHEATSHEET,
    lint_handoff as mission_lint_handoff,
    mission_plan as mission_plan_payload,
    validate_mission_dag,
)
from tooling.graph_diff import graph_diff
from intelligence.signature_enforcer import collect_signature_annotations, run_with_signature_retry
from intelligence.trace_export_ptc_jsonl import export_file as export_ptc_trace_file
from adapters.local_cache import LocalFileCacheAdapter
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLING_DIR = _REPO_ROOT / "tooling"
_INTEGRATIONS_DOCS_DIR = _REPO_ROOT / "docs" / "integrations"
# Filenames allowed for MCP resources under docs/integrations (path traversal safe).
_INTEGRATION_DOC_ALLOWLIST: frozenset[str] = frozenset(
    {
        "README.md",
        "HTTP_MACHINE_PAYMENTS.md",
        "AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md",
        "AGTP.md",
        "A2A_ADAPTER.md",
    }
)


def _read_integration_doc(filename: str) -> str:
    """Return UTF-8 text for a hub doc, or a short error markdown."""
    if filename not in _INTEGRATION_DOC_ALLOWLIST:
        return f"# Error\nunknown integration doc `{filename}`.\n"
    path = _INTEGRATIONS_DOCS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"# Error\nfailed to read `{filename}`: {exc}\n"


# Repo-relative paths allowed as MCP resources (must stay under ``_REPO_ROOT``).
_MCP_SNIPPET_RESOURCE_PATHS: frozenset[str] = frozenset(
    {
        "examples/http/http_machine_payment_flow_compact.ainl",
    }
)


def _read_allowlisted_repo_subpath(rel: str) -> str:
    """Return UTF-8 text for a allowlisted repo file (examples, etc.)."""
    if rel not in _MCP_SNIPPET_RESOURCE_PATHS:
        return f"# Error\nunknown MCP snippet path `{rel}`.\n"
    root = _REPO_ROOT.resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return "# Error\npath escapes repo root.\n"
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        return f"# Error\nfailed to read `{rel}`: {exc}\n"


def _augment_with_wizard_state(
    result: Dict[str, Any],
    tool_name: str,
    wizard_state_json: Optional[Dict[str, Any]] = None,
    *,
    run_adapters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Augment a tool result with updated wizard state if provided.

    If ``wizard_state_json`` is provided, updates the wizard state based on
    the tool result and includes the updated state in the response.

    For ``ainl_run``, pass ``run_adapters`` so the state machine can verify
    ``adapters_configured`` against ``pending_mcp_adapters`` from the last compile.
    """
    if wizard_state_json is None:
        return result
    try:
        proof = dict(result)
        if tool_name == "ainl_run" and run_adapters is not None:
            proof["_wizard_ainl_run_adapters"] = run_adapters
        state = WizardState.from_dict(wizard_state_json)
        state = wizard_state_from_tool_result(state, tool_name, proof)
        result["wizard_state_json"] = state.to_dict()
        result["wizard_stage"] = state.stage.value
        result["wizard_checkpoints_complete"] = [
            k for k, v in state.checkpoints.items()
            if v.status.value == "complete"
        ]
        result["wizard_blocking_checkpoints"] = state.blocking_checkpoints
    except Exception as exc:
        if env_truthy(os.environ.get("AINL_MCP_WIZARD_DEBUG")):
            _logger.warning("wizard_state augmentation failed for %s: %s", tool_name, exc)
    return result


# Catalog entries for ainl_capabilities (filtered by current MCP resource exposure).
_MCP_INTEGRATION_RESOURCE_CATALOG: List[Dict[str, str]] = [
    {
        "uri": "ainl://integrations-hub",
        "title": "Integrations hub",
        "summary": "Index of integrations docs (HTTP machine payments, A2A, AGTP, readiness).",
    },
    {
        "uri": "ainl://integrations-http-machine-payments",
        "title": "HTTP machine payments (x402 / MPP)",
        "summary": "payment_profile, 402 handling, http_payment frame merges, settlement metadata.",
    },
    {
        "uri": "ainl://integrations-agentic-protocols-readiness",
        "title": "Agentic protocols — practitioner readiness",
        "summary": "Operator checklist and cross-links for agentic HTTP payment flows.",
    },
    {
        "uri": "ainl://integrations-agtp",
        "title": "AGTP (Agentic Gateway Transport Protocol)",
        "summary": "AGTP overview and how it relates to AINL HTTP integration.",
    },
    {
        "uri": "ainl://integrations-a2a",
        "title": "A2A adapter",
        "summary": "Agent-to-Agent adapter threat model, wire profile, and security reporting.",
    },
    {
        "uri": "ainl://examples-http-machine-payment-flow",
        "title": "Example: HTTP machine payment flow (strict-valid)",
        "summary": "Opcode graph for 402/payment_required + frame.http_payment; run python scripts/run_http_machine_payment_roundtrip_demo.py for a local stdlib round-trip.",
    },
    {
        "uri": "ainl://strict-authoring-cheatsheet",
        "title": "Strict AINL authoring cheatsheet",
        "summary": "Strict-mode syntax, MCP code= contract, validate/compile/run chain, no inline dict/J-object pitfalls.",
    },
    {
        "uri": "ainl://strict-valid-examples",
        "title": "Strict-valid example index",
        "summary": "JSON list of repo paths from tooling/artifact_profiles.json strict-valid; safe templates for --strict CI.",
    },
    {
        "uri": "ainl://strict-valid-families",
        "title": "Strict-valid family index (mined)",
        "summary": "JSON from corpus/strict_valid_family_index.json — adapter families, by_adapter paths, generated via tooling/corpus_mining.py.",
    },
    {
        "uri": "ainl://adapter-contracts",
        "title": "Adapter contracts bundle",
        "summary": "JSON bundle of deterministic ainl_adapter_contract payloads (http, fs, browser, …).",
    },
]

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
    "ainl_get_started",
    "ainl_step_examples",
    "ainl_wizard_checkpoint",
    "ainl_adapter_contract",
    "ainl_validate",
    "ainl_compile",
    "ainl_emit_grammar_gbnf",
    "ainl_emit_grammar_jsonschema",
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
    "ainl_mission_plan",
    "ainl_mission_validate",
    "ainl_handoff_lint",
    "ainl_estimate",
]
ALL_RESOURCE_URIS: List[str] = [
    "ainl://adapter-manifest",
    "ainl://security-profiles",
    "ainl://authoring-cheatsheet",
    "ainl://strict-authoring-cheatsheet",
    "ainl://strict-valid-examples",
    "ainl://strict-valid-families",
    "ainl://adapter-contracts",
    "ainl://impact-checklist",
    "ainl://adapter-risk-matrix",
    "ainl://run-readiness",
    "ainl://policy-contract",
    "ainl://integrations-hub",
    "ainl://integrations-http-machine-payments",
    "ainl://integrations-agentic-protocols-readiness",
    "ainl://integrations-agtp",
    "ainl://integrations-a2a",
    "ainl://examples-http-machine-payment-flow",
    "ainl://mission-authoring-cheatsheet",
    "ainl://strict-valid-missions",
    "ainl://mission-worker-examples",
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

## HTTP machine payments (x402 / MPP)

- Full contract + examples: MCP resource **`ainl://integrations-http-machine-payments`** (also `docs/integrations/HTTP_MACHINE_PAYMENTS.md`).
- **`ainl_run`** → `adapters.http`: optional **`payment_profile`** (`none`, `auto`, `mpp`, `x402`) and **`max_payment_rounds`** (int, default 2). On **402** / payment-required flows, merge retry material from the prior result into **`frame.http_payment`** (see hub doc).
- Readiness / vocabulary: **`ainl://integrations-agentic-protocols-readiness`**, **`ainl://integrations-agtp`**, hub **`ainl://integrations-hub`**.
- Strict-valid graph template: **`ainl://examples-http-machine-payment-flow`** (opcode `http.GET` + `payment_required` branch + `http_payment` frame); local demo: **`python scripts/run_http_machine_payment_roundtrip_demo.py`**.
"""

_STRICT_AUTHORING_CHEATSHEET_MARKDOWN: str = """# Strict AINL authoring (MCP)

**Scope:** patterns that pass **`ainl_validate(..., strict=true)`** and match CI **`strict-valid`** examples in `tooling/artifact_profiles.json`. This is **not** the same as “will run on every host”: MCP **`ainl_run`** still needs per-run **`adapters`** for `http`, `fs`, `cache`, `sqlite`, etc.

## Golden path (agents)

1. **`ainl_get_started`** with a plain-language goal; finish **`missing_checkpoints`** before adapter-heavy lines.
2. **`ainl_capabilities`** → real verb names; do **not** invent verbs from memory or random repo files.
3. **`ainl_adapter_contract`** for each non-`core` adapter you will call.
4. **`ainl_validate`** (`strict=true`) after **each** small edit; **`ainl_compile`** before **`ainl_run`** when you need `frame_hints` / IR checks.
5. **`ainl_run`** with **`adapters`** matching `required_adapters` / `runtime_readiness` from validate/compile.

## MCP tool contract (critical)

- Pass the **full `.ainl` / `.lang` source text** in the **`code`** argument (string). Legacy alias **`ainl`** is accepted.
- **Do not** pass only a filesystem path unless your host also reads the file into `code` for you.

## Compact syntax starter (strict-valid shape)

```ainl
workflow:
  result = core.ADD 2 3
  out result
```

## HTTP (`R http.*` / compact `http.*`)

- **GET** positional args only: URL, optional headers dict, optional timeout seconds. Put query params **in the URL**.
- **POST**: URL, body variable (dict built in **`frame`** or via **`core`**, never inline `{...}` on the `R` line).
- Wrong: `params=`, `timeout=` as fake named tokens on the `R` line.

Example (strict-safe):

```ainl
fetch:
  res = http.GET "https://example.com/api?x=1" {} 15
  out res
```

## Strict bans (common agent mistakes)

- **No** inline JSON/object/map literals as operands to **`J`**, **`Set`**, or **`out`** in strict mode — use variables, **`frame`**, **`core.PARSE`**, **`core.STRINGIFY`**, **`core.MERGE`** (variables only).
- **No** invented **`core.FORMAT`** / formatting verbs — use **`core.CONCAT`**, **`core.STR`**, **`core.STRINGIFY`**.
- **`core.GET`** is **`core.GET container key`** (object first, key second).

## Where to copy templates from

- MCP resource **`ainl://strict-valid-examples`** — JSON index of **`strict-valid`** repo paths.
- Opcode HTTP payment template: **`ainl://examples-http-machine-payment-flow`**.
- Full adapter verb lists + `strict_contract` flags: **`ainl://adapter-manifest`** and **`ainl_capabilities.strict_summary`**.
- Deterministic adapter semantics bundle: **`ainl://adapter-contracts`**.
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
| `http` / `web` | Network egress; use host allowlists (`ainl_capabilities` + grants). Paid / **402** flows: see `ainl://integrations-http-machine-payments`. |
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


_ADAPTER_CONTRACT_BUNDLE_KEYS: Tuple[str, ...] = (
    "http",
    "browser",
    "fs",
    "cache",
    "pggraph",
    "llm",
    "core",
    "http_or_browser",
    "provider_or_http",
    "state_or_database",
)


def _strict_valid_examples_json() -> str:
    """JSON index of CI strict-valid example paths (artifact_profiles.json)."""
    profiles = load_artifact_profiles(_REPO_ROOT)
    paths = sorted(profiles.get("strict-valid", set()))
    payload: Dict[str, Any] = {
        "schema_version": "1.0",
        "profile": "strict-valid",
        "count": len(paths),
        "paths": paths,
        "note": (
            "These paths are the repo contract for `ainl validate --strict` in CI. "
            "Read file contents into MCP `code=` (full source string), not just the path."
        ),
        "snippet_resources": ["ainl://examples-http-machine-payment-flow"],
    }
    return json.dumps(payload, indent=2)


def _adapter_contracts_bundle_json() -> str:
    """Deterministic JSON bundle of adapter_contract payloads for MCP resources/read."""
    from tooling.ainl_get_started import ADAPTER_CONTRACTS

    bundle = {name: ainl_adapter_contract_payload(name) for name in _ADAPTER_CONTRACT_BUNDLE_KEYS}
    for host_key in (
        "mission_dispatch",
        "mission_handoff_record",
        "mission_assertion_check",
        "git_snapshot",
        "git_rollback",
        "ask_user",
    ):
        if host_key in ADAPTER_CONTRACTS:
            bundle[host_key] = ADAPTER_CONTRACTS[host_key]
    return json.dumps(bundle, indent=2)


def _strict_summary_from_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Compact strict-relevant view of adapter_manifest.json for agents."""
    adapters = manifest.get("adapters") or {}
    per_adapter: Dict[str, Any] = {}
    strict_valid_verbs: Dict[str, List[str]] = {}
    for name, info in adapters.items():
        if not isinstance(info, dict):
            continue
        verbs = info.get("verbs") or []
        verb_list = [str(v) for v in verbs] if isinstance(verbs, list) else []
        st = bool(info.get("strict_contract"))
        entry: Dict[str, Any] = {
            "strict_contract": st,
            "support_tier": info.get("support_tier"),
            "verb_count": len(verb_list),
        }
        if len(verb_list) <= 48:
            entry["verbs"] = verb_list
        if st and verb_list:
            strict_valid_verbs[name] = verb_list if len(verb_list) <= 120 else verb_list[:120] + ["…truncated"]
        per_adapter[name] = entry
    return {
        "schema_version": "1.0",
        "note": (
            "`strict_contract` reflects compiler catalog alignment; some verbs may still be "
            "unsupported at Python runtime — verify with `ainl_capabilities` + `ainl_validate --strict`."
        ),
        "adapters": per_adapter,
        "strict_valid_verbs": strict_valid_verbs,
    }


def _repair_recipe_from_failure(
    primary: Optional[Dict[str, Any]],
    failure_tags: Set[str],
) -> Dict[str, Any]:
    """Deterministic repair hints keyed off diagnostics (no auto-rewrite)."""
    recipe: Dict[str, Any] = {
        "resources": ["ainl://strict-authoring-cheatsheet"],
        "recommended_tools": ["ainl_get_started", "ainl_validate"],
        "steps": [],
    }
    if primary and isinstance(primary, dict):
        sfx = primary.get("suggested_fix")
        if sfx:
            recipe["steps"].append(str(sfx))
        kind = str(primary.get("kind") or "")
        msg_l = str(primary.get("message") or "").lower()
        if kind == "strict_validation_failure" or "inline" in msg_l and "literal" in msg_l:
            recipe["steps"].append(
                "For structured data, pass dicts via `ainl_run` `frame`, or build text with "
                "`core.STRINGIFY` / `core.PARSE` / variables — not `{...}` tokens on `R`/`J`/`out` lines."
            )
        if "unknown adapter" in msg_l or "unknown verb" in msg_l or "does not exist on adapter" in msg_l:
            recipe["recommended_tools"] = ["ainl_capabilities", "ainl_adapter_contract", "ainl_validate"]
        if "http" in msg_l and any(
            x in msg_l for x in ("params", "timeout", "named argument", "dict literal", "tokenize")
        ):
            recipe["resources"].append("ainl://authoring-cheatsheet")
    if "adapter_or_verb" in failure_tags:
        recipe["recommended_tools"] = ["ainl_capabilities", "ainl_adapter_contract", "ainl_validate"]
        recipe["steps"].append(
            "Do not remove non-core adapter lines just to get `ok: true` unless the user relaxes the workflow; "
            "fix verb names against `ainl_capabilities` / `ainl_adapter_contract` and use `adapters=` on `ainl_run`."
        )
    if "http_or_rline" in failure_tags:
        recipe["resources"].append("ainl://authoring-cheatsheet")
    recipe["resources"] = list(dict.fromkeys(recipe["resources"]))
    recipe["recommended_tools"] = list(dict.fromkeys(recipe["recommended_tools"]))
    recipe["resources"] = [u for u in recipe["resources"] if u in _ALLOWED_RESOURCES]
    recipe["recommended_tools"] = [t for t in recipe["recommended_tools"] if t in _ALLOWED_TOOLS]
    return recipe


def _missing_source_tool_error(tool: str) -> Dict[str, Any]:
    """Standard payload when MCP tools are called without `code` / `ainl` source text."""
    out_ms: Dict[str, Any] = {
        "ok": False,
        "errors": ["missing required argument: code"],
        "tool_call_error": True,
        "why_this_matters": (
            "This failure is a host/tool wiring issue: no AINL source was passed, so nothing was compiled."
        ),
        "next_step": (
            f"Read the target `.ainl` / `.lang` file (or your editor buffer) and pass the **full source** "
            f"into `{tool}(code=...)` as a string, **or** pass `path` to a UTF-8 workflow file (absolute or "
            "relative to the process cwd, or under `AINL_MCP_WORKFLOW_ROOT` when set). Legacy alias `ainl=` "
            "is accepted for inline source."
        ),
        "copy_paste_next_call": {
            "tool": tool,
            "args": {"path": "/absolute/path/to/workflow.ainl", "strict": True},
        },
        "recommended_resources": [u for u in ("ainl://strict-authoring-cheatsheet",) if u in _ALLOWED_RESOURCES],
        "recommended_next_tools": [t for t in ("ainl_get_started", tool) if t in _ALLOWED_TOOLS],
    }
    _attach_policy_contract_hints(out_ms)
    return out_ms


def _classify_source_arg(code: Optional[str], ainl: Optional[str]) -> str:
    """Return why a source argument is unusable, or ``"ok"`` if usable.

    - ``"missing_arg"`` — neither ``code`` nor ``ainl`` was provided (or both are non-strings).
    - ``"empty"`` — at least one was provided but contains only whitespace (e.g. a 0-byte file
      whose contents the host read into ``code=""``). This is the case where the agent should
      stop retrying ``ainl_compile`` and either ask the user or scaffold via ``ainl_get_started``.
    - ``"ok"`` — at least one argument has non-whitespace content.
    """
    has_string = False
    for raw in (code, ainl):
        if isinstance(raw, str):
            has_string = True
            if raw.strip():
                return "ok"
    return "empty" if has_string else "missing_arg"


_EMPTY_SOURCE_SCAFFOLD = (
    "S app core noop\n\nL_main:\n  R core.NOW ->ts\n  J ts\n"
)


def _empty_source_tool_error(tool: str) -> Dict[str, Any]:
    """Payload when ``code`` / ``ainl`` is present but empty / whitespace-only.

    Distinct from ``_missing_source_tool_error``: the host *did* read the file (or send the
    string), but it had no content. Common cause: a 0-byte ``.ainl`` workflow that was never
    populated (or truncated). The right repair is to stop retrying ``ainl_compile`` with the
    same empty buffer and either scaffold via ``ainl_get_started`` or ask the user.
    """
    out_es: Dict[str, Any] = {
        "ok": False,
        "errors": ["empty AINL source"],
        "error_kind": "empty_source",
        "tool_call_error": False,
        "why_this_matters": (
            "The source you passed is empty (0 non-whitespace characters). The compiler has nothing to "
            "validate, compile, or run. Retrying with the same empty buffer will keep failing — fix the "
            "source first."
        ),
        "next_step": (
            f"Stop calling `{tool}` with this buffer. Most likely the target `.ainl` file is 0 bytes (check "
            "with `file_read` / `stat`). Either scaffold a strict-valid graph for the user's goal via "
            "`ainl_get_started`, or ask the user what the workflow should do before writing any source."
        ),
        "minimal_strict_valid_example": _EMPTY_SOURCE_SCAFFOLD,
        "copy_paste_next_call": {
            "tool": "ainl_get_started",
            "args": {"goal": "<plain-language description of what this workflow should do>"},
        },
        "repair_recipe": {
            "resources": [
                u
                for u in ("ainl://strict-authoring-cheatsheet", "ainl://strict-valid-examples")
                if u in _ALLOWED_RESOURCES
            ],
            "recommended_tools": [
                t for t in ("ainl_get_started", "ainl_step_examples", "ainl_validate") if t in _ALLOWED_TOOLS
            ],
            "steps": [
                "Confirm the target file is empty (use `file_read` / `stat`); if so, surface that to the user instead of retrying.",
                "Call `ainl_get_started` with the user's goal in plain language to scaffold a strict-valid graph.",
                "Validate the scaffolded source with `ainl_validate(code=..., strict=True)` before writing it back.",
            ],
        },
        "recommended_resources": [
            u
            for u in ("ainl://strict-authoring-cheatsheet", "ainl://strict-valid-examples")
            if u in _ALLOWED_RESOURCES
        ],
        "recommended_next_tools": [
            t for t in ("ainl_get_started", "ainl_step_examples") if t in _ALLOWED_TOOLS
        ],
    }
    _attach_policy_contract_hints(out_es)
    return out_es


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
_COMPILE_CACHE_LOCK = threading.Lock()
_COMPILE_CACHE: "OrderedDict[tuple[str, bool, str], Dict[str, Any]]" = OrderedDict()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compile_cache_max_entries() -> int:
    raw = os.environ.get("AINL_MCP_COMPILE_CACHE_MAX_ENTRIES") or os.environ.get(
        "ARMARA_AINL_CACHE_MAX_ENTRIES"
    )
    try:
        return max(0, int(raw)) if raw is not None else 256
    except (TypeError, ValueError):
        return 256


def _compile_cache_version() -> str:
    return (
        os.environ.get("AINL_MCP_COMPILER_VERSION")
        or os.environ.get("ARMARA_AINL_COMPILER_VERSION")
        or RUNTIME_VERSION
    )


def _compile_cache_key(code: str, strict: bool) -> tuple[str, bool, str]:
    return (_sha256_text(code), bool(strict), _compile_cache_version())


def _compile_cache_get(code: str, strict: bool) -> Optional[Dict[str, Any]]:
    if _compile_cache_max_entries() <= 0:
        return None
    key = _compile_cache_key(code, strict)
    with _COMPILE_CACHE_LOCK:
        cached = _COMPILE_CACHE.get(key)
        if cached is None:
            return None
        _COMPILE_CACHE.move_to_end(key)
        with _TELEM_LOCK:
            _MCP_TELEM["compile_cache_hits"] = _MCP_TELEM.get("compile_cache_hits", 0) + 1
        return copy.deepcopy(cached)


def _compile_cache_put(code: str, strict: bool, ir: Dict[str, Any]) -> None:
    max_entries = _compile_cache_max_entries()
    if max_entries <= 0:
        return
    key = _compile_cache_key(code, strict)
    with _COMPILE_CACHE_LOCK:
        _COMPILE_CACHE[key] = copy.deepcopy(ir)
        _COMPILE_CACHE.move_to_end(key)
        while len(_COMPILE_CACHE) > max_entries:
            _COMPILE_CACHE.popitem(last=False)


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


def _attach_strict_mode_annotation(out: Dict[str, Any], strict: bool) -> None:
    """Make non-strict validate/compile/run responses explicit (roadmap: B4c / Track 2.1)."""
    out["strict"] = bool(strict)
    if not strict:
        out["strict_mode_note"] = (
            "This call used `strict=false`. The compiler used the non-strict path; that is **not** the same as "
            "CI `ainl validate --strict` or `strict-valid` in `tooling/artifact_profiles.json`. "
            "Re-run with `strict=true` (the default) before claiming strict alignment."
        )


def _annotate_run_return(out: Dict[str, Any], strict: bool) -> Dict[str, Any]:
    _attach_strict_mode_annotation(out, strict)
    return out


def _runtime_error_agent_repair_steps(
    err: "AinlRuntimeError",
    *,
    resolved_path: Optional[str],
    merged_limits: Dict[str, Any],
) -> List[str]:
    """Actionable host hints when ``ainl_run`` fails at runtime (not compile time)."""
    steps: List[str] = []
    code = getattr(err, "code", None) or ""
    if code == "RUNTIME_MAX_ADAPTER_CALLS" or "max_adapter_calls" in str(err).lower():
        lim = merged_limits.get("max_adapter_calls")
        steps.extend(
            [
                "Split the input into smaller batches (≈10–15 records per `ainl_run`) so each graph stays under the adapter-call budget.",
                f"Pass `limits: {{\"max_adapter_calls\": N}}` on this call (server ceiling applies; current merged limit: {lim!r}).",
                "For workspace-scale jobs, prefer CLI `ainl run <file.ainl>` or a Python/shell script via `script_run` — no MCP per-run adapter cap.",
            ]
        )
        if resolved_path:
            steps.append(
                f"Re-run with `path: {resolved_path!r}` after validate on the same path (no inline code drift)."
            )
        ws_hint = (
            "Place `ainl_mcp_limits.json` in the workspace fs root (see adapters.fs.root) "
            "to raise limits for that folder."
        )
        steps.append(ws_hint)
    if "inline" in str(err).lower() or "could not convert string to float" in str(err).lower():
        steps.append(
            "Do not use inline `{...}` dict literals on `R` lines — pass dicts via `frame` or build with variables + `core.MERGE`."
        )
    return steps


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
        strict_sheet = "ainl://strict-authoring-cheatsheet"
        contracts = "ainl://adapter-contracts"
        if adapter and not http:
            tools = ["ainl_capabilities", "ainl_validate", "ainl_compile"]
            resources = [strict_sheet, contracts]
        elif http and not adapter:
            tools = ["ainl_validate"]
            resources = [strict_sheet, "ainl://authoring-cheatsheet"]
        elif adapter and http:
            tools = ["ainl_capabilities", "ainl_validate"]
            resources = [strict_sheet, "ainl://authoring-cheatsheet"]
        else:
            tools = ["ainl_validate", "ainl_capabilities"]
            resources = [strict_sheet, "ainl://authoring-cheatsheet"]
    elif kind == "compile_ok":
        if if_:
            tools = ["ainl_ir_diff", "ainl_run", "ainl_validate", "ainl_security_report"]
        else:
            tools = ["ainl_run", "ainl_security_report", "ainl_validate"]
        # When the IR needs runtime adapters, surface capability/contract discovery next to
        # `ainl_run` so hosts can build a correct `adapters=` payload (Track 2 / 3 of phase2 roadmap).
        if (out.get("required_adapters") or []) and "ainl_capabilities" in _ALLOWED_TOOLS:
            if if_:
                tools = [
                    "ainl_ir_diff",
                    "ainl_run",
                    "ainl_capabilities",
                    "ainl_security_report",
                    "ainl_validate",
                ]
            else:
                tools = [
                    "ainl_run",
                    "ainl_capabilities",
                    "ainl_security_report",
                    "ainl_validate",
                ]
    else:
        return
    tools_f = [t for t in tools if t in _ALLOWED_TOOLS]
    res_f = [r for r in dict.fromkeys(resources) if r in _ALLOWED_RESOURCES]
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
            "Call ainl_get_started before writing unfamiliar adapter-heavy AINL. "
            "Thread wizard_state_json from each response into ainl_validate, ainl_compile, ainl_capabilities, "
            "ainl_adapter_contract, and ainl_run so checkpoints advance; use ainl_wizard_checkpoint for attestations "
            "such as strict_examples_reviewed after reading ainl://strict-valid-examples without another tool proof. "
            "Pass full program text in validate/compile/run `code` (string); legacy `ainl` alias is accepted. "
            "MCP resource ainl://strict-authoring-cheatsheet is the strict-mode syntax contract; "
            "ainl://authoring-cheatsheet adds HTTP machine-payment / R-line integration notes; "
            "ainl://strict-valid-examples lists CI strict-valid template paths; "
            "ainl://adapter-contracts is a JSON bundle of adapter semantics. "
            "ainl://integrations-* resources ship docs/integrations (machine payments, AGTP, A2A). "
            "validate/compile ok means compiler success — check required_adapters/runtime_readiness before assuming ainl_run works without adapters=. "
            "validate/compile responses include recommended_next_tools and repair_recipe on failures. "
            "ainl_capabilities returns strict_summary, mcp_telemetry (call counters), and mcp_resources (integration URIs)."
        ),
    )




def _load_config_from_path(config_path: str) -> dict:
    """Load YAML config from path and expand environment variables."""
    from tooling.config_loader import load_yaml_config

    return load_yaml_config(config_path)


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
    cached = _compile_cache_get(code, strict)
    if cached is not None:
        return cached
    compiler = AICodeCompiler(strict_mode=strict)
    ctx = CompilerContext()
    try:
        ir = compiler.compile(code, context=ctx)
    except CompilationDiagnosticError as e:
        ir = _ir_from_compilation_diagnostic_error(e)
    _compile_cache_put(code, strict, ir)
    return copy.deepcopy(ir)


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
            "strict_contract": info.get("strict_contract"),
            "effect_default": info.get("effect_default"),
            "recommended_lane": info.get("recommended_lane"),
            "privilege_tier": info.get("privilege_tier"),
            "destructive": info.get("destructive"),
            "network_facing": info.get("network_facing"),
            "sandbox_safe": info.get("sandbox_safe"),
        }
    catalog = [
        dict(entry)
        for entry in _MCP_INTEGRATION_RESOURCE_CATALOG
        if entry.get("uri") in _ALLOWED_RESOURCES
    ]
    return {
        "schema_version": "1.1",
        "runtime_version": RUNTIME_VERSION,
        "policy_support": True,
        "adapters": adapters,
        "strict_summary": _strict_summary_from_manifest(manifest),
        "mcp_telemetry": _telemetry_snapshot(),
        "mcp_resources": catalog,
    }


_MCP_CONFIGURABLE_ADAPTERS: Set[str] = {"http", "fs", "cache", "sqlite", "pggraph", "a2a"}


def _required_adapters_from_ir(ir: Dict[str, Any]) -> List[str]:
    """Return sorted non-core adapters required by compiled IR."""
    reqs = (ir.get("execution_requirements") or {}).get("required_capabilities") or []
    found: Set[str] = {str(x).strip().lower() for x in reqs if str(x).strip()}
    avm = (ir.get("avm_policy_fragment") or {}).get("allowed_adapters") or []
    found.update(str(x).strip().lower() for x in avm if str(x).strip())
    found.discard("core")
    return sorted(found)


def _http_hosts_from_ir(ir: Dict[str, Any]) -> List[str]:
    hosts: Set[str] = set()
    for body in (ir.get("labels") or {}).values():
        if not isinstance(body, dict):
            continue
        for node in body.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            data = node.get("data") or {}
            adapter = str(data.get("adapter") or "").lower()
            if not adapter.startswith("http."):
                continue
            target = str(data.get("target") or "")
            parsed = urlparse(target)
            if parsed.hostname:
                hosts.add(parsed.hostname)
    return sorted(hosts)


def _suggested_adapters_payload(required: List[str], ir: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a copyable per-run adapters payload for adapters MCP can configure."""
    enable = [a for a in required if a in _MCP_CONFIGURABLE_ADAPTERS]
    payload: Dict[str, Any] = {"enable": enable}
    for adapter in enable:
        if adapter == "http":
            hosts = _http_hosts_from_ir(ir or {}) or ["<host>"]
            payload["http"] = {
                "allow_hosts": hosts,
                "timeout_s": 15.0,
                "payment_profile": "none",
            }
        elif adapter == "fs":
            payload["fs"] = {
                "root": "<absolute-workspace-or-output-root>",
                "allow_extensions": [".json", ".jsonl", ".csv", ".txt"],
            }
        elif adapter == "cache":
            payload["cache"] = {"path": "<absolute-cache-json-path>"}
        elif adapter == "sqlite":
            payload["sqlite"] = {"db_path": "<absolute-sqlite-db-path>", "allow_write": False}
        elif adapter == "pggraph":
            payload["pggraph"] = {
                "url": "<postgresql-dsn-or-set-AINL_POSTGRES_URL>",
                "max_depth": 10,
                "max_rows": 1000,
                "default_schema": "public",
                "allow_admin": False,
            }
        elif adapter == "a2a":
            payload["a2a"] = {"allow_hosts": ["<agent-host>"], "timeout_s": 30.0}
    return payload


def _runtime_readiness_from_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    required = _required_adapters_from_ir(ir)
    configurable = [a for a in required if a in _MCP_CONFIGURABLE_ADAPTERS]
    unknown = [a for a in required if a not in _MCP_CONFIGURABLE_ADAPTERS and a not in {"llm"}]
    env_required = [a for a in required if a in {"llm"}]
    ready = not required
    out: Dict[str, Any] = {
        "ready": ready,
        "reason": (
            "core-only workflow; no per-run adapter registration required"
            if ready
            else "AINL source is valid, but ainl_run needs adapter registration/configuration for this host."
        ),
        "required_adapters": required,
        "missing_adapters": required,
        "mcp_configurable_adapters": configurable,
        "env_config_required": env_required,
        "unknown_or_external_adapters": unknown,
    }
    if configurable:
        out["suggested_adapters"] = _suggested_adapters_payload(configurable, ir)
    if unknown:
        out["next_step"] = (
            "Call ainl_adapter_contract for unknown/external adapters and inspect local gateway/OpenAPI docs before running."
        )
    return out


# Lightweight contract check (Track 1.2): compare IR `R` lines to `tooling/ainl_get_started` ADAPTER_CONTRACTS.
_CONTRACT_CHECK_ADAPTERS: Set[str] = {
    "http",
    "fs",
    "cache",
    "browser",
    "queue",
    "memory",
    "pggraph",
}


class ContractValidationStatus:
    """Explicit contract verification statuses for validate/compile responses."""

    SYNTAX_VALID_CONTRACT_VERIFIED = "syntax_valid_contract_verified"
    SYNTAX_VALID_CONTRACT_UNKNOWN = "syntax_valid_contract_unknown"
    SYNTAX_VALID_CONTRACT_MISMATCH = "syntax_valid_contract_mismatch"


def _determine_contract_validation_status(
    ir: Dict[str, Any],
    contract_items: List[Dict[str, Any]],
) -> Tuple[str, List[str], List[str]]:
    """Determine the contract validation status from IR analysis.

    Returns:
        (status, verified_adapters, unknown_adapters)
    """
    from tooling.ainl_get_started import ADAPTER_CONTRACTS

    adapters_used: Set[str] = set()
    for _lbl, body in (ir.get("labels") or {}).items():
        if not isinstance(body, dict):
            continue
        for node in body.get("nodes") or []:
            if not isinstance(node, dict) or node.get("op") != "R":
                continue
            data = node.get("data")
            if not isinstance(data, dict):
                continue
            src = _r_node_adapter_src(data)
            if src and src != "core":
                adapters_used.add(src)

    verified = [a for a in adapters_used if a in ADAPTER_CONTRACTS]
    unknown = [a for a in adapters_used if a not in ADAPTER_CONTRACTS and a not in _CONTRACT_CHECK_ADAPTERS]

    if contract_items:
        return ContractValidationStatus.SYNTAX_VALID_CONTRACT_MISMATCH, verified, unknown
    elif unknown:
        return ContractValidationStatus.SYNTAX_VALID_CONTRACT_UNKNOWN, verified, unknown
    else:
        return ContractValidationStatus.SYNTAX_VALID_CONTRACT_VERIFIED, verified, unknown


def _r_node_adapter_src(data: Dict[str, Any]) -> str:
    s = str(data.get("src") or "").strip().lower()
    if s:
        return s
    ad = str(data.get("adapter") or "")
    if "." in ad:
        return ad.split(".", 1)[0].strip().lower()
    return s


def _r_node_verb_token(data: Dict[str, Any], src: str) -> str:
    ad_full = str(data.get("adapter") or "")
    if "." in ad_full:
        tail = ad_full.split(".", 1)[1]
    else:
        tail = ""
    ro = str(data.get("req_op") or "")
    if src == "http":
        v = (ro or tail or "").upper()
        return v
    return (ro or tail or "").lower()


def _contract_verb_in_get_started_contract(adapter: str, verb: str) -> bool:
    from tooling.ainl_get_started import ADAPTER_CONTRACTS

    c = ADAPTER_CONTRACTS.get(adapter)
    if not c:
        return True
    verbs = c.get("verbs") or {}
    if not verbs:
        return True
    if adapter == "http":
        u = verb.upper()
        return any(str(k).upper() == u for k in verbs)
    u = verb.lower()
    return any(str(k).lower() == u for k in verbs)


def _contract_alignment_hints_from_ir(ir: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Return (warning strings, structured items) when an http/fs verb is not in the get_started contract.

    Warnings are non-fatal: compiler/strict may still be ok; the graph may use a newer runtime verb.
    """
    warns: List[str] = []
    items: List[Dict[str, Any]] = []
    for _lbl, body in (ir.get("labels") or {}).items():
        if not isinstance(body, dict):
            continue
        for node in body.get("nodes") or []:
            if not isinstance(node, dict) or node.get("op") != "R":
                continue
            data = node.get("data")
            if not isinstance(data, dict) or str(data.get("op") or "") != "R":
                continue
            src = _r_node_adapter_src(data)
            if src not in _CONTRACT_CHECK_ADAPTERS:
                continue
            verb = _r_node_verb_token(data, src)
            if not verb:
                continue
            if _contract_verb_in_get_started_contract(src, verb):
                continue
            ln = 0
            try:
                ln = int(data.get("lineno") or 0)
            except (TypeError, ValueError):
                ln = 0
            code = f"CONTRACT_VERB_NOT_IN_AINL_GET_STARTED:{src}.{verb}"
            items.append(
                {
                    "kind": "contract_verb_mismatch",
                    "adapter": src,
                    "verb": verb,
                    "line": ln,
                    "code": code,
                }
            )
            warns.append(
                f"{code} (line {ln or '?'}) — not listed under `ainl_adapter_contract({src!r})` / "
                f"`ADAPTER_CONTRACTS` in `tooling/ainl_get_started.py`. This is a **warning** only; "
                f"see `ainl_capabilities` and MCP resource `ainl://adapter-contracts`."
            )
    return warns, items


def _merge_contract_alignment_into_output(out: Dict[str, Any], ir: Dict[str, Any], *, ok_graph: bool) -> None:
    if not ok_graph:
        return
    w, items = _contract_alignment_hints_from_ir(ir)
    status, verified, unknown = _determine_contract_validation_status(ir, items)

    out["contract_validation_status"] = status

    if w:
        ow = [str(x) for x in (out.get("warnings") or []) if isinstance(x, str)]
        out["warnings"] = ow + w

    out["contract_alignment"] = {
        "schema_version": "1.1.0",
        "status": status,
        "severity": "warning" if items else "info",
        "verified_adapters": verified,
        "unknown_adapters": unknown,
        "adapters_checked": sorted(_CONTRACT_CHECK_ADAPTERS),
        "mismatched_calls": items,
        "source_of_truth": (
            "Authoritative full verb sets: `tooling/adapter_manifest.json` (strict_summary, ainl_capabilities) "
            "and runtime adapters; this check uses `ADAPTER_CONTRACTS` in `tooling/ainl_get_started.py` (MCP contract bundle)."
        ),
    }


def _attach_runtime_readiness(out: Dict[str, Any], ir: Dict[str, Any]) -> None:
    required = _required_adapters_from_ir(ir)
    out["required_adapters"] = required
    out["runtime_readiness"] = _runtime_readiness_from_ir(ir)


def _missing_adapter_from_error_text(text: str) -> Optional[str]:
    m = re.search(r"adapter not registered:\s*([A-Za-z0-9_\-.]+)", text)
    if not m:
        return None
    return m.group(1).split(".", 1)[0].lower()


def _pggraph_adapter_from_mcp_config(g: Dict[str, Any]) -> RuntimeAdapter:
    """Build :class:`PggraphAdapter` from ``adapters.pggraph`` MCP config (+ postgres env fallbacks)."""
    from adapters.pggraph import PggraphAdapter
    from adapters.postgres import PostgresAdapter
    from runtime.adapters.base import AdapterError

    url = (g.get("url") or g.get("postgres_url") or os.environ.get("AINL_POSTGRES_URL") or "").strip() or None
    host = (g.get("host") or os.environ.get("AINL_POSTGRES_HOST") or "").strip() or None
    if not url and not host:
        raise AdapterError(
            "pggraph adapter requires adapters.pggraph.url or host "
            "(or set AINL_POSTGRES_URL / AINL_POSTGRES_HOST)"
        )
    postgres = PostgresAdapter(
        dsn=url,
        host=host,
        port=int(g.get("port") or os.environ.get("AINL_POSTGRES_PORT") or 5432),
        database=(g.get("database") or g.get("dbname") or os.environ.get("AINL_POSTGRES_DB") or "").strip() or None,
        user=(g.get("user") or os.environ.get("AINL_POSTGRES_USER") or "").strip() or None,
        password=g.get("password") if "password" in g else os.environ.get("AINL_POSTGRES_PASSWORD"),
        sslmode=(g.get("sslmode") or os.environ.get("AINL_POSTGRES_SSLMODE") or "require"),
        sslrootcert=(g.get("sslrootcert") or os.environ.get("AINL_POSTGRES_SSLROOTCERT") or "").strip() or None,
        timeout_s=float(g.get("timeout_s", 5.0)),
        statement_timeout_ms=int(g.get("statement_timeout_ms", 5000)),
        allow_write=False,
        pool_min_size=int(g.get("pool_min", 1)),
        pool_max_size=int(g.get("pool_max", 5)),
    )
    return PggraphAdapter(
        postgres,
        max_depth=g.get("max_depth"),
        max_rows=g.get("max_rows"),
        default_schema=str(g.get("default_schema") or "public"),
        allow_admin=bool(g.get("allow_admin")),
    )


def _mcp_configurable_adapters_missing_from_registry(reg: "AdapterRegistry", ir: Dict[str, Any]) -> List[str]:
    """IR-required adapters that must be registered in MCP (http/fs/cache/sqlite/pggraph/a2a) but are absent from ``reg``."""
    missing: List[str] = []
    for name in _required_adapters_from_ir(ir):
        if name not in _MCP_CONFIGURABLE_ADAPTERS:
            continue
        if name not in reg:
            missing.append(name)
    return missing


def _adapter_registration_recommended_tools() -> List[str]:
    return [
        t
        for t in (
            "ainl_capabilities",
            "ainl_adapter_contract",
            "ainl_run",
            "ainl_compile",
            "ainl_validate",
        )
        if t in _ALLOWED_TOOLS
    ]


def _envelope_adapter_registration_error(
    trace_id: str,
    ir: Dict[str, Any],
    missing_mcp: List[str],
    *,
    error_text: Optional[str] = None,
    strict: bool = True,
) -> Dict[str, Any]:
    """Shared payload when ainl_run cannot execute until MCP registers required adapters (preflight or runtime)."""
    if not missing_mcp:
        return {}
    first = missing_mcp[0]
    required = _required_adapters_from_ir(ir)
    for m in missing_mcp:
        if m not in required:
            required = sorted(set(required + [m]))
    suggested = _suggested_adapters_payload(required, ir)
    rr = _runtime_readiness_from_ir(ir)
    rr["ready"] = False
    rr["missing_adapters"] = required
    out: Dict[str, Any] = {
        "ok": False,
        "trace_id": trace_id,
        "error": (error_text or f"adapter not registered: {first}"),
        "error_kind": "adapter_registration",
        "required_adapters": required,
        "runtime_readiness": rr,
        "adapter_registration_error": {
            "adapter": first,
            "missing_mcp_configurable": missing_mcp,
            "message": (
                f"The workflow requires these MCP-configurable runtime adapters, but the current `ainl_run` "
                f"call did not register them: {missing_mcp!r}. Use `suggested_adapters` as the `adapters` "
                "argument; confirm verb names and tiers with `ainl_capabilities` first."
            ),
            "suggested_adapters": suggested,
            "next_step": (
                "Retry `ainl_run` with the same `code` and `suggested_adapters` in the `adapters` parameter. "
                "Prefer adapter configuration over deleting fs/http/cache/sqlite lines unless the user changes requirements."
            ),
            "ainl_adapter_contract": {
                "tool": "ainl_adapter_contract",
                "args": {"adapter": first},
            },
            "recommended_resources": [
                u
                for u in (
                    "ainl://strict-authoring-cheatsheet",
                    "ainl://adapter-contracts",
                )
                if u in _ALLOWED_RESOURCES
            ],
            "recommended_next_tools": _adapter_registration_recommended_tools(),
        },
        "repair_recipe": {
            "kind": "adapter_registration",
            "summary": (
                f"Register missing MCP runtime adapters {missing_mcp!r} — copy `suggested_adapters` from this "
                "response into the next `ainl_run` call."
            ),
            "primary_fix": "adapters_parameter",
        },
    }
    _attach_strict_mode_annotation(out, strict)
    return out


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


def _expand_workflow_path(raw: str) -> Path:
    """Resolve a filesystem path for MCP workflow loading (mirrors CLI ``Path(args.file).resolve()`` behavior).

    - Expands ``~`` via :meth:`pathlib.Path.expanduser`.
    - Absolute paths resolve normally.
    - Relative paths resolve against ``AINL_MCP_WORKFLOW_ROOT`` when set (ArmaraOS / OpenClaw workspaces),
      otherwise against :func:`os.getcwd` (same as ``ainl run ./foo.ainl`` from the shell).
    """
    p = Path(str(raw).strip()).expanduser()
    if p.is_absolute():
        return p.resolve()
    root = (os.environ.get("AINL_MCP_WORKFLOW_ROOT") or "").strip()
    if root:
        return (Path(root).expanduser() / p).resolve()
    return (Path.cwd() / p).resolve()


def _list_sibling_workflows(parent: Path, *, limit: int = 20) -> List[str]:
    """Return up to ``limit`` ``.ainl`` / ``.lang`` siblings, sorted, for ``path_not_found`` hints."""
    if not parent.is_dir():
        return []
    out: List[str] = []
    try:
        for p in sorted(parent.iterdir()):
            if p.is_file() and p.suffix in {".ainl", ".lang"}:
                out.append(p.name)
                if len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def _empty_source_path_error(p: Path) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "empty_source",
        "error_kind": "empty_source",
        "path": str(p),
        "why_this_matters": (
            f"`{p.name}` is empty (0 non-whitespace bytes). The compiler has nothing to process — "
            "retrying validate/compile/run against the same path will keep failing. Fix the source first."
        ),
        "next_step": (
            "Tell the user the file is empty (or scaffold a strict-valid graph for their goal via the "
            "`ainl_get_started` MCP tool). Do not re-run until the file has content."
        ),
        "minimal_strict_valid_example": (
            "S app core noop\n\nL_main:\n  R core.NOW ->ts\n  J ts\n"
        ),
        "recommended_next_tools": [
            t for t in ("ainl_get_started", "ainl_step_examples") if t in _ALLOWED_TOOLS
        ],
        "recommended_resources": [
            u for u in ("ainl://strict-authoring-cheatsheet", "ainl://strict-valid-examples") if u in _ALLOWED_RESOURCES
        ],
        "sibling_workflows": _list_sibling_workflows(p.parent),
    }


def _preflight_workflow_path(src_path: str) -> Optional[Dict[str, Any]]:
    """Detect ``path_not_found`` / ``empty_source`` before compile — mirrors ``cli/main.py``."""
    p = Path(src_path)
    if not p.exists():
        parent = p.parent
        return {
            "ok": False,
            "error": "path_not_found",
            "error_kind": "path_not_found",
            "path": str(p),
            "why_this_matters": (
                f"The workflow file does not exist at {p}. Retrying with the same path will fail identically — "
                "confirm the path with the user or pick a sibling workflow."
            ),
            "next_step": (
                "List the directory or ask the user for the correct path. The `sibling_workflows` field "
                "lists nearby `.ainl` / `.lang` files for quick selection."
            ),
            "sibling_workflows": _list_sibling_workflows(parent),
            "recommended_next_tools": [t for t in ("ainl_get_started",) if t in _ALLOWED_TOOLS],
            "recommended_resources": [u for u in ("ainl://strict-authoring-cheatsheet",) if u in _ALLOWED_RESOURCES],
        }
    if not p.is_file():
        return {
            "ok": False,
            "error": "path_not_a_file",
            "error_kind": "path_not_a_file",
            "path": str(p),
            "next_step": "Pass an `.ainl` / `.lang` file path, not a directory or special file.",
        }
    try:
        size = p.stat().st_size
    except OSError as e:
        return {
            "ok": False,
            "error": "stat_failed",
            "error_kind": "stat_failed",
            "path": str(p),
            "details": str(e),
        }
    if size == 0:
        return _empty_source_path_error(p)
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    if not text.strip():
        return _empty_source_path_error(p)
    return None


def _filter_preflight_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure preflight dicts respect MCP exposure lists."""
    rt = payload.get("recommended_next_tools")
    if isinstance(rt, list):
        payload["recommended_next_tools"] = [t for t in rt if t in _ALLOWED_TOOLS]
    rr = payload.get("recommended_resources")
    if isinstance(rr, list):
        payload["recommended_resources"] = [u for u in rr if u in _ALLOWED_RESOURCES]
    return payload


def _resolve_workflow_source(
    code: Optional[str],
    ainl: Optional[str],
    path: Optional[str],
) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    """Resolve program text from inline ``code``/``ainl`` or a filesystem ``path``.

    Returns ``(source, resolved_absolute_path_or_None, preflight_error_or_None)``.
    Non-whitespace inline source wins over ``path`` (same buffer semantics as ``ainl_get_started``).
    """
    inline = _resolve_code_arg(code, ainl)
    if inline:
        return inline, None, None
    raw_path = (path or "").strip() if isinstance(path, str) else ""
    if not raw_path:
        return "", None, None
    resolved = _expand_workflow_path(raw_path)
    abs_s = str(resolved)
    pre = _preflight_workflow_path(abs_s)
    if pre is not None:
        _filter_preflight_payload(pre)
        _attach_policy_contract_hints(pre)
        return "", abs_s, pre
    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        err = {
            "ok": False,
            "error": "unicode_decode_error",
            "error_kind": "unicode_decode_error",
            "path": abs_s,
            "details": str(e),
            "next_step": "Ensure the workflow file is valid UTF-8 text.",
        }
        _attach_policy_contract_hints(err)
        return "", abs_s, err
    return text, abs_s, None


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@_register_tool
def ainl_get_started(
    goal: Optional[str] = None,
    detail_level: str = "standard",
    existing_source: Optional[str] = None,
    path: Optional[str] = None,
    diagnostics: Optional[dict] = None,
    capabilities_snapshot: Optional[dict] = None,
    adapter_contracts_snapshot: Optional[dict] = None,
    wizard_state_json: Optional[dict] = None,
    reverse_source: Optional[str] = None,
    reverse_path: Optional[str] = None,
    reverse_paths: Optional[List[str]] = None,
    current_step: Optional[str] = None,
    request_examples_for: Optional[str] = None,
    example_count: int = 3,
) -> dict:
    """Start AINL authoring from natural language.

    This read-only wizard is the first tool to call before writing unfamiliar
    AINL.  It accepts a natural-language goal, infers a deterministic task
    spec, returns an intent-to-syntax guide, and tells the agent which discovery
    checkpoint to complete next. Full responses include ``planner_and_host_follow_ups``
    (how ArmaraOS / inference ``deterministic_plan`` + ``follow_ups`` relates to MCP
    authoring). It can also return step-local examples without advancing the wizard,
    or reverse-engineer existing AINL source into human-like goals for fixture/corpus building.

    For session continuity, pass the ``wizard_state_json`` from a previous call to
    resume from the last checkpoint state. The response includes an updated
    ``wizard_state_json`` that can be passed to subsequent calls.
    """
    if current_step or request_examples_for:
        return ainl_get_started_step_examples(
            current_step=current_step or request_examples_for or "current_step",
            request_examples_for=request_examples_for,
            example_count=example_count,
        )
    if reverse_source:
        return {
            "ok": True,
            "mode": "reverse_engineer_source",
            "result": reverse_engineer_ainl_source(
                reverse_source,
                source_file=reverse_path,
            ),
        }
    if reverse_paths:
        root = _REPO_ROOT.resolve()
        paths: List[Path] = []
        for rel in reverse_paths:
            try:
                target = (root / str(rel)).resolve()
                target.relative_to(root)
            except Exception:
                continue
            if target.suffix in {".ainl", ".lang"} and target.is_file():
                paths.append(target)
        return {
            "ok": True,
            "mode": "reverse_engineer_corpus",
            "result": reverse_engineer_ainl_corpus(paths, repo_root=root),
        }
    if not isinstance(goal, str) or not goal.strip():
        return {
            "ok": False,
            "error": "missing required argument: goal",
            "tool_call_error": True,
            "next_step": "Call ainl_get_started with a plain-language goal, e.g. {'goal': 'Build a scraper that fills a form and saves a CSV.'}.",
        }
    return ainl_get_started_wizard(
        goal,
        detail_level=detail_level,
        existing_source=existing_source,
        path=path,
        diagnostics=diagnostics,
        capabilities_snapshot=capabilities_snapshot,
        adapter_contracts_snapshot=adapter_contracts_snapshot,
        wizard_state_json=wizard_state_json,
    )


@_register_tool
def ainl_adapter_contract(
    adapter: str,
    detail_level: str = "standard",
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Return the known argument/runtime contract for an AINL adapter.

    Use this after ``ainl_get_started`` / ``ainl_capabilities`` and before
    writing adapter-specific AINL. Known contracts cover common adapters such as
    ``http``, ``browser``, ``fs``, ``cache``, ``core``, and composite choices
    like ``http_or_browser``.

    Pass ``wizard_state_json`` from prior wizard responses to advance checkpoints.
    """
    if not isinstance(adapter, str) or not adapter.strip():
        return _augment_with_wizard_state(
            {
                "ok": False,
                "error": "missing required argument: adapter",
                "tool_call_error": True,
                "next_step": "Call ainl_adapter_contract with an adapter name, e.g. {'adapter': 'http'} or {'adapter': 'http_or_browser'}.",
            },
            "ainl_adapter_contract",
            wizard_state_json,
        )
    out = ainl_adapter_contract_payload(adapter, detail_level=detail_level)
    return _augment_with_wizard_state(out, "ainl_adapter_contract", wizard_state_json)


@_register_tool
def ainl_step_examples(
    current_step: str = "",
    request_examples_for: Optional[str] = None,
    example_count: int = 3,
    include_corpus_references: bool = True,
) -> dict:
    """Return code examples for a specific wizard step or adapter topic.

    Use this to get snippet examples for a particular adapter or workflow step
    without advancing wizard state. Good for incremental authoring when you
    want examples for a specific topic (fs, browser, http, cache, etc.).

    Args:
        current_step: Current wizard step name (e.g. "write_output").
        request_examples_for: Topic to get examples for (e.g. "fs", "browser", "http").
        example_count: Maximum number of examples to return (default 3).
        include_corpus_references: Include paths to strict-valid corpus files.

    Returns:
        Examples with code snippets and optional corpus file references.
    """
    result = ainl_get_started_step_examples(
        current_step=current_step or "",
        request_examples_for=request_examples_for,
        example_count=example_count,
        include_corpus_references=include_corpus_references,
    )
    result["ok"] = True
    result["schema_version"] = "1.0.0"
    result["recommended_next_tools"] = [
        t for t in ["ainl_validate", "ainl_compile", "ainl_adapter_contract"]
        if t in _ALLOWED_TOOLS
    ]
    return result


@_register_tool
def ainl_validate(
    code: Optional[str] = None,
    strict: bool = True,
    ainl: Optional[str] = None,
    path: Optional[str] = None,
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Validate AINL source code without executing it.

    Returns whether the code compiles successfully, along with any errors
    or warnings.  No side effects.

    Pass the **full** program source in the ``code`` argument (UTF-8 string).
    The legacy ``ainl`` parameter name is accepted as an alias for ``code``.
    Alternatively, pass ``path`` to a readable ``.ainl`` / ``.lang`` file; non-whitespace
    inline ``code``/``ainl`` takes precedence over ``path``.
    An empty call (e.g. ``{}``) or omitted ``code``/``ainl``/``path`` is a **tool wiring** error
    (``error`` / ``tool_call_error``) — fix the MCP invocation, not the graph source.

    On failure, ``primary_diagnostic`` and per-row ``source_context`` (snippet +
    caret) point at the first error to fix; ``agent_repair_steps`` suggests a
    tight validate loop instead of copying unrelated files as templates.

    Always includes ``recommended_next_tools`` (and on failure,
    ``recommended_resources`` lists ``ainl://strict-authoring-cheatsheet`` first,
    then optional ``ainl://authoring-cheatsheet`` for HTTP/R-line issues) filtered
    by MCP exposure. Failures also include a deterministic ``repair_recipe``.

    When using the authoring wizard, pass ``wizard_state_json`` from the prior
    tool response so checkpoints advance on each validate/compile/run call.
    """
    source, resolved_path, path_err = _resolve_workflow_source(code, ainl, path)
    if path_err is not None:
        return _augment_with_wizard_state(path_err, "ainl_validate", wizard_state_json)
    if not source:
        kind = _classify_source_arg(code, ainl)
        err = (
            _empty_source_tool_error("ainl_validate")
            if kind == "empty"
            else _missing_source_tool_error("ainl_validate")
        )
        return _augment_with_wizard_state(err, "ainl_validate", wizard_state_json)
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
        _attach_runtime_readiness(out, ir)
        _merge_contract_alignment_into_output(out, ir, ok_graph=True)
        out["compiler_vs_runtime_note"] = (
            "Compiler success under the requested strict flag does **not** imply `ainl_run` is ready: "
            "check `required_adapters` / `runtime_readiness` and register adapters per-run in MCP."
        )
    if resolved_path:
        out["source_path"] = resolved_path
    if ok:
        _add_recommended_next_steps(out, "validate_ok")
    else:
        tags = _failure_tags_from_diagnostics(
            fb["diagnostics"],
            fb.get("primary_diagnostic"),
        )
        _add_recommended_next_steps(out, "validate_fail", failure_tags=tags)
        out["repair_recipe"] = _repair_recipe_from_failure(out.get("primary_diagnostic"), tags)
    _attach_strict_mode_annotation(out, strict)
    return _augment_with_wizard_state(out, "ainl_validate", wizard_state_json)


@_register_tool
def ainl_compile(
    code: Optional[str] = None,
    strict: bool = True,
    ainl: Optional[str] = None,
    path: Optional[str] = None,
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Compile AINL source code to canonical graph IR.

    Returns the full IR JSON on success, plus a ``frame_hints`` list that
    describes variables the caller should supply via the ``frame`` parameter
    when calling ``ainl_run``.  Frame hints are derived from two sources:

    1. Explicit ``# frame: name: type`` comment lines in source (authoritative).
    2. Variables referenced in the IR that are never assigned (heuristic).

    Pass the **full** program source in ``code`` (string); ``ainl`` is a legacy
    alias for ``code``. Alternatively pass ``path`` to a UTF-8 workflow file;
    non-whitespace inline source takes precedence over ``path``.

    No execution, no side effects.

    On compile failure, returns the same diagnostic bundle as ``ainl_validate``
    (merged structured diagnostics, snippets, ``primary_diagnostic``).

    Success and failure responses include ``recommended_next_tools`` (and
    failure may add ``recommended_resources`` / ``repair_recipe``) like ``ainl_validate``.

    Pass ``wizard_state_json`` from prior wizard/tool responses to advance checkpoints.
    """
    source, resolved_path, path_err = _resolve_workflow_source(code, ainl, path)
    if path_err is not None:
        return _augment_with_wizard_state(path_err, "ainl_compile", wizard_state_json)
    if not source:
        kind = _classify_source_arg(code, ainl)
        err = (
            _empty_source_tool_error("ainl_compile")
            if kind == "empty"
            else _missing_source_tool_error("ainl_compile")
        )
        return _augment_with_wizard_state(err, "ainl_compile", wizard_state_json)
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
        out["repair_recipe"] = _repair_recipe_from_failure(out.get("primary_diagnostic"), tags)
        _attach_strict_mode_annotation(out, strict)
        if resolved_path:
            out["source_path"] = resolved_path
        return _augment_with_wizard_state(out, "ainl_compile", wizard_state_json)
    _on_compile_finished(True, source)
    frame_hints = _extract_frame_hints(source, ir)
    out_ok: Dict[str, Any] = {"ok": True, "ir": ir, "frame_hints": frame_hints}
    _attach_runtime_readiness(out_ok, ir)
    _merge_contract_alignment_into_output(out_ok, ir, ok_graph=True)
    out_ok["compiler_vs_runtime_note"] = (
        "IR is canonical for this compile; `ainl_run` still needs per-run `adapters` registration in MCP "
        "when the graph uses http/fs/cache/sqlite/a2a."
    )
    if resolved_path:
        out_ok["source_path"] = resolved_path
    _add_recommended_next_steps(out_ok, "compile_ok")
    _attach_strict_mode_annotation(out_ok, strict)
    return _augment_with_wizard_state(out_ok, "ainl_compile", wizard_state_json)


@_register_tool
def ainl_emit_grammar_gbnf(
    include_compact: bool = True,
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Emit a llama.cpp-compatible GBNF grammar for strict-valid AINL programs.

    No source required — grammar is derived from the compiler opcode registry and
    adapter effect contract. Use with constrained decode backends (llama.cpp grammar).
    """
    from tooling.grammar_emit_gbnf import emit_gbnf

    grammar = emit_gbnf(include_compact=include_compact)
    out: Dict[str, Any] = {
        "ok": True,
        "format": "gbnf",
        "grammar": grammar,
        "byte_length": len(grammar.encode("utf-8")),
        "recommended_next_tools": ["ainl_validate", "ainl_compile"],
    }
    return _augment_with_wizard_state(out, "ainl_emit_grammar_gbnf", wizard_state_json)


@_register_tool
def ainl_emit_grammar_jsonschema(
    format: str = "jsonschema",
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Emit JSON Schema or EBNF for vLLM / XGrammar guided decoding of strict-valid AINL.

    ``format`` is ``jsonschema`` (default) or ``ebnf``.
    """
    fmt = (format or "jsonschema").strip().lower()
    if fmt == "ebnf":
        from tooling.grammar_emit_jsonschema import emit_ebnf

        grammar = emit_ebnf()
        out: Dict[str, Any] = {"ok": True, "format": "ebnf", "grammar": grammar}
    elif fmt in ("jsonschema", "json"):
        from tooling.grammar_emit_jsonschema import emit_jsonschema

        schema = emit_jsonschema()
        out = {"ok": True, "format": "jsonschema", "schema": schema}
    else:
        return _augment_with_wizard_state(
            {
                "ok": False,
                "error_kind": "invalid_format",
                "error": f"Unknown format {format!r}; use jsonschema or ebnf",
            },
            "ainl_emit_grammar_jsonschema",
            wizard_state_json,
        )
    out["recommended_next_tools"] = ["ainl_validate", "ainl_compile"]
    return _augment_with_wizard_state(out, "ainl_emit_grammar_jsonschema", wizard_state_json)


@_register_tool
def ainl_capabilities(wizard_state_json: Optional[dict] = None) -> dict:
    """Discover runtime adapter capabilities, privilege tiers, and metadata.

    Returns available adapters with their verbs, support tiers, effect
    defaults, recommended lanes, and privilege tiers.  Also includes
    ``mcp_telemetry`` (per-process counters for validate/compile/run) and
    ``mcp_resources`` (integration doc URIs exposed for this process).  No side
    effects beyond bump-free read of those counters.

    Pass ``wizard_state_json`` from prior wizard responses to advance checkpoints.
    """
    return _augment_with_wizard_state(_load_capabilities(), "ainl_capabilities", wizard_state_json)


@_register_tool
def ainl_security_report(
    code: Optional[str] = None,
    ainl: Optional[str] = None,
    path: Optional[str] = None,
) -> dict:
    """Generate a security/privilege map for an AINL workflow.

    Shows which adapters, verbs, and privilege tiers the workflow uses,
    broken down per label and in aggregate.  No execution, no side effects.

    Pass full source in ``code`` (``ainl`` alias accepted), or ``path`` to a UTF-8 workflow file;
    non-whitespace inline source takes precedence over ``path``.
    """
    source, resolved_path, path_err = _resolve_workflow_source(code, ainl, path)
    if path_err is not None:
        return path_err
    if not source:
        kind = _classify_source_arg(code, ainl)
        return (
            _empty_source_tool_error("ainl_security_report")
            if kind == "empty"
            else _missing_source_tool_error("ainl_security_report")
        )
    ir = _compile(source, strict=False)
    errors = ir.get("errors") or []
    if errors:
        out_err: Dict[str, Any] = {"ok": False, "errors": errors}
        if resolved_path:
            out_err["source_path"] = resolved_path
        return out_err
    report = analyze_ir(ir)
    out_ok: Dict[str, Any] = {"ok": True, "report": report}
    if resolved_path:
        out_ok["source_path"] = resolved_path
    return out_ok


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
    path: Optional[str] = None,
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Compile, validate policy, and execute an AINL workflow.

    By default only the ``core`` adapter is registered. Any workflow that uses
    ``http``, ``fs``, ``cache``, or ``sqlite`` adapters MUST pass them via the
    ``adapters`` parameter or the run will fail with "adapter not registered".

    IMPORTANT — adapter registration is opt-in per-run:
      - ``http``  → requires ``allow_hosts`` (list of hostnames, e.g. ["example.com"])
      - ``http`` optional: ``payment_profile`` (``none`` / ``auto`` / ``mpp`` / ``x402``) and
        ``max_payment_rounds`` (int, default 2) for machine-payment retries; see MCP resource
        ``ainl://integrations-http-machine-payments`` for ``frame.http_payment`` merges.
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

    Example — workflow that does HTTP + file I/O + caching, or A2A to a remote agent card::

        adapters={
          "enable": ["http", "fs", "cache"],
          "http": {
            "allow_hosts": ["ohwarren.fidlar.com", "auditor.warrencountyohio.gov"],
            "timeout_s": 15.0,
            "payment_profile": "none",
            "max_payment_rounds": 2
          },
          "fs": {
            "root": "/Users/me/.armaraos/workspaces/MyProject",
            "allow_extensions": [".json", ".csv"]
          },
          "cache": {
            "path": "/Users/me/.armaraos/workspaces/MyProject/cache.json"
          }
        }

    A2A (Agent-to-Agent) to an ArmaraOS-shaped peer — enable ``a2a`` and scope hosts::

        adapters={
          "enable": ["a2a"],
          "a2a": {
            "allow_hosts": ["agent.example.com", "127.0.0.1"],
            "allow_insecure_local": true,
            "strict_ssrf": true,
            "follow_redirects": false,
            "timeout_s": 30.0
          }
        }

    See ``docs/integrations/A2A_ADAPTER.md`` for threat model, wire profile, and **SECURITY** reporting.

    Resource limits enforce a safety floor. The caller may supply additional
    policy restrictions and tighter limits but cannot widen beyond the merged
    server defaults.

    Returns structured execution output on success or a policy/runtime
    error on failure.  If the compiled graph needs MCP-configurable adapters
    (``http``, ``fs``, ``cache``, ``sqlite``, ``a2a``) but this call did not
    register them on ``reg``, the server returns ``error_kind: adapter_registration``
    with ``suggested_adapters`` **before** starting the runtime (no partial run).

    Pass full source in ``code`` (``ainl`` alias accepted), or ``path`` to a UTF-8 workflow file
    (non-whitespace inline source takes precedence). Matches CLI ``ainl run /path/to/graph.ainl`` ergonomics.

    Pass ``wizard_state_json`` from prior wizard/tool responses so checkpoints
    advance; the server records the ``adapters`` payload against ``pending_mcp_adapters``.
    """
    trace_id = str(uuid.uuid4())
    run_adapters_arg: Optional[Dict[str, Any]] = adapters if isinstance(adapters, dict) else None

    source, resolved_path, path_err = _resolve_workflow_source(code, ainl, path)

    def _wiz(out: Dict[str, Any]) -> Dict[str, Any]:
        if resolved_path:
            out = {**out, "source_path": resolved_path}
        return _augment_with_wizard_state(
            out, "ainl_run", wizard_state_json, run_adapters=run_adapters_arg
        )

    if path_err is not None:
        pe = dict(path_err)
        pe["trace_id"] = trace_id
        return _wiz(_annotate_run_return(pe, strict))
    if not source:
        kind = _classify_source_arg(code, ainl)
        if kind == "empty":
            out_ms = _empty_source_tool_error("ainl_run")
            out_ms["trace_id"] = trace_id
            out_ms["error"] = "empty_source"
        else:
            out_ms = _missing_source_tool_error("ainl_run")
            out_ms["trace_id"] = trace_id
            out_ms["error"] = "missing required argument: code"
        return _wiz(_annotate_run_return(out_ms, strict))
    if resolved_path and "intelligence" in Path(resolved_path).parts:
        if "AINL_ALLOW_IR_DECLARED_ADAPTERS" not in os.environ:
            os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = "1"
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
        tags = _failure_tags_from_diagnostics(
            fb["diagnostics"],
            fb.get("primary_diagnostic"),
        )
        _add_recommended_next_steps(out, "compile_fail", failure_tags=tags)
        out["repair_recipe"] = _repair_recipe_from_failure(out.get("primary_diagnostic"), tags)
        return _wiz(_annotate_run_return(out, strict))

    merged_policy = _merge_policy(policy)
    policy_result = validate_ir_against_policy(ir, merged_policy)
    if not policy_result["ok"]:
        return _wiz(
            _annotate_run_return(
                {
                    "ok": False,
                    "trace_id": trace_id,
                    "error": "policy_violation",
                    "policy_errors": policy_result["errors"],
                },
                strict,
            )
        )

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
    # adapters: { enable: ["http","fs","cache","sqlite","pggraph"], http: {...}, fs: {...}, cache: {...}, sqlite: {...}, pggraph: {...} }
    if isinstance(adapters, dict):
        enabled = set(adapters.get("enable") or [])
        if "http" in enabled:
            h = adapters.get("http") or {}
            allow_hosts = h.get("allow_hosts") or []
            if not isinstance(allow_hosts, list) or not allow_hosts:
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "http adapter enabled but adapters.http.allow_hosts must be a non-empty list",
                        },
                        strict,
                    )
                )
            reg.register(
                "http",
                SimpleHttpAdapter(
                    default_timeout_s=float(h.get("timeout_s", 5.0)),
                    max_response_bytes=int(h.get("max_response_bytes", 1_000_000)),
                    allow_hosts=[str(x) for x in allow_hosts],
                    payment_profile=str(h.get("payment_profile", "none") or "none"),
                    max_payment_rounds=int(h.get("max_payment_rounds", 2) or 2),
                ),
            )
        if "fs" in enabled:
            f = adapters.get("fs") or {}
            root = f.get("root")
            if not root:
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "fs adapter enabled but adapters.fs.root is missing",
                        },
                        strict,
                    )
                )
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
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "cache adapter enabled but adapters.cache.path is missing",
                        },
                        strict,
                    )
                )
            reg.register("cache", LocalFileCacheAdapter(path=str(cache_path)))
        if "sqlite" in enabled:
            s = adapters.get("sqlite") or {}
            db_path = s.get("db_path")
            if not db_path:
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "sqlite adapter enabled but adapters.sqlite.db_path is missing",
                        },
                        strict,
                    )
                )
            reg.register(
                "sqlite",
                SimpleSqliteAdapter(
                    db_path=str(db_path),
                    allow_write=bool(s.get("allow_write")),
                    allow_tables=s.get("allow_tables") or [],
                    timeout_s=float(s.get("timeout_s", 5.0)),
                ),
            )
        if "pggraph" in enabled:
            g = adapters.get("pggraph") or {}
            try:
                reg.register("pggraph", _pggraph_adapter_from_mcp_config(g))
            except Exception as e:
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": str(e),
                        },
                        strict,
                    )
                )
        if "a2a" in enabled:
            a2 = adapters.get("a2a") or {}
            allow_hosts = a2.get("allow_hosts") or []
            allow_insecure = bool(a2.get("allow_insecure_local", False))
            if not allow_hosts and not allow_insecure:
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "a2a adapter: set adapters.a2a.allow_hosts and/or allow_insecure_local",
                        },
                        strict,
                    )
                )
            if not isinstance(allow_hosts, list):
                return _wiz(
                    _annotate_run_return(
                        {
                            "ok": False,
                            "trace_id": trace_id,
                            "error": "adapter_config_error",
                            "details": "a2a: adapters.a2a.allow_hosts must be a list when set",
                        },
                        strict,
                    )
                )
            reg.register(
                "a2a",
                A2aAdapter(
                    allow_hosts=[str(x) for x in allow_hosts],
                    allow_insecure_local=allow_insecure,
                    default_timeout_s=float(a2.get("timeout_s", 30.0)),
                    max_response_bytes=int(a2.get("max_response_bytes", 1_000_000)),
                    strict_ssrf=bool(a2.get("strict_ssrf", False)),
                    follow_redirects=bool(a2.get("follow_redirects", False)),
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
                        return _wiz(
                            _annotate_run_return(
                                {
                                    "ok": False,
                                    "trace_id": trace_id,
                                    "error": "adapter_config_error",
                                    "details": f"cache.json at {_cp} is not valid JSON: {e}",
                                },
                                strict,
                            )
                        )
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

    miss = _mcp_configurable_adapters_missing_from_registry(reg, ir)
    if miss:
        return _wiz(_envelope_adapter_registration_error(trace_id, ir, miss, strict=strict))

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
        err_text = str(e)
        missing_adapter = _missing_adapter_from_error_text(err_text)
        if missing_adapter:
            out_err = _envelope_adapter_registration_error(
                trace_id, ir, [missing_adapter], error_text=err_text, strict=strict
            )
            if out_err:
                out_err["error_structured"] = e.to_dict()
                return _wiz(out_err)
        repair = _runtime_error_agent_repair_steps(
            e, resolved_path=resolved_path, merged_limits=merged_limits
        )
        payload: Dict[str, Any] = {
            "ok": False,
            "trace_id": trace_id,
            "error": err_text,
            "error_structured": e.to_dict(),
        }
        if repair:
            payload["agent_repair_steps"] = repair
            payload["cli_fallback"] = (
                "For long-running or high-volume enrichment, run "
                "`ainl run <path.ainl>` in the workspace shell or use `script_run` on a "
                "Python helper (e.g. enrich_one.py) instead of a single large MCP `ainl_run`."
            )
        return _wiz(_annotate_run_return(payload, strict))
    except Exception as e:
        err_text = str(e)
        missing_adapter = _missing_adapter_from_error_text(err_text)
        if missing_adapter:
            out_err = _envelope_adapter_registration_error(
                trace_id, ir, [missing_adapter], error_text=err_text, strict=strict
            )
            if out_err:
                return _wiz(out_err)
        return _wiz(_annotate_run_return({"ok": False, "trace_id": trace_id, "error": err_text}, strict))

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
    return _wiz(_annotate_run_return(out_run, strict))


@_register_tool
def ainl_wizard_checkpoint(
    checkpoint_id: str,
    wizard_state_json: Optional[dict] = None,
) -> dict:
    """Acknowledge a wizard checklist checkpoint (operator/agent attestation).

    Use for steps that are not tied to a single MCP tool result, e.g.
    ``strict_examples_reviewed`` after reading ``ainl://strict-valid-examples``.
    """
    cid = str(checkpoint_id or "").strip()
    if not cid:
        return _augment_with_wizard_state(
            {
                "ok": False,
                "error": "missing required argument: checkpoint_id",
                "tool_call_error": True,
            },
            "ainl_wizard_checkpoint",
            wizard_state_json,
        )
    out = {"ok": True, "checkpoint_id": cid}
    return _augment_with_wizard_state(out, "ainl_wizard_checkpoint", wizard_state_json)


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
def ainl_estimate(
    code: Optional[str] = None,
    ainl: Optional[str] = None,
    path: Optional[str] = None,
    model: str = "gpt-4o",
    runs_per_day: int = 10,
    strict: bool = True,
) -> dict:
    """Estimate compile-time LLM token cost for an AINL graph (static analysis).

    Returns the same JSON as ``ainl estimate --format json`` on the CLI.
    Accepts inline ``code`` or a filesystem ``path`` to a ``.ainl`` file.
    """
    from tooling.cost_estimate import estimate_ir_cost, MODEL_PRICING

    source = _resolve_code_arg(code, ainl)
    if not source and path:
        try:
            resolved = _expand_workflow_path(path)
            source = resolved.read_text(encoding="utf-8")
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    if not source.strip():
        return {
            "ok": False,
            "error_kind": "empty_source",
            "error": "No source code provided. Pass 'code' or 'path'.",
        }

    ir = _compile(source, strict=strict)
    errors = ir.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}

    try:
        est = estimate_ir_cost(ir, pricing_model=model, runs_per_day=runs_per_day)
    except Exception as exc:
        return {"ok": False, "error": f"Estimation failed: {exc}"}

    est["ok"] = True
    est["available_models"] = sorted(MODEL_PRICING.keys())
    return est


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
def ainl_mission_plan(
    objective: str,
    repo_intel: Optional[dict] = None,
    mission_root: Optional[str] = None,
) -> dict:
    """Propose a draft Mission + Feature + Assertion DAG from a natural-language objective.

    Optional ``repo_intel`` may include ``touches_files``, ``coding_domain``, ``git_snapshot``,
    or ``mission_root``. Output is validated with the same rules as ``ainl_mission_validate``.
    """
    out = mission_plan_payload(
        objective,
        repo_intel=repo_intel,
        mission_root=mission_root,
    )
    out["recommended_next_tools"] = [
        t for t in ("ainl_mission_validate", "ainl_handoff_lint", "ainl_validate")
        if t in _ALLOWED_TOOLS
    ]
    out["recommended_resources"] = [
        u
        for u in (
            "ainl://mission-authoring-cheatsheet",
            "ainl://mission-worker-examples",
            "ainl://strict-valid-missions",
        )
        if u in _ALLOWED_RESOURCES
    ]
    return out


@_register_tool
def ainl_mission_validate(
    mission: dict,
    features: List[dict],
    assertions: Optional[List[dict]] = None,
    validate_worker_ainl: bool = False,
) -> dict:
    """Validate Mission + Feature DAG: schema conformance, acyclic preconditions, assertion coverage.

    Set ``validate_worker_ainl=true`` to strict-validate each Feature ``worker_ainl_path`` under the repo.
    """
    validation = validate_mission_dag(
        mission,
        features,
        assertions or [],
        validate_worker_ainl=bool(validate_worker_ainl),
        repo_root=_REPO_ROOT,
    )
    return {
        "ok": validation["ok"],
        "schema_version": validation.get("schema_version", "1.0.0"),
        "validate_checksum": validation.get("validate_checksum"),
        "validation": validation,
        "recommended_next_tools": [
            t for t in ("ainl_mission_plan", "ainl_handoff_lint", "ainl_run")
            if t in _ALLOWED_TOOLS
        ],
        "recommended_resources": [
            u
            for u in ("ainl://mission-authoring-cheatsheet", "ainl://strict-valid-missions")
            if u in _ALLOWED_RESOURCES
        ],
    }


@_register_tool
def ainl_handoff_lint(
    handoff: dict,
    features: Optional[List[dict]] = None,
) -> dict:
    """Validate a Handoff object against handoff.schema.json and optional Feature cross-checks."""
    out = mission_lint_handoff(handoff, features=features)
    return {
        "ok": out["ok"],
        "schema_version": "1.0.0",
        "lint": out,
        "recommended_next_tools": [
            t for t in ("ainl_mission_validate", "ainl_mission_plan")
            if t in _ALLOWED_TOOLS
        ],
    }


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


@_register_resource("ainl://strict-authoring-cheatsheet")
def strict_authoring_cheatsheet_resource() -> str:
    """Strict-mode authoring contract: compact syntax, MCP `code=`, no inline dict/J pitfalls."""
    return _STRICT_AUTHORING_CHEATSHEET_MARKDOWN


@_register_resource("ainl://strict-valid-examples")
def strict_valid_examples_resource() -> str:
    """JSON index of CI `strict-valid` paths from tooling/artifact_profiles.json."""
    return _strict_valid_examples_json()


def _strict_valid_families_json() -> str:
    """JSON mined index: families, by_adapter, examples (see tooling/corpus_mining.py)."""
    path = _REPO_ROOT / "corpus" / "strict_valid_family_index.json"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return json.dumps(
            {
                "ok": False,
                "error": str(exc),
                "hint": "Run: python -m tooling.corpus_mining generate-family-index",
            },
            indent=2,
        )


@_register_resource("ainl://strict-valid-families")
def strict_valid_families_resource() -> str:
    """Mined strict-valid family index (corpus/strict_valid_family_index.json)."""
    return _strict_valid_families_json()


@_register_resource("ainl://adapter-contracts")
def adapter_contracts_bundle_resource() -> str:
    """JSON bundle of deterministic adapter_contract payloads (http, fs, browser, …)."""
    return _adapter_contracts_bundle_json()


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


@_register_resource("ainl://integrations-hub")
def integrations_hub_resource() -> str:
    """Integrations documentation index (docs/integrations/README.md)."""
    return _read_integration_doc("README.md")


@_register_resource("ainl://integrations-http-machine-payments")
def integrations_http_machine_payments_resource() -> str:
    """HTTP adapter machine payments: x402, MPP, payment_profile, http_payment frame (full doc)."""
    return _read_integration_doc("HTTP_MACHINE_PAYMENTS.md")


@_register_resource("ainl://integrations-agentic-protocols-readiness")
def integrations_agentic_protocols_readiness_resource() -> str:
    """Practitioner readiness checklist for agentic HTTP / payment flows."""
    return _read_integration_doc("AGENTIC_PROTOCOLS_PRACTITIONER_READINESS.md")


@_register_resource("ainl://integrations-agtp")
def integrations_agtp_resource() -> str:
    """AGTP (Agentic Gateway Transport Protocol) integration notes."""
    return _read_integration_doc("AGTP.md")


@_register_resource("ainl://integrations-a2a")
def integrations_a2a_resource() -> str:
    """A2A adapter threat model and wire profile (docs/integrations/A2A_ADAPTER.md)."""
    return _read_integration_doc("A2A_ADAPTER.md")


@_register_resource("ainl://examples-http-machine-payment-flow")
def examples_http_machine_payment_flow_resource() -> str:
    """Strict-valid compact example: HTTP GET + payment_required branch (examples/http/...)."""
    return _read_allowlisted_repo_subpath("examples/http/http_machine_payment_flow_compact.ainl")


def _strict_valid_missions_json() -> str:
    """JSON index of strict-valid mission worker paths from artifact_profiles.json."""
    profiles = load_artifact_profiles()
    paths = [
        p
        for p in profiles.get("examples", {}).get("strict-valid", [])
        if "mission_workers/" in p.replace("\\", "/")
    ]
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "description": "Strict-valid mission worker examples (CI via artifact_profiles.json).",
            "paths": sorted(paths),
        },
        indent=2,
    )


@_register_resource("ainl://strict-valid-missions")
def strict_valid_missions_resource() -> str:
    """JSON index of strict-valid mission worker paths."""
    return _strict_valid_missions_json()


@_register_resource("ainl://mission-authoring-cheatsheet")
def mission_authoring_cheatsheet_resource() -> str:
    """Mission substrate authoring: schemas, MCP tools, host tool contracts."""
    return MISSION_AUTHORING_CHEATSHEET


@_register_resource("ainl://mission-worker-examples")
def mission_worker_examples_resource() -> str:
    """Concatenated strict-valid mission worker .ainl sources."""
    profiles = load_artifact_profiles()
    paths = sorted(
        p
        for p in profiles.get("examples", {}).get("strict-valid", [])
        if "mission_workers/" in p.replace("\\", "/")
    )
    chunks: List[str] = ["# Mission worker examples (strict-valid)\n"]
    for rel in paths:
        try:
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError as exc:
            chunks.append(f"\n## {rel}\n\n(read error: {exc})\n")
            continue
        chunks.append(f"\n## {rel}\n\n```ainl\n{text.rstrip()}\n```\n")
    return "".join(chunks)


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
