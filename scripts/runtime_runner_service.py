#!/usr/bin/env python3
from __future__ import annotations

"""Runtime runner service for execution-oriented endpoints.

Contract boundary:
- This service exposes runtime execution APIs (`/run`, `/enqueue`, `/result`,
  `/health`, `/ready`, `/metrics`, `/capabilities`,
  `/capabilities/langgraph`, `/capabilities/temporal` (static emitter discovery for MCP hosts).
- It intentionally does not expose emitted product/business REST routes (for example `/api/products`, `/api/checkout`).
- UI/frontends expecting business routes should run against emitted app servers, not this runner.
"""

import hashlib
import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.executor_bridge import ExecutorBridgeAdapter
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.a2a import A2aAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.replay import RecordingAdapterRegistry, ReplayAdapterRegistry
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.adapters.tools import ToolBridgeAdapter
from runtime.adapters.wasm import WasmAdapter
from runtime.sandbox_shim import SandboxClient
from runtime.engine import AinlRuntimeError, RuntimeEngine, RUNTIME_VERSION
from tooling.policy_validator import validate_ir_against_policy
from tooling.capability_grant import (
    empty_grant,
    env_truthy,
    merge_grants,
    grant_to_policy,
    grant_to_limits,
    grant_to_allowed_adapters,
    load_profile_as_grant,
)

