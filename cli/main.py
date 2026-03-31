#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque
import datetime
import time

from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.executor_bridge import ExecutorBridgeAdapter
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.replay import RecordingAdapterRegistry, ReplayAdapterRegistry
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.adapters.tools import ToolBridgeAdapter
from runtime.adapters.wasm import WasmAdapter
from runtime.adapters.memory import MemoryAdapter
from runtime.sandbox_shim import SandboxClient
from runtime.engine import RuntimeEngine


def _parse_bridge_endpoints(items: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in items or []:
        if "=" not in raw:
            raise SystemExit(f"--bridge-endpoint must be NAME=URL, got {raw!r}")
        k, v = raw.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            raise SystemExit(f"invalid --bridge-endpoint: {raw!r}")
        out[k] = v
    return out


def _limits_from_args(args: argparse.Namespace) -> dict:
    out = {}
    for k in ("max_steps", "max_depth", "max_adapter_calls", "max_time_ms", "max_frame_bytes", "max_loop_iters"):
        v = getattr(args, k, None)
        if v is not None:
            out[k] = v
    return out


def _adapter_registry_from_args(args: argparse.Namespace):
    if args.record_adapters and args.replay_adapters:
        raise SystemExit("--record-adapters and --replay-adapters are mutually exclusive")
    allowed = [
        "core",
        "ext",
        "http",
        "bridge",
        "sqlite",
        "postgres",
        "mysql",
        "redis",
        "dynamodb",
        "airtable",
        "supabase",
        "fs",
        "tools",
        "db",
        "api",
        "cache",
        "queue",
        "txn",
        "auth",
        "wasm",
        "memory",
        "vector_memory",
        "embedding_memory",
        "code_context",
        "tool_registry",
        "langchain_tool",
    ]
    if args.replay_adapters:
        data = json.loads(Path(args.replay_adapters).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit("--replay-adapters must point to a JSON array call log")
        return ReplayAdapterRegistry(data, allowed=allowed)
    if args.record_adapters:
        return RecordingAdapterRegistry(allowed=allowed)
    return AdapterRegistry(allowed=allowed)


class _EchoAdapter(RuntimeAdapter):
    def call(self, target, args, context):
        return args[0] if args else target


class _InMemoryDbAdapter(RuntimeAdapter):
    def __init__(self):
        self.rows: Dict[str, List[Dict[str, Any]]] = {}
        self.seq = 0

    def call(self, target, args, context):
        verb = str(target or "").upper()
        entity = str(args[0]) if len(args) > 0 else "Entity"
        payload = args[1] if len(args) > 1 else None
        rows = self.rows.setdefault(entity, [])
        if verb == "F":
            return list(rows)
        if verb == "G":
            if payload is None:
                return rows[0] if rows else None
            for row in rows:
                if row.get("id") == payload:
                    return row
            return None
        if verb in {"C", "P"}:
            self.seq += 1
            row = {"id": self.seq}
            if isinstance(payload, dict):
                row.update(payload)
            rows.append(row)
            return row
        if verb == "U":
            if rows and isinstance(payload, dict):
                rows[0].update(payload)
                return rows[0]
            return rows[0] if rows else None
        if verb == "D":
            if not rows:
                return False
            if payload is None:
                rows.pop(0)
                return True
            for i, row in enumerate(rows):
                if row.get("id") == payload:
                    rows.pop(i)
                    return True
            return False
        return []


class _NullApiAdapter(RuntimeAdapter):
    def call(self, target, args, context):
        verb = str(target or "").upper()
        path = str(args[0]) if args else "/"
        body = args[1] if len(args) > 1 else None
        if verb in {"G", "GET"}:
            return {"ok": True, "method": "GET", "path": path, "data": []}
        if verb in {"P", "POST"}:
            return {"ok": True, "method": "POST", "path": path, "body": body}
        return {"ok": True, "method": verb or "GET", "path": path}


def _register_enabled_adapters(reg: AdapterRegistry, args: argparse.Namespace) -> None:
    enabled = set(args.enable_adapter or [])
    env_enable_ptc = str(os.environ.get("AINL_ENABLE_PTC", "")).strip().lower() in {"1", "true", "yes", "on"}
    if "ext" in enabled:
        reg.register("ext", _EchoAdapter())
    if "http" in enabled:
        reg.register(
            "http",
            SimpleHttpAdapter(
                default_timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
                allow_hosts=args.http_allow_host or [],
            ),
        )
    if "bridge" in enabled:
        endpoints = _parse_bridge_endpoints(getattr(args, "bridge_endpoint", None) or [])
        if not endpoints:
            raise SystemExit("--enable-adapter bridge requires at least one --bridge-endpoint NAME=URL")
        reg.register(
            "bridge",
            ExecutorBridgeAdapter(
                endpoints=endpoints,
                default_timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
                allow_hosts=args.http_allow_host or [],
            ),
        )
    if "sqlite" in enabled:
        db = args.sqlite_db or ":memory:"
        reg.register(
            "sqlite",
            SimpleSqliteAdapter(
                db_path=db,
                allow_write=bool(args.sqlite_allow_write),
                allow_tables=args.sqlite_allow_table or [],
                timeout_s=args.sqlite_timeout_s,
            ),
        )
    if "postgres" in enabled:
        from adapters.postgres import PostgresAdapter

        reg.register(
            "postgres",
            PostgresAdapter(
                dsn=args.postgres_url or None,
                host=args.postgres_host or None,
                port=args.postgres_port,
                database=args.postgres_db or None,
                user=args.postgres_user or None,
                password=args.postgres_password if args.postgres_password else None,
                sslmode=args.postgres_sslmode or None,
                sslrootcert=args.postgres_sslrootcert or None,
                timeout_s=args.postgres_timeout_s,
                statement_timeout_ms=args.postgres_statement_timeout_ms,
                allow_write=bool(args.postgres_allow_write),
                allow_tables=args.postgres_allow_table or [],
                pool_min_size=args.postgres_pool_min,
                pool_max_size=args.postgres_pool_max,
            ),
        )
    if "mysql" in enabled:
        from adapters.mysql import MySQLAdapter

        reg.register(
            "mysql",
            MySQLAdapter(
                dsn=args.mysql_url or None,
                host=args.mysql_host or None,
                port=args.mysql_port,
                database=args.mysql_db or None,
                user=args.mysql_user or None,
                password=args.mysql_password if args.mysql_password else None,
                ssl_mode=args.mysql_ssl_mode or None,
                ssl_ca=args.mysql_ssl_ca or None,
                timeout_s=args.mysql_timeout_s,
                allow_write=bool(args.mysql_allow_write),
                allow_tables=args.mysql_allow_table or [],
                pool_min_size=args.mysql_pool_min,
                pool_max_size=args.mysql_pool_max,
            ),
        )
    if "redis" in enabled:
        from adapters.redis import RedisAdapter

        reg.register(
            "redis",
            RedisAdapter(
                url=args.redis_url or None,
                host=args.redis_host or None,
                port=args.redis_port,
                db=args.redis_db,
                username=args.redis_user or None,
                password=args.redis_password if args.redis_password else None,
                ssl=bool(args.redis_ssl),
                timeout_s=args.redis_timeout_s,
                allow_write=bool(args.redis_allow_write),
                allow_prefixes=args.redis_allow_prefix or [],
            ),
        )
    if "dynamodb" in enabled:
        from adapters.dynamodb import DynamoDBAdapter

        reg.register(
            "dynamodb",
            DynamoDBAdapter(
                url=args.dynamodb_url or None,
                region=args.dynamodb_region or None,
                timeout_s=args.dynamodb_timeout_s,
                allow_write=bool(args.dynamodb_allow_write),
                allow_tables=args.dynamodb_allow_table or [],
                consistent_read=bool(args.dynamodb_consistent_read),
            ),
        )
    if "airtable" in enabled:
        from adapters.airtable import AirtableAdapter

        reg.register(
            "airtable",
            AirtableAdapter(
                api_key=args.airtable_api_key or None,
                base_id=args.airtable_base_id or None,
                timeout_s=args.airtable_timeout_s,
                allow_write=bool(args.airtable_allow_write),
                allow_tables=args.airtable_allow_table or [],
                allow_attachment_hosts=args.airtable_allow_attachment_host or [],
                max_page_size=args.airtable_max_page_size,
            ),
        )
    if "supabase" in enabled:
        from adapters.supabase import SupabaseAdapter

        reg.register(
            "supabase",
            SupabaseAdapter(
                db_url=args.supabase_db_url or None,
                supabase_url=args.supabase_url or None,
                anon_key=args.supabase_anon_key or None,
                service_role_key=args.supabase_service_role_key or None,
                timeout_s=args.supabase_timeout_s,
                allow_write=bool(args.supabase_allow_write),
                allow_tables=args.supabase_allow_table or [],
                allow_buckets=args.supabase_allow_bucket or [],
                allow_channels=args.supabase_allow_channel or [],
            ),
        )
    if "fs" in enabled:
        if not args.fs_root:
            raise SystemExit("--fs-root is required when --enable-adapter fs is used")
        reg.register(
            "fs",
            SandboxedFileSystemAdapter(
                sandbox_root=args.fs_root,
                max_read_bytes=args.fs_max_read_bytes,
                max_write_bytes=args.fs_max_write_bytes,
                allow_extensions=args.fs_allow_ext or [],
                allow_delete=bool(args.fs_allow_delete),
            ),
        )
    if "tools" in enabled:
        tools = {
            "echo": lambda *a, context=None: a[0] if a else None,
            "sum": lambda a, b, context=None: int(a) + int(b),
            "join": lambda sep, arr, context=None: str(sep).join([str(x) for x in (arr or [])]),
        }
        reg.register("tools", ToolBridgeAdapter(tools, allow_tools=args.tools_allow or tools.keys()))
    if "db" in enabled:
        reg.register("db", _InMemoryDbAdapter())
    if "api" in enabled:
        reg.register("api", _NullApiAdapter())
        if "wasm" in enabled:
            modules: Dict[str, str] = {}
            for raw in (getattr(args, "wasm_module", None) or []):
                if "=" not in raw:
                    raise SystemExit("--wasm-module entries must be name=path")
                name, path = raw.split("=", 1)
                name = name.strip()
                path = path.strip()
                if not name or not path:
                    raise SystemExit("--wasm-module entries must be name=path")
                modules[name] = path
            if not modules:
                raise SystemExit("--enable-adapter wasm requires at least one --wasm-module name=path")
            reg.register("wasm", WasmAdapter(modules=modules, allowed_modules=(getattr(args, "wasm_allow_module", None) or None)))
    # Always register memory (used by record_decision includes)
    mem_db = (
        str(getattr(args, "memory_db", "") or "").strip()
        or os.environ.get("AINL_MEMORY_DB")
        or str(Path.home() / ".openclaw" / "ainl_memory.sqlite3")
    )
    reg.register("memory", MemoryAdapter(db_path=mem_db))
    if "vector_memory" in enabled:
        from adapters.vector_memory import VectorMemoryAdapter

        reg.register("vector_memory", VectorMemoryAdapter())
    if "embedding_memory" in enabled:
        from adapters.embedding_memory import EmbeddingMemoryAdapter

        reg.register("embedding_memory", EmbeddingMemoryAdapter())
    if "code_context" in enabled:
        from adapters.code_context import CodeContextAdapter

        reg.register("code_context", CodeContextAdapter())
    if "tool_registry" in enabled:
        from adapters.tool_registry import ToolRegistryAdapter

        reg.register("tool_registry", ToolRegistryAdapter())
    if "langchain_tool" in enabled:
        from adapters.langchain_tool import LangchainToolAdapter

        reg.register("langchain_tool", LangchainToolAdapter())
    if "ptc_runner" in enabled or env_enable_ptc:
        from adapters.ptc_runner import PtcRunnerAdapter

        reg.register(
            "ptc_runner",
            PtcRunnerAdapter(
                enabled=True,
                allow_hosts=args.http_allow_host or [],
                timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
            ),
        )
    if "llm_query" in enabled or str(os.environ.get("AINL_ENABLE_LLM_QUERY", "")).strip().lower() in {"1", "true", "yes", "on"}:
        from adapters.llm_query import LlmQueryAdapter

        reg.register(
            "llm_query",
            LlmQueryAdapter(
                enabled=True,
                allow_hosts=args.http_allow_host or [],
                timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
            ),
        )
    if "audit_trail" in enabled:
        from adapters.audit_trail import AuditTrailAdapter

        sink = str(getattr(args, "audit_sink", "") or "").strip() or os.environ.get("AINL_AUDIT_SINK", "").strip() or "stderr://"
        reg.register("audit_trail", AuditTrailAdapter(sink=sink))


def _pretty_runtime_error(err: Exception) -> str:
    msg = str(err)
    m = re.search(r"\[line=(\d+)\s+source=(.+?)\]", msg)
    if not m:
        return msg
    line_no = m.group(1)
    raw_src = m.group(2)
    try:
        src = ast.literal_eval(raw_src)
    except Exception:
        src = raw_src.strip("'")
    caret_col = 0
    while caret_col < len(src) and src[caret_col] in (" ", "\t"):
        caret_col += 1
    caret = " " * caret_col + "^"
    return f"{msg}\n  line {line_no}: {src}\n           {caret}"



def _load_config(args) -> dict:
    """Load YAML config from args.config or AINL_CONFIG env, expanding environment variables."""
    import yaml
    config_path = getattr(args, "config", None) or os.environ.get("AINL_CONFIG")
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    # Recursively expand environment variables in all strings
    def _expand(value):
        if isinstance(value, str):
            return os.path.expandvars(value)
        if isinstance(value, dict):
            return {k: _expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_expand(v) for v in value]
        return value
    return _expand(raw)


def cmd_run_hybrid_ptc(args: argparse.Namespace) -> int:

    print("Running hybrid PTC order processor example...")
    print("  source: examples/hybrid_order_processor.ainl")
    print(f"  trace:  {args.trace_jsonl}")
    print("  mock:  ", "yes" if os.environ.get("AINL_PTC_RUNNER_MOCK") else "no (live)")
    print()
    print("Next steps:")
    print("  Export PTC JSONL:     PYTHONPATH=. python3 scripts/ainl_trace_viewer.py --ptc-export")
    print("  LangGraph bridge:     PYTHONPATH=. python3 scripts/run_intelligence.py ptc_to_langgraph_bridge")
    print()

    # Build a namespace that cmd_run accepts, re-using all existing defaults.
    run_args = argparse.Namespace(
        file="examples/hybrid_order_processor.ainl",
        label="",
        strict=False,
        strict_reachability=False,
        trace=False,
        log_trajectory=False,
        trace_jsonl=args.trace_jsonl,
        json=False,
        no_step_fallback=False,
        execution_mode="graph-preferred",
        unknown_op_policy=None,
        runtime_async=False,
        trace_out="",
        record_adapters="",
        replay_adapters="",
        enable_adapter=["ptc_runner"],
        bridge_endpoint=[],
        http_allow_host=["localhost"],
        http_timeout_s=5.0,
        http_max_response_bytes=1_000_000,
        sqlite_db="",
        sqlite_allow_write=False,
        sqlite_allow_table=[],
        sqlite_timeout_s=5.0,
        fs_root="",
        fs_max_read_bytes=1_000_000,
        fs_max_write_bytes=1_000_000,
        fs_allow_ext=[],
        fs_allow_delete=False,
        tools_allow=[],
        wasm_module=[],
        wasm_allow_module=[],
        memory_db="",
        max_steps=None,
        max_depth=None,
        max_adapter_calls=None,
        max_time_ms=None,
        max_frame_bytes=None,
        max_loop_iters=None,
        self_test_graph=False,
    )
    return cmd_run(run_args)


def cmd_run(args: argparse.Namespace) -> int:
    if args.self_test_graph:
        return cmd_self_test_graph(args)
    if not args.file:
        raise SystemExit("run requires <file> unless --self-test-graph is set")
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    reg = _adapter_registry_from_args(args)
    config = _load_config(args)
    # Register LLM adapters only if LLM configuration is present
    if config.get("llm") and (config["llm"].get("fallback_chain") or config["llm"].get("providers")):
        from adapters import register_llm_adapters
        register_llm_adapters(reg, config)
    _register_enabled_adapters(reg, args)
    env_traj = os.environ.get("AINL_LOG_TRAJECTORY", "").strip().lower()
    trajectory_path: Optional[str] = None
    if getattr(args, "trace_jsonl", ""):
        raw = str(args.trace_jsonl).strip()
        trajectory_path = "/dev/stdout" if raw == "-" else str(Path(raw).expanduser())
    elif getattr(args, "log_trajectory", False) or env_traj in ("1", "true", "yes", "on"):
        trajectory_path = str(Path(src_path).parent / (Path(src_path).stem + ".trajectory.jsonl"))
    sandbox_client = SandboxClient.try_connect(logger=lambda msg: print(msg))
    eng = RuntimeEngine.from_code(
        code,
        strict=args.strict,
        strict_reachability=getattr(args, "strict_reachability", False),
        trace=args.trace,
        step_fallback=not args.no_step_fallback,
        execution_mode=args.execution_mode,
        unknown_op_policy=args.unknown_op_policy,
        limits=_limits_from_args(args),
        adapters=reg,
        source_path=src_path,
        trajectory_log_path=trajectory_path,
        avm_event_hasher=sandbox_client.event_hash if sandbox_client.connected else None,
        sandbox_metadata_provider=sandbox_client.trajectory_metadata if sandbox_client.connected else None,
        runtime_async=bool(getattr(args, "runtime_async", False)),
        observability=bool(getattr(args, "observability", False)),
        observability_jsonl_path=str(getattr(args, "observability_jsonl", "") or "").strip() or None,
    )
    try:
        label = args.label or eng.default_entry_label()
        try:
            if getattr(eng, "runtime_async", False):
                result = asyncio.run(eng.run_label_async(label, frame={}))
            else:
                result = eng.run_label(label, frame={})
            payload = {"ok": True, "label": str(label), "result": result, "runtime_version": eng.runtime_version}
        except Exception as e:
            payload = {"ok": False, "label": str(label), "error": str(e), "runtime_version": eng.runtime_version}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(_pretty_runtime_error(e))
            return 1
        if args.trace:
            payload["trace"] = eng.trace_events
            if args.trace_out:
                Path(args.trace_out).write_text(json.dumps(eng.trace_events, indent=2), encoding="utf-8")
        if reg is not None and args.record_adapters:
            Path(args.record_adapters).write_text(json.dumps(getattr(reg, "call_log", []), indent=2), encoding="utf-8")
            payload["adapter_calls_recorded"] = len(getattr(reg, "call_log", []))
        if reg is not None and args.replay_adapters:
            payload["adapter_calls_replayed"] = len(getattr(reg, "call_log", []))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(payload)
        return 0
    finally:
        eng.close()


def cmd_self_test_graph(args: argparse.Namespace) -> int:
    tests = [
        {
            "name": "graph_add",
            "code": "L1: R core.add 2 3 ->x J x\n",
            "expect": 5,
            "should_error": False,
        },
        {
            "name": "graph_if_call",
            "code": "L1: Set cond true If cond ->L2 ->L3\nL2: Call L9 J _call_result\nL3: Set bad nope J bad\nL9: R core.add 20 22 ->v J v\n",
            "expect": 42,
            "should_error": False,
        },
        {
            "name": "graph_while_guard",
            "code": "L1: Set cond true While cond ->L2 ->L3\nL2: J keep_going\nL3: J done\n",
            "expect_contains": "while loop iteration limit exceeded",
            "should_error": True,
        },
    ]

    results = []
    all_ok = True
    for t in tests:
        item = {"name": t["name"], "ok": False}
        try:
            eng = RuntimeEngine.from_code(
                t["code"],
                strict=True,
                trace=False,
                step_fallback=False,
                execution_mode="graph-only",
            )
            out = eng.run_label("1")
            if t["should_error"]:
                item["ok"] = False
                item["error"] = f"expected error, got result={out!r}"
                all_ok = False
            else:
                item["ok"] = out == t["expect"]
                item["result"] = out
                if not item["ok"]:
                    item["error"] = f"expected {t['expect']!r}, got {out!r}"
                    all_ok = False
        except Exception as e:
            if t["should_error"]:
                msg = str(e)
                want = t.get("expect_contains", "")
                item["ok"] = want in msg if want else True
                item["error"] = msg
                if not item["ok"]:
                    all_ok = False
            else:
                item["ok"] = False
                item["error"] = str(e)
                all_ok = False
        results.append(item)

    payload = {"ok": all_ok, "mode": "graph_only", "tests": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload)
    return 0 if all_ok else 1


def cmd_check(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    c = AICodeCompiler(strict_mode=args.strict)
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    ok = len(ir.get("errors", [])) == 0
    diagnostics = list(ir.get("diagnostics") or [])
    if not diagnostics:
        src_lines = (ir.get("source") or {}).get("lines", [])
        for e in ir.get("errors", []):
            m = re.search(r"Line\s+(\d+)", str(e))
            if not m:
                continue
            ln = int(m.group(1))
            line = src_lines[ln - 1] if 0 <= ln - 1 < len(src_lines) else ""
            diagnostics.append({"line": ln, "source": line, "error": e})
    payload = {
        "ok": ok,
        "ir_version": ir.get("ir_version"),
        "errors": ir.get("errors", []),
        "warnings": ir.get("warnings", []),
        "meta": ir.get("meta", []),
        "diagnostics": diagnostics,
    }
    if bool(getattr(args, "estimate", False)):
        try:
            from tooling.cost_estimate import estimate_ir_cost, format_estimate_table

            est = estimate_ir_cost(ir)
            payload["cost_estimate"] = est
            # Human table to stderr, JSON stays on stdout.
            sys.stderr.write(format_estimate_table(est))
        except Exception as _e:
            payload["cost_estimate"] = {"error": str(_e)}
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


def cmd_compile(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()

    c = AICodeCompiler(strict_mode=bool(args.strict))
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1

    emit = str(getattr(args, "emit", "ir") or "ir").strip().lower()
    if emit == "ir":
        print(json.dumps(ir, indent=2))
        return 0

    if emit in ("hermes-skill", "hermes"):
        stem = Path(src_path).stem
        out_raw = str(getattr(args, "output", "") or "").strip()
        out_dir = Path(out_raw).expanduser() if out_raw else Path.cwd() / f"{stem}_hermes_skill"
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle = c.emit_hermes_skill_bundle(ir, ainl_source=code, skill_name=stem, source_stem=stem)
        written = []
        for rel, content in sorted(bundle.items()):
            p = out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(str(p.resolve()))
        print(json.dumps({"ok": True, "emit": "hermes-skill", "dir": str(out_dir.resolve()), "files": written}, indent=2))
        return 0

    if emit in ("solana-client", "blockchain-client"):
        stem = Path(src_path).stem
        out_raw = str(getattr(args, "output", "") or "").strip()
        out_path = Path(out_raw).expanduser() if out_raw else Path.cwd() / "solana_client.py"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = c.emit_solana_client(ir, source_stem=stem)
        out_path.write_text(content, encoding="utf-8")
        print(
            json.dumps(
                {"ok": True, "emit": emit, "path": str(out_path.resolve()), "source_stem": stem},
                indent=2,
            )
        )
        return 0

    print(json.dumps({"ok": False, "error": f"unknown --emit target: {emit!r}"}, indent=2))
    return 2


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate an .ainl file. With --json-output emits the full compiled IR."""
    if getattr(args, "json_output", False):
        src_path = str(Path(args.file).resolve())
        with open(src_path, "r", encoding="utf-8") as f:
            code = f.read()
        c = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False)))
        ir = c.compile(code, emit_graph=True, source_path=src_path)
        ok = len(ir.get("errors", [])) == 0
        ir["_validation"] = {
            "ok": ok,
            "source_path": src_path,
            "strict": bool(getattr(args, "strict", False)),
        }
        print(json.dumps(ir, indent=2))
        return 0 if ok else 1
    return cmd_check(args)


def cmd_emit(args: argparse.Namespace) -> int:
    """Compile an .ainl file and emit to a target platform."""
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()

    c = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False)))
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1

    target = str(args.target).strip().lower()
    stem = Path(src_path).stem
    out_raw = str(getattr(args, "output", "") or "").strip()

    # IR passthrough
    if target == "ir":
        print(json.dumps(ir, indent=2))
        return 0

    # Hermes skill bundle
    if target in ("hermes-skill", "hermes"):
        out_dir = Path(out_raw).expanduser() if out_raw else Path.cwd() / f"{stem}_hermes_skill"
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle = c.emit_hermes_skill_bundle(ir, ainl_source=code, skill_name=stem, source_stem=stem)
        written = []
        for rel, content in sorted(bundle.items()):
            p = out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(str(p.resolve()))
        print(json.dumps({"ok": True, "emit": target, "dir": str(out_dir.resolve()), "files": written}, indent=2))
        return 0

    # Solana / blockchain client
    if target in ("solana-client", "blockchain-client"):
        out_path = Path(out_raw).expanduser() if out_raw else Path.cwd() / "solana_client.py"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = c.emit_solana_client(ir, source_stem=stem)
        out_path.write_text(content, encoding="utf-8")
        print(json.dumps({"ok": True, "emit": target, "path": str(out_path.resolve())}, indent=2))
        return 0

    # LangGraph hybrid wrapper
    if target == "langgraph":
        import scripts.emit_langgraph as emit_langgraph
        out_path = Path(out_raw).expanduser() if out_raw else Path.cwd() / f"{stem}_langgraph.py"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        emit_langgraph.emit_langgraph_to_path(ir, out_path, source_stem=stem)
        print(json.dumps({"ok": True, "emit": "langgraph", "path": str(out_path.resolve()), "source_stem": stem}, indent=2))
        return 0

    # Temporal hybrid wrapper
    if target == "temporal":
        import scripts.emit_temporal as emit_temporal
        out_dir = Path(out_raw).expanduser() if out_raw else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        act_path, wf_path = emit_temporal.emit_temporal_pair(ir, output_dir=out_dir, source_stem=stem)
        print(json.dumps({"ok": True, "emit": "temporal", "dir": str(out_dir.resolve()), "files": [str(act_path), str(wf_path)]}, indent=2))
        return 0

    # Emitters available on the compiler
    emitter_map = {
        "server": "emit_server",
        "python-api": "emit_python_api",
        "react": "emit_react",
        "openapi": "emit_openapi",
        "prisma": "emit_prisma_schema",
        "sql": "emit_sql_migrations",
        "docker": "emit_dockerfile",
        "k8s": "emit_k8s",
        "cron": "emit_cron_stub",
    }
    if target in emitter_map:
        method = getattr(c, emitter_map[target], None)
        if method:
            content = method(ir)
            if out_raw:
                out_path = Path(out_raw).expanduser()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(str(content), encoding="utf-8")
                print(json.dumps({"ok": True, "emit": target, "path": str(out_path.resolve())}, indent=2))
            else:
                if isinstance(content, dict):
                    print(json.dumps(content, indent=2))
                else:
                    print(content)
            return 0

    print(json.dumps({"ok": False, "error": f"unknown --target: {target!r}"}, indent=2))
    return 2

# ====================== OpenFang Integration ======================
# AINL-OPENFANG-TOP1

def cmd_install_openfang_one_command(args: argparse.Namespace) -> int:
    """One-command OpenFang install + health check (mirrors OpenClaw)."""
    from pathlib import Path
    import subprocess
    import sys

    from tooling.openfang_install import run_install_openfang
    from openfang.bridge.ainl_bridge_main import ainl_openfang_validate
    from openfang.bridge.user_friendly_error import INIT_INSTALL_OPENFANG, user_friendly_ainl_error

    dry = bool(getattr(args, "install_openfang_dry_run", False))
    verbose = bool(getattr(args, "install_openfang_verbose", False))

    # 1) pip install ainl[mcp] (unless dry-run)
    if not dry:
        code = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "ainativelang[mcp]"]).returncode
        if code != 0:
            print("pip install failed", file=sys.stderr)
            return code

    # 2) MCP registration
    home = Path.home()
    try:
        from tooling.mcp_host_install import ensure_mcp_registration as _ensure_mcp_registration
        from tooling.mcp_host_install import OPENFANG_PROFILE
        _ensure_mcp_registration(OPENFANG_PROFILE, home=home, dry_run=dry, verbose=verbose)
    except Exception as e:
        print(f"MCP registration failed: {e}", file=sys.stderr)
        return 1

    # 3) ainl-run wrapper
    try:
        from tooling.mcp_host_install import ensure_ainl_run_wrapper as _ensure_ainl_run_wrapper
        _ensure_ainl_run_wrapper(OPENFANG_PROFILE, home=home, dry_run=dry, verbose=verbose)
    except Exception as e:
        print(f"Wrapper install failed: {e}", file=sys.stderr)
        return 1

    # 4) PATH hint in shell RC
    try:
        from tooling.mcp_host_install import ensure_path_hint_in_shell_rc as _ensure_path_hint
        _ensure_path_hint(OPENFANG_PROFILE, home=home, dry_run=dry, verbose=verbose)
    except Exception as e:
        print(f"PATH hint failed: {e}", file=sys.stderr)
        # continue

    # 5) Validate install
    val = ainl_openfang_validate()
    if not val["ok"] or val.get("missing_env"):
        print(user_friendly_ainl_error(INIT_INSTALL_OPENFANG, val))
        return 1

    ok = True
    if val.get("cron_ok") is False:
        print("Warning: OpenFang cron integration incomplete: " + str(val.get("cron_detail", "")))
        ok = False
    if val["warnings"]:
        for w in val["warnings"]:
            print("Warning:", w)

    print("AINL OpenFang MCP bootstrap complete. " + OPENFANG_PROFILE.success_tip)
    return 0 if ok else 1


def cmd_cron_add_openfang(args: argparse.Namespace) -> int:
    """Schedule an .ainl file to run as an OpenFang hand."""
    ainl_path = Path(args.ainl_path).resolve()
    if not ainl_path.exists():
        print(f"File not found: {ainl_path}", file=sys.stderr)
        return 2

    name = getattr(args, "name", "") or f"AINL: {ainl_path.stem}"
    cron_expr = getattr(args, "cron", "") or getattr(args, "every", "")
    if not cron_expr:
        print("Must specify either --cron or --every", file=sys.stderr)
        return 2

    # Use openfang cron add command
    cmd = ["openfang", "cron", "add", str(ainl_path), "--name", name, "--cron", cron_expr]
    if getattr(args, "every", ""):
        cmd = ["openfang", "cron", "add", str(ainl_path), "--name", name, "--every", args.every]
    if getattr(args, "agent", ""):
        cmd.extend(["--agent", args.agent])
    if getattr(args, "session", ""):
        cmd.extend(["--session", args.session])
    if getattr(args, "announce", False):
        cmd.append("--announce")

    if getattr(args, "cron_dry_run", False):
        print("[dry-run] would run:", " ".join(map(shlex.quote, cmd)))
        return 0

    subprocess.run(cmd, check=False)
    return 0


def cmd_status_openfang(args: argparse.Namespace) -> int:
    """Show OpenFang integration status."""
    import json
    import shutil
    import subprocess
    from datetime import datetime, timezone

    from openfang.bridge.cron_drift_check import run_report as _cron_drift_report
    from openfang.bridge.schema_bootstrap import bootstrap_tables
    from openfang.bridge.user_friendly_error import INIT_INSTALL_OPENFANG, user_friendly_ainl_error

    json_out = bool(getattr(args, "status_json", False))
    ws = _openfang_default_workspace()
    db_path = Path(os.getenv("OPENFANG_MEMORY_DB", str(ws / ".ainl" / "ainl_memory.sqlite3"))).expanduser()
    schema_ok, schema_detail = bootstrap_tables(db_path)

    # Check OpenFang cron jobs (we assume they're managed by openfang CLI)
    cron_ok = True
    cron_detail = "ok"
    try:
        # Try to list OpenFang crons if possible; not critical
        pass
    except Exception:
        pass

    val = {
        "openfang_installed": shutil.which("openfang") is not None,
        "ainl_mcp_registered": True,  # could check file existence
        "schema_ok": schema_ok,
        "schema_detail": schema_detail,
        "database_path": str(db_path),
    }

    if json_out:
        print(json.dumps(val, indent=2))
    else:
        print("OpenFang Integration Status:")
        for k, v in val.items():
            print(f"  {k}: {v}")
        if not schema_ok:
            print("  Note:", schema_detail)
    return 0 if schema_ok else 1


def cmd_migrate_openclaw_to_openfang(args: argparse.Namespace) -> int:
    """Migrate OpenClaw workspace configuration to OpenFang."""
    print("OpenFang migration: This tool will copy your OpenClaw config and hands to OpenFang format.")
    src = Path.home() / ".openclaw"
    dst = Path.home() / ".openfang"
    if not src.exists():
        print(f"OpenClaw workspace not found at {src}", file=sys.stderr)
        return 2

    # Copy config and data directories
    for sub in ["config.toml", "workspace", "data"]:
        src_item = src / sub
        if src_item.exists():
            dst_item = dst / sub
            dst_item.parent.mkdir(parents=True, exist_ok=True)
            if src_item.is_dir():
                shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(src_item, dst_item)
            print(f"Copied {src_item} -> {dst_item}")

    # Reconfigure MCP if needed
    print("Migration complete. Run 'ainl install openfang' to ensure MCP integration.")
    return 0


def _openfang_default_workspace() -> Path:
    """Guess OpenFang workspace root: ~/.openfang/workspace if present, else cwd."""
    default_ws = Path.home() / ".openfang" / "workspace"
    if default_ws.exists():
        return default_ws
    return Path.cwd()

# ================================================================
class MetricsCollector:
    """Simple in-memory metrics collector for dashboard."""

    def __init__(self):
        self.total_validations = 0
        self.successes = 0
        self.errors = 0
        self.error_categories: Dict[str, int] = {}
        # Keep last 1000 validation results for history
        self.history: deque = deque(maxlen=1000)

    def record_validation(self, ok: bool, errors: List[Dict], duration_ms: float = 0):
        self.total_validations += 1
        if ok:
            self.successes += 1
        else:
            self.errors += 1
            for err in errors:
                cat = self._categorize_error(err)
                self.error_categories[cat] = self.error_categories.get(cat, 0) + 1
        self.history.append({
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "ok": ok,
            "errors": errors if not ok else [],
            "duration_ms": duration_ms,
        })

    def _categorize_error(self, err: Dict) -> str:
        msg = err.get("message", "").lower()
        if "strict" in msg or "if" in msg:
            return "compile"
        if "adapter" in msg or "connection" in msg or "timeout" in msg:
            return "adapter"
        if "input" in msg or "missing" in msg or "required" in msg:
            return "input"
        return "other"

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "period": "24h",
            "total_validations": self.total_validations,
            "successes": self.successes,
            "errors": self.errors,
            "success_rate": self.successes / self.total_validations if self.total_validations > 0 else 0,
            "adapter_metrics": {},  # TODO: instrument adapter calls
            "top_errors": sorted([
                {"category": cat, "count": cnt, "sample": ""}
                for cat, cnt in self.error_categories.items()
            ], key=lambda x: x["count"], reverse=True)[:5],
        }

    def get_history(self, limit: int = 100):
        return list(self.history)[-limit:]
def cmd_serve(args: argparse.Namespace) -> int:
    """Start an HTTP server that validates and runs AINL files via REST API."""
    host = getattr(args, "host", "0.0.0.0")
    port = int(getattr(args, "port", 8080))

    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
    except ImportError:
        print(json.dumps({"ok": False, "error": "http.server not available"}))
        return 1
    metrics = MetricsCollector()


    class AINLRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/validate" or self.path == "/check":
                try:
                    payload = json.loads(body) if body.strip().startswith("{") else {"source": body}
                    source = payload.get("source", body)
                    strict = payload.get("strict", False)
                    start = time.time()
                    c = AICodeCompiler(strict_mode=strict)
                    ir = c.compile(source, emit_graph=True)
                    duration = (time.time() - start) * 1000
                    errors = ir.get("errors", [])
                    ok = len(errors) == 0
                    metrics.record_validation(ok, errors, duration)
                    result = {
                        "ok": ok,
                        "ir_version": ir.get("ir_version"),
                        "errors": errors,
                        "warnings": ir.get("warnings", []),
                        "diagnostics": list(ir.get("diagnostics") or []),
                    }
                    self._json_response(200 if ok else 400, result)
                except Exception as e:
                    duration = (time.time() - start) * 1000 if "start" in locals() else 0
                    metrics.record_validation(False, [{"message": str(e)}], duration)
                    self._json_response(500, {"ok": False, "error": str(e)})

            elif self.path == "/compile":
                try:
                    payload = json.loads(body) if body.strip().startswith("{") else {"source": body}
                    source = payload.get("source", body)
                    strict = payload.get("strict", False)
                    start = time.time()
                    c = AICodeCompiler(strict_mode=strict)
                    ir = c.compile(source, emit_graph=True)
                    duration = (time.time() - start) * 1000
                    errors = ir.get("errors", [])
                    if errors:
                        metrics.record_validation(False, errors, duration)
                        self._json_response(400, {"ok": False, "errors": errors})
                    else:
                        metrics.record_validation(True, [], duration)
                        self._json_response(200, ir)
                except Exception as e:
                    duration = (time.time() - start) * 1000 if "start" in locals() else 0
                    metrics.record_validation(False, [{"message": str(e)}], duration)
                    self._json_response(500, {"ok": False, "error": str(e)})

            elif self.path == "/run":
                try:
                    payload = json.loads(body) if body.strip().startswith("{") else {"source": body}
                    source = payload.get("source", body)
                    strict = payload.get("strict", False)
                    frame = payload.get("frame", {})
                    start = time.time()
                    c = AICodeCompiler(strict_mode=strict)
                    ir = c.compile(source, emit_graph=True)
                    compile_errors = ir.get("errors", [])
                    compile_duration = (time.time() - start) * 1000
                    if compile_errors:
                        metrics.record_validation(False, compile_errors, compile_duration)
                        self._json_response(400, {"ok": False, "errors": compile_errors})
                        return
                    engine = RuntimeEngine(ir)
                    result = engine.run(source, frame=frame)
                    run_duration = (time.time() - start) * 1000
                    ok = result.get("ok", False) if isinstance(result, dict) else False
                    errors = result.get("errors", []) if isinstance(result, dict) else []
                    metrics.record_validation(ok, errors, run_duration)
                    self._json_response(200, result)
                except Exception as e:
                    duration = (time.time() - start) * 1000 if "start" in locals() else 0
                    metrics.record_validation(False, [{"message": str(e)}], duration)
                    self._json_response(500, {"ok": False, "error": str(e)})

            else:
                self._json_response(404, {"error": f"Unknown endpoint: {self.path}", "endpoints": ["/validate", "/compile", "/run"]})
        def do_GET(self):
            if self.path == "/health" or self.path == "/":
                self._json_response(200, {
                    "status": "ok",
                    "service": "ainl-serve",
                    "version": "1.3.3",
                    "endpoints": {
                        "POST /validate": "Validate AINL source (JSON body: {source, strict?})",
                        "POST /compile": "Compile AINL source to IR (JSON body: {source, strict?})",
                        "POST /run": "Compile and run AINL source (JSON body: {source, strict?, frame?})",
                        "GET /health": "Health check",
                        "GET /metrics": "Get aggregated validation metrics",
                        "GET /history": "Get recent validation history (X-Limit header)",
                    },
                })
            elif self.path == "/metrics":
                self._json_response(200, metrics.get_metrics())
            elif self.path == "/history":
                limit = int(self.headers.get("X-Limit", "100"))
                self._json_response(200, {"history": metrics.get_history(limit)})
            else:
                self._json_response(404, {"error": "Not found"})

        def _json_response(self, status: int, data: dict):
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *a):
            import sys
            sys.stderr.write(f"[ainl-serve] {self.address_string()} {format % a}\n")

    print(f"Starting AINL server on {host}:{port}")
    print(f"Endpoints: POST /validate, POST /compile, POST /run, GET /health")
    server = HTTPServer((host, port), AINLRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    c = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False)))
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    if bool(getattr(args, "estimate", False)):
        try:
            from tooling.cost_estimate import estimate_ir_cost

            ir["_cost_estimate"] = estimate_ir_cost(ir)
        except Exception as _e:
            ir["_cost_estimate"] = {"error": str(_e)}
    print(json.dumps(ir, indent=2))
    return 0 if not ir.get("errors") else 1


def cmd_generate_avm_policy(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    ir = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False))).compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1
    fragment = ir.get("avm_policy_fragment") or {"allowed_adapters": ["core"], "capability_policy_names": []}
    print(f"# Generated AVM policy fragment from {Path(src_path).name}")
    print("# Paste or merge this object into ~/.hyperspace/avm-policy.json")
    if args.output:
        Path(args.output).write_text(json.dumps(fragment, indent=2), encoding="utf-8")
        print(f"# Wrote JSON fragment to {args.output}")
    print(json.dumps(fragment, indent=2))
    return 0


def cmd_generate_sandbox_config(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    ir = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False))).compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1
    req = ir.get("execution_requirements") or {}
    avm_fragment = req.get("avm_policy_fragment") or ir.get("avm_policy_fragment") or {}
    target = str(args.target or "general")
    out: Dict[str, Any] = {
        "target": target,
        "execution_requirements": req,
        "avm_policy_fragment": avm_fragment,
        # Tiny, neutral sandbox hints for non-AVM runtimes.
        "sandbox_hints": {
            "isolation_level": req.get("isolation_level", "none"),
            "required_capabilities": req.get("required_capabilities", []),
            "ephemeral": req.get("ephemeral", True),
        },
    }
    print(f"# Generated sandbox config from {Path(src_path).name} (target={target})")
    print("# Paste/merge into your AVM policy, microVM wrapper, or sandbox runtime config.")
    if args.output:
        Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"# Wrote JSON config to {args.output}")
    print(json.dumps(out, indent=2))
    return 0


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_import_markdown(args: argparse.Namespace) -> int:
    """Fetch Markdown and write compiling .ainl (parsed graph when possible, else Phase-1 stub)."""
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import import_markdown_to_ainl

    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    gen_soul = bool(getattr(args, "generate_soul", False))
    if gen_soul and args.type != "agent":
        print("import markdown: --generate-soul applies only to --type agent", file=sys.stderr)
        return 1
    try:
        ainl, meta = import_markdown_to_ainl(
            args.url_or_path,
            md_type=args.type,
            personality=args.personality or "",
            openclaw_bridge=openclaw,
            generate_soul=gen_soul,
        )
    except Exception as e:
        if args.verbose:
            raise
        print(f"import markdown: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        for k, v in meta.items():
            if k == "sidecars" and v:
                print(f"{k}: SOUL.md + IDENTITY.md", file=sys.stderr)
                continue
            print(f"{k}: {v}", file=sys.stderr)

    if args.dry_run:
        print(ainl, end="")
        return 0

    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ainl, encoding="utf-8")
    kind = "stub AINL" if meta.get("fallback_stub") else "parsed AINL"
    print(f"Wrote {out} ({meta.get('markdown_chars', 0)} chars markdown → {kind})")
    side = meta.get("sidecars")
    if gen_soul and isinstance(side, dict):
        for fname, text in side.items():
            p = out.parent / fname
            p.write_text(text, encoding="utf-8")
            print(f"Wrote {p}")
    return 0


def _ecosystem_readme_blurb(*, upstream: str, slug: str, parsed: bool) -> str:
    p = "parsed" if parsed else "stub fallback"
    return "\n".join(
        [
            f"# {slug}",
            "",
            f"Upstream: {upstream}",
            "",
            "## Files",
            "",
            "- `original.md` — source Markdown from the ecosystem repo.",
            f"- `converted.ainl` — deterministic AINL graph ({p}).",
            "",
            "## Notes",
            "",
            "This folder is a **deterministic AINL version** of the prose workflow/agent spec — structured graph, explicit cron/steps or gates, and predictable control flow for **100% reliability** at compile/run time (vs free-form Markdown prompts).",
            "",
            "Diff vs upstream: headings and lists become `S core cron`, `Call` steps, `If` gates, and optional `memory` / `queue` bridge hooks instead of narrative instructions only.",
            "",
        ]
    )


def cmd_import_clawflows(args: argparse.Namespace) -> int:
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import (
        CLAWFLOWS_SAMPLE_URLS,
        DEFAULT_FETCH_TIMEOUT_S,
        load_markdown_source,
        markdown_to_ainl_from_body,
    )

    base = Path(args.output_dir).expanduser() if args.output_dir else root / "examples" / "ecosystem" / "clawflows"
    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    timeout = float(getattr(args, "timeout_s", DEFAULT_FETCH_TIMEOUT_S))
    ok = 0
    for slug, url in CLAWFLOWS_SAMPLE_URLS:
        try:
            _prov, md = load_markdown_source(url, timeout_s=timeout)
        except Exception as e:
            if args.verbose:
                raise
            print(f"import clawflows: skip {slug}: {e}", file=sys.stderr)
            continue
        sub = base / slug
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "original.md").write_text(md, encoding="utf-8")
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=url,
            md_type="workflow",
            openclaw_bridge=openclaw,
        )
        (sub / "converted.ainl").write_text(ainl, encoding="utf-8")
        (sub / "README.md").write_text(
            _ecosystem_readme_blurb(
                upstream=f"[nikilster/clawflows](https://github.com/nikilster/clawflows) `{slug}`",
                slug=slug,
                parsed=bool(meta.get("parsed")),
            ),
            encoding="utf-8",
        )
        ok += 1
        if args.verbose:
            print(f"{slug}: parsed={meta.get('parsed')} stub={meta.get('fallback_stub')}", file=sys.stderr)
    print(f"import clawflows: wrote {ok} workflow(s) under {base}")
    return 0 if ok else 1


def cmd_import_agency_agents(args: argparse.Namespace) -> int:
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import (
        AGENCY_AGENTS_SAMPLE_URLS,
        DEFAULT_FETCH_TIMEOUT_S,
        load_markdown_source,
        markdown_to_ainl_from_body,
    )

    base = Path(args.output_dir).expanduser() if args.output_dir else root / "examples" / "ecosystem" / "agency-agents"
    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    timeout = float(getattr(args, "timeout_s", DEFAULT_FETCH_TIMEOUT_S))
    ok = 0
    for slug, url in AGENCY_AGENTS_SAMPLE_URLS:
        try:
            _prov, md = load_markdown_source(url, timeout_s=timeout)
        except Exception as e:
            if args.verbose:
                raise
            print(f"import agency-agents: skip {slug}: {e}", file=sys.stderr)
            continue
        sub = base / slug
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "original.md").write_text(md, encoding="utf-8")
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=url,
            md_type="agent",
            personality=getattr(args, "personality", "") or "",
            openclaw_bridge=openclaw,
        )
        (sub / "converted.ainl").write_text(ainl, encoding="utf-8")
        (sub / "README.md").write_text(
            _ecosystem_readme_blurb(
                upstream=f"[msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) `{slug}`",
                slug=slug,
                parsed=bool(meta.get("parsed")),
            ),
            encoding="utf-8",
        )
        ok += 1
        if args.verbose:
            print(f"{slug}: parsed={meta.get('parsed')} stub={meta.get('fallback_stub')}", file=sys.stderr)
    print(f"import agency-agents: wrote {ok} agent(s) under {base}")
    return 0 if ok else 1


def cmd_golden(args: argparse.Namespace) -> int:
    examples_dir = Path(args.examples_dir)
    ainl_files = sorted(examples_dir.rglob("*.ainl"))
    if not ainl_files:
        raise SystemExit(f"no .ainl files found in {examples_dir}")
    profile_path = Path(__file__).resolve().parent.parent / "tooling" / "artifact_profiles.json"
    strict_map: Dict[str, bool] = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        for rel in profile.get("examples", {}).get("strict-valid", []):
            strict_map[str(rel)] = True
        for rel in profile.get("examples", {}).get("non-strict-only", []):
            strict_map[str(rel)] = False
    results = []
    ok_all = True
    for f in ainl_files:
        expected_path = f.with_suffix(".expected.json")
        if not expected_path.exists():
            continue
        try:
            rel = str(f.resolve().relative_to(Path(__file__).resolve().parent.parent))
        except Exception:
            rel = str(f)
        strict = bool(strict_map.get(rel, False))
        code = f.read_text(encoding="utf-8")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        payload = RuntimeEngine.run(
            code,
            frame={},
            strict=strict,
            trace=bool(args.trace),
            execution_mode=args.execution_mode,
            unknown_op_policy=args.unknown_op_policy,
            limits={"max_steps": args.max_steps} if args.max_steps else None,
        )
        same = payload.get("ok") == expected.get("ok") and str(payload.get("label")) == str(expected.get("label")) and payload.get(
            "result"
        ) == expected.get("result")
        results.append({"file": f.name, "ok": same, "result": payload.get("result"), "expected": expected.get("result")})
        if not same:
            ok_all = False
    out = {"ok": ok_all, "results": results}
    print(json.dumps(out, indent=2))
    return 0 if ok_all else 1


_INIT_MAIN_AINL = '''\
# {name}/main.ainl
# Generated by `ainl init` — edit freely, then:
#
#   ainl check main.ainl --strict   ← compile + validate strict graph semantics
#   ainl run   main.ainl            ← execute locally
#   ainl visualize main.ainl --output graph.mmd  ← render Mermaid control-flow diagram
#
# ─── AINL syntax cheat-sheet ───────────────────────────────────────────────────
#
#  HEADER LINE (required, once at the top):
#    S <scope> <adapter> <path>
#    e.g. S app core noop
#         ^   ^    ^
#         │   │    └─ route (noop = no external routing)
#         │   └────── adapter family (core, cache, email, http, llm, memory…)
#         └────────── scope name (app, worker, monitor, …)
#
#  LABELS  (L1:, L2:, END, …)
#    Each label is a control-flow node. Execution starts at L1:.
#    Every label must end with exactly one: J, If, or a jump to another label.
#
#  STEPS inside a label:
#    R <adapter>.<op> [args…] -><var>
#       "Request" — call an adapter operation and bind the result.
#       e.g.  R cache get "state" "last_run" ->last_run
#             R core.ADD 2 3 ->sum
#             R email G ->messages
#
#    X <var> <value>
#       "Assign" — set a local variable to a literal or expression.
#       e.g.  X greeting "Hello, world!"
#             X threshold 100
#
#    J <var>
#       "Join" — return the value of <var> and finish this node.
#       The runtime passes the value forward to the next graph stage.
#
#    If (<expr>) -><then-label> -><else-label>
#       "Branch" — conditional jump.
#       e.g.  If (core.gt count 0) ->L3 ->END
#
# ───────────────────────────────────────────────────────────────────────────────
# This starter program shows two patterns: a computation (L1) and a
# simple cache-read → branch flow (L2/L3/L4). Uncomment L2–L4 to try it.

S app core noop

# ── Pattern 1: Simple computation ───────────────────────────────────────────
L1:
  # R core.ADD calls the built-in core adapter's ADD operation.
  # The result is bound to the variable `sum`.
  R core.ADD 2 3 ->sum
  # J returns `sum` to the runtime and finishes this node.
  J sum

# ── Pattern 2: Cache read → branch (uncomment to activate) ──────────────────
# L2:
#   # Read a value from the cache adapter (key-value store).
#   # R cache get "<namespace>" "<key>" -><variable>
#   R cache get "state" "run_count" ->run_count
#   # Branch: if run_count > 0 go to L3, otherwise go to L4.
#   If (core.gt run_count 0) ->L3 ->L4
#
# L3:
#   X msg "Seen before — incrementing."
#   J msg
#
# L4:
#   X msg "First run!"
#   J msg

# END is the implicit terminal. Successful jumps without a target land here.
'''

_INIT_README = '''\
# {name}

Generated by `ainl init`. A minimal AINL worker ready to validate and run.

## 3-minute quickstart

```bash
# 1. Check the program compiles cleanly (strict graph semantics)
ainl check main.ainl --strict

# 2. Run it
ainl run main.ainl

# 3. Visualise the control-flow graph (paste output into https://mermaid.live)
ainl visualize main.ainl --output -

# 4. Inspect the canonical IR (useful for agent loops)
ainl inspect main.ainl --strict
```

## Next steps

- Edit `main.ainl` — add cache reads, HTTP calls, memory ops, or LLM steps.
- Browse `examples/` in the ainativelang repo for real production patterns.
- Read the docs: https://ainativelang.com/docs
- Deep dive: https://ainativelang.com/whitepaper
'''


def cmd_init(args: argparse.Namespace) -> int:
    """Create a new AINL project directory with a starter program and README."""
    import os

    name: str = args.name.strip()
    if not name:
        print("ainl init: project name must not be empty", file=sys.stderr)
        return 1

    target = os.path.join(args.output_dir or ".", name) if args.output_dir else name
    target = os.path.abspath(target)

    if os.path.exists(target):
        if not args.force:
            print(
                f"ainl init: directory already exists: {target}\n"
                "  Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1
    else:
        os.makedirs(target, exist_ok=True)

    main_ainl = os.path.join(target, "main.ainl")
    readme = os.path.join(target, "README.md")

    with open(main_ainl, "w") as fh:
        fh.write(_INIT_MAIN_AINL.format(name=name))
    with open(readme, "w") as fh:
        target_kind = str(getattr(args, "target", "") or "").strip().lower()
        body = _INIT_README.format(name=name)
        if target_kind in ("hermes", "hermes-agent"):
            body += "\n".join(
                [
                    "",
                    "## Hermes Agent target",
                    "",
                    "Emit this project as a Hermes skill bundle:",
                    "",
                    "```bash",
                    "ainl compile main.ainl --strict --emit hermes-skill -o ./dist/hermes-skill",
                    "# Copy ./dist/hermes-skill into ~/.hermes/skills/ainl-imports/<skill-name>/",
                    "```",
                    "",
                ]
            )
        fh.write(body)

    print(f"\n✓  Created AINL project: {target}/")
    print(f"   main.ainl   — starter workflow")
    print(f"   README.md   — quickstart steps")
    print(f"\nNext steps:")
    print(f"   cd {name}")
    print(f"   ainl check main.ainl --strict")
    print(f"   ainl run   main.ainl")
    print(f"   ainl visualize main.ainl --output -")
    print()
    return 0


def _openclaw_default_workspace() -> Path:  # AINL-OPENCLAW-TOP5
    env = str(os.getenv("OPENCLAW_WORKSPACE", "")).strip()  # AINL-OPENCLAW-TOP5
    if env:  # AINL-OPENCLAW-TOP5
        return Path(env).expanduser().resolve()  # AINL-OPENCLAW-TOP5
    ws = Path.home() / ".openclaw" / "workspace"  # AINL-OPENCLAW-TOP5
    return ws if ws.is_dir() else Path.cwd()  # AINL-OPENCLAW-TOP5

def _ai_native_lang_example_yml_path() -> Optional[Path]:  # AINL-OPENCLAW-TOP5
    """Return bundled example path if present (repo root or tooling package)."""  # AINL-OPENCLAW-TOP5
    root = _repo_root()  # AINL-OPENCLAW-TOP5
    for candidate in (root / "aiNativeLang.example.yml", root / "tooling" / "aiNativeLang.example.yml"):  # AINL-OPENCLAW-TOP5
        if candidate.is_file():  # AINL-OPENCLAW-TOP5
            return candidate  # AINL-OPENCLAW-TOP5
    return None  # AINL-OPENCLAW-TOP5


def _write_ai_native_lang_yml_if_missing(workspace: Path) -> bool:  # AINL-OPENCLAW-TOP5
    """Return True if written; copy ``aiNativeLang.example.yml`` when present, else inline defaults."""  # AINL-OPENCLAW-TOP5
    path = workspace / "aiNativeLang.yml"  # AINL-OPENCLAW-TOP5
    if path.is_file():  # AINL-OPENCLAW-TOP5
        return False  # AINL-OPENCLAW-TOP5
    ex = _ai_native_lang_example_yml_path()  # AINL-OPENCLAW-TOP5
    if ex is not None:  # AINL-OPENCLAW-TOP5
        path.write_text(ex.read_text(encoding="utf-8"), encoding="utf-8")  # AINL-OPENCLAW-TOP5
        return True  # AINL-OPENCLAW-TOP5
    body = "\n".join(  # AINL-OPENCLAW-TOP5
        [  # AINL-OPENCLAW-TOP5
            "version: 1.0",  # AINL-OPENCLAW-TOP5
            'project: "OpenClaw"',  # AINL-OPENCLAW-TOP5
            'description: "OpenClaw integration with AINL — safe defaults"',  # AINL-OPENCLAW-TOP5
            "env:",  # AINL-OPENCLAW-TOP5
            "  AINL_EXECUTION_MODE: \"graph-preferred\"",  # AINL-OPENCLAW-TOP5
            "  OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT: 1",  # AINL-OPENCLAW-TOP5
            "  AINL_IR_CACHE: 1",  # AINL-OPENCLAW-TOP5
            "  AINL_OBSERVABILITY: 1",  # AINL-OPENCLAW-TOP5
            "providers: []",  # AINL-OPENCLAW-TOP5
        ]  # AINL-OPENCLAW-TOP5
    ) + "\n"  # AINL-OPENCLAW-TOP5
    path.write_text(body, encoding="utf-8")  # AINL-OPENCLAW-TOP5
    return True  # AINL-OPENCLAW-TOP5


def _openclaw_json_path_for_workspace(workspace: Path) -> Path:  # AINL-OPENCLAW-TOP5
    # Prefer host-global config; allow workspace-local override if present.  # AINL-OPENCLAW-TOP5
    home_cfg = Path.home() / ".openclaw" / "openclaw.json"  # AINL-OPENCLAW-TOP5
    ws_cfg = workspace / ".openclaw" / "openclaw.json"  # AINL-OPENCLAW-TOP5
    return ws_cfg if ws_cfg.is_file() else home_cfg  # AINL-OPENCLAW-TOP5


def _merge_openclaw_json_shellenv(workspace: Path, env: Dict[str, str]) -> Optional[str]:  # AINL-OPENCLAW-TOP5
    """Merge keys into ``<workspace>/.openclaw/openclaw.json`` under ``env.shellEnv``.  # AINL-OPENCLAW-TOP5
    OpenClaw's ``config set`` rejects AINL-specific keys (schema whitelist); file merge is authoritative.  # AINL-OPENCLAW-TOP5
    """  # AINL-OPENCLAW-TOP5
    oc_dir = workspace / ".openclaw"  # AINL-OPENCLAW-TOP5
    cfg_path = oc_dir / "openclaw.json"  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        oc_dir.mkdir(parents=True, exist_ok=True)  # AINL-OPENCLAW-TOP5
        if cfg_path.is_file():  # AINL-OPENCLAW-TOP5
            raw = cfg_path.read_text(encoding="utf-8")  # AINL-OPENCLAW-TOP5
            data: Dict[str, Any] = json.loads(raw) if raw.strip() else {}  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            data = {}  # AINL-OPENCLAW-TOP5
        if not isinstance(data, dict):  # AINL-OPENCLAW-TOP5
            return f"{cfg_path}: root must be a JSON object"  # AINL-OPENCLAW-TOP5
        env_block = data.setdefault("env", {})  # AINL-OPENCLAW-TOP5
        if not isinstance(env_block, dict):  # AINL-OPENCLAW-TOP5
            env_block = {}  # AINL-OPENCLAW-TOP5
            data["env"] = env_block  # AINL-OPENCLAW-TOP5
        shell = env_block.setdefault("shellEnv", {})  # AINL-OPENCLAW-TOP5
        if not isinstance(shell, dict):  # AINL-OPENCLAW-TOP5
            shell = {}  # AINL-OPENCLAW-TOP5
            env_block["shellEnv"] = shell  # AINL-OPENCLAW-TOP5
        for k, v in sorted(env.items()):  # AINL-OPENCLAW-TOP5
            shell[k] = str(v)  # AINL-OPENCLAW-TOP5
        cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")  # AINL-OPENCLAW-TOP5
    except OSError as e:  # AINL-OPENCLAW-TOP5
        return f"openclaw.json shellEnv merge failed: {e}"  # AINL-OPENCLAW-TOP5
    except json.JSONDecodeError as e:  # AINL-OPENCLAW-TOP5
        return f"{cfg_path}: invalid JSON: {e}"  # AINL-OPENCLAW-TOP5
    return None  # AINL-OPENCLAW-TOP5


def _patch_openclaw_env_shellenv(workspace: Path, env: Dict[str, str]) -> Optional[str]:  # AINL-OPENCLAW-TOP5
    """Return error string if patch fails, else None."""  # AINL-OPENCLAW-TOP5
    return _merge_openclaw_json_shellenv(workspace, env)  # AINL-OPENCLAW-TOP5


def _read_weekly_remaining_rollup(db_path: Path) -> tuple[Optional[int], str, Optional[str]]:  # AINL-OPENCLAW-TOP5
    """Rolling budget: legacy ``weekly_remaining_v1`` row, else ``memory_records`` workflow aggregate."""  # AINL-OPENCLAW-TOP5
    import sqlite3  # AINL-OPENCLAW-TOP5

    try:  # AINL-OPENCLAW-TOP5
        con = sqlite3.connect(str(db_path))  # AINL-OPENCLAW-TOP5
        cur = con.cursor()  # AINL-OPENCLAW-TOP5
        cur.execute(  # AINL-OPENCLAW-TOP5
            "SELECT week_start, remaining_budget FROM weekly_remaining_v1 ORDER BY week_start DESC LIMIT 1"  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        row = cur.fetchone()  # AINL-OPENCLAW-TOP5
        if row is not None and row[1] is not None:  # AINL-OPENCLAW-TOP5
            rem = int(row[1])  # AINL-OPENCLAW-TOP5
            ws = str(row[0] or "")  # AINL-OPENCLAW-TOP5
            con.close()  # AINL-OPENCLAW-TOP5
            return rem, ws, None  # AINL-OPENCLAW-TOP5
        cur.execute(  # AINL-OPENCLAW-TOP5
            "SELECT payload_json FROM memory_records "  # AINL-OPENCLAW-TOP5
            "WHERE namespace='workflow' AND record_kind='budget.aggregate' AND record_id='weekly_remaining_v1' "  # AINL-OPENCLAW-TOP5
            "ORDER BY updated_at DESC LIMIT 1"  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        mrow = cur.fetchone()  # AINL-OPENCLAW-TOP5
        con.close()  # AINL-OPENCLAW-TOP5
        if not mrow or not mrow[0]:  # AINL-OPENCLAW-TOP5
            return None, "", None  # AINL-OPENCLAW-TOP5
        payload = json.loads(mrow[0])  # AINL-OPENCLAW-TOP5
        if not isinstance(payload, dict):  # AINL-OPENCLAW-TOP5
            return None, "", None  # AINL-OPENCLAW-TOP5
        wr = payload.get("weekly_remaining_tokens")  # AINL-OPENCLAW-TOP5
        if wr is None:  # AINL-OPENCLAW-TOP5
            return None, "", None  # AINL-OPENCLAW-TOP5
        rem = int(wr)  # AINL-OPENCLAW-TOP5
        ws = str(payload.get("week_start") or payload.get("updated_at_utc") or "")  # AINL-OPENCLAW-TOP5
        return rem, ws, None  # AINL-OPENCLAW-TOP5
    except Exception as e:  # AINL-OPENCLAW-TOP5
        return None, "", str(e)  # AINL-OPENCLAW-TOP5


def _cron_payload_message(job: Dict[str, Any]) -> str:  # AINL-OPENCLAW-TOP5
    p = job.get("payload") or {}  # AINL-OPENCLAW-TOP5
    if isinstance(p, dict):  # AINL-OPENCLAW-TOP5
        return str(p.get("message") or "")  # AINL-OPENCLAW-TOP5
    return ""  # AINL-OPENCLAW-TOP5


def _gold_standard_cron_add_argv(job: Dict[str, Any]) -> List[str]:  # AINL-OPENCLAW-TOP5
    """Build argv for `openclaw cron add` (OpenClaw 2026+ flag style; gold-standard payloads)."""  # AINL-OPENCLAW-TOP5
    name = str(job.get("name") or "")  # AINL-OPENCLAW-TOP5
    p = job.get("payload") if isinstance(job.get("payload"), dict) else {}  # AINL-OPENCLAW-TOP5
    msg = str(p.get("message") or "")  # AINL-OPENCLAW-TOP5
    agent = str(p.get("agentId") or "ainl-advocate")  # AINL-OPENCLAW-TOP5
    session = str(job.get("sessionTarget") or "isolated")  # AINL-OPENCLAW-TOP5
    argv: List[str] = [  # AINL-OPENCLAW-TOP5
        "openclaw",  # AINL-OPENCLAW-TOP5
        "cron",  # AINL-OPENCLAW-TOP5
        "add",  # AINL-OPENCLAW-TOP5
        "--name",  # AINL-OPENCLAW-TOP5
        name,  # AINL-OPENCLAW-TOP5
        "--message",  # AINL-OPENCLAW-TOP5
        msg,  # AINL-OPENCLAW-TOP5
        "--agent",  # AINL-OPENCLAW-TOP5
        agent,  # AINL-OPENCLAW-TOP5
        "--session",  # AINL-OPENCLAW-TOP5
        session,  # AINL-OPENCLAW-TOP5
    ]  # AINL-OPENCLAW-TOP5
    if (job.get("delivery") or {}).get("mode") == "announce":  # AINL-OPENCLAW-TOP5
        argv.append("--announce")  # AINL-OPENCLAW-TOP5
    sched = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}  # AINL-OPENCLAW-TOP5
    sk = str(sched.get("kind") or "")  # AINL-OPENCLAW-TOP5
    if sk == "every":  # AINL-OPENCLAW-TOP5
        every_ms = int(sched.get("everyMs") or 300000)  # AINL-OPENCLAW-TOP5
        minutes = max(1, every_ms // 60000)  # AINL-OPENCLAW-TOP5
        argv.extend(["--every", f"{minutes}m"])  # AINL-OPENCLAW-TOP5
    elif sk == "cron":  # AINL-OPENCLAW-TOP5
        expr = str(sched.get("expr") or "")  # AINL-OPENCLAW-TOP5
        argv.extend(["--cron", expr])  # AINL-OPENCLAW-TOP5
    return argv  # AINL-OPENCLAW-TOP5


def _openclaw_cron_list_json() -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        proc = subprocess.run(  # AINL-OPENCLAW-TOP5
            ["openclaw", "cron", "list", "--json"],  # AINL-OPENCLAW-TOP5
            capture_output=True,  # AINL-OPENCLAW-TOP5
            text=True,  # AINL-OPENCLAW-TOP5
            timeout=30,  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
    except FileNotFoundError:  # AINL-OPENCLAW-TOP5
        return None, "openclaw CLI not found on PATH"  # AINL-OPENCLAW-TOP5
    except Exception as e:  # AINL-OPENCLAW-TOP5
        return None, str(e)[:300]  # AINL-OPENCLAW-TOP5
    if proc.returncode != 0:  # AINL-OPENCLAW-TOP5
        return None, (proc.stderr or proc.stdout or "cron list failed")[:400]  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        data = json.loads(proc.stdout)  # AINL-OPENCLAW-TOP5
    except json.JSONDecodeError as e:  # AINL-OPENCLAW-TOP5
        return None, f"invalid JSON from openclaw cron list: {e}"  # AINL-OPENCLAW-TOP5
    jobs = data.get("jobs") if isinstance(data, dict) else None  # AINL-OPENCLAW-TOP5
    return (jobs if isinstance(jobs, list) else []), None  # AINL-OPENCLAW-TOP5


def _ensure_gold_standard_crons_idempotent(  # AINL-OPENCLAW-TOP5
    jobs: List[Dict[str, Any]], *, dry_run: bool, verbose: bool  # AINL-OPENCLAW-TOP5
) -> tuple[List[str], List[str]]:  # AINL-OPENCLAW-TOP5
    """Return (errors, notes). Skips add when same name or same payload message exists."""  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    import sys  # AINL-OPENCLAW-TOP5
    errs: List[str] = []  # AINL-OPENCLAW-TOP5
    notes: List[str] = []  # AINL-OPENCLAW-TOP5
    existing, err = _openclaw_cron_list_json()  # AINL-OPENCLAW-TOP5
    if err:  # AINL-OPENCLAW-TOP5
        return [err], notes  # AINL-OPENCLAW-TOP5
    names = {str(j.get("name")) for j in (existing or []) if isinstance(j, dict) and j.get("name")}  # AINL-OPENCLAW-TOP5
    msgs = {_cron_payload_message(j) for j in (existing or []) if isinstance(j, dict)}  # AINL-OPENCLAW-TOP5
    for job in jobs:  # AINL-OPENCLAW-TOP5
        jn = str(job.get("name") or "")  # AINL-OPENCLAW-TOP5
        jm = _cron_payload_message(job)  # AINL-OPENCLAW-TOP5
        if jn in names or (jm and jm in msgs):  # AINL-OPENCLAW-TOP5
            notes.append(f"already registered (skipped): {jn or jm[:48]}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        if dry_run:  # AINL-OPENCLAW-TOP5
            notes.append(f"[dry-run] would openclaw cron add: {jn!r}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        argv = _gold_standard_cron_add_argv(job)  # AINL-OPENCLAW-TOP5
        if verbose:  # AINL-OPENCLAW-TOP5
            print("+ " + " ".join(argv), file=sys.stderr)  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)  # AINL-OPENCLAW-TOP5
        except Exception as e:  # AINL-OPENCLAW-TOP5
            errs.append(f"cron add {jn!r}: {e}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5

        def _register_success() -> None:  # AINL-OPENCLAW-TOP5
            notes.append(f"added: {jn}")  # AINL-OPENCLAW-TOP5
            if jn:  # AINL-OPENCLAW-TOP5
                names.add(jn)  # AINL-OPENCLAW-TOP5
            if jm:  # AINL-OPENCLAW-TOP5
                msgs.add(jm)  # AINL-OPENCLAW-TOP5

        if proc.returncode == 0:  # AINL-OPENCLAW-TOP5
            _register_success()  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        msg = (proc.stderr or proc.stdout or "").strip()  # AINL-OPENCLAW-TOP5
        if "already" in msg.lower() or "duplicate" in msg.lower() or "exists" in msg.lower():  # AINL-OPENCLAW-TOP5
            notes.append(f"host reported existing job: {jn!r}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            proc = subprocess.run(  # AINL-OPENCLAW-TOP5
                ["openclaw", "cron", "add", json.dumps(job)],  # AINL-OPENCLAW-TOP5 — legacy JSON  # AINL-OPENCLAW-TOP5
                capture_output=True,  # AINL-OPENCLAW-TOP5
                text=True,  # AINL-OPENCLAW-TOP5
                timeout=60,  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
        except Exception as e2:  # AINL-OPENCLAW-TOP5
            errs.append(f"cron add {jn!r} exit={proc.returncode} (flags), legacy failed: {e2}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        if proc.returncode == 0:  # AINL-OPENCLAW-TOP5
            _register_success()  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        msg = (proc.stderr or proc.stdout or "").strip()  # AINL-OPENCLAW-TOP5
        if "already" in msg.lower() or "duplicate" in msg.lower() or "exists" in msg.lower():  # AINL-OPENCLAW-TOP5
            notes.append(f"host reported existing job: {jn!r}")  # AINL-OPENCLAW-TOP5
            continue  # AINL-OPENCLAW-TOP5
        errs.append(f"cron add {jn!r} exit={proc.returncode}: {msg[:220]}")  # AINL-OPENCLAW-TOP5
    return errs, notes  # AINL-OPENCLAW-TOP5


def _openclaw_gateway_restart() -> Optional[str]:  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        proc = subprocess.run(  # AINL-OPENCLAW-TOP5
            ["openclaw", "gateway", "restart"],  # AINL-OPENCLAW-TOP5
            capture_output=True,  # AINL-OPENCLAW-TOP5
            text=True,  # AINL-OPENCLAW-TOP5
            timeout=60,  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
    except FileNotFoundError:  # AINL-OPENCLAW-TOP5
        return "openclaw CLI not found on PATH"  # AINL-OPENCLAW-TOP5
    except Exception as e:  # AINL-OPENCLAW-TOP5
        return f"openclaw gateway restart failed: {e}"  # AINL-OPENCLAW-TOP5
    if proc.returncode != 0:  # AINL-OPENCLAW-TOP5
        msg = (proc.stderr or proc.stdout or "").strip()  # AINL-OPENCLAW-TOP5
        return f"openclaw gateway restart exit={proc.returncode}: {msg[:300]}"  # AINL-OPENCLAW-TOP5
    return None  # AINL-OPENCLAW-TOP5


def _markdown_health_table(rows: List[tuple[str, str, str]]) -> str:  # AINL-OPENCLAW-TOP5
    # rows: (emoji, item, detail)  # AINL-OPENCLAW-TOP5
    out = ["| | Check | Detail |", "|---|---|---|"]  # AINL-OPENCLAW-TOP5
    out += [f"| {e} | {c} | {d} |" for (e, c, d) in rows]  # AINL-OPENCLAW-TOP5
    return "\n".join(out) + "\n"  # AINL-OPENCLAW-TOP5


def _openclaw_gold_standard_shell_env(ws: Path, ainl_root: Path) -> Dict[str, str]:  # AINL-OPENCLAW-TOP5
    """Full `env.shellEnv` map aligned with docs/operations/OPENCLAW_AINL_GOLD_STANDARD.md."""  # AINL-OPENCLAW-TOP5
    return {  # AINL-OPENCLAW-TOP5
        "OPENCLAW_WORKSPACE": str(ws),  # AINL-OPENCLAW-TOP5
        "OPENCLAW_MEMORY_DIR": str(ws / "memory"),  # AINL-OPENCLAW-TOP5
        "OPENCLAW_DAILY_MEMORY_DIR": str(ws / "memory"),  # AINL-OPENCLAW-TOP5
        "AINL_FS_ROOT": str(ainl_root),  # AINL-OPENCLAW-TOP5
        "AINL_MEMORY_DB": str(ws / ".ainl" / "ainl_memory.sqlite3"),  # AINL-OPENCLAW-TOP5
        "MONITOR_CACHE_JSON": str(ws / ".ainl" / "monitor_state.json"),  # AINL-OPENCLAW-TOP5
        "AINL_EMBEDDING_MEMORY_DB": str(ws / ".ainl" / "embedding_memory.sqlite3"),  # AINL-OPENCLAW-TOP5
        "AINL_IR_CACHE_DIR": str(ws / ".cache" / "ainl" / "ir"),  # AINL-OPENCLAW-TOP5
        "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": "true",  # AINL-OPENCLAW-TOP5
        "AINL_BRIDGE_REPORT_MAX_CHARS": "500",  # AINL-OPENCLAW-TOP5
        "AINL_WEEKLY_TOKEN_BUDGET_CAP": "100000",  # AINL-OPENCLAW-TOP5
        "AINL_EXECUTION_MODE": "graph-preferred",  # AINL-OPENCLAW-TOP5
    }  # AINL-OPENCLAW-TOP5


def _emit_openclaw_install_dry_run_preview(  # AINL-OPENCLAW-TOP5
    workspace: Path,  # AINL-OPENCLAW-TOP5
    env: Dict[str, str],  # AINL-OPENCLAW-TOP5
    core_jobs: List[Dict[str, Any]],  # AINL-OPENCLAW-TOP5
    db_path: Path,  # AINL-OPENCLAW-TOP5
) -> None:  # AINL-OPENCLAW-TOP5
    import sys  # AINL-OPENCLAW-TOP5

    from openclaw.bridge.schema_bootstrap import dry_run_sql_preview  # AINL-OPENCLAW-TOP5

    cfg_path = workspace / ".openclaw" / "openclaw.json"  # AINL-OPENCLAW-TOP5
    patch_obj = {"env": {"shellEnv": {k: str(v) for k, v in sorted(env.items())}}}  # AINL-OPENCLAW-TOP5
    sys.stderr.write(  # AINL-OPENCLAW-TOP5
        "--- ainl install openclaw --dry-run: would merge env.shellEnv into " + str(cfg_path) + " (file merge; CLI rejects unknown keys)\n"  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5
    sys.stderr.write(json.dumps(patch_obj, indent=2) + "\n")  # AINL-OPENCLAW-TOP5
    sys.stderr.write("--- SQLite: bootstrap_tables (CREATE IF NOT EXISTS) ---\n")  # AINL-OPENCLAW-TOP5
    sys.stderr.write(f"db_path: {db_path}\n")  # AINL-OPENCLAW-TOP5
    sys.stderr.write(dry_run_sql_preview())  # AINL-OPENCLAW-TOP5
    sys.stderr.write("\n--- would `openclaw cron add` (2026+ argv; legacy JSON after) ---\n")  # AINL-OPENCLAW-TOP5
    for job in core_jobs:  # AINL-OPENCLAW-TOP5
        sys.stderr.write(" ".join(_gold_standard_cron_add_argv(job)) + "\n")  # AINL-OPENCLAW-TOP5
        sys.stderr.write(json.dumps(job) + "\n")  # AINL-OPENCLAW-TOP5
    sys.stderr.write("--- skipped: aiNativeLang.yml write, gateway restart ---\n")  # AINL-OPENCLAW-TOP5


def cmd_cron_add(args: argparse.Namespace) -> int:  # AINL-OPENCLAW-TOP5
    """Wrap ``openclaw cron add`` with an ``ainl run <file>`` message for an .ainl path."""  # AINL-OPENCLAW-TOP5
    import shlex  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    import sys  # AINL-OPENCLAW-TOP5

    path = Path(args.ainl_path).expanduser().resolve()  # AINL-OPENCLAW-TOP5
    if not path.is_file():  # AINL-OPENCLAW-TOP5
        print(f"ainl cron add: not a file: {path}", file=sys.stderr)  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    if path.suffix.lower() != ".ainl":  # AINL-OPENCLAW-TOP5
        print(f"ainl cron add: expected .ainl file, got {path.suffix!r}", file=sys.stderr)  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    name = (args.name or "").strip() or f"AINL: {path.stem}"  # AINL-OPENCLAW-TOP5
    cron_expr = (args.cron or "").strip()  # AINL-OPENCLAW-TOP5
    every = (args.every or "").strip()  # AINL-OPENCLAW-TOP5
    if not cron_expr and not every:  # AINL-OPENCLAW-TOP5
        print("ainl cron add: provide --cron '0 9 * * *' or --every 15m", file=sys.stderr)  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    if cron_expr and every:  # AINL-OPENCLAW-TOP5
        print("ainl cron add: use only one of --cron or --every", file=sys.stderr)  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    agent = (args.agent or "").strip() or "ainl-advocate"  # AINL-OPENCLAW-TOP5
    session = (args.session or "").strip() or "isolated"  # AINL-OPENCLAW-TOP5
    msg = f"ainl run {shlex.quote(str(path))}"  # AINL-OPENCLAW-TOP5
    argv: List[str] = [  # AINL-OPENCLAW-TOP5
        "openclaw",  # AINL-OPENCLAW-TOP5
        "cron",  # AINL-OPENCLAW-TOP5
        "add",  # AINL-OPENCLAW-TOP5
        "--name",  # AINL-OPENCLAW-TOP5
        name,  # AINL-OPENCLAW-TOP5
        "--message",  # AINL-OPENCLAW-TOP5
        msg,  # AINL-OPENCLAW-TOP5
        "--agent",  # AINL-OPENCLAW-TOP5
        agent,  # AINL-OPENCLAW-TOP5
        "--session",  # AINL-OPENCLAW-TOP5
        session,  # AINL-OPENCLAW-TOP5
    ]  # AINL-OPENCLAW-TOP5
    if args.announce:  # AINL-OPENCLAW-TOP5
        argv.append("--announce")  # AINL-OPENCLAW-TOP5
    if every:  # AINL-OPENCLAW-TOP5
        argv.extend(["--every", every])  # AINL-OPENCLAW-TOP5
    else:  # AINL-OPENCLAW-TOP5
        argv.extend(["--cron", cron_expr])  # AINL-OPENCLAW-TOP5
    if args.dry_run:  # AINL-OPENCLAW-TOP5
        print(" ".join(shlex.quote(a) for a in argv))  # AINL-OPENCLAW-TOP5
        return 0  # AINL-OPENCLAW-TOP5
    r = subprocess.run(argv)  # AINL-OPENCLAW-TOP5
    return int(r.returncode)  # AINL-OPENCLAW-TOP5


def cmd_dashboard(args: argparse.Namespace) -> int:  # AINL-OPENCLAW-TOP5
    import subprocess  # AINL-OPENCLAW-TOP5
    import sys  # AINL-OPENCLAW-TOP5

    root = _repo_root()  # AINL-OPENCLAW-TOP5
    emitted_server = root / "tests" / "emits" / "server" / "server.py"  # AINL-OPENCLAW-TOP5
    if not emitted_server.is_file():  # AINL-OPENCLAW-TOP5
        print(  # AINL-OPENCLAW-TOP5
            "ainl dashboard: emitted UI server not present.\n"  # AINL-OPENCLAW-TOP5
            "  Build it once from a git checkout of the AINL repo:\n"  # AINL-OPENCLAW-TOP5
            "    python3 scripts/run_tests_and_emit.py\n"  # AINL-OPENCLAW-TOP5
            f"  Expected file: {emitted_server}\n"  # AINL-OPENCLAW-TOP5
            "  (PyPI installs typically do not include tests/emits; this path is dev-oriented.)",  # AINL-OPENCLAW-TOP5
            file=sys.stderr,  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    script = root / "scripts" / "serve_dashboard.py"  # AINL-OPENCLAW-TOP5
    if not script.is_file():  # AINL-OPENCLAW-TOP5
        print(f"ainl dashboard: missing {script}", file=sys.stderr)  # AINL-OPENCLAW-TOP5
        return 1  # AINL-OPENCLAW-TOP5
    argv: List[str] = [sys.executable, str(script)]  # AINL-OPENCLAW-TOP5
    if getattr(args, "dashboard_port", None) is not None:  # AINL-OPENCLAW-TOP5
        argv.extend(["--port", str(args.dashboard_port)])  # AINL-OPENCLAW-TOP5
    if getattr(args, "dashboard_no_browser", False):  # AINL-OPENCLAW-TOP5
        argv.append("--no-browser")  # AINL-OPENCLAW-TOP5
    return int(subprocess.call(argv))  # AINL-OPENCLAW-TOP5


def main() -> None:
    ap = argparse.ArgumentParser(  # AINL-OPENCLAW-TOP5
        description="AINL runtime CLI",  # AINL-OPENCLAW-TOP5
        epilog="OpenClaw helpers: `ainl install openclaw`, `ainl status [--json|--json-summary|--summary]`, `ainl cron add`, `ainl dashboard` (needs emitted server — run `python3 scripts/run_tests_and_emit.py` in a dev checkout), `ainl doctor --ainl`. See docs/QUICKSTART_OPENCLAW.md.",  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5
    sub = ap.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="Run AINL file")
    runp.add_argument("file", nargs="?")
    runp.add_argument("--config", help="Path to AINL config YAML (for LLM adapter configuration)", default=None)
    runp.add_argument("--label", default="")
    runp.add_argument("--strict", action="store_true")
    runp.add_argument("--strict-reachability", action="store_true")
    runp.add_argument("--trace", action="store_true")
    runp.add_argument(
        "--log-trajectory",
        action="store_true",
        help="Append one JSON object per executed step to <stem>.trajectory.jsonl next to the source file; or set AINL_LOG_TRAJECTORY=1.",
    )
    runp.add_argument(
        "--trace-jsonl",
        default="",
        metavar="PATH|-",
        help="Append structured execution trace JSONL to file PATH or '-' for stdout.",
    )
    runp.add_argument("--json", action="store_true")
    runp.add_argument("--no-step-fallback", action="store_true")
    runp.add_argument("--execution-mode", choices=["graph-preferred", "steps-only", "graph-only"], default="graph-preferred")
    runp.add_argument("--unknown-op-policy", choices=["skip", "error"], default=None)
    runp.add_argument(
        "--runtime-async",
        action="store_true",
        help="Enable async-capable adapter dispatch (or set AINL_RUNTIME_ASYNC=1).",
    )
    runp.add_argument(
        "--observability",
        action="store_true",
        help="Enable lightweight runtime observability metrics (or set AINL_OBSERVABILITY=1).",
    )
    runp.add_argument(
        "--observability-jsonl",
        default="",
        metavar="PATH",
        help="Append observability metrics JSONL to PATH (or set AINL_OBSERVABILITY_JSONL).",
    )
    runp.add_argument("--trace-out", default="")
    runp.add_argument("--record-adapters", default="")
    runp.add_argument("--replay-adapters", default="")
    runp.add_argument(
        "--enable-adapter",
        action="append",
        choices=[
            "http",
            "bridge",
            "sqlite",
            "postgres",
            "mysql",
            "redis",
            "dynamodb",
            "airtable",
            "supabase",
            "fs",
            "tools",
            "ext",
            "db",
            "api",
            "wasm",
            "memory",
            "vector_memory",
            "embedding_memory",
            "code_context",
            "tool_registry",
            "langchain_tool",
            "ptc_runner",
            "llm_query",
            "audit_trail",
        ],
        default=[],
    )
    runp.add_argument(
        "--audit-sink",
        dest="audit_sink",
        default="",
        metavar="URI",
        help="With --enable-adapter audit_trail: sink URI (or env AINL_AUDIT_SINK). e.g. file:///tmp/ainl_audit.jsonl",
    )
    runp.add_argument(
        "--bridge-endpoint",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="With --enable-adapter bridge: map executor key to POST URL (repeatable)",
    )
    runp.add_argument("--http-allow-host", action="append", default=[])
    runp.add_argument(
        "--http-timeout-s",
        type=float,
        default=5.0,
        help="Per-request timeout for http + bridge adapters (seconds). Use 60–120+ for LLM-backed bridge routes.",
    )
    runp.add_argument("--http-max-response-bytes", type=int, default=1_000_000)
    runp.add_argument("--sqlite-db", default="")
    runp.add_argument("--sqlite-allow-write", action="store_true")
    runp.add_argument("--sqlite-allow-table", action="append", default=[])
    runp.add_argument("--sqlite-timeout-s", type=float, default=5.0)
    runp.add_argument("--postgres-url", default="", help="Postgres DSN/URL (or set AINL_POSTGRES_URL)")
    runp.add_argument("--postgres-host", default="")
    runp.add_argument("--postgres-port", type=int, default=5432)
    runp.add_argument("--postgres-db", default="")
    runp.add_argument("--postgres-user", default="")
    runp.add_argument("--postgres-password", default="", help="Prefer env var AINL_POSTGRES_PASSWORD in production")
    runp.add_argument("--postgres-sslmode", default="require")
    runp.add_argument("--postgres-sslrootcert", default="", help="Path to CA root cert PEM for PostgreSQL TLS")
    runp.add_argument("--postgres-timeout-s", type=float, default=5.0)
    runp.add_argument("--postgres-statement-timeout-ms", type=int, default=5000)
    runp.add_argument("--postgres-pool-min", type=int, default=1)
    runp.add_argument("--postgres-pool-max", type=int, default=5)
    runp.add_argument("--postgres-allow-write", action="store_true")
    runp.add_argument("--postgres-allow-table", action="append", default=[])
    runp.add_argument("--mysql-url", default="", help="MySQL DSN/URL (or set AINL_MYSQL_URL)")
    runp.add_argument("--mysql-host", default="")
    runp.add_argument("--mysql-port", type=int, default=3306)
    runp.add_argument("--mysql-db", default="")
    runp.add_argument("--mysql-user", default="")
    runp.add_argument("--mysql-password", default="", help="Prefer env var AINL_MYSQL_PASSWORD in production")
    runp.add_argument("--mysql-ssl-mode", default="REQUIRED")
    runp.add_argument("--mysql-ssl-ca", default="", help="Path to CA root cert PEM for MySQL TLS")
    runp.add_argument("--mysql-timeout-s", type=float, default=5.0)
    runp.add_argument("--mysql-pool-min", type=int, default=1)
    runp.add_argument("--mysql-pool-max", type=int, default=5)
    runp.add_argument("--mysql-allow-write", action="store_true")
    runp.add_argument("--mysql-allow-table", action="append", default=[])
    runp.add_argument("--redis-url", default="", help="Redis URL/DSN (or set AINL_REDIS_URL)")
    runp.add_argument("--redis-host", default="")
    runp.add_argument("--redis-port", type=int, default=6379)
    runp.add_argument("--redis-db", type=int, default=0)
    runp.add_argument("--redis-user", default="")
    runp.add_argument("--redis-password", default="", help="Prefer env var AINL_REDIS_PASSWORD in production")
    runp.add_argument("--redis-ssl", action="store_true")
    runp.add_argument("--redis-timeout-s", type=float, default=5.0)
    runp.add_argument("--redis-allow-write", action="store_true")
    runp.add_argument("--redis-allow-prefix", action="append", default=[])
    runp.add_argument("--dynamodb-url", default="", help="DynamoDB endpoint URL (or set AINL_DYNAMODB_URL)")
    runp.add_argument("--dynamodb-region", default="us-east-1", help="AWS region for DynamoDB")
    runp.add_argument("--dynamodb-timeout-s", type=float, default=5.0)
    runp.add_argument("--dynamodb-allow-write", action="store_true")
    runp.add_argument("--dynamodb-allow-table", action="append", default=[])
    runp.add_argument("--dynamodb-consistent-read", action="store_true")
    runp.add_argument("--airtable-api-key", default="", help="Airtable personal access token (or AINL_AIRTABLE_API_KEY)")
    runp.add_argument("--airtable-base-id", default="", help="Airtable base id (or AINL_AIRTABLE_BASE_ID)")
    runp.add_argument("--airtable-timeout-s", type=float, default=8.0)
    runp.add_argument("--airtable-max-page-size", type=int, default=100)
    runp.add_argument("--airtable-allow-write", action="store_true")
    runp.add_argument("--airtable-allow-table", action="append", default=[])
    runp.add_argument("--airtable-allow-attachment-host", action="append", default=[], help="Allowed host(s) for attachment download/upload-by-url")
    runp.add_argument("--supabase-db-url", default="", help="Supabase Postgres DB URL (or AINL_SUPABASE_DB_URL / AINL_POSTGRES_URL)")
    runp.add_argument("--supabase-url", default="", help="Supabase project URL (or AINL_SUPABASE_URL)")
    runp.add_argument("--supabase-anon-key", default="", help="Supabase anon key (or AINL_SUPABASE_ANON_KEY)")
    runp.add_argument("--supabase-service-role-key", default="", help="Supabase service role key (or AINL_SUPABASE_SERVICE_ROLE_KEY)")
    runp.add_argument("--supabase-timeout-s", type=float, default=8.0)
    runp.add_argument("--supabase-allow-write", action="store_true")
    runp.add_argument("--supabase-allow-table", action="append", default=[])
    runp.add_argument("--supabase-allow-bucket", action="append", default=[])
    runp.add_argument("--supabase-allow-channel", action="append", default=[])
    runp.add_argument("--fs-root", default="")
    runp.add_argument("--fs-max-read-bytes", type=int, default=1_000_000)
    runp.add_argument("--fs-max-write-bytes", type=int, default=1_000_000)
    runp.add_argument("--fs-allow-ext", action="append", default=[])
    runp.add_argument("--fs-allow-delete", action="store_true")
    runp.add_argument("--tools-allow", action="append", default=[])
    runp.add_argument("--wasm-module", action="append", default=[], help="WASM module mapping: name=/abs/path/module.wasm")
    runp.add_argument("--wasm-allow-module", action="append", default=[], help="Optional wasm module allowlist")
    runp.add_argument(
        "--memory-db",
        default="",
        help="SQLite path for --enable-adapter memory (defaults to AINL_MEMORY_DB or ~/.openclaw/ainl_memory.sqlite3)",
    )
    runp.add_argument("--max-steps", type=int, default=None)
    runp.add_argument("--max-depth", type=int, default=None)
    runp.add_argument("--max-adapter-calls", type=int, default=None)
    runp.add_argument("--max-time-ms", type=int, default=None)
    runp.add_argument("--max-frame-bytes", type=int, default=None)
    runp.add_argument("--max-loop-iters", type=int, default=None)
    runp.add_argument("--self-test-graph", action="store_true")
    runp.set_defaults(func=cmd_run)

    hybrid_p = sub.add_parser(
        "run-hybrid-ptc",
        help="run the hybrid PTC order processor example (mock-friendly; requires ptc_runner adapter)",
    )
    hybrid_p.add_argument(
        "--no-mock",
        action="store_true",
        help="do not force AINL_PTC_RUNNER_MOCK=1 (use current env)",
    )
    hybrid_p.add_argument(
        "--trace-jsonl",
        default="/tmp/hybrid_orders.trace.jsonl",
        help="path to write hybrid trace JSONL (default: /tmp/hybrid_orders.trace.jsonl)",
    )
    hybrid_p.set_defaults(func=cmd_run_hybrid_ptc)

    chk = sub.add_parser("check", help="Compile/check AINL file")
    chk.add_argument("file")
    chk.add_argument("--strict", action="store_true")
    chk.add_argument("--estimate", action="store_true", default=False, help="Append static LLM cost estimate to output JSON")
    chk.set_defaults(func=cmd_check)

    cmp = sub.add_parser("compile", help="Compile an .ainl file and optionally emit artifacts")
    cmp.add_argument("file")
    cmp.add_argument("--strict", action="store_true")
    cmp.add_argument(
        "--emit",
        choices=["ir", "hermes-skill", "hermes", "solana-client", "blockchain-client"],
        default="ir",
        help="Emit target (ir, hermes-skill bundle, or solana-client / blockchain-client single-file runner).",
    )
    cmp.add_argument("-o", "--output", default="", help="Output directory for bundle emitters")
    cmp.set_defaults(func=cmd_compile)

    # --- ainl validate (alias for check) ---
    val = sub.add_parser("validate", help="Validate an .ainl file (alias for 'check')")
    val.add_argument("file")
    val.add_argument("--strict", action="store_true")
    val.add_argument("--estimate", action="store_true", default=False, help="Append static LLM cost estimate to output JSON")
    val.add_argument("--json-output", action="store_true", help="Output full IR JSON instead of summary (for CI/tooling)")
    val.set_defaults(func=cmd_validate)

    # --- ainl emit (full emitter with all targets) ---
    emt = sub.add_parser("emit", help="Compile an .ainl file and emit to a target platform")
    emt.add_argument("file")
    emt.add_argument(
        "--target", "-t",
        required=True,
        choices=[
            "ir", "langgraph", "temporal", "hermes-skill", "hermes",
            "solana-client", "blockchain-client",
            "server", "python-api", "react", "openapi", "prisma", "sql",
            "docker", "k8s", "cron",
        ],
        help="Emit target platform.",
    )
    emt.add_argument("-o", "--output", default="", help="Output path or directory")
    emt.add_argument("--strict", action="store_true")
    emt.set_defaults(func=cmd_emit)

    # --- ainl serve (HTTP server for validation/compile/run) ---
    srv = sub.add_parser("serve", help="Start an HTTP server exposing AINL validate/compile/run as REST API")
    srv.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    srv.add_argument("--port", "-p", type=int, default=8080, help="Port (default: 8080)")
    srv.set_defaults(func=cmd_serve)

    isp = sub.add_parser("inspect", help="Compile an .ainl file and dump full canonical IR JSON")
    isp.add_argument("file")
    isp.add_argument("--strict", action="store_true")
    isp.add_argument("--estimate", action="store_true", default=False, help="Embed static LLM cost estimate into IR as _cost_estimate")
    isp.add_argument("--json", action="store_true", help="Compatibility flag (output is always JSON)")
    isp.set_defaults(func=cmd_inspect)

    avm = sub.add_parser("generate-avm-policy", help="Generate AVM policy fragment JSON from an .ainl file")
    avm.add_argument("file")
    avm.add_argument("--strict", action="store_true")
    avm.add_argument("--output", "-o", default="")
    avm.set_defaults(func=cmd_generate_avm_policy)

    sbx = sub.add_parser("generate-sandbox-config", help="Generate sandbox/AVM config fragments from an .ainl file")
    sbx.add_argument("file")
    sbx.add_argument("--strict", action="store_true")
    sbx.add_argument("--output", "-o", default="")
    sbx.add_argument("--target", choices=["avm", "firecracker", "gvisor", "k8s", "general"], default="general")
    sbx.set_defaults(func=cmd_generate_sandbox_config)

    from tooling.mcp_host_install import list_mcp_host_ids, run_install_mcp_host

    def cmd_install_mcp(args: argparse.Namespace) -> int:
        if bool(getattr(args, "mcp_list_hosts", False)):
            print(" ".join(list_mcp_host_ids()))
            return 0
        return run_install_mcp_host(
            args.mcp_host,
            dry_run=bool(args.dry_run),
            verbose=bool(args.verbose),
        )

    mcp_inst = sub.add_parser(
        "install-mcp",
        help="Bootstrap AINL MCP + ainl-run for any supported host (same as install-openclaw / install-zeroclaw)",
    )
    mcp_mx = mcp_inst.add_mutually_exclusive_group(required=True)
    mcp_mx.add_argument(
        "--list-hosts",
        dest="mcp_list_hosts",
        action="store_true",
        help="Print supported --host values and exit",
    )
    mcp_mx.add_argument(
        "--host",
        dest="mcp_host",
        choices=list(list_mcp_host_ids()),
        help="Agent stack: openclaw, zeroclaw, …",
    )
    mcp_inst.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    mcp_inst.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    mcp_inst.set_defaults(func=cmd_install_mcp)

    def cmd_install_hermes(args: argparse.Namespace) -> int:
        # Shortcut alias for `ainl install-mcp --host hermes`
        return run_install_mcp_host(
            "hermes",
            dry_run=bool(args.dry_run),
            verbose=bool(args.verbose),
        )

    hms = sub.add_parser(
        "hermes-install",
        help="Bootstrap AINL for Hermes Agent: pip upgrade, ~/.hermes/config.yaml MCP, bin/ainl-run, PATH hint",
    )
    hms.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    hms.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    hms.set_defaults(func=cmd_install_hermes)

    def cmd_install_zeroclaw(args: argparse.Namespace) -> int:
        from tooling.zeroclaw_install import run_install_zeroclaw

        return run_install_zeroclaw(dry_run=bool(args.dry_run), verbose=bool(args.verbose))

    zcw = sub.add_parser(
        "install-zeroclaw",
        help="Bootstrap AINL for ZeroClaw: pip upgrade, ~/.zeroclaw/mcp.json, bin/ainl-run, PATH hint",
    )
    zcw.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    zcw.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    zcw.set_defaults(func=cmd_install_zeroclaw)

    def cmd_install_openclaw(args: argparse.Namespace) -> int:
        from tooling.openclaw_install import run_install_openclaw

        return run_install_openclaw(dry_run=bool(args.dry_run), verbose=bool(args.verbose))

    ocl = sub.add_parser(
        "install-openclaw",
        help="Bootstrap AINL for OpenClaw: pip upgrade, ~/.openclaw/openclaw.json MCP, bin/ainl-run, PATH hint",
    )
    ocl.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    ocl.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    ocl.set_defaults(func=cmd_install_openclaw)

    def cmd_doctor(args: argparse.Namespace) -> int:
        from tooling.doctor import run_doctor

        return run_doctor(
            host=(args.host or None),
            json_output=bool(args.json),
            verbose=bool(args.verbose),
            ainl_openclaw=bool(getattr(args, "ainl_openclaw", False)),  # AINL-OPENCLAW-TOP5
        )

    doc = sub.add_parser(
        "doctor",
        help="Run environment diagnostics (imports, PATH, MCP config, install-mcp dry-run)",
    )
    doc.add_argument(
        "--host",
        choices=list(list_mcp_host_ids()),
        default="",
        help="Limit MCP checks to one host (default: check all known hosts)",
    )
    doc.add_argument(  # AINL-OPENCLAW-TOP5
        "--ainl",  # AINL-OPENCLAW-TOP5
        dest="ainl_openclaw",  # AINL-OPENCLAW-TOP5
        action="store_true",  # AINL-OPENCLAW-TOP5
        help="Also validate OpenClaw AINL integration (env, schema, core cron drift hints)",  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5
    doc.add_argument("--json", action="store_true", help="Emit JSON diagnostics output")
    doc.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    doc.set_defaults(func=cmd_doctor)

    def cmd_install_openclaw_one_command(args: argparse.Namespace) -> int:  # AINL-OPENCLAW-TOP5
        from openclaw.bridge.cron_drift_check import run_report as _cron_drift_report_install  # AINL-OPENCLAW-TOP5
        from openclaw.bridge.schema_bootstrap import bootstrap_tables  # AINL-OPENCLAW-TOP5
        from openclaw.bridge.user_friendly_error import INIT_INSTALL_OPENCLAW, user_friendly_ainl_error  # AINL-OPENCLAW-TOP5

        dry = bool(getattr(args, "install_openclaw_dry_run", False))  # AINL-OPENCLAW-TOP5
        verbose = bool(getattr(args, "install_openclaw_verbose", False))  # AINL-OPENCLAW-TOP5
        ws = Path(args.workspace).expanduser().resolve() if getattr(args, "workspace", "") else _openclaw_default_workspace()  # AINL-OPENCLAW-TOP5
        ws.mkdir(parents=True, exist_ok=True)  # AINL-OPENCLAW-TOP5
        wrote_yml = False  # AINL-OPENCLAW-TOP5
        if not dry:  # AINL-OPENCLAW-TOP5
            wrote_yml = _write_ai_native_lang_yml_if_missing(ws)  # AINL-OPENCLAW-TOP5

        ainl_root = _repo_root()  # AINL-OPENCLAW-TOP5
        env = _openclaw_gold_standard_shell_env(ws, ainl_root)  # AINL-OPENCLAW-TOP5
        db_path = Path(env["AINL_MEMORY_DB"])  # AINL-OPENCLAW-TOP5

        # Three gold-standard crons only (OPENCLAW_AINL_GOLD_STANDARD.md §3).  # AINL-OPENCLAW-TOP5
        core_jobs: List[Dict[str, Any]] = [  # AINL-OPENCLAW-TOP5
            {  # AINL-OPENCLAW-TOP5
                "name": "AINL Context Injection",  # AINL-OPENCLAW-TOP5
                "schedule": {"kind": "every", "everyMs": 300000},  # AINL-OPENCLAW-TOP5
                "payload": {"kind": "agentTurn", "agentId": "ainl-advocate", "message": "run intelligence: context"},  # AINL-OPENCLAW-TOP5
                "delivery": {"mode": "announce"},  # AINL-OPENCLAW-TOP5
                "sessionTarget": "isolated",  # AINL-OPENCLAW-TOP5
                "enabled": True,  # AINL-OPENCLAW-TOP5
            },  # AINL-OPENCLAW-TOP5
            {  # AINL-OPENCLAW-TOP5
                "name": "AINL Session Summarizer",  # AINL-OPENCLAW-TOP5
                "schedule": {"kind": "cron", "expr": "0 3 * * *"},  # AINL-OPENCLAW-TOP5
                "payload": {"kind": "agentTurn", "agentId": "ainl-advocate", "message": "run intelligence: summarizer"},  # AINL-OPENCLAW-TOP5
                "delivery": {"mode": "announce"},  # AINL-OPENCLAW-TOP5
                "sessionTarget": "isolated",  # AINL-OPENCLAW-TOP5
                "enabled": True,  # AINL-OPENCLAW-TOP5
            },  # AINL-OPENCLAW-TOP5
            {  # AINL-OPENCLAW-TOP5
                "name": "AINL Weekly Token Trends",  # AINL-OPENCLAW-TOP5
                "schedule": {"kind": "cron", "expr": "0 9 * * 0"},  # AINL-OPENCLAW-TOP5
                "payload": {"kind": "agentTurn", "agentId": "ainl-advocate", "message": "run bridge: weekly-token-trends"},  # AINL-OPENCLAW-TOP5
                "delivery": {"mode": "announce"},  # AINL-OPENCLAW-TOP5
                "sessionTarget": "isolated",  # AINL-OPENCLAW-TOP5
                "enabled": True,  # AINL-OPENCLAW-TOP5
            },  # AINL-OPENCLAW-TOP5
        ]  # AINL-OPENCLAW-TOP5
        core_cron_names = [str(j.get("name") or "") for j in core_jobs]  # AINL-OPENCLAW-TOP5

        if dry:  # AINL-OPENCLAW-TOP5
            _emit_openclaw_install_dry_run_preview(ws, env, core_jobs, db_path)  # AINL-OPENCLAW-TOP5

        patch_err: Optional[str] = None  # AINL-OPENCLAW-TOP5
        if dry:  # AINL-OPENCLAW-TOP5
            patch_err = None  # AINL-OPENCLAW-TOP5 — skipped  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            patch_err = _patch_openclaw_env_shellenv(ws, env)  # AINL-OPENCLAW-TOP5

        schema_ok = True  # AINL-OPENCLAW-TOP5
        schema_detail = "skipped (dry-run)" if dry else ""  # AINL-OPENCLAW-TOP5
        if not dry:  # AINL-OPENCLAW-TOP5
            schema_ok, schema_detail = bootstrap_tables(db_path)  # AINL-OPENCLAW-TOP5

        cron_errs, cron_notes = _ensure_gold_standard_crons_idempotent(core_jobs, dry_run=dry, verbose=verbose)  # AINL-OPENCLAW-TOP5

        drift_note = "skipped (dry-run)"  # AINL-OPENCLAW-TOP5
        if not dry:  # AINL-OPENCLAW-TOP5
            try:  # AINL-OPENCLAW-TOP5
                dr = _cron_drift_report_install()  # AINL-OPENCLAW-TOP5
                drift_note = "ok" if dr.get("ok") else "see `python3 openclaw/bridge/cron_drift_check.py`"  # AINL-OPENCLAW-TOP5
            except Exception as e:  # AINL-OPENCLAW-TOP5
                drift_note = user_friendly_ainl_error(e)[:200]  # AINL-OPENCLAW-TOP5

        restart_err: Optional[str] = None  # AINL-OPENCLAW-TOP5
        if dry:  # AINL-OPENCLAW-TOP5
            restart_err = None  # AINL-OPENCLAW-TOP5 — skipped  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            restart_err = _openclaw_gateway_restart()  # AINL-OPENCLAW-TOP5

        rows: List[tuple[str, str, str]] = []  # AINL-OPENCLAW-TOP5
        rows.append(("📁", "Workspace", str(ws) + (" (dry-run)" if dry else "")))  # AINL-OPENCLAW-TOP5
        rows.append(  # AINL-OPENCLAW-TOP5
            ("➖" if dry else ("✅" if wrote_yml else "➖"), "aiNativeLang.yml", ("[dry-run] would write if missing" if dry else ("written" if wrote_yml else "already present")))  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        rows.append(  # AINL-OPENCLAW-TOP5
            (  # AINL-OPENCLAW-TOP5
                "➖" if dry and not patch_err else ("✅" if not patch_err else "❌"),  # AINL-OPENCLAW-TOP5
                "env.shellEnv (+" + str(len(env)) + " keys)",  # AINL-OPENCLAW-TOP5
                "[dry-run] preview on stderr"  # AINL-OPENCLAW-TOP5
                if dry  # AINL-OPENCLAW-TOP5
                else ("ok" if not patch_err else user_friendly_ainl_error(RuntimeError(patch_err or ""))),  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        rows.append(("✅" if schema_ok else "❌", "SQLite: weekly_remaining_v1", schema_detail))  # AINL-OPENCLAW-TOP5
        cron_detail = "ok"  # AINL-OPENCLAW-TOP5
        if cron_errs:  # AINL-OPENCLAW-TOP5
            cron_detail = user_friendly_ainl_error(RuntimeError("; ".join(cron_errs)))  # AINL-OPENCLAW-TOP5
        elif cron_notes:  # AINL-OPENCLAW-TOP5
            cron_detail = "; ".join(cron_notes[:6]) + ("…" if len(cron_notes) > 6 else "")  # AINL-OPENCLAW-TOP5
        rows.append(("✅" if not cron_errs else "❌", "Gold-standard crons (summary)", cron_detail))  # AINL-OPENCLAW-TOP5
        job_list: Optional[List[Dict[str, Any]]] = None  # AINL-OPENCLAW-TOP5
        jl, _jerr = _openclaw_cron_list_json()  # AINL-OPENCLAW-TOP5
        if jl is not None:  # AINL-OPENCLAW-TOP5
            job_list = [j for j in jl if isinstance(j, dict)]  # AINL-OPENCLAW-TOP5
        for cn in core_cron_names:  # AINL-OPENCLAW-TOP5
            if not cn:  # AINL-OPENCLAW-TOP5
                continue  # AINL-OPENCLAW-TOP5
            present = bool(job_list and any(str(j.get("name")) == cn for j in job_list))  # AINL-OPENCLAW-TOP5
            if dry:  # AINL-OPENCLAW-TOP5
                rows.append(("➖", f"Cron: {cn}", "[dry-run] would openclaw cron add if missing"))  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                rows.append(("✅" if present else "❌", f"Cron: {cn}", "registered" if present else user_friendly_ainl_error(RuntimeError(f"Cron job {cn!r} not found"))))  # AINL-OPENCLAW-TOP5
        if cron_errs:  # AINL-OPENCLAW-TOP5
            three_core_detail = user_friendly_ainl_error(RuntimeError("; ".join(cron_errs)))[:160]  # AINL-OPENCLAW-TOP5
            rows.append(("❌", "3 core cron jobs (gold-standard)", three_core_detail))  # AINL-OPENCLAW-TOP5
        elif dry:  # AINL-OPENCLAW-TOP5
            rows.append(("➖", "3 core cron jobs (gold-standard)", "preview — see stderr JSON (no `openclaw cron add`)"))  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            three_ok = bool(  # AINL-OPENCLAW-TOP5
                job_list  # AINL-OPENCLAW-TOP5
                and all(  # AINL-OPENCLAW-TOP5
                    any(str(j.get("name")) == cn for j in job_list)  # AINL-OPENCLAW-TOP5
                    for cn in core_cron_names  # AINL-OPENCLAW-TOP5
                    if cn  # AINL-OPENCLAW-TOP5
                )  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
            rows.append(  # AINL-OPENCLAW-TOP5
                (  # AINL-OPENCLAW-TOP5
                    "✅" if three_ok else "❌",  # AINL-OPENCLAW-TOP5
                    "3 core cron jobs (gold-standard)",  # AINL-OPENCLAW-TOP5
                    "registered (or already present)" if three_ok else INIT_INSTALL_OPENCLAW,  # AINL-OPENCLAW-TOP5
                )  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
        rows.append(("➖" if dry else ("✅" if drift_note == "ok" else "⚠️"), "Cron drift (read-only)", drift_note))  # AINL-OPENCLAW-TOP5
        rows.append(  # AINL-OPENCLAW-TOP5
            (  # AINL-OPENCLAW-TOP5
                "➖" if dry and not restart_err else ("✅" if not restart_err else "❌"),  # AINL-OPENCLAW-TOP5
                "openclaw gateway restart",  # AINL-OPENCLAW-TOP5
                "[dry-run] skipped" if dry else ("ok" if not restart_err else user_friendly_ainl_error(RuntimeError(restart_err or ""))),  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5

        try:  # AINL-OPENCLAW-TOP5
            ir_dir = Path(env["AINL_IR_CACHE_DIR"])  # AINL-OPENCLAW-TOP5
            if dry:  # AINL-OPENCLAW-TOP5
                rows.append(("➖", "IR cache writable", f"[dry-run] would ensure {ir_dir}"))  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                ir_dir.mkdir(parents=True, exist_ok=True)  # AINL-OPENCLAW-TOP5
                test = ir_dir / ".ainl_write_test"  # AINL-OPENCLAW-TOP5
                test.write_text("ok\n", encoding="utf-8")  # AINL-OPENCLAW-TOP5
                test.unlink(missing_ok=True)  # type: ignore[arg-type]  # AINL-OPENCLAW-TOP5
                rows.append(("✅", "IR cache writable", str(ir_dir)))  # AINL-OPENCLAW-TOP5
        except Exception as e:  # AINL-OPENCLAW-TOP5
            rows.append(("⚠️", "IR cache writable", user_friendly_ainl_error(e)))  # AINL-OPENCLAW-TOP5

        print(_markdown_health_table(rows))  # AINL-OPENCLAW-TOP5
        if dry:  # AINL-OPENCLAW-TOP5
            print("\n✅ Dry-run complete — no config/cron/restart writes. Run without `--dry-run` to apply.\n")  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            print("\n✅ OpenClaw integration step finished. Check `ainl status` and `openclaw cron list`.\n")  # AINL-OPENCLAW-TOP5
        if dry:  # AINL-OPENCLAW-TOP5
            return 0 if not cron_errs else 1  # AINL-OPENCLAW-TOP5
        ok = (patch_err is None) and schema_ok and (not cron_errs) and (restart_err is None)  # AINL-OPENCLAW-TOP5
        return 0 if ok else 1  # AINL-OPENCLAW-TOP5

    inst = sub.add_parser("install", help="Install helpers (additive; does not replace install-mcp)")  # AINL-OPENCLAW-TOP5
    inst_sub = inst.add_subparsers(dest="install_cmd", required=True)  # AINL-OPENCLAW-TOP5
    inst_oc = inst_sub.add_parser("openclaw", help="One-command OpenClaw install + health check")  # AINL-OPENCLAW-TOP5
    inst_oc.add_argument(  # AINL-OPENCLAW-TOP5
        "--workspace",  # AINL-OPENCLAW-TOP5
        default="",  # AINL-OPENCLAW-TOP5
        metavar="PATH",  # AINL-OPENCLAW-TOP5
        help="OpenClaw workspace root (default: ~/.openclaw/workspace if present, else cwd)",  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5
    inst_oc.add_argument("--dry-run", dest="install_openclaw_dry_run", action="store_true", help="Print actions only; no patch/cron/restart/SQLite writes")  # AINL-OPENCLAW-TOP5
    inst_oc.add_argument("--verbose", "-v", dest="install_openclaw_verbose", action="store_true", help="Log steps to stderr")  # AINL-OPENCLAW-TOP5
    inst_oc.set_defaults(func=cmd_install_openclaw_one_command)  # AINL-OPENCLAW-TOP5

    cronp = sub.add_parser("cron", help="OpenClaw cron helpers")  # AINL-OPENCLAW-TOP5
    cron_sub = cronp.add_subparsers(dest="cron_cmd", required=True)  # AINL-OPENCLAW-TOP5
    cron_add = cron_sub.add_parser("add", help="Schedule an .ainl file (wraps openclaw cron add)")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("ainl_path", help="Path to .ainl file")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--name", default="", help="Cron job name (default: AINL: <stem>)")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--cron", default="", help="Cron expression, e.g. 0 9 * * *")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--every", default="", help="Interval, e.g. 15m or 1h")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--agent", default="", help="OpenClaw agent id (default: ainl-advocate)")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--session", default="", help="Session target (default: isolated)")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--announce", action="store_true", help="Pass --announce to openclaw cron add")  # AINL-OPENCLAW-TOP5
    cron_add.add_argument("--dry-run", action="store_true", help="Print openclaw argv only")  # AINL-OPENCLAW-TOP5
    cron_add.set_defaults(func=cmd_cron_add)  # AINL-OPENCLAW-TOP5

    dashp = sub.add_parser(  # AINL-OPENCLAW-TOP5
        "dashboard",  # AINL-OPENCLAW-TOP5
        help="Serve emitted dashboard via scripts/serve_dashboard.py (requires tests/emits/server from run_tests_and_emit)",  # AINL-OPENCLAW-TOP5
        formatter_class=argparse.RawDescriptionHelpFormatter,  # AINL-OPENCLAW-TOP5
        description="Serve the emitted FastAPI/static dashboard under tests/emits/server.",  # AINL-OPENCLAW-TOP5
        epilog="Prerequisite: from a git checkout, run `python3 scripts/run_tests_and_emit.py` so tests/emits/server/server.py exists. PyPI-only installs usually lack this tree.",  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5
    dashp.add_argument("--port", type=int, default=None, dest="dashboard_port", help="HTTP port (default 8765)")  # AINL-OPENCLAW-TOP5
    dashp.add_argument("--no-browser", action="store_true", dest="dashboard_no_browser", help="Do not open browser")  # AINL-OPENCLAW-TOP5
    dashp.set_defaults(func=cmd_dashboard)  # AINL-OPENCLAW-TOP5

    # OpenFang commands
    inst_of = inst_sub.add_parser("openfang", help="One-command OpenFang install + health check")  # AINL-OPENFANG-TOP1
    inst_of.add_argument(
        "--workspace",
        default="",
        metavar="PATH",
        help="OpenFang workspace root (default: ~/.openfang/workspace if present, else cwd)",
    )
    inst_of.add_argument("--dry-run", dest="install_openfang_dry_run", action="store_true", help="Print actions only; no patch/cron/restart/SQLite writes")
    inst_of.add_argument("--verbose", "-v", dest="install_openfang_verbose", action="store_true", help="Log steps to stderr")
    inst_of.set_defaults(func=cmd_install_openfang_one_command)

    # Extend cron add to support --host openfang
    cron_add.add_argument("--host", default="openclaw", choices=["openclaw", "openfang"], help="Agent host (default: openclaw)")  # AINL-OPENFANG-TOP2

    # emit target openfang is handled in cmd_emit; no new parser needed

    # migrate command
    migp = sub.add_parser("migrate", help="Migrate from OpenClaw to OpenFang")  # AINL-OPENFANG-TOP4
    migp.add_argument("source", choices=["openclaw-to-openfang"], help="Migration path")
    migp.set_defaults(func=cmd_migrate_openclaw_to_openfang)

    def cmd_status(args: argparse.Namespace) -> int:  # AINL-OPENCLAW-TOP5
        import sqlite3  # AINL-OPENCLAW-TOP5
        import subprocess  # AINL-OPENCLAW-TOP5
        import sys  # AINL-OPENCLAW-TOP5
        from datetime import datetime, timezone  # AINL-OPENCLAW-TOP5

        from openclaw.bridge.cron_drift_check import run_report as _cron_drift_report  # AINL-OPENCLAW-TOP5
        from openclaw.bridge.schema_bootstrap import bootstrap_tables  # AINL-OPENCLAW-TOP5
        from openclaw.bridge.user_friendly_error import INIT_INSTALL_OPENCLAW, user_friendly_ainl_error  # AINL-OPENCLAW-TOP5

        json_out = bool(getattr(args, "status_json", False))  # AINL-OPENCLAW-TOP5
        ws = _openclaw_default_workspace()  # AINL-OPENCLAW-TOP5
        db_path = Path(os.getenv("AINL_MEMORY_DB", str(ws / ".ainl" / "ainl_memory.sqlite3"))).expanduser()  # AINL-OPENCLAW-TOP5
        schema_ok, schema_detail = bootstrap_tables(db_path)  # AINL-OPENCLAW-TOP5

        weekly_remaining: Optional[int]  # AINL-OPENCLAW-TOP5
        week_start: str  # AINL-OPENCLAW-TOP5
        sql_err: Optional[str]  # AINL-OPENCLAW-TOP5
        weekly_remaining, week_start, sql_err = _read_weekly_remaining_rollup(db_path)  # AINL-OPENCLAW-TOP5
        if sql_err:  # AINL-OPENCLAW-TOP5
            sql_err = user_friendly_ainl_error(RuntimeError(sql_err))  # AINL-OPENCLAW-TOP5

        cron_jobs: Dict[str, Dict[str, Any]] = {}  # AINL-OPENCLAW-TOP5
        cron_err: Optional[str] = None  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            proc = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=30)  # AINL-OPENCLAW-TOP5
            if proc.returncode != 0:  # AINL-OPENCLAW-TOP5
                cron_err = user_friendly_ainl_error(RuntimeError((proc.stderr or proc.stdout or "").strip() or "cron list failed"))[:240]  # AINL-OPENCLAW-TOP5
            else:  # AINL-OPENCLAW-TOP5
                data = json.loads(proc.stdout)  # AINL-OPENCLAW-TOP5
                jobs = data.get("jobs") if isinstance(data, dict) else None  # AINL-OPENCLAW-TOP5
                if isinstance(jobs, list):  # AINL-OPENCLAW-TOP5
                    for j in jobs:  # AINL-OPENCLAW-TOP5
                        if isinstance(j, dict) and j.get("name"):  # AINL-OPENCLAW-TOP5
                            cron_jobs[str(j["name"])] = j  # AINL-OPENCLAW-TOP5
        except FileNotFoundError:  # AINL-OPENCLAW-TOP5
            cron_err = user_friendly_ainl_error(RuntimeError("openclaw not found"))[:240]  # AINL-OPENCLAW-TOP5
        except Exception as e:  # AINL-OPENCLAW-TOP5
            cron_err = user_friendly_ainl_error(e)[:240]  # AINL-OPENCLAW-TOP5

        drift_ok: Optional[bool] = None  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            drift = _cron_drift_report()  # AINL-OPENCLAW-TOP5
            drift_ok = bool(drift.get("ok"))  # AINL-OPENCLAW-TOP5
        except Exception as e:  # AINL-OPENCLAW-TOP5
            drift_ok = None  # AINL-OPENCLAW-TOP5

        def _last_run(job: Dict[str, Any]) -> str:  # AINL-OPENCLAW-TOP5
            for k in ("lastRunAt", "last_run_at", "lastRun", "last_run"):  # AINL-OPENCLAW-TOP5
                v = job.get(k)  # AINL-OPENCLAW-TOP5
                if v:  # AINL-OPENCLAW-TOP5
                    return str(v)  # AINL-OPENCLAW-TOP5
            return "—"  # AINL-OPENCLAW-TOP5

        core_names = [  # AINL-OPENCLAW-TOP5 — gold-standard §3  # AINL-OPENCLAW-TOP5
            "AINL Context Injection",  # AINL-OPENCLAW-TOP5
            "AINL Session Summarizer",  # AINL-OPENCLAW-TOP5
            "AINL Weekly Token Trends",  # AINL-OPENCLAW-TOP5
        ]  # AINL-OPENCLAW-TOP5

        caps = {  # AINL-OPENCLAW-TOP5
            "AINL_BRIDGE_REPORT_MAX_CHARS": os.getenv("AINL_BRIDGE_REPORT_MAX_CHARS", ""),  # AINL-OPENCLAW-TOP5
            "AINL_WEEKLY_TOKEN_BUDGET_CAP": os.getenv("AINL_WEEKLY_TOKEN_BUDGET_CAP", ""),  # AINL-OPENCLAW-TOP5
            "OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT": os.getenv("OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT", ""),  # AINL-OPENCLAW-TOP5
        }  # AINL-OPENCLAW-TOP5

        week_tokens: Optional[int] = None  # AINL-OPENCLAW-TOP5
        token_usage_error: Optional[str] = None  # AINL-OPENCLAW-TOP5
        try:  # AINL-OPENCLAW-TOP5
            proc = subprocess.run(  # AINL-OPENCLAW-TOP5
                [sys.executable, str(_repo_root() / "openclaw" / "bridge" / "ainl_bridge_main.py"), "token-usage", "--dry-run", "--json-output", "--days-back", "7"],  # AINL-OPENCLAW-TOP5
                capture_output=True,  # AINL-OPENCLAW-TOP5
                text=True,  # AINL-OPENCLAW-TOP5
                timeout=60,  # AINL-OPENCLAW-TOP5
            )  # AINL-OPENCLAW-TOP5
            if proc.returncode == 0 and (proc.stdout or "").strip():  # AINL-OPENCLAW-TOP5
                data = json.loads(proc.stdout)  # AINL-OPENCLAW-TOP5
                if isinstance(data, dict) and data.get("total_tokens") is not None:  # AINL-OPENCLAW-TOP5
                    week_tokens = int(data["total_tokens"])  # AINL-OPENCLAW-TOP5
            elif proc.returncode != 0:  # AINL-OPENCLAW-TOP5
                token_usage_error = user_friendly_ainl_error(  # AINL-OPENCLAW-TOP5
                    RuntimeError((proc.stderr or proc.stdout or "token-usage failed").strip()[:400])  # AINL-OPENCLAW-TOP5
                )  # AINL-OPENCLAW-TOP5
        except Exception as e:  # AINL-OPENCLAW-TOP5
            week_tokens = None  # AINL-OPENCLAW-TOP5
            token_usage_error = user_friendly_ainl_error(e)  # AINL-OPENCLAW-TOP5

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")  # AINL-OPENCLAW-TOP5
        fix_hint = INIT_INSTALL_OPENCLAW + " Or `ainl install openclaw --workspace " + str(ws) + "`."  # AINL-OPENCLAW-TOP5

        not_init_budget = (not sql_err) and weekly_remaining is None  # AINL-OPENCLAW-TOP5
        payload: Dict[str, Any] = {  # AINL-OPENCLAW-TOP5
            "checked_at": now,  # AINL-OPENCLAW-TOP5
            "workspace": str(ws),  # AINL-OPENCLAW-TOP5
            "db_path": str(db_path),  # AINL-OPENCLAW-TOP5
            "schema_ok": schema_ok,  # AINL-OPENCLAW-TOP5
            "schema_detail": schema_detail,  # AINL-OPENCLAW-TOP5
            "weekly_remaining": weekly_remaining,  # AINL-OPENCLAW-TOP5
            "week_start": week_start or None,  # AINL-OPENCLAW-TOP5
            "weekly_budget_not_initialized": not_init_budget,  # AINL-OPENCLAW-TOP5
            "sql_error": sql_err,  # AINL-OPENCLAW-TOP5
            "cron_error": cron_err,  # AINL-OPENCLAW-TOP5
            "cron_jobs": {k: cron_jobs[k] for k in core_names if k in cron_jobs},  # AINL-OPENCLAW-TOP5
            "cron_drift_ok": drift_ok,  # AINL-OPENCLAW-TOP5
            "token_usage_7d": week_tokens,  # AINL-OPENCLAW-TOP5
            "token_usage_error": token_usage_error,  # AINL-OPENCLAW-TOP5
            "caps": caps,  # AINL-OPENCLAW-TOP5
            "fix_hint": fix_hint,  # AINL-OPENCLAW-TOP5
        }  # AINL-OPENCLAW-TOP5

        rows: List[tuple[str, str, str]] = []  # AINL-OPENCLAW-TOP5
        rows.append(("📁", "Workspace", str(ws)))  # AINL-OPENCLAW-TOP5
        rows.append(("✅" if schema_ok else "❌", "SQLite schema", schema_detail if schema_ok else (sql_err or schema_detail)))  # AINL-OPENCLAW-TOP5
        if sql_err:  # AINL-OPENCLAW-TOP5
            rows.append(("⚠️", "weekly_remaining_v1", sql_err + " " + fix_hint))  # AINL-OPENCLAW-TOP5
        elif weekly_remaining is None:  # AINL-OPENCLAW-TOP5
            rows.append(("⚠️", "Weekly budget remaining", "Not initialized — " + INIT_INSTALL_OPENCLAW))  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            rows.append(("✅", "Weekly budget remaining", f"{weekly_remaining} (week_start={week_start or '—'})"))  # AINL-OPENCLAW-TOP5
        if drift_ok is not None:  # AINL-OPENCLAW-TOP5
            rows.append(("✅" if drift_ok else "⚠️", "Cron drift (registry vs OpenClaw)", "ok" if drift_ok else "see `python3 openclaw/bridge/cron_drift_check.py`"))  # AINL-OPENCLAW-TOP5
        if cron_err:  # AINL-OPENCLAW-TOP5
            rows.append(("❌", "OpenClaw cron list", cron_err + " " + fix_hint))  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            for name in core_names:  # AINL-OPENCLAW-TOP5
                j = cron_jobs.get(name)  # AINL-OPENCLAW-TOP5
                if not j:  # AINL-OPENCLAW-TOP5
                    rows.append(("❌", f"Cron: {name}", user_friendly_ainl_error(RuntimeError(f"Cron job {name!r} not found")) + " " + fix_hint))  # AINL-OPENCLAW-TOP5
                else:  # AINL-OPENCLAW-TOP5
                    rows.append(("✅" if j.get("enabled") else "⚠️", f"Cron: {name}", f"enabled={bool(j.get('enabled'))} last_run={_last_run(j)}"))  # AINL-OPENCLAW-TOP5
        tu_detail = str(week_tokens) if week_tokens is not None else ("unknown" + ((" — " + token_usage_error) if token_usage_error else ""))  # AINL-OPENCLAW-TOP5
        rows.append(("✅" if week_tokens is not None else "⚠️", "Token usage (7d)", tu_detail))  # AINL-OPENCLAW-TOP5
        # Cost savings estimate: AINL context compaction typically avoids re-sending 60–80% of raw context.
        # We estimate avoided tokens at 2× the optimised usage and price at $3/M tokens (Claude Sonnet input).
        if week_tokens is not None:  # AINL-OPENCLAW-TOP5
            avoided_tokens = int(week_tokens * 2)  # conservative 2:1 compression ratio  # AINL-OPENCLAW-TOP5
            cost_per_m = float(os.getenv("AINL_STATUS_COST_PER_M_TOKENS", "3.0"))  # AINL-OPENCLAW-TOP5
            avoided_cost = avoided_tokens * cost_per_m / 1_000_000  # AINL-OPENCLAW-TOP5
            payload["estimated_tokens_avoided_7d"] = avoided_tokens  # AINL-OPENCLAW-TOP5
            payload["estimated_cost_avoided_usd_7d"] = round(avoided_cost, 2)  # AINL-OPENCLAW-TOP5
            rows.append(("💰", "Est. cost avoided (7d)", f"~${avoided_cost:.2f} USD (≈{avoided_tokens:,} tokens at ${cost_per_m}/M; override via AINL_STATUS_COST_PER_M_TOKENS)"))  # AINL-OPENCLAW-TOP5
        for k, v in caps.items():  # AINL-OPENCLAW-TOP5
            rows.append(("✅" if str(v).strip() else "⚠️", f"Cap: {k}", str(v).strip() or "not set in this shell (gateway may still set via shellEnv)"))  # AINL-OPENCLAW-TOP5

        missing_cron = not cron_err and any(n not in cron_jobs for n in core_names)  # AINL-OPENCLAW-TOP5
        ok = bool(schema_ok and not cron_err and not missing_cron and (drift_ok is not False))  # AINL-OPENCLAW-TOP5
        rows.append(("✅" if ok else "⚠️", "Overall health", ("All green" if ok else "Needs attention — " + fix_hint) + f" ({now})"))  # AINL-OPENCLAW-TOP5
        payload["ok"] = ok  # AINL-OPENCLAW-TOP5
        core_cron_ok = sum(1 for n in core_names if n in cron_jobs)  # AINL-OPENCLAW-TOP5
        sl_parts: List[str] = [  # AINL-OPENCLAW-TOP5
            f"ok={str(ok).lower()}",  # AINL-OPENCLAW-TOP5
            f"weekly_remaining={weekly_remaining if weekly_remaining is not None else 'na'}",  # AINL-OPENCLAW-TOP5
            f"token_7d={week_tokens if week_tokens is not None else 'na'}",  # AINL-OPENCLAW-TOP5
            f"cron_gold={core_cron_ok}/3",  # AINL-OPENCLAW-TOP5
        ]  # AINL-OPENCLAW-TOP5
        if payload.get("estimated_cost_avoided_usd_7d") is not None:  # AINL-OPENCLAW-TOP5
            sl_parts.append(f"est_cost_avoided_usd_7d={payload['estimated_cost_avoided_usd_7d']}")  # AINL-OPENCLAW-TOP5
        payload["summary_line"] = " ".join(sl_parts) + f" | {now}"  # AINL-OPENCLAW-TOP5

        if bool(getattr(args, "status_summary", False)):  # AINL-OPENCLAW-TOP5
            print(payload["summary_line"])  # AINL-OPENCLAW-TOP5
            return 0 if ok else 1  # AINL-OPENCLAW-TOP5
        if bool(getattr(args, "status_json_summary", False)):  # AINL-OPENCLAW-TOP5
            print(json.dumps(payload, separators=(",", ":")))  # AINL-OPENCLAW-TOP5
            return 0 if ok else 1  # AINL-OPENCLAW-TOP5
        if json_out:  # AINL-OPENCLAW-TOP5
            print(json.dumps(payload, indent=2))  # AINL-OPENCLAW-TOP5
        else:  # AINL-OPENCLAW-TOP5
            print(_markdown_health_table(rows))  # AINL-OPENCLAW-TOP5
        return 0 if ok else 1  # AINL-OPENCLAW-TOP5

    def cmd_status_mux(args: argparse.Namespace) -> int:
        host = str(getattr(args, "host", "openclaw") or "openclaw").strip().lower()
        if host == "openfang":
            return cmd_status_openfang(args)
        return cmd_status(args)

    st = sub.add_parser("status", help="Unified OpenClaw + AINL status view")  # AINL-OPENCLAW-TOP5
    st_out = st.add_mutually_exclusive_group()  # AINL-OPENCLAW-TOP5
    st_out.add_argument("--json", dest="status_json", action="store_true", help="Emit machine-readable JSON (indented)")  # AINL-OPENCLAW-TOP5
    st_out.add_argument("--json-summary", dest="status_json_summary", action="store_true", help="One-line minified JSON (CI, log ship)")  # AINL-OPENCLAW-TOP5
    st_out.add_argument("--summary", dest="status_summary", action="store_true", help="One-line human summary (Telegram, Slack)")  # AINL-OPENCLAW-TOP5

    st.set_defaults(func=cmd_status)  # AINL-OPENCLAW-TOP5

    st.add_argument("--host", default="openclaw", choices=["openclaw", "openfang"], help="Agent host (default: openclaw)")  # AINL-OPENFANG-TOP3
    st.add_argument("--estimate", action="store_true", default=False, help="Include monthly spend/limit snapshot from CostTracker (read-only)")  # AINL-OPENCLAW-TOP5
    st.set_defaults(func=cmd_status_mux)  # AINL-OPENCLAW-TOP5

    def cmd_bridge_sizing_probe(args: argparse.Namespace) -> int:
        import json

        from scripts.bridge_sizing_probe import print_plain_report, run_probe

        md = Path(args.bsz_memory_dir).expanduser() if args.bsz_memory_dir else None
        data = run_probe(args.bsz_db_path, args.bsz_days, memory_dir=md)
        if args.bsz_json:
            print(json.dumps(data, indent=2))
        else:
            print_plain_report(data)
        return 0

    bsz = sub.add_parser(
        "bridge-sizing-probe",
        help="Read-only OpenClaw bridge sizing: SQLite namespace counts + Token Usage Report section sizes",
    )
    bsz.add_argument(
        "--db-path",
        dest="bsz_db_path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3"),
        help="SQLite memory DB (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3)",
    )
    bsz.add_argument(
        "--memory-dir",
        dest="bsz_memory_dir",
        default="",
        help="Directory for daily YYYY-MM-DD.md (overrides OPENCLAW_* for this run)",
    )
    bsz.add_argument(
        "--days",
        dest="bsz_days",
        type=int,
        default=14,
        help="How many newest daily *.md files to scan (default: 14)",
    )
    bsz.add_argument(
        "--json",
        dest="bsz_json",
        action="store_true",
        help="Emit JSON only",
    )
    bsz.set_defaults(func=cmd_bridge_sizing_probe)

    def cmd_profile(args: argparse.Namespace) -> int:
        import json

        from tooling.ainl_profile_catalog import (
            emit_shell_exports,
            format_profile_text,
            get_profile,
            list_profile_ids,
        )

        pc = getattr(args, "profile_cmd", None)
        if pc == "list":
            for pid in list_profile_ids():
                print(pid)
            return 0
        if pc == "show":
            try:
                if args.profile_json:
                    print(json.dumps(get_profile(args.profile_id), indent=2))
                else:
                    print(format_profile_text(args.profile_id), end="")
            except KeyError:
                raise SystemExit(f"unknown profile: {args.profile_id!r} (try: ainl profile list)")
            return 0
        if pc == "emit-shell":
            try:
                print(emit_shell_exports(args.profile_id), end="")
            except KeyError:
                raise SystemExit(f"unknown profile: {args.profile_id!r} (try: ainl profile list)")
            return 0
        raise SystemExit(f"unknown profile subcommand: {pc!r}")

    prf = sub.add_parser(
        "profile",
        help="Named env profiles (IR cache, embedding mode, bridge caps, intelligence defaults)",
    )
    prf_sub = prf.add_subparsers(dest="profile_cmd", required=True)
    prf_list = prf_sub.add_parser("list", help="List profile ids")
    prf_list.set_defaults(func=cmd_profile)
    prf_show = prf_sub.add_parser("show", help="Show one profile (env + notes)")
    prf_show.add_argument("profile_id", help="Profile id (e.g. openclaw-default)")
    prf_show.add_argument(
        "--json",
        dest="profile_json",
        action="store_true",
        help="Emit JSON",
    )
    prf_show.set_defaults(func=cmd_profile)
    prf_emit = prf_sub.add_parser(
        "emit-shell",
        help="Print export VAR=value lines for bash/zsh (eval \"$(ainl profile emit-shell ID)\")",
    )
    prf_emit.add_argument("profile_id")
    prf_emit.set_defaults(func=cmd_profile)

    gld = sub.add_parser("golden", help="Run golden fixtures from examples")
    gld.add_argument("--examples-dir", default=str(Path(__file__).resolve().parent.parent / "examples"))
    gld.add_argument("--trace", action="store_true")
    gld.add_argument("--execution-mode", choices=["graph-preferred", "steps-only", "graph-only"], default="graph-preferred")
    gld.add_argument("--unknown-op-policy", choices=["skip", "error"], default=None)
    gld.add_argument("--max-steps", type=int, default=None)
    gld.set_defaults(func=cmd_golden)

    def cmd_visualize(args: argparse.Namespace) -> int:
        from scripts.visualize_ainl import main as visualize_main

        return visualize_main(list(args.visualize_argv))

    vis = sub.add_parser(
        "visualize",
        help="Compile .ainl to a Mermaid/DOT-style diagram (pass-through to ainl-visualize)",
    )
    vis.add_argument(
        "visualize_argv",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments for ainl-visualize (path, --output, --no-clusters, …)",
    )
    vis.set_defaults(func=cmd_visualize)

    imp = sub.add_parser("import", help="Import external formats into AINL")
    imp_sub = imp.add_subparsers(dest="import_cmd", required=True)

    mdp = imp_sub.add_parser(
        "markdown",
        help="Convert Markdown (Clawflows WORKFLOW.md or Agency-Agents doc) to .ainl",
    )
    mdp.add_argument(
        "url_or_path",
        help="https URL, GitHub blob/raw link, or local Markdown file path",
    )
    mdp.add_argument(
        "--type",
        choices=("workflow", "agent"),
        required=True,
        help="workflow ≈ Clawflows WORKFLOW.md; agent ≈ Agency-Agents personality markdown",
    )
    mdp.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output path (e.g. morning.ainl)",
    )
    mdp.add_argument(
        "--personality",
        default="",
        help="Optional tone/instructions for agent-type imports (stored in header comment for now)",
    )
    mdp.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue bridge hooks in generated graph",
    )
    mdp.add_argument(
        "--generate-soul",
        action="store_true",
        help="With --type agent: also write SOUL.md and IDENTITY.md next to -o",
    )
    mdp.add_argument("--dry-run", action="store_true", help="Print .ainl to stdout; do not write file")
    mdp.add_argument("--verbose", "-v", action="store_true")
    mdp.set_defaults(func=cmd_import_markdown)

    cfp = imp_sub.add_parser(
        "clawflows",
        help="Fetch 5 sample workflows from nikilster/clawflows into examples/ecosystem/clawflows/",
    )
    cfp.add_argument(
        "--output-dir",
        default="",
        help="Destination directory (default: <repo>/examples/ecosystem/clawflows)",
    )
    cfp.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue in generated graphs",
    )
    cfp.add_argument("--timeout-s", type=float, default=30.0, help="HTTP timeout per workflow")
    cfp.add_argument("--verbose", "-v", action="store_true")
    cfp.set_defaults(func=cmd_import_clawflows)

    aap = imp_sub.add_parser(
        "agency-agents",
        help="Fetch 5 sample agents from msitarzewski/agency-agents into examples/ecosystem/agency-agents/",
    )
    aap.add_argument(
        "--output-dir",
        default="",
        help="Destination directory (default: <repo>/examples/ecosystem/agency-agents)",
    )
    aap.add_argument(
        "--personality",
        default="",
        help="Optional tone merged into parsed agent graph",
    )
    aap.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue in generated graphs",
    )
    aap.add_argument("--timeout-s", type=float, default=30.0, help="HTTP timeout per agent file")
    aap.add_argument("--verbose", "-v", action="store_true")
    aap.set_defaults(func=cmd_import_agency_agents)

    initp = sub.add_parser(
        "init",
        help="Create a new AINL project directory with a starter main.ainl and README",
    )
    initp.add_argument("name", help="Project name (also becomes the directory name)")
    initp.add_argument(
        "--target",
        choices=["generic", "hermes"],
        default="generic",
        help="Initialize templates for a specific host target (default: generic)",
    )
    initp.add_argument(
        "--output-dir",
        default="",
        metavar="DIR",
        help="Parent directory for the new project (default: current directory)",
    )
    initp.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target directory if it already exists",
    )
    initp.set_defaults(func=cmd_init)

    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
