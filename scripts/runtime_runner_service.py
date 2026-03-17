#!/usr/bin/env python3
from __future__ import annotations

"""Runtime runner service for execution-oriented endpoints.

Contract boundary:
- This service exposes runtime execution APIs (`/run`, `/enqueue`, `/result`,
  `/health`, `/ready`, `/metrics`, `/capabilities`).
- It intentionally does not expose emitted product/business REST routes (for example `/api/products`, `/api/checkout`).
- UI/frontends expecting business routes should run against emitted app servers, not this runner.
"""

import hashlib
import json
import logging
import queue
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.replay import RecordingAdapterRegistry, ReplayAdapterRegistry
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.adapters.tools import ToolBridgeAdapter
from runtime.adapters.wasm import WasmAdapter
from runtime.engine import AinlRuntimeError, RuntimeEngine, RUNTIME_VERSION
from tooling.policy_validator import validate_ir_against_policy

logger = logging.getLogger("ainl.runner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(title="AINL Runtime Runner", version="1.0.0")

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


def _instrument_registry(reg: AdapterRegistry, trace_id: str, replay_artifact_id: str) -> Dict[str, List[float]]:
    per_adapter: Dict[str, List[float]] = {}
    original_call = reg.call

    def wrapped_call(adapter_name: str, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t0 = time.perf_counter()
        try:
            return original_call(adapter_name, target, args, context)
        finally:
            dt = round((time.perf_counter() - t0) * 1000, 3)
            per_adapter.setdefault(adapter_name, []).append(dt)
            _json_log(
                {
                    "event": "adapter_call",
                    "trace_id": trace_id,
                    "replay_artifact_id": replay_artifact_id,
                    "adapter": adapter_name,
                    "verb": target,
                    "duration_ms": dt,
                    "args": _redact_value(list(args or [])),
                }
            )

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
    allowed = req.get("allowed_adapters") or ["core", "ext", "http", "sqlite", "fs", "tools", "cache", "queue", "txn", "auth", "wasm"]
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


def _run_once(req: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    strict = bool(req.get("strict", True))
    ir = req.get("ir")
    code = req.get("code")
    if ir is None and not code:
        raise ValueError("request must include either 'code' or 'ir'")
    if ir is None:
        ir = _get_ir_from_code(str(code), strict=strict)

    policy = req.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            raise ValueError("'policy' must be a JSON object")
        policy_result = validate_ir_against_policy(ir, policy)
        if not policy_result["ok"]:
            raise PolicyViolationError(policy_result["errors"])

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
        limits=req.get("limits") or {},
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


@app.on_event("startup")
def _startup() -> None:
    _ensure_worker()


@app.on_event("shutdown")
def _shutdown() -> None:
    _STOP.set()


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
        }

    return {
        "schema_version": "1.0",
        "runtime_version": RUNTIME_VERSION,
        "policy_support": True,
        "adapters": adapters,
    }


_CAPABILITIES_CACHE: Optional[Dict[str, Any]] = None


@app.get("/capabilities")
def capabilities():
    global _CAPABILITIES_CACHE
    if _CAPABILITIES_CACHE is None:
        _CAPABILITIES_CACHE = _load_capabilities()
    return _CAPABILITIES_CACHE


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