logger = logging.getLogger("ainl.runner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
# Optional sandbox discovery at startup; runner behavior is unchanged when unavailable.
_SANDBOX_CLIENT = SandboxClient.try_connect(logger=logger.info)

# --- Server-level defaults (safety floor) --------------------------------
_SERVER_DEFAULT_LIMITS: Dict[str, int] = {
    "max_steps": 500000,
    "max_depth": 500,
    "max_adapter_calls": 50000,
    "max_time_ms": 900000,
}


def _bare_runner_floor() -> Dict[str, Any]:
    """Resource floor + permissive adapter cap (None) for merge with strict preset."""
    return {
        "allowed_adapters": None,
        "forbidden_adapters": [],
        "forbidden_effects": [],
        "forbidden_effect_tiers": [],
        "forbidden_privilege_tiers": [],
        "limits": dict(_SERVER_DEFAULT_LIMITS),
        "adapter_constraints": {},
    }


def _load_server_grant() -> Dict[str, Any]:
    """Build the server-level capability grant from env/defaults."""
    profile_name = (os.environ.get("AINL_SECURITY_PROFILE") or "").strip()
    if profile_name:
        try:
            return load_profile_as_grant(profile_name)
        except ValueError:
            logger.warning("unknown AINL_SECURITY_PROFILE %r; using defaults", profile_name)
            return _bare_runner_floor()
    if env_truthy(os.environ.get("AINL_STRICT_MODE")):
        sp = (os.environ.get("AINL_STRICT_PROFILE") or "consumer_secure_default").strip()
        try:
            return merge_grants(_bare_runner_floor(), load_profile_as_grant(sp))
        except ValueError:
            logger.warning("unknown AINL_STRICT_PROFILE %r; using permissive defaults", sp)
    return _bare_runner_floor()

# Cached default grant; request execution refreshes from env to keep tests and
# long-lived runner processes aligned with dynamic profile changes.
_SERVER_GRANT_PROFILE: Optional[str] = os.environ.get("AINL_SECURITY_PROFILE")
_SERVER_GRANT: Dict[str, Any] = _load_server_grant()

_COMPILE_CACHE: Dict[str, Dict[str, Any]] = {}
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOB_Q: "queue.Queue[tuple[str, Dict[str, Any]]]" = queue.Queue()
_STOP = threading.Event()
_WORKER: Optional[threading.Thread] = None
_LOCK = threading.Lock()
_METRICS: Dict[str, Any] = {
    "runs_total": 0,
    "failures_total": 0,
    "durations_ms": [],
    "adapter_calls_total": 0,
    "compile_cache_hits": 0,
    "compile_cache_misses": 0,
    "adapter_counts": {},
    "adapter_durations_ms": {},
    "adapter_capability_blocks_total": 0,
    "adapter_capability_blocks_by_adapter": {},
}
_SENSITIVE_TOKENS = ("authorization", "token", "secret", "password", "api_key", "apikey", "x-api-key")


class PolicyViolationError(Exception):
    """Raised when IR violates a submitted policy before execution."""

    def __init__(self, errors: List[Dict[str, Any]]):
        self.errors = errors
        super().__init__(f"Policy violation: {len(errors)} error(s)")


class _EchoAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        return args[0] if args else target


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _p95(vals: List[float]) -> float:
    if not vals:
        return 0.0
    xs = sorted(vals)
    idx = int(0.95 * (len(xs) - 1))
    return float(xs[idx])


def _json_log(payload: Dict[str, Any]) -> None:
    logger.info(json.dumps(payload, ensure_ascii=False))


def _redact_value(v: Any) -> Any:
    if isinstance(v, dict):
        out = {}
        for k, vv in v.items():
            ks = str(k).lower()
            if any(tok in ks for tok in _SENSITIVE_TOKENS):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact_value(vv)
        return out
    if isinstance(v, list):
        return [_redact_value(x) for x in v]
    if isinstance(v, str):
        s = v.strip().lower()
        if any(tok in s for tok in _SENSITIVE_TOKENS) or s.startswith("bearer "):
            return "[REDACTED]"
        return v
    return v


def _result_hash(result: Any) -> Optional[str]:
    """SHA-256 of JSON-serialised result, or None if not serialisable."""
    try:
        return hashlib.sha256(
            json.dumps(result, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()
    except (TypeError, ValueError, OverflowError):
        return None


def _instrument_registry(reg: AdapterRegistry, trace_id: str, replay_artifact_id: str) -> Dict[str, List[float]]:
    per_adapter: Dict[str, List[float]] = {}
    original_call = reg.call

    def wrapped_call(adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t0 = time.perf_counter()
        status = "ok"
        error_summary: Optional[str] = None
        result = None
        try:
            result = original_call(adapter_name, target, args, context)
            return result
        except Exception as exc:
            status = "error"
            raw = str(exc)[:200]
            error_summary = _redact_value(raw) if isinstance(raw, str) else raw
            if isinstance(raw, str) and "capability gate" in raw:
                with _LOCK:
                    _METRICS["adapter_capability_blocks_total"] = (
                        int(_METRICS.get("adapter_capability_blocks_total", 0)) + 1
                    )
                    by = _METRICS.setdefault("adapter_capability_blocks_by_adapter", {})
                    by[adapter_name] = int(by.get(adapter_name, 0)) + 1
            raise
        finally:
            dt = round((time.perf_counter() - t0) * 1000, 3)
            per_adapter.setdefault(adapter_name, []).append(dt)
            log_entry: Dict[str, Any] = {
                "event": "adapter_call",
                "ts": ts,
                "trace_id": trace_id,
                "replay_artifact_id": replay_artifact_id,
                "adapter": adapter_name,
                "verb": target,
                "duration_ms": dt,
                "status": status,
                "args": _redact_value(list(args or [])),
                "result_hash": _result_hash(result) if status == "ok" else None,
            }
            if error_summary is not None:
                log_entry["error_summary"] = error_summary
            _json_log(log_entry)

    reg.call = wrapped_call  # type: ignore[assignment]
    return per_adapter


def _get_ir_from_code(code: str, strict: bool = True) -> Dict[str, Any]:
    key = f"{_sha256(code)}:{'strict' if strict else 'nonstrict'}"
    with _LOCK:
        if key in _COMPILE_CACHE:
            _METRICS["compile_cache_hits"] += 1
            return _COMPILE_CACHE[key]
        _METRICS["compile_cache_misses"] += 1
    ir = RuntimeEngine.from_code(code, strict=strict).ir
    with _LOCK:
        _COMPILE_CACHE[key] = ir
    return ir


def _build_registry(req: Dict[str, Any]) -> AdapterRegistry:
    replay_log = req.get("replay_log")
    record_calls = bool(req.get("record_calls"))
    raw_allowed = req.get("allowed_adapters")
    # None = no host allowlist for the registry bootstrap; RuntimeEngine will
    # .allow() every adapter the IR references. Non-None includes [] (deny-all).
    allowed: List[str] = [] if raw_allowed is None else list(raw_allowed)
    if replay_log is not None:
        if not isinstance(replay_log, list):
            raise ValueError("replay_log must be a list")
        reg: AdapterRegistry = ReplayAdapterRegistry(replay_log, allowed=allowed)
    elif record_calls:
        reg = RecordingAdapterRegistry(allowed=allowed)
    else:
        reg = AdapterRegistry(allowed=allowed)

    cfg = req.get("adapters") or {}
    enabled = set(cfg.get("enable", []))
    if "ext" in enabled:
        reg.register("ext", _EchoAdapter())
    if "http" in enabled:
        h = cfg.get("http") or {}
        reg.register(
            "http",
            SimpleHttpAdapter(
                default_timeout_s=float(h.get("timeout_s", 5.0)),
                max_response_bytes=int(h.get("max_response_bytes", 1_000_000)),
                allow_hosts=h.get("allow_hosts") or [],
                payment_profile=str(h.get("payment_profile", "none") or "none"),
                max_payment_rounds=int(h.get("max_payment_rounds", 2) or 2),
            ),
        )
    if "a2a" in enabled:
        a2 = cfg.get("a2a") or {}
        allow_hosts = a2.get("allow_hosts") or []
        allow_insecure = bool(a2.get("allow_insecure_local", False))
        if not allow_hosts and not allow_insecure:
            raise ValueError("a2a adapter: set adapters.a2a.allow_hosts and/or allow_insecure_local")
        if not isinstance(allow_hosts, list):
            raise ValueError("a2a adapter: allow_hosts must be a list of strings when set")
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
    if "bridge" in enabled:
        b = cfg.get("bridge") or {}
        endpoints = b.get("endpoints")
        if not isinstance(endpoints, dict) or not endpoints:
            raise ValueError("bridge adapter enabled but adapters.bridge.endpoints must be a non-empty object")
        h = b.get("http") or {}
        reg.register(
            "bridge",
            ExecutorBridgeAdapter(
                endpoints={str(k): str(v) for k, v in endpoints.items()},
                default_timeout_s=float(h.get("timeout_s", 5.0)),
                max_response_bytes=int(h.get("max_response_bytes", 1_000_000)),
                allow_hosts=h.get("allow_hosts") or [],
            ),
        )
    if "sqlite" in enabled:
        s = cfg.get("sqlite") or {}
        reg.register(
            "sqlite",
            SimpleSqliteAdapter(
                db_path=str(s.get("db_path") or ":memory:"),
                allow_write=bool(s.get("allow_write")),
                allow_tables=s.get("allow_tables") or [],
                timeout_s=float(s.get("timeout_s", 5.0)),
            ),
        )
    if "fs" in enabled:
        f = cfg.get("fs") or {}
        root = f.get("root")
        if not root:
            raise ValueError("fs adapter enabled but adapters.fs.root is missing")
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
    if "tools" in enabled:
        t = cfg.get("tools") or {}
        allow_tools = t.get("allow_tools") or ["echo", "sum", "join"]
        tools = {
            "echo": lambda *a, context=None: a[0] if a else None,
            "sum": lambda a, b, context=None: int(a) + int(b),
            "join": lambda sep, arr, context=None: str(sep).join([str(x) for x in (arr or [])]),
        }
        reg.register("tools", ToolBridgeAdapter(tools, allow_tools=allow_tools))
    if "wasm" in enabled:
        w = cfg.get("wasm") or {}
        modules = w.get("modules") or {}
        if not isinstance(modules, dict) or not modules:
            raise ValueError("wasm adapter enabled but adapters.wasm.modules is missing or invalid")
        reg.register("wasm", WasmAdapter(modules=modules, allowed_modules=w.get("allow_modules")))
    return reg


def _caller_grant_from_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Build a caller-level grant from request fields."""
    grant = empty_grant()
    if req.get("allowed_adapters") is not None:
        grant["allowed_adapters"] = list(req["allowed_adapters"])
    caller_policy = req.get("policy")
    if isinstance(caller_policy, dict):
        for key in ("forbidden_adapters", "forbidden_effects",
                     "forbidden_effect_tiers", "forbidden_privilege_tiers"):
            vals = caller_policy.get(key)
            if vals:
                grant[key] = list(vals)
    caller_limits = req.get("limits")
    if isinstance(caller_limits, dict):
        grant["limits"] = {k: int(v) for k, v in caller_limits.items()
                           if isinstance(v, (int, float))}
    return grant


def _run_once(req: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    import datetime
    t0 = time.perf_counter()
    strict = bool(req.get("strict", True))
    ir = req.get("ir")
    code = req.get("code")
    if ir is None and not code:
        raise ValueError("request must include either 'code' or 'ir'")
    if ir is None:
        ir = _get_ir_from_code(str(code), strict=strict)

    # Merge server grant with caller request (restrictive-only).
    effective = merge_grants(_SERVER_GRANT, _caller_grant_from_request(req))
    effective_policy = grant_to_policy(effective)


    if effective_policy:
        policy_result = validate_ir_against_policy(ir, effective_policy)
        if not policy_result["ok"]:
            raise PolicyViolationError(policy_result["errors"])

    # Override request fields with effective grant values so _build_registry
    # and RuntimeEngine use the merged/restricted values.

    req = dict(req)
    req["allowed_adapters"] = grant_to_allowed_adapters(effective)
    req["limits"] = grant_to_limits(effective)

    _json_log(
        {
            "event": "run_start",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trace_id": trace_id,
            "replay_artifact_id": str(req.get("replay_artifact_id") or ""),
            "limits_summary": dict(req.get("limits") or {}),
            "policy_present": bool(effective_policy),
        }
    )

    reg = _build_registry(req)
    replay_artifact_id = str(req.get("replay_artifact_id") or "")
    per_adapter_durations = _instrument_registry(reg, trace_id=trace_id, replay_artifact_id=replay_artifact_id)
    eng = RuntimeEngine(
        ir=ir,
        adapters=reg,
        trace=bool(req.get("trace")),
        step_fallback=bool(req.get("step_fallback", True)),
        execution_mode=str(req.get("execution_mode") or "graph-preferred"),
        unknown_op_policy=req.get("unknown_op_policy"),
        limits=req["limits"],
        host_adapter_allowlist=req.get("allowed_adapters"),
    )
    label = str(req.get("label") or eng.default_entry_label())
    frame = req.get("frame") or {}
    out = eng.run_label(label, frame=frame)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

    calls = len(getattr(reg, "call_log", []))
    with _LOCK:
        _METRICS["runs_total"] += 1
        _METRICS["durations_ms"].append(elapsed_ms)
        _METRICS["adapter_calls_total"] += calls
        for adp, ds in per_adapter_durations.items():
            _METRICS["adapter_counts"][adp] = int(_METRICS["adapter_counts"].get(adp, 0)) + len(ds)
            _METRICS["adapter_durations_ms"].setdefault(adp, []).extend(ds)

    payload = {
        "ok": True,
        "trace_id": trace_id,
        "replay_artifact_id": replay_artifact_id,
        "label": label,
        "out": out,
        "runtime_version": eng.runtime_version,
        "ir_version": ir.get("ir_version"),
        "duration_ms": elapsed_ms,
    }
    if req.get("trace"):
        payload["trace"] = _redact_value(eng.trace_events)
    if hasattr(reg, "call_log"):
        payload["adapter_calls"] = _redact_value(getattr(reg, "call_log"))
    payload["adapter_p95_ms"] = {k: _p95(v) for k, v in per_adapter_durations.items()}

    for ev in eng.trace_events:
        _json_log(
            {
                "event": "runtime_op",
                "trace_id": trace_id,
                "replay_artifact_id": replay_artifact_id,
                "label": ev.get("label"),
                "op": ev.get("op"),
                "duration_ms": ev.get("duration_ms"),
                "lineno": ev.get("lineno"),
            }
        )

    _json_log(
        {
            "event": "run_complete",
            "trace_id": trace_id,
            "replay_artifact_id": replay_artifact_id,
            "label": label,
            "duration_ms": elapsed_ms,
            "adapter_calls": calls,
            "ok": True,
        }
    )
    return payload


def _run_guarded(req: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    try:
        return _run_once(req, trace_id=trace_id)
    except PolicyViolationError:
        raise
    except AinlRuntimeError as e:
        with _LOCK:
            _METRICS["runs_total"] += 1
            _METRICS["failures_total"] += 1
        replay_artifact_id = str(req.get("replay_artifact_id") or "")
        err = str(e)
        line_match = re.search(r"\[line=(\d+)", err)
        stack_match = re.search(r"stack=([^\]]+)", err)
        _json_log(
            {
                "event": "run_failed",
                "trace_id": trace_id,
                "replay_artifact_id": replay_artifact_id,
                "ok": False,
                "error": _redact_value(err),
                "line": int(line_match.group(1)) if line_match else None,
                "stack": stack_match.group(1) if stack_match else None,
            }
        )
        return {
            "ok": False,
            "trace_id": trace_id,
            "replay_artifact_id": replay_artifact_id,
            "error": _redact_value(err),
            "error_structured": e.to_dict(),
        }
    except Exception as e:
        with _LOCK:
            _METRICS["runs_total"] += 1
            _METRICS["failures_total"] += 1
        replay_artifact_id = str(req.get("replay_artifact_id") or "")
        err = str(e)
        line_match = re.search(r"\[line=(\d+)", err)
        stack_match = re.search(r"stack=([^\]]+)", err)
        _json_log(
            {
                "event": "run_failed",
                "trace_id": trace_id,
                "replay_artifact_id": replay_artifact_id,
                "ok": False,
                "error": _redact_value(err),
                "line": int(line_match.group(1)) if line_match else None,
                "stack": stack_match.group(1) if stack_match else None,
            }
        )
        return {"ok": False, "trace_id": trace_id, "replay_artifact_id": replay_artifact_id, "error": _redact_value(err)}


def _worker_loop() -> None:
    while not _STOP.is_set():
        try:
            job_id, req = _JOB_Q.get(timeout=0.2)
        except queue.Empty:
            continue
        trace_id = str(uuid.uuid4())
        _JOBS[job_id] = {"status": "running", "trace_id": trace_id}
        res = _run_guarded(req, trace_id=trace_id)
        _JOBS[job_id] = {"status": "done", "result": res, "trace_id": trace_id}
        _JOB_Q.task_done()


def _ensure_worker() -> None:
    global _WORKER
    if _WORKER is None or not _WORKER.is_alive():
        _STOP.clear()
        _WORKER = threading.Thread(target=_worker_loop, daemon=True)
        _WORKER.start()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Start background worker on application startup.
    _ensure_worker()
    try:
        yield
    finally:
    # Signal worker loop to stop on application shutdown.
        _STOP.set()


app = FastAPI(title="AINL Runtime Runner", version=RUNTIME_VERSION, lifespan=_lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"ready": True, "worker_alive": bool(_WORKER and _WORKER.is_alive())}


@app.get("/metrics")
def metrics():
    with _LOCK:
        durations = list(_METRICS["durations_ms"])
        return {
            "runs_total": _METRICS["runs_total"],
            "failures_total": _METRICS["failures_total"],
            "runs_per_sec_est": round((_METRICS["runs_total"] / max(1.0, sum(durations) / 1000.0)), 3) if durations else 0.0,
            "p95_duration_ms": _p95(durations),
            "adapter_calls_total": _METRICS["adapter_calls_total"],
            "adapter_counts": dict(_METRICS["adapter_counts"]),
            "adapter_p95_duration_ms": {k: _p95(v) for k, v in _METRICS["adapter_durations_ms"].items()},
            "compile_cache_hits": _METRICS["compile_cache_hits"],
            "compile_cache_misses": _METRICS["compile_cache_misses"],
            "queue_depth": _JOB_Q.qsize(),
            "adapter_capability_blocks_total": int(_METRICS.get("adapter_capability_blocks_total", 0)),
            "adapter_capability_blocks_by_adapter": dict(_METRICS.get("adapter_capability_blocks_by_adapter") or {}),
        }


def _load_capabilities() -> Dict[str, Any]:
    tooling_dir = Path(__file__).resolve().parent.parent / "tooling"
    manifest_path = tooling_dir / "adapter_manifest.json"
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}

    adapters = {}
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
        "host_security_env": {
            "AINL_SECURITY_PROFILE": "Named preset from tooling/security_profiles.json (replaces default grant when set).",
            "AINL_STRICT_MODE": "If true and AINL_SECURITY_PROFILE is unset, merge consumer_secure_default (or AINL_STRICT_PROFILE) with runner resource floors.",
            "AINL_STRICT_PROFILE": "Override profile name for AINL_STRICT_MODE (default consumer_secure_default).",
            "AINL_HOST_ADAPTER_ALLOWLIST": "Comma-separated: intersect IR adapters with this set.",
            "AINL_HOST_ADAPTER_DENYLIST": "Comma-separated: remove these adapters after allowlist intersection.",
            "AINL_ALLOW_IR_DECLARED_ADAPTERS": "If true, RuntimeEngine ignores AINL_HOST_ADAPTER_ALLOWLIST from the environment (IR-declared adapters allowed; denylist still applies).",
        },
    }


_CAPABILITIES_CACHE: Optional[Dict[str, Any]] = None


def _capabilities_langgraph() -> Dict[str, Any]:
    """Static descriptor for validate_ainl --emit langgraph (runner does not compile)."""
    return {
        "schema_version": "1.0",
        "emitter": "langgraph",
        "runtime_version": RUNTIME_VERSION,
        "summary": "LangGraph StateGraph wrapper module from compiled AINL IR.",
        "cli_example_strict": (
            "python3 scripts/validate_ainl.py --strict path/workflow.ainl --emit langgraph -o workflow_langgraph.py"
        ),
        "docs": ["docs/HYBRID_GUIDE.md", "examples/hybrid/README.md"],
        "emit_entrypoint": "scripts/emit_langgraph.py",
    }


def _capabilities_temporal() -> Dict[str, Any]:
    """Static descriptor for validate_ainl --emit temporal (runner does not compile)."""
    return {
        "schema_version": "1.0",
        "emitter": "temporal",
        "runtime_version": RUNTIME_VERSION,
        "summary": "Temporal activities + workflow Python modules from compiled AINL IR.",
        "cli_example_strict": (
            "python3 scripts/validate_ainl.py --strict path/workflow.ainl --emit temporal -o ./out/prefix"
        ),
        "docs": ["docs/HYBRID_GUIDE.md", "docs/hybrid_temporal.md", "examples/hybrid/README.md"],
        "emit_entrypoint": "scripts/emit_temporal.py",
    }


@app.get("/capabilities")
def capabilities():
    global _CAPABILITIES_CACHE
    if _CAPABILITIES_CACHE is None:
        _CAPABILITIES_CACHE = _load_capabilities()
    return _CAPABILITIES_CACHE


@app.get("/capabilities/langgraph")
def capabilities_langgraph():
    return _capabilities_langgraph()


@app.get("/capabilities/temporal")
def capabilities_temporal():
    return _capabilities_temporal()


@app.post("/run")
def run_sync(payload: Dict[str, Any]):
    trace_id = str(uuid.uuid4())
    try:
        return _run_guarded(payload, trace_id=trace_id)
    except PolicyViolationError as e:
        _json_log(
            {
                "event": "policy_rejected",
                "trace_id": trace_id,
                "replay_artifact_id": str(payload.get("replay_artifact_id") or ""),
                "ok": False,
                "violations": len(e.errors),
            }
        )
        raise HTTPException(
            status_code=403,
            detail={
                "ok": False,
                "trace_id": trace_id,
                "error": "policy_violation",
                "policy_errors": e.errors,
            },
        )


@app.post("/enqueue")
def enqueue(payload: Dict[str, Any]):
    _ensure_worker()
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "queued"}
    _JOB_Q.put((job_id, payload))
    return {"ok": True, "job_id": job_id}


@app.get("/result/{job_id}")
def result(job_id: str):
    item = _JOBS.get(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="job not found")
    return item


def main() -> None:
    import uvicorn

    uvicorn.run("scripts.runtime_runner_service:app", host="0.0.0.0", port=8770, reload=False)


if __name__ == "__main__":
    main()
