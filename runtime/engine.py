from __future__ import annotations
import uuid

import json
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from compiler_v2 import (
    AICodeCompiler,
    runtime_canonicalize_r_step,
    runtime_normalize_label_id,
    runtime_normalize_node_id,
)
from runtime.values import compare, deep_get, deep_put, json_safe, stable_sort, truthy
from runtime.adapters.base import AdapterRegistry, AdapterError
from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.observability import RuntimeObservability


class AinlRuntimeError(RuntimeError):
    """Structured runtime error with stable schema for agent consumption."""

    def __init__(
        self,
        message: str,
        label: str,
        step_index: int,
        op: str,
        stack: List[str],
        code: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        # Preserve existing string format for backwards compatibility.
        super().__init__(f"{message} [label={label} step={step_index} op={op} stack={'->'.join(stack)}]")
        self.label = label
        self.step_index = step_index
        self.op = op
        self.stack = list(stack)
        # Machine-readable extensions.
        self.code = code or "AINL_RUNTIME_ERROR"
        self.data = dict(data or {})

    def to_dict(self) -> Dict[str, Any]:
        """Return a stable, machine-readable error envelope."""
        return {
            "code": self.code,
            "message": str(self),
            "label": self.label,
            "step_index": self.step_index,
            "op": self.op,
            "stack": list(self.stack),
            "data": dict(self.data or {}),
        }


def _norm_lid(tgt: Any) -> str:
    return runtime_normalize_label_id(tgt)


def _norm_node_id(tok: Any) -> Optional[str]:
    return runtime_normalize_node_id(tok)


SUPPORTED_IR_MAJOR = 1
RUNTIME_VERSION = "1.4.5"


def _parse_host_csv_env(name: str) -> Optional[List[str]]:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def _fallback_adapters_from_label_steps(ir: Dict[str, Any]) -> List[str]:
    """Infer adapters from label steps when avm metadata is missing or incomplete.

    Matches compiler ``_compute_avm_policy_fragment`` / ``_iter_all_steps`` so
    ``QueuePut``/``Cache*`` ops still enable ``queue``/``cache`` capabilities.
    """
    found: Set[str] = set()
    labels = ir.get("labels") or {}
    for _lid, body in labels.items():
        if not isinstance(body, dict):
            continue
        legacy = (body.get("legacy") or {})
        for step in (legacy.get("steps") or []):
            if not isinstance(step, dict):
                continue
            op = str(step.get("op") or "").strip()
            if op == "QueuePut":
                found.add("queue")
            elif op in ("CacheGet", "CacheSet"):
                found.add("cache")
            elif op == "R":
                adapter = str(step.get("adapter") or "").strip()
                if adapter:
                    found.add(adapter.split(".", 1)[0].lower())
    return sorted(found)


def _allowed_adapter_names_from_ir(ir: Dict[str, Any]) -> List[str]:
    """Adapter names allowed through [`AdapterRegistry`] for this IR.

    Explicit ``capabilities.allow`` wins if present. Otherwise use the compiler's
    ``execution_requirements.required_capabilities`` or ``avm_policy_fragment.allowed_adapters``
    (derived from ``R`` steps). Without this, the default would be only ``["core"]``, which
    blocks any ``R web ...``, ``R cache ...``, etc. even though the graph references them.
    """
    caps = ir.get("capabilities") or {}
    cap_allow = caps.get("allow")
    if isinstance(cap_allow, list) and cap_allow:
        out = [str(x) for x in cap_allow if x is not None]
        return out if out else ["core"]

    exec_req = ir.get("execution_requirements") or {}
    req = exec_req.get("required_capabilities")
    base: List[str]
    if isinstance(req, list) and req:
        base = [str(x) for x in req if x is not None]
        base = base if base else ["core"]
    else:
        avm = ir.get("avm_policy_fragment") or {}
        aa = avm.get("allowed_adapters")
        if isinstance(aa, list) and aa:
            base = [str(x) for x in aa if x is not None]
            base = base if base else ["core"]
        else:
            base = ["core"]

    extra = _fallback_adapters_from_label_steps(ir)
    if not extra:
        return base
    return sorted(set(base) | set(extra))

# Stable, machine-readable runtime error codes for agents.
ERROR_CODE_MAX_DEPTH = "RUNTIME_MAX_DEPTH"
ERROR_CODE_MAX_STEPS = "RUNTIME_MAX_STEPS"
ERROR_CODE_MAX_TIME = "RUNTIME_MAX_TIME"
ERROR_CODE_MAX_FRAME_BYTES = "RUNTIME_MAX_FRAME_BYTES"
ERROR_CODE_MAX_ADAPTER_CALLS = "RUNTIME_MAX_ADAPTER_CALLS"
ERROR_CODE_X_MISSING_DST = "RUNTIME_X_MISSING_DST"
ERROR_CODE_X_UNKNOWN_FN = "RUNTIME_X_UNKNOWN_FN"
ERROR_CODE_UNSUPPORTED_IR_VERSION = "RUNTIME_UNSUPPORTED_IR_VERSION"
ERROR_CODE_UNKNOWN_OP = "RUNTIME_UNKNOWN_OP"
ERROR_CODE_GRAPH_AMBIGUOUS_NEXT = "RUNTIME_GRAPH_AMBIGUOUS_NEXT"
ERROR_CODE_GRAPH_ONLY_REQUIRES_GRAPH = "RUNTIME_GRAPH_ONLY_REQUIRES_GRAPH"
ERROR_CODE_MAX_LOOP_ITERS = "RUNTIME_MAX_LOOP_ITERS"
ERROR_CODE_WHILE_LIMIT = "RUNTIME_WHILE_LIMIT"
ERROR_CODE_ERR_HANDLER_RECURSION = "RUNTIME_ERR_HANDLER_RECURSION"
ERROR_CODE_GRAPH_EXEC_GUARD = "RUNTIME_GRAPH_EXEC_GUARD"
ERROR_CODE_ADAPTER_ERROR = "RUNTIME_ADAPTER_ERROR"
ERROR_CODE_RUNTIME_OP_ERROR = "RUNTIME_OP_ERROR"


class RuntimeEngine:
    def __init__(
        self,
        ir: Dict[str, Any],
        adapters: Optional[AdapterRegistry] = None,
        trace: bool = False,
        step_fallback: bool = True,
        limits: Optional[Dict[str, Any]] = None,
        execution_mode: str = "graph-preferred",
        unknown_op_policy: Optional[str] = None,
        trace_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        trajectory_log_path: Optional[str] = None,
        avm_event_hasher: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
        sandbox_metadata_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        runtime_async: bool = False,
        observability: bool = False,
        observability_jsonl_path: Optional[str] = None,
        host_adapter_allowlist: Optional[List[str]] = None,
        host_adapter_denylist: Optional[List[str]] = None,
    ):
        self.ir = ir
        self.labels = ir.get("labels", {})
        self.trace_enabled = trace
        self.step_fallback = step_fallback
        runtime_policy = ir.get("runtime_policy") or {}
        self.execution_mode = execution_mode or runtime_policy.get("execution_mode") or "graph-preferred"
        self.unknown_op_policy = (
            unknown_op_policy
            or runtime_policy.get("unknown_op_policy")
            or ("error" if self.execution_mode == "graph-only" else "skip")
        )
        self.trace_events: List[Dict[str, Any]] = []
        self.trace_sink = trace_sink
        self._trajectory_log_path: Optional[str] = trajectory_log_path
        # Optional AVM hook: append AVM hash when an AVM daemon shim is connected.
        self._avm_event_hasher = avm_event_hasher
        self._sandbox_metadata_provider = sandbox_metadata_provider
        self._trajectory_seq: int = 0
        self._trace_lineno: Optional[int] = None
        self.runtime_version = RUNTIME_VERSION
        env_async = str(os.environ.get("AINL_RUNTIME_ASYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
        self.runtime_async = bool(runtime_async or env_async)
        self.observability = RuntimeObservability.from_env_or_flag(observability, jsonl_path=observability_jsonl_path)
        self.limits = limits or {}
        self._run_started_at: float = 0.0
        self._steps_executed: int = 0
        self._adapter_calls: int = 0
        effective_host = host_adapter_allowlist
        if effective_host is None:
            # When set, ignore AINL_HOST_ADAPTER_ALLOWLIST from the environment so graphs may use
            # any adapter referenced in the IR (OpenClaw / IDE hosts sometimes export a narrow list).
            _relax_env_allowlist = str(os.environ.get("AINL_ALLOW_IR_DECLARED_ADAPTERS") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            if not _relax_env_allowlist:
                raw = str(os.environ.get("AINL_HOST_ADAPTER_ALLOWLIST") or "").strip()
                if raw:
                    effective_host = [x.strip() for x in raw.split(",") if x.strip()]
        allowed = _allowed_adapter_names_from_ir(ir)
        if effective_host is not None:
            host_set = set(effective_host)
            allowed = [a for a in allowed if a in host_set]
        effective_deny = host_adapter_denylist
        if effective_deny is None:
            effective_deny = _parse_host_csv_env("AINL_HOST_ADAPTER_DENYLIST")
        if effective_deny:
            deny_set = set(effective_deny)
            allowed = [a for a in allowed if a not in deny_set]
        if adapters is not None:
            self.adapters = adapters
            for name in allowed:
                self.adapters.allow(name)
        else:
            self.adapters = AdapterRegistry(allowed=allowed)
        # Ensure core stdlib exists for MVP.
        self.adapters.register("core", CoreBuiltinAdapter())
        self._ensure_optional_adapters_registered(allowed)
        self._source_lines = (ir.get("source") or {}).get("lines", []) or []
        self._cst_by_line = {ln.get("lineno"): ln for ln in ((ir.get("cst") or {}).get("lines") or []) if isinstance(ln, dict)}
        self._validate_ir_version()

    def _ensure_optional_adapters_registered(self, allowed: List[str]) -> None:
        """Register adapters referenced by the IR when missing (minimal `ainl serve` / no CLI registry)."""
        need = set(allowed)
        reg = self.adapters
        try:
            if "web" in need and "web" not in reg:
                from adapters.openclaw_integration import WebAdapter

                reg.register("web", WebAdapter())
            if "tiktok" in need and "tiktok" not in reg:
                from adapters.openclaw_integration import TiktokAdapter

                reg.register("tiktok", TiktokAdapter())
            if "queue" in need and "queue" not in reg:
                from adapters.openclaw_integration import NotificationQueueAdapter

                reg.register("queue", NotificationQueueAdapter())
            if "cache" in need and "cache" not in reg:
                from adapters.local_cache import LocalFileCacheAdapter

                reg.register("cache", LocalFileCacheAdapter())
            if "memory" in need and "memory" not in reg:
                from pathlib import Path

                from runtime.adapters.memory import MemoryAdapter

                mem_db = (
                    str(os.environ.get("AINL_MEMORY_DB") or "").strip()
                    or str(Path.home() / ".openclaw" / "ainl_memory.sqlite3")
                )
                reg.register("memory", MemoryAdapter(db_path=mem_db))
        except Exception:
            pass

    @classmethod
    def from_code(
        cls,
        code: str,
        strict: bool = False,
        strict_reachability: bool = False,
        trace: bool = False,
        adapters: Optional[AdapterRegistry] = None,
        step_fallback: bool = True,
        limits: Optional[Dict[str, Any]] = None,
        execution_mode: str = "graph-preferred",
        unknown_op_policy: Optional[str] = None,
        trace_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        source_path: Optional[str] = None,
        trajectory_log_path: Optional[str] = None,
        avm_event_hasher: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
        sandbox_metadata_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        runtime_async: bool = False,
        observability: bool = False,
        observability_jsonl_path: Optional[str] = None,
        host_adapter_allowlist: Optional[List[str]] = None,
        host_adapter_denylist: Optional[List[str]] = None,
    ) -> "RuntimeEngine":
        if source_path:
            try:
                from pathlib import Path as _Path

                if "intelligence" in _Path(source_path).resolve().parts:
                    # Intelligence graphs (e.g. intelligence_digest.lang) declare web/tiktok/queue in IR.
                    # Scheduled hosts may set AINL_ALLOW_IR_DECLARED_ADAPTERS=0 from manifest while still
                    # exporting a narrow AINL_HOST_ADAPTER_ALLOWLIST — that would strip `web` and fail at
                    # runtime. Default: always honor IR-declared adapters for paths under .../intelligence/.
                    # Operators can force strict host policy with AINL_INTELLIGENCE_FORCE_HOST_POLICY=1.
                    _intel_strict = str(
                        os.environ.get("AINL_INTELLIGENCE_FORCE_HOST_POLICY") or ""
                    ).strip().lower() in {"1", "true", "yes", "on"}
                    if not _intel_strict:
                        os.environ["AINL_ALLOW_IR_DECLARED_ADAPTERS"] = "1"
            except Exception:
                pass
        c = AICodeCompiler(strict_mode=strict, strict_reachability=strict_reachability)
        ir = c.compile(code, emit_graph=True, source_path=source_path)
        if ir.get("errors"):
            raise RuntimeError("compile failed: " + "; ".join(ir.get("errors", [])[:5]))
        return cls(
            ir=ir,
            adapters=adapters,
            trace=trace,
            step_fallback=step_fallback,
            limits=limits,
            execution_mode=execution_mode,
            unknown_op_policy=unknown_op_policy,
            trace_sink=trace_sink,
            trajectory_log_path=trajectory_log_path,
            avm_event_hasher=avm_event_hasher,
            sandbox_metadata_provider=sandbox_metadata_provider,
            runtime_async=runtime_async,
            observability=observability,
            observability_jsonl_path=observability_jsonl_path,
            host_adapter_allowlist=host_adapter_allowlist,
            host_adapter_denylist=host_adapter_denylist,
        )

    @classmethod
    def run(
        cls,
        code: str,
        frame: Optional[Dict[str, Any]] = None,
        *,
        label: Optional[str] = None,
        strict: bool = False,
        strict_reachability: bool = False,
        trace: bool = False,
        adapters: Optional[AdapterRegistry] = None,
        step_fallback: bool = True,
        execution_mode: str = "graph-preferred",
        unknown_op_policy: Optional[str] = None,
        limits: Optional[Dict[str, Any]] = None,
        trace_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        runtime_async: bool = False,
        observability: bool = False,
        observability_jsonl_path: Optional[str] = None,
        host_adapter_allowlist: Optional[List[str]] = None,
        host_adapter_denylist: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        eng = cls.from_code(
            code,
            strict=strict,
            strict_reachability=strict_reachability,
            trace=trace,
            adapters=adapters,
            step_fallback=step_fallback,
            execution_mode=execution_mode,
            unknown_op_policy=unknown_op_policy,
            limits=limits,
            trace_sink=trace_sink,
            runtime_async=runtime_async,
            observability=observability,
            observability_jsonl_path=observability_jsonl_path,
            host_adapter_allowlist=host_adapter_allowlist,
            host_adapter_denylist=host_adapter_denylist,
        )
        try:
            lid = label or eng.default_entry_label()
            if eng.runtime_async:
                result = asyncio.run(eng.run_label_async(lid, frame=frame or {}))
            else:
                result = eng.run_label(lid, frame=frame or {})
            payload = {"ok": True, "label": str(lid), "result": result, "runtime_version": eng.runtime_version}
            if trace:
                payload["trace"] = eng.trace_events
            return payload
        finally:
            eng.close()

    def close(self) -> None:
        try:
            self.observability.close()
        except Exception:
            pass

    def _steps(self, label_id: str) -> List[Dict[str, Any]]:
        b = self.labels.get(label_id, {})
        leg = b.get("legacy", {})
        if "steps" in leg:
            return leg.get("steps", [])
        return b.get("steps", [])

    def _limit_int(self, key: str) -> Optional[int]:
        raw = self.limits.get(key)
        if raw is None:
            return None
        try:
            v = int(raw)
            return v if v > 0 else None
        except Exception:
            return None

    def _start_run(self) -> None:
        self._run_started_at = time.perf_counter()
        self._steps_executed = 0
        self._adapter_calls = 0
        self._trajectory_seq = 0

    def _guard_depth(self, stack: List[str]) -> None:
        lim = self._limit_int("max_depth")
        if lim is not None and len(stack) > lim:
            raise AinlRuntimeError(
                "max_depth exceeded",
                stack[-1] if stack else "?",
                0,
                "CALL",
                stack,
                code=ERROR_CODE_MAX_DEPTH,
            )

    def _guard_tick(self, lid: str, idx: int, op: str, stack: List[str], frame: Dict[str, Any]) -> None:
        self._steps_executed += 1
        max_steps = self._limit_int("max_steps")
        if max_steps is not None and self._steps_executed > max_steps:
            raise AinlRuntimeError("max_steps exceeded", lid, idx, op, stack, code=ERROR_CODE_MAX_STEPS)
        max_time_ms = self._limit_int("max_time_ms")
        if max_time_ms is not None and self._run_started_at > 0:
            elapsed_ms = int((time.perf_counter() - self._run_started_at) * 1000)
            if elapsed_ms > max_time_ms:
                raise AinlRuntimeError("max_time_ms exceeded", lid, idx, op, stack, code=ERROR_CODE_MAX_TIME)
        max_frame_bytes = self._limit_int("max_frame_bytes")
        if max_frame_bytes is not None:
            try:
                frame_bytes = len(json.dumps(json_safe(frame), ensure_ascii=False).encode("utf-8"))
            except Exception:
                frame_bytes = len(repr(frame).encode("utf-8"))
            if frame_bytes > max_frame_bytes:
                raise AinlRuntimeError("max_frame_bytes exceeded", lid, idx, op, stack, code=ERROR_CODE_MAX_FRAME_BYTES)

    def _count_adapter_call(self, lid: str, idx: int, op: str, stack: List[str]) -> None:
        self._adapter_calls += 1
        lim = self._limit_int("max_adapter_calls")
        if lim is not None and self._adapter_calls > lim:
            raise AinlRuntimeError("max_adapter_calls exceeded", lid, idx, op, stack, code=ERROR_CODE_MAX_ADAPTER_CALLS)

    def _record_reactive_metrics(self, adapter_name: str, target: str, result: Any) -> None:
        if not self.observability.enabled:
            return
        a = str(adapter_name or "").lower()
        t = str(target or "").lower()
        labels = {"adapter": a, "target": t}
        # Batch event counts for reactive subscriptions.
        if a == "dynamodb" and t == "streams_subscribe":
            events = result.get("events") if isinstance(result, dict) else None
            if isinstance(events, list):
                self.observability.emit("reactive.events_per_batch", len(events), labels=labels)
                if events:
                    seq = (((events[-1] or {}).get("dynamodb") or {}).get("SequenceNumber"))
                    self.observability.sequence_gap("dynamodb:streams", seq, labels=labels)
        elif a == "supabase" and t == "realtime_subscribe":
            events = None
            if isinstance(result, dict):
                inner = result.get("result")
                if isinstance(inner, dict):
                    events = inner.get("events")
            if isinstance(events, list):
                self.observability.emit("reactive.events_per_batch", len(events), labels=labels)
                if events:
                    ts = (events[-1] or {}).get("timestamp")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                            lag_s = max(0.0, time.time() - dt.timestamp())
                            self.observability.emit("reactive.lag_seconds", round(lag_s, 6), labels=labels)
                        except Exception:
                            pass
                    seq = (events[-1] or {}).get("sequence")
                    self.observability.sequence_gap("supabase:realtime", seq, labels=labels)
        elif a == "redis" and t == "subscribe":
            messages = result.get("messages") if isinstance(result, dict) else None
            if isinstance(messages, list):
                self.observability.emit("reactive.events_per_batch", len(messages), labels=labels)

    def _resolve(self, token: Any, frame: Dict[str, Any]) -> Any:
        if isinstance(token, str):
            if token.startswith("$"):
                return frame.get(token[1:])
            if token in frame:
                return frame[token]
            if token == "true":
                return True
            if token == "false":
                return False
            if token == "null":
                return None
            if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
                try:
                    return int(token)
                except Exception:
                    return token
            s = token.strip()
            s2 = s[1:] if s.startswith("-") else s
            try:
                if "." in s2 and s2.replace(".", "", 1).isdigit():
                    return float(s)
            except Exception:
                pass
            try:
                if any(ch in s2 for ch in ("e", "E")):
                    return float(s)
            except Exception:
                pass
        return token

    def _eval_cond(self, cond: Any, frame: Dict[str, Any]) -> bool:
        """Match compiler_v2 condition token semantics: var, var?, var=value."""
        if cond is None:
            return False
        if not isinstance(cond, str):
            return truthy(self._resolve(cond, frame))
        s = cond.strip()
        if not s:
            return False
        if s.endswith("?"):
            return self._resolve(s[:-1], frame) is not None
        if "=" in s:
            var, val = s.split("=", 1)
            left = self._resolve(var.strip(), frame)
            right = self._resolve(val.strip(), frame)
            return str(left) == str(right)
        return truthy(self._resolve(s, frame))

    def _exec_x(self, step: Dict[str, Any], frame: Dict[str, Any], lid: str, idx: int, stack: List[str]) -> Any:
        dst = step.get("dst")
        if not dst:
            raise AinlRuntimeError("X missing destination variable", lid, idx, "X", stack, code=ERROR_CODE_X_MISSING_DST)
        fn = (step.get("fn") or "").strip()
        args = [self._resolve(a, frame) for a in (step.get("args") or [])]
        if fn == "add":
            frame[dst] = (args[0] if len(args) > 0 else 0) + (args[1] if len(args) > 1 else 0)
        elif fn == "sub":
            frame[dst] = (args[0] if len(args) > 0 else 0) - (args[1] if len(args) > 1 else 0)
        elif fn == "mul":
            frame[dst] = (args[0] if len(args) > 0 else 0) * (args[1] if len(args) > 1 else 0)
        elif fn == "div":
            b = args[1] if len(args) > 1 else 1
            frame[dst] = (args[0] if len(args) > 0 else 0) / b
        elif fn == "len":
            frame[dst] = len(args[0]) if args else 0
        elif fn == "get":
            frame[dst] = deep_get(args[0], str(args[1])) if len(args) >= 2 else None
        elif fn == "put":
            frame[dst] = deep_put(args[0], str(args[1]), args[2]) if len(args) >= 3 else args[0]
        elif fn == "push":
            arr = list(args[0]) if args and isinstance(args[0], list) else []
            if len(args) > 1:
                arr.append(args[1])
            frame[dst] = arr
        elif fn == "obj":
            obj = {}
            if len(args) >= 2:
                obj[str(args[0])] = args[1]
            frame[dst] = obj
        elif fn == "arr":
            frame[dst] = list(args)
        elif fn == "eq":
            frame[dst] = (args[0] if len(args) > 0 else None) == (args[1] if len(args) > 1 else None)
        elif fn == "ne":
            frame[dst] = (args[0] if len(args) > 0 else None) != (args[1] if len(args) > 1 else None)
        elif fn == "lt":
            frame[dst] = (args[0] if len(args) > 0 else None) < (args[1] if len(args) > 1 else None)
        elif fn == "lte":
            frame[dst] = (args[0] if len(args) > 0 else None) <= (args[1] if len(args) > 1 else None)
        elif fn == "gt":
            frame[dst] = (args[0] if len(args) > 0 else None) > (args[1] if len(args) > 1 else None)
        elif fn == "gte":
            frame[dst] = (args[0] if len(args) > 0 else None) >= (args[1] if len(args) > 1 else None)
        elif fn == "and":
            frame[dst] = truthy(args[0] if len(args) > 0 else False) and truthy(args[1] if len(args) > 1 else False)
        elif fn == "or":
            frame[dst] = truthy(args[0] if len(args) > 0 else False) or truthy(args[1] if len(args) > 1 else False)
        elif fn == "not":
            frame[dst] = not truthy(args[0] if len(args) > 0 else False)
        elif fn == "ite" or fn == "if":
            # ite cond then_val else_val
            frame[dst] = (args[1] if len(args) > 1 else None) if truthy(args[0] if len(args) > 0 else False) else (args[2] if len(args) > 2 else None)
        elif fn.startswith("core."):
            # Support core.* functions in X expressions
            sub_fn = fn[5:]  # strip "core."
            if sub_fn == "concat":
                frame[dst] = "".join(str(a) for a in args)
            elif sub_fn == "len":
                frame[dst] = len(args[0]) if args else 0
            elif sub_fn == "add":
                frame[dst] = (args[0] if len(args) > 0 else 0) + (args[1] if len(args) > 1 else 0)
            elif sub_fn == "sub":
                frame[dst] = (args[0] if len(args) > 0 else 0) - (args[1] if len(args) > 1 else 0)
            elif sub_fn == "mul":
                frame[dst] = (args[0] if len(args) > 0 else 0) * (args[1] if len(args) > 1 else 0)
            elif sub_fn == "div":
                b = args[1] if len(args) > 1 else 1
                frame[dst] = (args[0] if len(args) > 0 else 0) / b
            elif sub_fn == "gt":
                frame[dst] = (args[0] if len(args) > 0 else None) > (args[1] if len(args) > 1 else None)
            elif sub_fn == "gte":
                frame[dst] = (args[0] if len(args) > 0 else None) >= (args[1] if len(args) > 1 else None)
            elif sub_fn == "lt":
                frame[dst] = (args[0] if len(args) > 0 else None) < (args[1] if len(args) > 1 else None)
            elif sub_fn == "lte":
                frame[dst] = (args[0] if len(args) > 0 else None) <= (args[1] if len(args) > 1 else None)
            elif sub_fn == "eq":
                frame[dst] = (args[0] if len(args) > 0 else None) == (args[1] if len(args) > 1 else None)
            elif sub_fn == "ne":
                frame[dst] = (args[0] if len(args) > 0 else None) != (args[1] if len(args) > 1 else None)
            elif sub_fn == "join":
                delim = str(args[0]) if args else ""
                arr = args[1] if len(args) > 1 and isinstance(args[1], list) else args[1:]
                frame[dst] = delim.join(str(x) for x in (arr if isinstance(arr, list) else [arr]))
            elif sub_fn == "or":
                frame[dst] = truthy(args[0] if len(args) > 0 else False) or truthy(args[1] if len(args) > 1 else False)
            elif sub_fn == "and":
                frame[dst] = truthy(args[0] if len(args) > 0 else False) and truthy(args[1] if len(args) > 1 else False)
            elif sub_fn == "not":
                frame[dst] = not truthy(args[0] if len(args) > 0 else False)
            elif sub_fn == "min":
                frame[dst] = min(args) if args else 0
            elif sub_fn == "max":
                frame[dst] = max(args) if args else 0
            elif sub_fn == "clamp":
                x = float(args[0]) if args else 0
                lo = float(args[1]) if len(args) > 1 else 0
                hi = float(args[2]) if len(args) > 2 else x
                frame[dst] = max(lo, min(hi, x))
            elif sub_fn == "idiv":
                b = args[1] if len(args) > 1 else 1
                frame[dst] = int((args[0] if args else 0) // b) if b else 0
            elif sub_fn == "lower":
                frame[dst] = str(args[0]).lower() if args else ""
            elif sub_fn == "upper":
                frame[dst] = str(args[0]).upper() if args else ""
            elif sub_fn == "trim":
                frame[dst] = str(args[0]).strip() if args else ""
            elif sub_fn == "stringify":
                import json as _json
                frame[dst] = _json.dumps(args[0], ensure_ascii=False) if args else ""
            elif sub_fn == "parse":
                import json as _json
                frame[dst] = _json.loads(str(args[0])) if args else None
            elif sub_fn == "split":
                frame[dst] = str(args[0]).split(str(args[1])) if len(args) > 1 else str(args[0]).split() if args else []
            elif sub_fn == "replace":
                frame[dst] = str(args[0]).replace(str(args[1]), str(args[2])) if len(args) > 2 else str(args[0])
            elif sub_fn == "contains":
                frame[dst] = str(args[1]) in str(args[0]) if len(args) > 1 else False
            elif sub_fn == "now":
                import time as _time
                frame[dst] = int(_time.time())
            elif sub_fn == "iso":
                import time as _time
                frame[dst] = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            elif sub_fn == "substr":
                s = str(args[0]) if args else ""
                start = int(args[1]) if len(args) > 1 and args[1] is not None else 0
                length = int(args[2]) if len(args) > 2 and args[2] is not None else max(0, len(s) - start)
                start = max(0, start)
                length = max(0, length)
                frame[dst] = s[start : start + length]
            elif sub_fn == "env":
                import os as _os
                name = str(args[0]) if args else ""
                default = None if len(args) < 2 else args[1]
                frame[dst] = _os.environ.get(name, default) if name else None
            else:
                # Fall through to adapter call for any other core.* function
                try:
                    result = self.adapters.call("core", sub_fn, args, frame)
                    frame[dst] = result
                except Exception:
                    raise AinlRuntimeError(f"unknown core fn: {sub_fn}", lid, idx, "X", stack, code=ERROR_CODE_X_UNKNOWN_FN)
        else:
            raise AinlRuntimeError(f"unknown X fn: {fn}", lid, idx, "X", stack, code=ERROR_CODE_X_UNKNOWN_FN)
        return frame.get(dst)

    def _trajectory_inputs_payload(
        self, trajectory_step: Optional[Dict[str, Any]], node_id: Optional[str]
    ) -> Any:
        if trajectory_step is not None and node_id is not None:
            return json_safe({"node_id": node_id, "step": dict(trajectory_step)})
        if trajectory_step is not None:
            return json_safe(trajectory_step)
        if node_id is not None:
            return json_safe({"node_id": node_id})
        return None

    def _emit_trajectory(
        self,
        *,
        label: str,
        operation: str,
        frame: Dict[str, Any],
        output: Any,
        outcome: str,
        trajectory_step: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> None:
        path = self._trajectory_log_path
        if not path:
            return
        sid = self._trajectory_seq
        self._trajectory_seq += 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        rec = {
            "step_id": sid,
            "label": label,
            "operation": operation,
            "inputs": self._trajectory_inputs_payload(trajectory_step, node_id),
            "output": json_safe(output),
            "outcome": outcome,
            "timestamp": ts,
            "user_reward": json_safe(frame.get("_trajectory_user_reward")),
        }
        if self._avm_event_hasher is not None:
            rec["avm_event_hash"] = self._avm_event_hasher(rec)
        if self._sandbox_metadata_provider is not None:
            rec.update(self._sandbox_metadata_provider() or {})
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _emit_trajectory_fail(
        self,
        lid: str,
        op: str,
        frame: Dict[str, Any],
        step: Dict[str, Any],
        err: Exception,
        *,
        node_id: Optional[str] = None,
    ) -> None:
        if not self._trajectory_log_path:
            return
        self._emit_trajectory(
            label=lid,
            operation=op,
            frame=frame,
            output={"error": str(err), "type": type(err).__name__},
            outcome="fail",
            trajectory_step=step,
            node_id=node_id,
        )

    def _emit_trace(
        self,
        label: str,
        op: str,
        idx: int,
        start: float,
        frame: Dict[str, Any],
        out: Any = None,
        *,
        node_id: Optional[str] = None,
        port_taken: Optional[str] = None,
        edge_taken: Optional[Dict[str, Any]] = None,
        branch: Optional[Dict[str, Any]] = None,
        err_routed: Optional[bool] = None,
        retry_attempt: Optional[Dict[str, Any]] = None,
        trajectory_step: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.trace_enabled:
            event = {
                "label": label,
                "op": op,
                "step": idx,
                "lineno": self._trace_lineno,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                "out": json_safe(out),
                "frame_keys": sorted(list(frame.keys())),
            }
            if node_id is not None:
                event["node_id"] = node_id
            if port_taken is not None:
                event["port_taken"] = port_taken
            if edge_taken is not None:
                event["edge_taken"] = dict(edge_taken)
            if branch is not None:
                event["branch"] = dict(branch)
            if err_routed is not None:
                event["err_routed"] = err_routed
            if retry_attempt is not None:
                event["retry_attempt"] = dict(retry_attempt)
            self.trace_events.append(event)
            if self.trace_sink is not None:
                self.trace_sink(event)
        if self._trajectory_log_path:
            self._emit_trajectory(
                label=label,
                operation=op,
                frame=frame,
                output=out,
                outcome="success",
                trajectory_step=trajectory_step,
                node_id=node_id,
            )

    def _validate_ir_version(self) -> None:
        v = str(self.ir.get("ir_version") or "1.0")
        try:
            major = int(v.split(".", 1)[0])
        except Exception:
            major = SUPPORTED_IR_MAJOR
        if major != SUPPORTED_IR_MAJOR:
            raise AinlRuntimeError(
                f"unsupported ir_version={v}; supported major={SUPPORTED_IR_MAJOR}",
                "?",
                0,
                "IR",
                [],
                code=ERROR_CODE_UNSUPPORTED_IR_VERSION,
            )

    def _handle_unknown_op(self, lid: str, idx: int, op: str, stack: List[str], frame: Dict[str, Any], *, mode: str) -> None:
        if self.unknown_op_policy == "error":
            raise AinlRuntimeError(
                f"unknown op in {mode} mode: {op}",
                lid,
                idx,
                op,
                stack,
                code=ERROR_CODE_UNKNOWN_OP,
            )

    def _exec_r_call(
        self, adapter: str, target: str, args: List[Any], frame: Dict[str, Any], lid: str, idx: int, op: str, stack: List[str]
    ) -> Any:
        self._count_adapter_call(lid, idx, op, stack)
        started = time.perf_counter()
        if "." in adapter:
            adp_name, verb = adapter.split(".", 1)
            # Graph-mode R steps put the first operand in `target` without pre-resolving; step-mode
            # does the same via _exec_r_step. Resolve here so frame variables (e.g. core.PARSE var)
            # work consistently with JSON literals that pass through _resolve unchanged.
            t0 = self._resolve(target, frame) if isinstance(target, str) else target
            call_ctx = dict(frame)
            call_ctx["_runtime_async"] = self.runtime_async
            call_ctx["_observability"] = self.observability
            call_ctx["_adapter_registry"] = self.adapters
            try:
                out = self.adapters.call(adp_name, verb, [t0] + args, call_ctx)
                return out
            finally:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                self.observability.emit(
                    "adapter.call.duration_ms",
                    duration_ms,
                    labels={"adapter": adp_name, "target": verb},
                )
                if "out" in locals():
                    self._record_reactive_metrics(adp_name, verb, out)
        call_ctx = dict(frame)
        call_ctx["_runtime_async"] = self.runtime_async
        call_ctx["_observability"] = self.observability
        call_ctx["_adapter_registry"] = self.adapters
        try:
            out = self.adapters.call(adapter, target, args, call_ctx)
            return out
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self.observability.emit(
                "adapter.call.duration_ms",
                duration_ms,
                labels={"adapter": adapter, "target": target},
            )
            if "out" in locals():
                self._record_reactive_metrics(adapter, target, out)

    async def _exec_r_call_async(
        self, adapter: str, target: str, args: List[Any], frame: Dict[str, Any], lid: str, idx: int, op: str, stack: List[str]
    ) -> Any:
        self._count_adapter_call(lid, idx, op, stack)
        started = time.perf_counter()
        call_ctx = dict(frame)
        call_ctx["_runtime_async"] = True
        call_ctx["_observability"] = self.observability
        call_ctx["_adapter_registry"] = self.adapters
        if "." in adapter:
            adp_name, verb = adapter.split(".", 1)
            t0 = self._resolve(target, frame) if isinstance(target, str) else target
            try:
                out = await self.adapters.call_async(adp_name, verb, [t0] + args, call_ctx)
                return out
            finally:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                self.observability.emit(
                    "adapter.call.duration_ms",
                    duration_ms,
                    labels={"adapter": adp_name, "target": verb},
                )
                if "out" in locals():
                    self._record_reactive_metrics(adp_name, verb, out)
        try:
            out = await self.adapters.call_async(adapter, target, args, call_ctx)
            return out
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self.observability.emit(
                "adapter.call.duration_ms",
                duration_ms,
                labels={"adapter": adapter, "target": target},
            )
            if "out" in locals():
                self._record_reactive_metrics(adapter, target, out)

    def _exec_r_step(self, step: Dict[str, Any], frame: Dict[str, Any], lid: str, idx: int, op: str, stack: List[str]) -> Any:
        canon = runtime_canonicalize_r_step(step)
        adapter = str(canon.get("adapter") or "").strip()
        if not adapter:
            raise RuntimeError("R step missing adapter")
        target = canon.get("target", "")
        raw_args = list(canon.get("args") or [])
        args = [self._resolve(x, frame) for x in raw_args]
        out_var = str(canon.get("out") or "res")
        frame[out_var] = self._exec_r_call(adapter, target, args, frame, lid, idx, op, stack)
        return out_var

    def _exec_set(self, step: Dict[str, Any], frame: Dict[str, Any]) -> Any:
        name = step.get("name")
        if not name:
            raise RuntimeError("Set missing destination variable")
        frame[name] = self._resolve(step.get("ref"), frame)
        return frame.get(name)

    def _exec_filt(self, step: Dict[str, Any], frame: Dict[str, Any]) -> Any:
        out = step.get("name")
        if not out:
            raise RuntimeError("Filt missing destination variable")
        ref = self._resolve(step.get("ref"), frame)
        field = step.get("field")
        cmp_op = step.get("cmp", "==")
        val = self._resolve(step.get("value"), frame)
        arr = ref if isinstance(ref, list) else []
        frame[out] = [x for x in arr if isinstance(x, dict) and compare(x.get(field), cmp_op, val)]
        return frame.get(out)

    def _exec_sort(self, step: Dict[str, Any], frame: Dict[str, Any]) -> Any:
        out = step.get("name")
        if not out:
            raise RuntimeError("Sort missing destination variable")
        ref = self._resolve(step.get("ref"), frame)
        field = step.get("field")
        desc = str(step.get("order", "asc")).lower() == "desc"
        arr = ref if isinstance(ref, list) else []
        frame[out] = stable_sort(arr, field, desc=desc)
        return frame.get(out)

    def _store_call_result(self, step: Dict[str, Any], frame: Dict[str, Any], out: Any) -> str:
        out_var = step.get("out") or "_call_result"
        frame[out_var] = out
        if out_var != "_call_result":
            frame["_call_result"] = out
        return out_var

    def _exec_step(
        self,
        step: Dict[str, Any],
        frame: Dict[str, Any],
        lid: str,
        idx: int,
        stack: List[str],
        *,
        force_steps_for_call: bool,
        if_runner: Optional[Callable[[str], Any]] = None,
        if_target_resolver: Optional[Callable[[bool], Optional[str]]] = None,
        if_none_action: str = "continue",
        r_executor: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        op = step.get("op", "")
        if op == "R":
            out_var = step.get("out", "res")
            if r_executor is not None:
                frame[out_var] = r_executor(step, frame)
            else:
                self._exec_r_step(step, frame, lid, idx, op, stack)
            return {"action": "continue", "out": frame.get(out_var)}
        if op == "If":
            cond = self._eval_cond(step.get("cond", ""), frame)
            raw_tgt = if_target_resolver(cond) if if_target_resolver is not None else (step.get("then") if cond else step.get("else"))
            tgt = _norm_lid(raw_tgt)
            out = if_runner(tgt) if if_runner and tgt else None
            if out is not None:
                return {"action": "return", "out": out}
            return {"action": if_none_action, "out": out}
        if op == "J":
            # Return the resolved value of the named variable (or literal).
            out = self._resolve(step.get("var") or step.get("data"), frame)
            return {"action": "return", "out": out}
        if op == "Call":
            tgt = _norm_lid(step.get("label"))
            out = self._run_label(tgt, frame, stack, force_steps=force_steps_for_call)
            self._store_call_result(step, frame, out)
            return {"action": "continue", "out": out}
        if op == "Set":
            return {"action": "continue", "out": self._exec_set(step, frame)}
        if op == "Filt":
            return {"action": "continue", "out": self._exec_filt(step, frame)}
        if op == "Sort":
            return {"action": "continue", "out": self._exec_sort(step, frame)}
        if op == "X":
            return {"action": "continue", "out": self._exec_x(step, frame, lid, idx, stack)}
        if op == "CacheGet":
            name = step.get("name", "default")
            key = str(self._resolve(step.get("key", ""), frame))
            out_var = step.get("out", "data")
            fallback = step.get("fallback")
            self._count_adapter_call(lid, idx, op, stack)
            cached = self.adapters.get_cache().get(name, key)
            if cached is None and fallback is not None:
                cached = self._resolve(fallback, frame)
            frame[out_var] = cached
            return {"action": "continue", "out": frame.get(out_var)}
        if op == "CacheSet":
            name = step.get("name", "default")
            key = str(self._resolve(step.get("key", ""), frame))
            value = self._resolve(step.get("value"), frame)
            ttl_s = int(step.get("ttl_s", 0))
            self._count_adapter_call(lid, idx, op, stack)
            self.adapters.get_cache().set(name, key, value, ttl_s=ttl_s)
            return {"action": "continue", "out": None}
        if op == "QueuePut":
            queue = step.get("queue", "")
            value = self._resolve(step.get("value"), frame)
            out_var = step.get("out")
            self._count_adapter_call(lid, idx, op, stack)
            msg_id = self.adapters.get_queue().push(queue, value)
            if out_var:
                frame[out_var] = msg_id
            return {"action": "continue", "out": msg_id}
        if op == "Tx":
            action = (step.get("action") or "begin").lower()
            name = step.get("name", "default")
            self._count_adapter_call(lid, idx, op, stack)
            if action == "begin":
                frame["_txid"] = self.adapters.get_txn().begin(name)
            elif action == "commit":
                self.adapters.get_txn().commit(name)
            elif action == "rollback":
                self.adapters.get_txn().rollback(name)
            return {"action": "continue", "out": frame.get("_txid")}
        if op == "Enf":
            policy_name = step.get("policy", "")
            cap = self.ir.get("capabilities", {}) or {}
            pol = (cap.get("policy", {}) or {}).get(policy_name) or {}
            constraints = pol.get("constraints", {})
            must_auth = str(constraints.get("auth", constraints.get("require_auth", "false"))).lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            if must_auth and not bool(frame.get("_auth_present")):
                raise RuntimeError(f"POLICY_VIOLATION[{policy_name}]: auth required")
            req_role = constraints.get("role")
            if req_role and str(frame.get("_role", "")) != str(req_role):
                raise RuntimeError(f"POLICY_VIOLATION[{policy_name}]: role mismatch")
            return {"action": "continue", "out": None}
        return None

    def _source_context(self, lineno: Optional[int]) -> Dict[str, Any]:
        if not lineno or lineno < 1:
            return {}
        line = self._source_lines[lineno - 1] if lineno - 1 < len(self._source_lines) else ""
        cst = self._cst_by_line.get(lineno, {})
        op_tok = None
        for t in (cst.get("tokens") or []):
            if t.get("kind") in ("bare", "string"):
                op_tok = t
                break
        return {"lineno": lineno, "line": line, "op_span": op_tok.get("span") if isinstance(op_tok, dict) else None}

    def _raise_runtime_error(
        self,
        err: Exception,
        lid: str,
        idx: int,
        op: str,
        stack: List[str],
        frame: Dict[str, Any],
        step: Dict[str, Any],
        *,
        node_id: Optional[str] = None,
    ) -> None:
        self._emit_trajectory_fail(lid, op, frame, step, err, node_id=node_id)
        public_lid = stack[-2] if lid == "__tmp__" and len(stack) >= 2 else lid
        ctx = self._source_context(step.get("lineno"))
        msg = str(err)
        if ctx:
            msg = f"{msg} [line={ctx.get('lineno')} source={ctx.get('line')!r}]"
        data = {
            "cause_type": type(err).__name__,
            "cause_message": str(err),
            "lineno": ctx.get("lineno") if ctx else None,
            "source": ctx.get("line") if ctx else None,
        }
        code = ERROR_CODE_ADAPTER_ERROR if isinstance(err, AdapterError) else ERROR_CODE_RUNTIME_OP_ERROR
        if isinstance(err, AdapterError) and "capability gate" in str(err):
            data["user_hint"] = (
                "This step needs an adapter your host has not enabled. "
                "See the error text for AINL_HOST_ADAPTER_ALLOWLIST, AINL_HOST_ADAPTER_DENYLIST, "
                "AINL_STRICT_MODE, and AINL_SECURITY_PROFILE."
            )
        raise AinlRuntimeError(msg, public_lid, idx, op, stack, code=code, data=data)

    def _next_linear_node_edge(
        self, out_edges: List[Dict[str, Any]], lid: str, idx: int, op: str, stack: List[str]
    ) -> Optional[Dict[str, Any]]:
        node_edges = [e for e in out_edges if e.get("to_kind") == "node"]
        if not node_edges:
            return None
        explicit_next = [e for e in node_edges if str(e.get("port", "")) == "next"]
        if len(explicit_next) == 1:
            return explicit_next[0]
        if len(explicit_next) > 1:
            raise AinlRuntimeError(
                "ambiguous graph next edges: multiple port=next edges",
                lid,
                idx,
                op,
                stack,
                code=ERROR_CODE_GRAPH_AMBIGUOUS_NEXT,
            )
        if len(node_edges) == 1:
            # Backward compatibility: single node edge (e.g. retry) is treated as
            # linear successor. Sharp edge: that single edge may not be "next"
            # semantically. After graph normalization, prefer requiring
            # port="next" for linear successor and keep this only under
            # ir_version or runtime_policy (e.g. allow_legacy_unported_next=True).
            return node_edges[0]
        unported = [e for e in node_edges if not e.get("port")]
        if len(unported) > 1:
            raise AinlRuntimeError(
                "ambiguous graph next edges: multiple unported node edges",
                lid,
                idx,
                op,
                stack,
                code=ERROR_CODE_GRAPH_AMBIGUOUS_NEXT,
            )
        # Multiple node edges and no explicit next edge is ambiguous.
        raise AinlRuntimeError(
            "ambiguous graph next edges: define port=next",
            lid,
            idx,
            op,
            stack,
            code=ERROR_CODE_GRAPH_AMBIGUOUS_NEXT,
        )

    def _route_graph_error(
        self,
        err: Exception,
        *,
        cur: Optional[str],
        out_by_from: Dict[str, List[Dict[str, Any]]],
        node_by_id: Dict[str, Dict[str, Any]],
        active_err_handler: Optional[str],
        lid: str,
        idx: int,
        op: str,
        stack: List[str],
        frame: Dict[str, Any],
    ) -> Dict[str, Any]:
        err_edge = next((ed for ed in out_by_from.get(cur, []) if ed.get("port") == "err"), None)
        handler: Optional[str] = None
        if err_edge and err_edge.get("to_kind") == "node":
            err_node = node_by_id.get(err_edge.get("to"))
            h_step = (err_node or {}).get("data", {})
            if h_step.get("op") == "Err":
                handler = _norm_lid(h_step.get("handler"))
        if not handler:
            handler = active_err_handler
        if not handler:
            return {"handled": False}
        if handler in stack:
            raise AinlRuntimeError(
                f"error handler recursion detected: handler={handler} failing_op={op}",
                lid,
                idx,
                op,
                stack,
                code=ERROR_CODE_ERR_HANDLER_RECURSION,
            )
        frame["_error"] = str(err)
        step_data = (node_by_id.get(cur or "") or {}).get("data")
        if not isinstance(step_data, dict):
            step_data = {"op": op}
        if self._trajectory_log_path:
            self._emit_trajectory_fail(lid, op, frame, step_data, err, node_id=cur)
        if self.trace_enabled:
            self.trace_events.append(
                {"err_routed": True, "from_node": cur, "handler": handler, "label": lid}
            )
            if self.trace_sink is not None:
                self.trace_sink(self.trace_events[-1])
        out = self._run_label(handler, frame, stack, force_steps=False)
        return {"handled": True, "out": out}

    def _node_index_map_for_steps(self, steps: List[Dict[str, Any]]) -> Dict[str, int]:
        """Mirror compiler steps_to_graph node numbering: nth step op => n<nth>."""
        return {f"n{i + 1}": i for i in range(len(steps))}

    def _build_step_err_routes(self, steps: List[Dict[str, Any]]) -> Dict[int, str]:
        """Build failing-step-index -> handler label mapping from Err steps."""
        node_to_index = self._node_index_map_for_steps(steps)
        routes: Dict[int, str] = {}
        for idx, step in enumerate(steps):
            if step.get("op") != "Err":
                continue
            handler = _norm_lid(step.get("handler"))
            if not handler:
                continue
            source_idx: Optional[int] = None
            at = _norm_node_id(step.get("at_node_id"))
            if at and at in node_to_index:
                source_idx = node_to_index[at]
            elif idx > 0:
                # Bare Err in step-list attaches to immediately prior step node.
                source_idx = idx - 1
            if source_idx is not None and source_idx >= 0:
                routes[source_idx] = handler
        return routes

    @staticmethod
    def _compute_retry_delay_ms(cfg: Dict[str, Any], attempt: int) -> float:
        """Return delay in ms for the given attempt number (1-based)."""
        base = cfg.get("backoff_ms", 0)
        if base <= 0:
            return 0.0
        strategy = cfg.get("backoff_strategy", "fixed")
        if strategy == "exponential":
            delay = base * (2 ** (attempt - 1))
            cap = cfg.get("max_backoff_ms", 30000)
            return min(delay, cap)
        return float(base)

    def _build_step_retry_routes(self, steps: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Build failing-step-index -> retry config from Retry steps."""
        node_to_index = self._node_index_map_for_steps(steps)
        routes: Dict[int, Dict[str, Any]] = {}
        for idx, step in enumerate(steps):
            if step.get("op") != "Retry":
                continue
            source_idx: Optional[int] = None
            at = _norm_node_id(step.get("at_node_id"))
            if at and at in node_to_index:
                source_idx = node_to_index[at]
            elif idx > 0:
                # Bare Retry in step-list attaches to immediately prior step node.
                source_idx = idx - 1
            if source_idx is None or source_idx < 0:
                continue
            try:
                count = int(step.get("count", 3))
            except Exception:
                count = 3
            try:
                backoff_ms = int(step.get("backoff_ms", 0))
            except Exception:
                backoff_ms = 0
            strategy = str(step.get("backoff_strategy", "fixed"))
            if strategy not in ("fixed", "exponential"):
                strategy = "fixed"
            routes[source_idx] = {"count": max(1, count), "backoff_ms": max(0, backoff_ms), "backoff_strategy": strategy}
        return routes

    def _retry_policy_from_graph(
        self,
        cur: Optional[str],
        edge_by_from_port_kind: Dict[tuple, Dict[str, Any]],
        node_by_id: Dict[str, Dict[str, Any]],
        frame: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not cur:
            return None
        retry_edge = edge_by_from_port_kind.get((cur, "retry", "node"))
        if not retry_edge or retry_edge.get("to_kind") != "node":
            return None
        rnode = node_by_id.get(retry_edge.get("to"))
        rstep = (rnode or {}).get("data", {})
        if rstep.get("op") != "Retry":
            return None
        try:
            count = int(self._resolve(rstep.get("count", 3), frame))
        except Exception:
            count = 3
        try:
            backoff_ms = int(self._resolve(rstep.get("backoff_ms", 0), frame))
        except Exception:
            backoff_ms = 0
        strategy = str(rstep.get("backoff_strategy", "fixed"))
        if strategy not in ("fixed", "exponential"):
            strategy = "fixed"
        return {"count": max(1, count), "backoff_ms": max(0, backoff_ms), "backoff_strategy": strategy}

    def _resolve_label_key(self, label_id: Any, stack: List[str]) -> str:
        # Support nested If/ForEach in included subgraphs (fixes access_aware_memory.ainl LACCESS_LIST etc.)
        n = _norm_lid(label_id)
        if n in self.labels:
            return n
        if "/" in n:
            return n
        for frame_lid in reversed(stack):
            if "/" not in frame_lid:
                continue
            alias = frame_lid.split("/", 1)[0]
            cand = f"{alias}/{n}"
            if cand in self.labels:
                return cand
        return n

    def _run_label(self, label_id: str, frame: Dict[str, Any], stack: List[str], force_steps: bool = False) -> Any:
        if not stack:
            self._start_run()
            frame['_run_id'] = str(uuid.uuid4())
        lid = self._resolve_label_key(label_id, stack)
        stack = stack + [lid]
        self._guard_depth(stack)
        body = self.labels.get(lid, {})
        has_graph = bool(body.get("nodes")) and body.get("edges") is not None and bool(body.get("entry"))
        if self.execution_mode == "steps-only":
            force_steps = True
        if self.execution_mode == "graph-only" and not force_steps and has_graph:
            return self._run_label_graph(lid, frame, stack)
        if self.execution_mode == "graph-only" and not force_steps and not has_graph:
            raise AinlRuntimeError(
                "graph-only mode requires graph label data",
                lid,
                0,
                "GRAPH",
                stack,
                code=ERROR_CODE_GRAPH_ONLY_REQUIRES_GRAPH,
            )
        if not force_steps:
            body = self.labels.get(lid, {})
            if body.get("nodes") and body.get("edges") is not None and body.get("entry"):
                return self._run_label_graph(lid, frame, stack)
        steps = self._steps(lid)
        err_routes = self._build_step_err_routes(steps)
        retry_routes = self._build_step_retry_routes(steps)

        def _retry_current_step() -> Optional[Dict[str, Any]]:
            if op == "R":
                self._exec_r_step(s, frame, lid, i, op, stack)
                return {"action": "continue", "out": frame.get(s.get("out", "res"))}
            shared_retry = self._exec_step(
                s,
                frame,
                lid,
                i,
                stack,
                force_steps_for_call=False,
                if_runner=lambda target: self._run_label(target, frame, stack),
                if_target_resolver=lambda cond: s.get("then") if cond else s.get("else"),
                if_none_action="continue",
            )
            if shared_retry is not None:
                return shared_retry
            # Retry currently targets executable ops only; metadata ops have no replay.
            raise RuntimeError(f"retry unsupported for op: {op}")

        i = 0
        while i < len(steps):
            s = steps[i]
            op = s.get("op", "")
            t0 = time.perf_counter()
            self._trace_lineno = s.get("lineno")
            self._guard_tick(lid, i, op, stack, frame)
            try:
                if op == "Err":
                    self._emit_trace(lid, op, i, t0, frame, None, trajectory_step=s)
                    i += 1
                    continue

                shared = self._exec_step(
                    s,
                    frame,
                    lid,
                    i,
                    stack,
                    force_steps_for_call=False,
                    if_runner=lambda target: self._run_label(target, frame, stack),
                    if_target_resolver=lambda cond: s.get("then") if cond else s.get("else"),
                    if_none_action="continue",
                )
                if shared is not None:
                    self._emit_trace(lid, op, i, t0, frame, shared.get("out"), trajectory_step=s)
                    if shared.get("action") == "return":
                        return shared.get("out")
                    i += 1
                    continue

                if op == "Retry":
                    # Retry is compiler-lowered metadata; actual retries happen when
                    # the source step fails and routes to this Retry policy.
                    self._emit_trace(lid, op, i, t0, frame, None, trajectory_step=s)
                    i += 1
                    continue

                if op == "Loop":
                    ref = self._resolve(s.get("ref"), frame)
                    item_var = s.get("item", "item")
                    body = _norm_lid(s.get("body"))
                    after = _norm_lid(s.get("after"))
                    arr = ref if isinstance(ref, list) else []
                    max_loop_iters = self._limit_int("max_loop_iters")
                    if max_loop_iters is not None and len(arr) > max_loop_iters:
                        raise AinlRuntimeError("max_loop_iters exceeded", lid, i, op, stack, code=ERROR_CODE_MAX_LOOP_ITERS)
                    sentinel = object()
                    prev_item = frame.get(item_var, sentinel)
                    for it in arr:
                        frame[item_var] = it
                        out = self._run_label(body, frame, stack)
                        if out is not None:
                            frame["_loop_last"] = out
                    if prev_item is sentinel:
                        frame.pop(item_var, None)
                    else:
                        frame[item_var] = prev_item
                    if after:
                        out = self._run_label(after, frame, stack)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, i, t0, frame, frame.get("_loop_last"), trajectory_step=s)
                    i += 1
                    continue

                if op == "While":
                    cond_tok = s.get("cond")
                    body = _norm_lid(s.get("body"))
                    after = _norm_lid(s.get("after"))
                    limit = int(s.get("limit", 10000))
                    max_loop_iters = self._limit_int("max_loop_iters")
                    if max_loop_iters is not None:
                        limit = min(limit, max_loop_iters)
                    n = 0
                    while self._eval_cond(cond_tok, frame):
                        out = self._run_label(body, frame, stack)
                        n += 1
                        if n > limit:
                            raise AinlRuntimeError(
                                "while loop iteration limit exceeded",
                                lid,
                                i,
                                op,
                                stack,
                                code=ERROR_CODE_WHILE_LIMIT,
                            )
                        if out is not None:
                            frame["_while_last"] = out
                    if after:
                        out = self._run_label(after, frame, stack)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, i, t0, frame, frame.get("_while_last"), trajectory_step=s)
                    i += 1
                    continue

                # Unknown runtime op in label: skip for backward compatibility.
                self._handle_unknown_op(lid, i, op, stack, frame, mode="steps")
                self._emit_trace(lid, op, i, t0, frame, None, trajectory_step=s)
                i += 1
            except AdapterError as e:
                retry_cfg = retry_routes.get(i)
                if retry_cfg:
                    last_err: Optional[Exception] = e
                    for _ra in range(1, retry_cfg["count"] + 1):
                        try:
                            shared_retry = _retry_current_step()
                            if shared_retry and shared_retry.get("action") == "return":
                                return shared_retry.get("out")
                            last_err = None
                            break
                        except Exception as re:
                            last_err = re
                            delay = self._compute_retry_delay_ms(retry_cfg, _ra)
                            if delay > 0:
                                time.sleep(delay / 1000.0)
                    if last_err is None:
                        self._emit_trace(
                            lid,
                            op,
                            i,
                            t0,
                            frame,
                            frame.get(s.get("out", "res")),
                            trajectory_step=s,
                        )
                        i += 1
                        continue
                    e = last_err  # type: ignore[assignment]
                err_handler = err_routes.get(i)
                if err_handler:
                    if err_handler in stack:
                        raise AinlRuntimeError(
                            f"error handler recursion detected: handler={err_handler} failing_op={op}",
                            lid,
                            i,
                            op,
                            stack,
                            code=ERROR_CODE_ERR_HANDLER_RECURSION,
                        )
                    frame["_error"] = str(e)
                    self._emit_trajectory_fail(lid, op, frame, s, e, node_id=None)
                    return self._run_label(err_handler, frame, stack)
                self._raise_runtime_error(e, lid, i, op, stack, frame, s)
            except AinlRuntimeError as e:
                retry_cfg = retry_routes.get(i)
                if retry_cfg:
                    last_err: Optional[Exception] = e
                    for _ra in range(1, retry_cfg["count"] + 1):
                        try:
                            shared_retry = _retry_current_step()
                            if shared_retry and shared_retry.get("action") == "return":
                                return shared_retry.get("out")
                            last_err = None
                            break
                        except Exception as re:
                            last_err = re
                            delay = self._compute_retry_delay_ms(retry_cfg, _ra)
                            if delay > 0:
                                time.sleep(delay / 1000.0)
                    if last_err is None:
                        self._emit_trace(
                            lid,
                            op,
                            i,
                            t0,
                            frame,
                            frame.get(s.get("out", "res")),
                            trajectory_step=s,
                        )
                        i += 1
                        continue
                    e = last_err if isinstance(last_err, AinlRuntimeError) else e
                err_handler = err_routes.get(i)
                if err_handler:
                    if err_handler in stack:
                        raise AinlRuntimeError(
                            f"error handler recursion detected: handler={err_handler} failing_op={op}",
                            lid,
                            i,
                            op,
                            stack,
                            code=ERROR_CODE_ERR_HANDLER_RECURSION,
                        )
                    frame["_error"] = str(e)
                    self._emit_trajectory_fail(lid, op, frame, s, e, node_id=None)
                    return self._run_label(err_handler, frame, stack)
                self._emit_trajectory_fail(lid, op, frame, s, e, node_id=None)
                raise
            except Exception as e:
                retry_cfg = retry_routes.get(i)
                if retry_cfg:
                    last_err: Optional[Exception] = e
                    for _ra in range(1, retry_cfg["count"] + 1):
                        try:
                            shared_retry = _retry_current_step()
                            if shared_retry and shared_retry.get("action") == "return":
                                return shared_retry.get("out")
                            last_err = None
                            break
                        except Exception as re:
                            last_err = re
                            delay = self._compute_retry_delay_ms(retry_cfg, _ra)
                            if delay > 0:
                                time.sleep(delay / 1000.0)
                    if last_err is None:
                        self._emit_trace(
                            lid,
                            op,
                            i,
                            t0,
                            frame,
                            frame.get(s.get("out", "res")),
                            trajectory_step=s,
                        )
                        i += 1
                        continue
                    e = last_err  # type: ignore[assignment]
                err_handler = err_routes.get(i)
                if err_handler:
                    if err_handler in stack:
                        raise AinlRuntimeError(
                            f"error handler recursion detected: handler={err_handler} failing_op={op}",
                            lid,
                            i,
                            op,
                            stack,
                            code=ERROR_CODE_ERR_HANDLER_RECURSION,
                        )
                    frame["_error"] = str(e)
                    self._emit_trajectory_fail(lid, op, frame, s, e, node_id=None)
                    return self._run_label(err_handler, frame, stack)
                self._raise_runtime_error(e, lid, i, op, stack, frame, s)
        return None

    def _run_label_graph(self, lid: str, frame: Dict[str, Any], stack: List[str]) -> Any:
        body = self.labels.get(lid, {})
        nodes = body.get("nodes") or []
        edges = body.get("edges") or []
        entry = body.get("entry")
        node_by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        out_by_from: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            out_by_from.setdefault(e.get("from"), []).append(e)
        edge_by_from_port_kind: Dict[tuple, Dict[str, Any]] = {}
        for e in edges:
            k = (e.get("from"), e.get("port"), e.get("to_kind"))
            if k not in edge_by_from_port_kind:
                edge_by_from_port_kind[k] = e
        cur = entry
        active_err_handler: Optional[str] = None
        executed_nonmeta = False
        retry_attempts: Dict[str, int] = {}
        guard = 0
        while cur and cur in node_by_id:
            guard += 1
            if guard > 100000:
                raise AinlRuntimeError(
                    "graph execution guard exceeded",
                    lid,
                    guard,
                    "GRAPH",
                    stack,
                    code=ERROR_CODE_GRAPH_EXEC_GUARD,
                )
            n = node_by_id[cur]
            step = n.get("data") or {}
            op = step.get("op", n.get("op", ""))
            if op != "Err":
                executed_nonmeta = True
            idx = guard - 1
            t0 = time.perf_counter()
            self._trace_lineno = step.get("lineno")
            self._guard_tick(lid, idx, op, stack, frame)
            try:
                if op == "Err":
                    active_err_handler = _norm_lid(step.get("handler"))
                    if self._trajectory_log_path:
                        self._emit_trajectory(
                            label=lid,
                            operation=op,
                            frame=frame,
                            output=None,
                            outcome="success",
                            trajectory_step=step,
                            node_id=cur,
                        )
                    nxt = self._next_linear_node_edge(out_by_from.get(cur, []), lid, idx, op, stack)
                    cur = nxt.get("to") if nxt else None
                    continue

                if op == "R":
                    adapter = step.get("adapter", "")
                    target = step.get("target", "")
                    args = [self._resolve(x, frame) for x in (step.get("args") or [])]
                    out_var = step.get("out", "res")
                    shared = self._exec_step(
                        step,
                        frame,
                        lid,
                        idx,
                        stack,
                        force_steps_for_call=False,
                        r_executor=lambda _s, _f: self._exec_r_call(adapter, target, args, frame, lid, idx, op, stack),
                    )
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        shared.get("out") if shared else frame.get(out_var),
                        node_id=cur,
                        trajectory_step=step,
                    )

                elif op == "If":
                    then_edge = edge_by_from_port_kind.get((cur, "then", "label"))
                    else_edge = edge_by_from_port_kind.get((cur, "else", "label"))
                    cond = self._eval_cond(step.get("cond"), frame)
                    shared = self._exec_step(
                        step,
                        frame,
                        lid,
                        idx,
                        stack,
                        force_steps_for_call=False,
                        if_target_resolver=lambda c: (then_edge.get("to") if (then_edge and c) else (else_edge.get("to") if else_edge else None)),
                        if_runner=lambda target: self._run_label(target, frame, stack, force_steps=False),
                        if_none_action="terminate",
                    )
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        shared.get("out") if shared else None,
                        node_id=cur,
                        branch={"port": "then" if cond else "else", "condition": cond},
                        trajectory_step=step,
                    )
                    if shared and shared.get("action") == "return":
                        return shared.get("out")
                    # Branch label returned no value: terminate this graph path explicitly.
                    cur = None
                    continue

                elif op in ("J", "Call", "Set", "Filt", "Sort", "X"):
                    shared = self._exec_step(step, frame, lid, idx, stack, force_steps_for_call=False)
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        shared.get("out") if shared else None,
                        node_id=cur,
                        trajectory_step=step,
                    )
                    if shared and shared.get("action") == "return":
                        return shared.get("out")

                elif op == "Loop":
                    ref = self._resolve(step.get("ref"), frame)
                    item_var = step.get("item", "item")
                    body_edge = edge_by_from_port_kind.get((cur, "body", "label"))
                    after_edge = edge_by_from_port_kind.get((cur, "after", "label"))
                    arr = ref if isinstance(ref, list) else []
                    max_loop_iters = self._limit_int("max_loop_iters")
                    if max_loop_iters is not None and len(arr) > max_loop_iters:
                        raise AinlRuntimeError(
                            "max_loop_iters exceeded",
                            lid,
                            idx,
                            op,
                            stack,
                            code=ERROR_CODE_MAX_LOOP_ITERS,
                        )
                    sentinel = object()
                    prev_item = frame.get(item_var, sentinel)
                    for it in arr:
                        frame[item_var] = it
                        if body_edge:
                            out = self._run_label(_norm_lid(body_edge.get("to")), frame, stack, force_steps=False)
                            if out is not None:
                                frame["_loop_last"] = out
                    if prev_item is sentinel:
                        frame.pop(item_var, None)
                    else:
                        frame[item_var] = prev_item
                    if after_edge:
                        out = self._run_label(_norm_lid(after_edge.get("to")), frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        frame.get("_loop_last"),
                        node_id=cur,
                        trajectory_step=step,
                    )
                    cur = None
                    continue

                elif op == "While":
                    cond_tok = step.get("cond")
                    body_edge = edge_by_from_port_kind.get((cur, "body", "label"))
                    after_edge = edge_by_from_port_kind.get((cur, "after", "label"))
                    limit = int(step.get("limit", 10000))
                    max_loop_iters = self._limit_int("max_loop_iters")
                    if max_loop_iters is not None:
                        limit = min(limit, max_loop_iters)
                    n_iter = 0
                    while self._eval_cond(cond_tok, frame):
                        n_iter += 1
                        if n_iter > limit:
                            raise AinlRuntimeError(
                                "while loop iteration limit exceeded",
                                lid,
                                idx,
                                op,
                                stack,
                                code=ERROR_CODE_WHILE_LIMIT,
                            )
                        if body_edge:
                            out = self._run_label(_norm_lid(body_edge.get("to")), frame, stack, force_steps=False)
                            if out is not None:
                                frame["_while_last"] = out
                    if after_edge:
                        out = self._run_label(_norm_lid(after_edge.get("to")), frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        frame.get("_while_last"),
                        node_id=cur,
                        trajectory_step=step,
                    )
                    cur = None
                    continue

                elif op == "CacheGet":
                    name = step.get("name", "default")
                    key = str(self._resolve(step.get("key", ""), frame))
                    out_var = step.get("out", "data")
                    fallback = step.get("fallback")
                    self._count_adapter_call(lid, idx, op, stack)
                    cached = self.adapters.get_cache().get(name, key)
                    if cached is None and fallback is not None:
                        cached = self._resolve(fallback, frame)
                    frame[out_var] = cached
                    self._emit_trace(
                        lid,
                        op,
                        idx,
                        t0,
                        frame,
                        frame.get(out_var),
                        node_id=cur,
                        trajectory_step=step,
                    )

                elif op == "CacheSet":
                    name = step.get("name", "default")
                    key = str(self._resolve(step.get("key", ""), frame))
                    value = self._resolve(step.get("value"), frame)
                    ttl_s = int(step.get("ttl_s", 0))
                    self._count_adapter_call(lid, idx, op, stack)
                    self.adapters.get_cache().set(name, key, value, ttl_s=ttl_s)
                    self._emit_trace(lid, op, idx, t0, frame, None, node_id=cur, trajectory_step=step)

                elif op == "QueuePut":
                    queue = step.get("queue", "")
                    value = self._resolve(step.get("value"), frame)
                    out_var = step.get("out")
                    self._count_adapter_call(lid, idx, op, stack)
                    msg_id = self.adapters.get_queue().push(queue, value)
                    if out_var:
                        frame[out_var] = msg_id
                    self._emit_trace(lid, op, idx, t0, frame, msg_id, node_id=cur, trajectory_step=step)

                elif op == "Tx":
                    action = (step.get("action") or "begin").lower()
                    name = step.get("name", "default")
                    self._count_adapter_call(lid, idx, op, stack)
                    if action == "begin":
                        frame["_txid"] = self.adapters.get_txn().begin(name)
                    elif action == "commit":
                        self.adapters.get_txn().commit(name)
                    elif action == "rollback":
                        self.adapters.get_txn().rollback(name)
                    self._emit_trace(lid, op, idx, t0, frame, frame.get("_txid"), node_id=cur, trajectory_step=step)

                elif op == "Enf":
                    policy_name = step.get("policy", "")
                    cap = self.ir.get("capabilities", {}) or {}
                    pol = (cap.get("policy", {}) or {}).get(policy_name) or {}
                    constraints = pol.get("constraints", {})
                    must_auth = str(constraints.get("auth", constraints.get("require_auth", "false"))).lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    )
                    if must_auth and not bool(frame.get("_auth_present")):
                        raise RuntimeError(f"POLICY_VIOLATION[{policy_name}]: auth required")
                    req_role = constraints.get("role")
                    if req_role and str(frame.get("_role", "")) != str(req_role):
                        raise RuntimeError(f"POLICY_VIOLATION[{policy_name}]: role mismatch")
                    self._emit_trace(lid, op, idx, t0, frame, None, node_id=cur, trajectory_step=step)

                else:
                    self._handle_unknown_op(lid, idx, op, stack, frame, mode="graph")
                    self._emit_trace(lid, op, idx, t0, frame, None, node_id=cur, trajectory_step=step)

                retry_attempts.pop(cur, None)
                # advance linear node edge with explicit/validated selection.
                nxt = self._next_linear_node_edge(out_by_from.get(cur, []), lid, idx, op, stack)
                if self.trace_events and nxt:
                    self.trace_events[-1]["port_taken"] = nxt.get("port")
                    self.trace_events[-1]["edge_taken"] = {
                        "port": nxt.get("port"),
                        "to_kind": nxt.get("to_kind", "node"),
                        "to": nxt.get("to"),
                    }
                cur = nxt.get("to") if nxt else None
            except AdapterError as e:
                retry_policy = self._retry_policy_from_graph(cur, edge_by_from_port_kind, node_by_id, frame)
                if retry_policy and cur:
                    attempt = retry_attempts.get(cur, 0) + 1
                    if attempt <= retry_policy["count"]:
                        retry_attempts[cur] = attempt
                        delay = self._compute_retry_delay_ms(retry_policy, attempt)
                        if delay > 0:
                            time.sleep(delay / 1000.0)
                        if self.trace_enabled:
                            self.trace_events.append(
                                {
                                    "label": lid,
                                    "node_id": cur,
                                    "op": op,
                                    "retry_attempt": {"attempt": attempt, "count": retry_policy["count"], "succeeded": False},
                                }
                            )
                            if self.trace_sink is not None:
                                self.trace_sink(self.trace_events[-1])
                        continue
                routed = self._route_graph_error(
                    e,
                    cur=cur,
                    out_by_from=out_by_from,
                    node_by_id=node_by_id,
                    active_err_handler=active_err_handler,
                    lid=lid,
                    idx=idx,
                    op=op,
                    stack=stack,
                    frame=frame,
                )
                if routed.get("handled"):
                    return routed.get("out")
                self._raise_runtime_error(e, lid, idx, op, stack, frame, step, node_id=cur)
            except AinlRuntimeError:
                retry_policy = self._retry_policy_from_graph(cur, edge_by_from_port_kind, node_by_id, frame)
                if retry_policy and cur:
                    attempt = retry_attempts.get(cur, 0) + 1
                    if attempt <= retry_policy["count"]:
                        retry_attempts[cur] = attempt
                        delay = self._compute_retry_delay_ms(retry_policy, attempt)
                        if delay > 0:
                            time.sleep(delay / 1000.0)
                        if self.trace_enabled:
                            self.trace_events.append(
                                {
                                    "label": lid,
                                    "node_id": cur,
                                    "op": op,
                                    "retry_attempt": {"attempt": attempt, "count": retry_policy["count"], "succeeded": False},
                                }
                            )
                            if self.trace_sink is not None:
                                self.trace_sink(self.trace_events[-1])
                        continue
                self._emit_trajectory_fail(lid, op, frame, step, e, node_id=cur)
                raise
            except Exception as e:
                retry_policy = self._retry_policy_from_graph(cur, edge_by_from_port_kind, node_by_id, frame)
                if retry_policy and cur:
                    attempt = retry_attempts.get(cur, 0) + 1
                    if attempt <= retry_policy["count"]:
                        retry_attempts[cur] = attempt
                        delay = self._compute_retry_delay_ms(retry_policy, attempt)
                        if delay > 0:
                            time.sleep(delay / 1000.0)
                        if self.trace_enabled:
                            self.trace_events.append(
                                {
                                    "label": lid,
                                    "node_id": cur,
                                    "op": op,
                                    "retry_attempt": {"attempt": attempt, "count": retry_policy["count"], "succeeded": False},
                                }
                            )
                            if self.trace_sink is not None:
                                self.trace_sink(self.trace_events[-1])
                        continue
                routed = self._route_graph_error(
                    e,
                    cur=cur,
                    out_by_from=out_by_from,
                    node_by_id=node_by_id,
                    active_err_handler=active_err_handler,
                    lid=lid,
                    idx=idx,
                    op=op,
                    stack=stack,
                    frame=frame,
                )
                if routed.get("handled"):
                    return routed.get("out")
                self._raise_runtime_error(e, lid, idx, op, stack, frame, step, node_id=cur)
        # If graph terminates without explicit return, optionally fallback for compatibility.
        # Never re-run step-mode after non-meta graph work (prevents duplicate side effects).
        # Err-only graph paths can still fallback.
        if self.step_fallback and not executed_nonmeta:
            return self._run_label(lid, frame, stack, force_steps=True)
        return None

    def run_label(self, label_id: str, frame: Optional[Dict[str, Any]] = None) -> Any:
        return self._run_label(_norm_lid(label_id), dict(frame or {}), [], force_steps=False)

    async def _run_label_async(self, label_id: str, frame: Dict[str, Any], stack: List[str], force_steps: bool = False) -> Any:
        if not stack:
            self._start_run()
        lid = self._resolve_label_key(label_id, stack)
        stack = stack + [lid]
        self._guard_depth(stack)
        body = self.labels.get(lid, {})
        has_graph = bool(body.get("nodes")) and body.get("edges") is not None and bool(body.get("entry"))
        if self.execution_mode == "steps-only":
            force_steps = True
        if self.execution_mode == "graph-only" and not force_steps and has_graph:
            return await self._run_label_graph_async(lid, frame, stack)
        if self.execution_mode == "graph-only" and not force_steps and not has_graph:
            raise AinlRuntimeError(
                "graph-only mode requires graph label data",
                lid,
                0,
                "GRAPH",
                stack,
                code=ERROR_CODE_GRAPH_ONLY_REQUIRES_GRAPH,
            )
        if not force_steps and has_graph:
            return await self._run_label_graph_async(lid, frame, stack)

        steps = self._steps(lid)
        i = 0
        while i < len(steps):
            s = steps[i]
            op = s.get("op", "")
            t0 = time.perf_counter()
            self._trace_lineno = s.get("lineno")
            self._guard_tick(lid, i, op, stack, frame)
            try:
                if op == "R":
                    canon = runtime_canonicalize_r_step(s)
                    adapter = str(canon.get("adapter") or "").strip()
                    target = canon.get("target", "")
                    args = [self._resolve(x, frame) for x in list(canon.get("args") or [])]
                    out_var = str(canon.get("out") or "res")
                    frame[out_var] = await self._exec_r_call_async(adapter, target, args, frame, lid, i, op, stack)
                    self._emit_trace(lid, op, i, t0, frame, frame.get(out_var), trajectory_step=s)
                    i += 1
                    continue
                if op == "If":
                    cond = self._eval_cond(s.get("cond", ""), frame)
                    tgt = _norm_lid(s.get("then") if cond else s.get("else"))
                    out = await self._run_label_async(tgt, frame, stack, force_steps=False) if tgt else None
                    self._emit_trace(lid, op, i, t0, frame, out, trajectory_step=s)
                    if out is not None:
                        return out
                    i += 1
                    continue
                if op == "Call":
                    tgt = _norm_lid(s.get("label"))
                    out = await self._run_label_async(tgt, frame, stack, force_steps=False)
                    self._store_call_result(s, frame, out)
                    self._emit_trace(lid, op, i, t0, frame, out, trajectory_step=s)
                    i += 1
                    continue
                if op == "J":
                    out = self._resolve(s.get("var") or s.get("data"), frame)
                    self._emit_trace(lid, op, i, t0, frame, out, trajectory_step=s)
                    return out
                if op == "Loop":
                    ref = self._resolve(s.get("ref"), frame)
                    item_var = s.get("item", "item")
                    body_l = _norm_lid(s.get("body"))
                    after = _norm_lid(s.get("after"))
                    arr = ref if isinstance(ref, list) else []
                    for it in arr:
                        frame[item_var] = it
                        out = await self._run_label_async(body_l, frame, stack, force_steps=False)
                        if out is not None:
                            frame["_loop_last"] = out
                    if after:
                        out = await self._run_label_async(after, frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, i, t0, frame, frame.get("_loop_last"), trajectory_step=s)
                    i += 1
                    continue
                if op == "While":
                    cond_tok = s.get("cond")
                    body_l = _norm_lid(s.get("body"))
                    after = _norm_lid(s.get("after"))
                    limit = int(s.get("limit", 10000))
                    n = 0
                    while self._eval_cond(cond_tok, frame):
                        out = await self._run_label_async(body_l, frame, stack, force_steps=False)
                        n += 1
                        if n > limit:
                            raise AinlRuntimeError(
                                "while loop iteration limit exceeded",
                                lid,
                                i,
                                op,
                                stack,
                                code=ERROR_CODE_WHILE_LIMIT,
                            )
                        if out is not None:
                            frame["_while_last"] = out
                    if after:
                        out = await self._run_label_async(after, frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, i, t0, frame, frame.get("_while_last"), trajectory_step=s)
                    i += 1
                    continue
                shared = self._exec_step(
                    s,
                    frame,
                    lid,
                    i,
                    stack,
                    force_steps_for_call=False,
                    if_runner=None,
                    if_target_resolver=None,
                )
                if shared is not None and shared.get("action") == "return":
                    self._emit_trace(lid, op, i, t0, frame, shared.get("out"), trajectory_step=s)
                    return shared.get("out")
                self._emit_trace(lid, op, i, t0, frame, shared.get("out") if shared else None, trajectory_step=s)
                i += 1
            except Exception as e:
                self._raise_runtime_error(e, lid, i, op, stack, frame, s)
        return None

    async def _run_label_graph_async(self, lid: str, frame: Dict[str, Any], stack: List[str]) -> Any:
        body = self.labels.get(lid, {})
        nodes = body.get("nodes") or []
        edges = body.get("edges") or []
        entry = body.get("entry")
        node_by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        out_by_from: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            out_by_from.setdefault(e.get("from"), []).append(e)
        edge_by_from_port_kind: Dict[tuple, Dict[str, Any]] = {}
        for e in edges:
            k = (e.get("from"), e.get("port"), e.get("to_kind"))
            if k not in edge_by_from_port_kind:
                edge_by_from_port_kind[k] = e
        cur = entry
        guard = 0
        while cur and cur in node_by_id:
            guard += 1
            n = node_by_id[cur]
            step = n.get("data") or {}
            op = step.get("op", n.get("op", ""))
            idx = guard - 1
            t0 = time.perf_counter()
            self._trace_lineno = step.get("lineno")
            self._guard_tick(lid, idx, op, stack, frame)
            try:
                if op == "R":
                    adapter = step.get("adapter", "")
                    target = step.get("target", "")
                    args = [self._resolve(x, frame) for x in (step.get("args") or [])]
                    out_var = step.get("out", "res")
                    frame[out_var] = await self._exec_r_call_async(adapter, target, args, frame, lid, idx, op, stack)
                    self._emit_trace(lid, op, idx, t0, frame, frame.get(out_var), node_id=cur, trajectory_step=step)
                elif op == "If":
                    then_edge = edge_by_from_port_kind.get((cur, "then", "label"))
                    else_edge = edge_by_from_port_kind.get((cur, "else", "label"))
                    cond = self._eval_cond(step.get("cond"), frame)
                    tgt = _norm_lid(then_edge.get("to") if (then_edge and cond) else (else_edge.get("to") if else_edge else None))
                    out = await self._run_label_async(tgt, frame, stack, force_steps=False) if tgt else None
                    self._emit_trace(lid, op, idx, t0, frame, out, node_id=cur, trajectory_step=step)
                    return out
                elif op == "Call":
                    tgt = _norm_lid(step.get("label"))
                    out = await self._run_label_async(tgt, frame, stack, force_steps=False)
                    self._store_call_result(step, frame, out)
                    self._emit_trace(lid, op, idx, t0, frame, out, node_id=cur, trajectory_step=step)
                elif op == "Loop":
                    ref = self._resolve(step.get("ref"), frame)
                    item_var = step.get("item", "item")
                    body_edge = edge_by_from_port_kind.get((cur, "body", "label"))
                    after_edge = edge_by_from_port_kind.get((cur, "after", "label"))
                    arr = ref if isinstance(ref, list) else []
                    for it in arr:
                        frame[item_var] = it
                        if body_edge:
                            out = await self._run_label_async(_norm_lid(body_edge.get("to")), frame, stack, force_steps=False)
                            if out is not None:
                                frame["_loop_last"] = out
                    if after_edge:
                        out = await self._run_label_async(_norm_lid(after_edge.get("to")), frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, idx, t0, frame, frame.get("_loop_last"), node_id=cur, trajectory_step=step)
                    cur = None
                    continue
                elif op == "While":
                    cond_tok = step.get("cond")
                    body_edge = edge_by_from_port_kind.get((cur, "body", "label"))
                    after_edge = edge_by_from_port_kind.get((cur, "after", "label"))
                    limit = int(step.get("limit", 10000))
                    n_iter = 0
                    while self._eval_cond(cond_tok, frame):
                        n_iter += 1
                        if n_iter > limit:
                            raise AinlRuntimeError(
                                "while loop iteration limit exceeded",
                                lid,
                                idx,
                                op,
                                stack,
                                code=ERROR_CODE_WHILE_LIMIT,
                            )
                        if body_edge:
                            out = await self._run_label_async(_norm_lid(body_edge.get("to")), frame, stack, force_steps=False)
                            if out is not None:
                                frame["_while_last"] = out
                    if after_edge:
                        out = await self._run_label_async(_norm_lid(after_edge.get("to")), frame, stack, force_steps=False)
                        if out is not None:
                            return out
                    self._emit_trace(lid, op, idx, t0, frame, frame.get("_while_last"), node_id=cur, trajectory_step=step)
                    cur = None
                    continue
                elif op == "J":
                    out = self._resolve(step.get("var") or step.get("data"), frame)
                    self._emit_trace(lid, op, idx, t0, frame, out, node_id=cur, trajectory_step=step)
                    return out
                else:
                    shared = self._exec_step(step, frame, lid, idx, stack, force_steps_for_call=False)
                    self._emit_trace(lid, op, idx, t0, frame, shared.get("out") if shared else None, node_id=cur, trajectory_step=step)
                    if shared and shared.get("action") == "return":
                        return shared.get("out")
                nxt = self._next_linear_node_edge(out_by_from.get(cur, []), lid, idx, op, stack)
                cur = nxt.get("to") if nxt else None
            except Exception as e:
                self._raise_runtime_error(e, lid, idx, op, stack, frame, step, node_id=cur)
        return None

    async def run_label_async(self, label_id: str, frame: Optional[Dict[str, Any]] = None) -> Any:
        return await self._run_label_async(_norm_lid(label_id), dict(frame or {}), [], force_steps=False)

    # ---- Public trace / step helpers for agents ----

    def get_trace(self) -> List[Dict[str, Any]]:
        """Return collected trace events from the last run in a stable schema.

        Each event has:
        - label: str
        - op: str
        - step: int
        - lineno: Optional[int]
        - duration_ms: float
        - out: JSON-safe representation of the op's output (if any)
        - frame_keys: sorted list of visible frame keys at that step
        """
        return list(self.trace_events)

    def clear_trace(self) -> None:
        """Clear accumulated trace events."""
        self.trace_events.clear()

    def last_trace_event(self) -> Optional[Dict[str, Any]]:
        """Return the most recent trace event, if any."""
        return self.trace_events[-1] if self.trace_events else None

    def default_entry_label(self) -> str:
        core = self.ir.get("services", {}).get("core", {})
        eps = core.get("eps", {})
        for _path, val in (eps or {}).items():
            if isinstance(val, dict) and ("label_id" in val or "method" in val):
                return str(val.get("label_id", "1"))
            if isinstance(val, dict):
                for _m, ep in val.items():
                    if isinstance(ep, dict):
                        return str(ep.get("label_id", "1"))
        if "1" in self.labels:
            return "1"
        for k in self.labels.keys():
            if k != "_anon":
                return str(k)
        return "1"


def run_with_debug(
    engine: RuntimeEngine,
    label: str,
    frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Agent-facing runner: one call returns result or structured error plus trace.

    Contract for autonomous repair loops:
    - On success: {"ok": True, "result": <return value>, "trace": [...]}
    - On AinlRuntimeError: {"ok": False, "error": e.to_dict(), "trace": [...]}
    - Other exceptions propagate (no catch-all).

    Enable trace when building the engine (trace=True) so "trace" is populated.
    """
    frame = dict(frame or {})
    try:
        out = engine.run_label(label, frame)
        return {"ok": True, "result": out, "trace": engine.get_trace()}
    except AinlRuntimeError as e:
        return {"ok": False, "error": e.to_dict(), "trace": engine.get_trace()}
